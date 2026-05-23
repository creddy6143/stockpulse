"""Data fetcher.

Primary sources:
  - Stock prices:   Finnhub quote()
  - Forex rates:    Frankfurter.app (ECB rates, free, no key)
  - Market indices: Yahoo Finance v8 (cookie+crumb auth) → Finnhub ETF proxies

Yahoo Finance cookie+crumb auth lets us get real ^VIX, ^GSPC, ^IXIC, ^GDAXI, ^NSEI.
Falls back to Finnhub ETF proxies (SPY, QQQ, EWG, INDA, VXX) if Yahoo is blocked.

Rate limiting:
  - Finnhub free tier: 60 calls/min. We use a token bucket capped at 50/min (safety margin).
    All Finnhub client calls go through _fh_call() which acquires a token first.
  - yfinance Python library: no published limit but bursts trigger 429s. Serialised via
    _YF_LIB_LOCK so only one thread calls yfinance at a time, with 0.8s between calls.
  - Yahoo Finance REST (v8/v10): max 3 concurrent requests via _YF_REST_SEM.
    Both endpoints retry with exponential backoff (1s → 5s → 15s) on HTTP 429.
"""
import os
import time as _time
import threading
import requests
import finnhub
from datetime import datetime, timedelta, timezone
from .cache import (cache_get, cache_set,
                     TTL_PRICE, TTL_MARKET, TTL_RATES, TTL_FUNDAMENTALS,
                     TTL_ANALYST, TTL_INSIDER, TTL_HISTORY, TTL_NEWS,
                     TTL_SEARCH, TTL_TRUST, TTL_STRATEGY)

FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")
FMP_KEY = os.getenv("FMP_API_KEY", "")
_fh_client = None

# Yahoo Finance authenticated session (cookie+crumb, refreshed every 30 min)
_yf_session = None
_yf_crumb = None
_yf_crumb_ts = 0.0

# ── Rate limiters ─────────────────────────────────────────────────────────────

class _TokenBucket:
    """Thread-safe token bucket for API rate limiting."""
    def __init__(self, rate_per_min: float):
        self._rate = rate_per_min / 60.0   # tokens per second
        self._tokens = float(rate_per_min) # start full
        self._max = float(rate_per_min)
        self._last = _time.monotonic()
        self._lock = threading.Lock()

    def acquire(self):
        with self._lock:
            now = _time.monotonic()
            elapsed = now - self._last
            self._last = now
            self._tokens = min(self._max, self._tokens + elapsed * self._rate)
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
            # Not enough tokens — calculate exact wait and sleep outside the lock
            wait = (1.0 - self._tokens) / self._rate
            self._tokens = 0.0
        _time.sleep(wait)


# Finnhub: 50 calls/min (free tier limit is 60; 50 gives a safety margin)
_FH_LIMITER = _TokenBucket(rate_per_min=50)

# yfinance Python library: serialise to 1 concurrent call + 0.8s gap
_YF_LIB_LOCK = threading.Semaphore(1)
_YF_LIB_LAST = [0.0]           # mutable so the inner func can update it
_YF_LIB_GAP = 0.8              # seconds between yfinance lib calls

# Yahoo Finance REST (v8/v10): max 3 concurrent requests
_YF_REST_SEM = threading.Semaphore(3)


def _fh_call(method, *args, **kwargs):
    """Execute a Finnhub client method with rate limiting.
    Usage: _fh_call(fh.quote, symbol)  →  fh.quote(symbol) after acquiring a token.
    """
    _FH_LIMITER.acquire()
    return method(*args, **kwargs)


def _yf_rest_get(url: str, session=None, timeout=10) -> requests.Response | None:
    """GET a Yahoo Finance REST URL with semaphore + exponential backoff on 429."""
    with _YF_REST_SEM:
        for attempt, wait in enumerate([0, 1, 5, 15]):
            if wait:
                _time.sleep(wait)
            try:
                r = (session or requests).get(url, headers=_HEADERS, timeout=timeout)
                if r.status_code == 200:
                    return r
                if r.status_code == 429:
                    if attempt < 3:
                        continue  # retry with longer wait
                    return None
                if r.status_code in (401, 403, 404):
                    return None   # no point retrying auth/not-found errors
            except requests.RequestException:
                if attempt >= 2:
                    return None
        return None

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}


def _finnhub():
    global _fh_client
    if _fh_client is None and FINNHUB_KEY:
        _fh_client = finnhub.Client(api_key=FINNHUB_KEY)
    return _fh_client


def _get_yf_auth() -> tuple:
    """Returns (session, crumb) for authenticated Yahoo Finance requests.
    Visits finance.yahoo.com to get a cookie, then fetches the crumb token.
    Result cached for 30 minutes. Returns (None, None) on failure.
    """
    global _yf_session, _yf_crumb, _yf_crumb_ts
    if _yf_session and _yf_crumb and (_time.time() - _yf_crumb_ts < 1800):
        return _yf_session, _yf_crumb
    try:
        sess = requests.Session()
        sess.headers.update(_HEADERS)
        sess.get("https://finance.yahoo.com", timeout=10)
        r = sess.get(
            "https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=8
        )
        if r.status_code == 200 and r.text.strip():
            _yf_session = sess
            _yf_crumb = r.text.strip()
            _yf_crumb_ts = _time.time()
            return _yf_session, _yf_crumb
    except Exception:
        pass
    return None, None


def _yf_chart(symbol: str) -> dict:
    """Yahoo Finance v8 chart. Tries cookie+crumb auth first, then unauthenticated.
    Uses _yf_rest_get which enforces the shared semaphore and retries on 429."""
    session, crumb = _get_yf_auth()
    base = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=5m"
    urls = [f"{base}&crumb={crumb}" if crumb else None, base]
    for url in urls:
        if url is None:
            continue
        try:
            r = _yf_rest_get(url, session=session, timeout=10)
            if r is not None:
                results = r.json().get("chart", {}).get("result")
                if results:
                    return results[0].get("meta", {})
        except Exception:
            continue
    return {}


def _yf_quotesummary(ticker: str) -> dict:
    """Yahoo Finance v10 quoteSummary — returns rich fundamentals + analyst target price.
    More reliable than Finnhub for international stocks (.ST, .AS, .L etc.).
    Uses cookie+crumb auth and _yf_rest_get (semaphore + 429 backoff).
    """
    key = f"yf_qs:{ticker}"
    cached = cache_get(key, TTL_FUNDAMENTALS)
    if cached is not None:
        return cached

    session, crumb = _get_yf_auth()
    modules = "financialData,defaultKeyStatistics"
    base = (
        f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
        f"?modules={modules}&corsDomain=finance.yahoo.com"
    )
    urls = [f"{base}&crumb={crumb}" if crumb else None, base]
    for url in urls:
        if url is None:
            continue
        try:
            r = _yf_rest_get(url, session=session, timeout=10)
            if r is None:
                continue
            qs = r.json().get("quoteSummary", {})
            if qs.get("error"):
                break
            results = qs.get("result") or []
            if results:
                fd = results[0].get("financialData", {})
                ks = results[0].get("defaultKeyStatistics", {})
                merged = {}
                for d in (fd, ks):
                    for k, v in d.items():
                        merged[k] = v.get("raw") if isinstance(v, dict) else v
                cache_set(key, merged, ttl=TTL_FUNDAMENTALS)
                return merged
        except Exception:
            continue

    empty = {}
    cache_set(key, empty)
    return empty


def _yf_lib_fundamentals(ticker: str) -> dict:
    """Use yfinance Python library for international stock fundamentals (.ST, .AS, .L etc.).

    Serialised via _YF_LIB_LOCK: only one thread calls yfinance at a time, with a
    minimum 0.8s gap between calls. This prevents the burst 429s that caused 85% of
    the 410-ticker universe to fail in parallel scans.

    NOTE: yfinance 0.2+ moved price fields (regularMarketPrice, currentPrice) OUT of
    info and into fast_info. Do NOT check for price fields — check fundamental fields only.
    This was the root cause of Stockholm stocks scoring 2/100 (always returned {} before).
    """
    key = f"yf_lib:{ticker}"
    cached = cache_get(key, TTL_FUNDAMENTALS)
    # Three states for a cached entry:
    #   1. Has "recommendation_key"  → new full-data entry  → return it
    #   2. Has "_no_data": True      → confirmed no yfinance coverage → return {}
    #   3. Neither (old entry)       → pre-dates analyst fields → bypass and re-fetch
    if cached is not None:
        if "recommendation_key" in cached:
            return cached
        if cached.get("_no_data"):
            return {}

    with _YF_LIB_LOCK:
        # Enforce minimum gap between consecutive yfinance calls
        since_last = _time.monotonic() - _YF_LIB_LAST[0]
        if since_last < _YF_LIB_GAP:
            _time.sleep(_YF_LIB_GAP - since_last)
        _YF_LIB_LAST[0] = _time.monotonic()

        # Re-check cache inside lock — another thread may have fetched while we waited
        cached2 = cache_get(key, TTL_FUNDAMENTALS)
        if cached2 is not None:
            if "recommendation_key" in cached2:
                return cached2
            if cached2.get("_no_data"):
                return {}

        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            info = t.info or {}
            # Extract fundamentals — do NOT gate on price fields (not in info in yfinance 0.2+)
            market_cap = int(info.get("marketCap") or 0)
            if not market_cap:
                # yfinance 0.2+ puts market cap in fast_info
                try:
                    market_cap = int(getattr(t.fast_info, "market_cap", 0) or 0)
                except Exception:
                    pass
            revenue_growth = float(info.get("revenueGrowth") or 0)
            profit_margins = float(info.get("profitMargins") or 0)
            gross_margins  = float(info.get("grossMargins") or 0)
            # Fetch these BEFORE has_data check so we can include them in the gate
            raw_target = info.get("targetMeanPrice")
            # Verify we got at least ONE useful value from yfinance
            has_data = bool(
                market_cap
                or abs(revenue_growth) > 0.001
                or abs(profit_margins) > 0.001
                or abs(gross_margins) > 0.001
                or raw_target  # analyst target alone is sufficient
            )
            if not has_data:
                cache_set(key, {"_no_data": True}, ttl=5*60)  # short TTL: retry in 5 min
                return {}
            # Analyst target price — free via yfinance; Finnhub paywalls this
            analyst_target = None
            if raw_target:
                try:
                    analyst_target = round(float(raw_target), 2)
                except (TypeError, ValueError):
                    pass
            # Short interest as % of float — Finnhub free tier returns 0 for this
            short_pct = 0.0
            raw_short = info.get("shortPercentOfFloat")
            if raw_short:
                try:
                    short_pct = round(float(raw_short) * 100, 1)
                except (TypeError, ValueError):
                    pass
            # Quarterly earnings growth YoY — proxy for earnings beat/miss
            earn_qtr = 0.0
            raw_eq = info.get("earningsQuarterlyGrowth") or info.get("earningsGrowth")
            if raw_eq:
                try:
                    earn_qtr = round(float(raw_eq), 4)
                except (TypeError, ValueError):
                    pass
            # Analyst consensus — Finnhub free tier blocks this; yfinance has it free
            # recommendationKey: "strongBuy", "buy", "hold", "underperform", "sell"
            # numberOfAnalystOpinions: total analyst count covering this stock
            rec_key = (info.get("recommendationKey") or "").lower().replace(" ", "_")
            try:
                num_analysts = int(info.get("numberOfAnalystOpinions") or 0)
            except (TypeError, ValueError):
                num_analysts = 0
            result = {
                "revenue_growth":      round(revenue_growth, 4),
                "profit_margins":      round(profit_margins, 4),
                "gross_margins":       round(gross_margins, 4),
                "gaap_profitable":     profit_margins > 0,
                "market_cap":          market_cap,
                "pe_ratio":            round(float(p), 2) if (p := info.get("trailingPE") or info.get("forwardPE")) else None,
                "w52_high":            info.get("fiftyTwoWeekHigh"),
                "w52_low":             info.get("fiftyTwoWeekLow"),
                "earnings_growth":     round(float(info.get("earningsGrowth") or 0), 4),
                "sector":              info.get("sector") or None,
                "analyst_target":      analyst_target,
                "short_interest_pct":  short_pct,
                "earnings_qtr_growth": earn_qtr,
                "recommendation_key":  rec_key,
                "num_analysts":        num_analysts,
            }
            cache_set(key, result, ttl=TTL_FUNDAMENTALS)
            return result
        except Exception:
            cache_set(key, {"_no_data": True}, ttl=5*60)  # short TTL: retry in 5 min
            return {}


def _yf_earnings_date(ticker: str) -> str | None:
    """Next earnings date from Yahoo Finance calendarEvents module.
    Fallback when Finnhub free tier doesn't cover a stock's earnings calendar.
    Works for US, EU, and Indian stocks.
    """
    from datetime import datetime as _dt2
    cache_key = f"yf_earn:{ticker}"
    cached = cache_get(cache_key, TTL_FUNDAMENTALS)
    if cached is not None:
        return cached if cached else None
    try:
        session, crumb = _get_yf_auth()
        url = (
            f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
            f"?modules=calendarEvents"
        )
        if crumb:
            url += f"&crumb={crumb}"
        r = (session or requests).get(url, headers=_HEADERS, timeout=8)
        if r.status_code == 200:
            res = r.json().get("quoteSummary", {}).get("result") or []
            if res:
                today_ts = _dt2.now().timestamp()
                earn_dates = (
                    res[0].get("calendarEvents", {})
                    .get("earnings", {})
                    .get("earningsDate", [])
                )
                for d in earn_dates:
                    ts = d.get("raw") if isinstance(d, dict) else d
                    if ts and float(ts) > today_ts:
                        date_str = _dt2.utcfromtimestamp(float(ts)).strftime("%Y-%m-%d")
                        cache_set(cache_key, date_str)
                        return date_str
    except Exception:
        pass
    cache_set(cache_key, "")
    return None


def _is_us_stock(ticker: str) -> bool:
    return "." not in ticker


def _finnhub_symbol(ticker: str) -> str | None:
    """Convert ticker to Finnhub-compatible symbol."""
    if _is_us_stock(ticker):
        return ticker
    if ticker.endswith(".NS"):
        return "NSE:" + ticker[:-3]
    if ticker.endswith(".BO"):
        return "BSE:" + ticker[:-3]
    # European stocks — strip suffix and try (works for many)
    return ticker.rsplit(".", 1)[0]


# ── EXCHANGE RATES ────────────────────────────────────────────────────────────

def get_exchange_rates() -> dict:
    """Live SEK per 1 unit of each currency.
    Primary: Frankfurter.app (ECB-based, free, no key, no rate limiting).
    Fallback: hardcoded sensible defaults.
    Cached 15 minutes.
    """
    key = "exchange_rates"
    cached = cache_get(key, TTL_RATES)
    if cached:
        return cached

    rates = {"USDSEK": 10.4, "EURSEK": 11.2, "INRSEK": 0.124, "GBPSEK": 13.2}

    try:
        r = requests.get(
            "https://api.frankfurter.app/latest?from=USD&to=SEK,EUR,GBP,INR",
            timeout=8,
        )
        if r.status_code == 200:
            data = r.json().get("rates", {})
            usd_to_sek = float(data.get("SEK", rates["USDSEK"]))
            usd_to_inr = float(data.get("INR", 0))
            usd_to_eur = float(data.get("EUR", 0))
            usd_to_gbp = float(data.get("GBP", 0))

            rates["USDSEK"] = round(usd_to_sek, 4)
            if usd_to_inr > 0:
                rates["INRSEK"] = round(usd_to_sek / usd_to_inr, 6)
            # EUR and GBP per SEK: EUR→SEK = SEK/USD ÷ EUR/USD
            if usd_to_eur > 0:
                rates["EURSEK"] = round(usd_to_sek / usd_to_eur, 4)
            if usd_to_gbp > 0:
                rates["GBPSEK"] = round(usd_to_sek / usd_to_gbp, 4)
    except Exception:
        pass

    cache_set(key, rates)
    return rates


# ── PRICE DATA ────────────────────────────────────────────────────────────────

def get_stock_price(ticker: str) -> dict:
    """Returns current price, change %, volume for a ticker.
    Primary: Finnhub quote().
    Fallback: Yahoo Finance v8 chart.
    """
    key = f"price:{ticker}"
    cached = cache_get(key, TTL_PRICE)
    if cached:
        return cached

    fh = _finnhub()
    fh_sym = _finnhub_symbol(ticker)

    # Primary: Finnhub (rate-limited via _fh_call)
    if fh and fh_sym:
        try:
            q = _fh_call(fh.quote, fh_sym)
            price = float(q.get("c") or 0)
            if price > 0:
                prev = float(q.get("pc") or price)
                change_pct = float(q.get("dp") or 0)
                result = {
                    "ticker": ticker,
                    "price": round(price, 4),
                    "change_pct": round(change_pct, 2),
                    "volume": 0,
                    "prev_close": round(prev, 4),
                    "currency": _detect_currency(ticker),
                    "name": ticker,
                    "market_cap": None,
                    "sector": None,
                    "industry": None,
                }
                cache_set(key, result)
                return result
        except Exception:
            pass

    # Fallback: Yahoo v8 chart
    try:
        meta = _yf_chart(ticker)
        if meta:
            price = float(meta.get("regularMarketPrice") or 0)
            prev = float(meta.get("chartPreviousClose") or meta.get("previousClose") or price)
            change_pct = ((price - prev) / prev * 100) if prev else 0
            if price > 0:
                result = {
                    "ticker": ticker,
                    "price": round(price, 4),
                    "change_pct": round(change_pct, 2),
                    "volume": int(meta.get("regularMarketVolume") or 0),
                    "prev_close": round(prev, 4),
                    "currency": meta.get("currency") or _detect_currency(ticker),
                    "name": meta.get("shortName") or meta.get("longName") or ticker,
                    "market_cap": None,
                    "sector": None,
                    "industry": None,
                }
                cache_set(key, result)
                return result
    except Exception:
        pass

    return {"ticker": ticker, "price": 0, "change_pct": 0, "volume": 0}


def _detect_currency(ticker: str) -> str:
    if ticker.endswith(".NS") or ticker.endswith(".BO"):
        return "INR"
    if ticker.endswith(".ST"):
        return "SEK"
    if any(ticker.endswith(s) for s in (".AS", ".DE", ".PA", ".F", ".MI", ".MC", ".BR")):
        return "EUR"
    if ticker.endswith(".L"):
        return "GBP"
    return "USD"


def _get_market_sessions() -> dict:
    """Returns open/closed status for US, EU, and India markets.
    All countdown times expressed in Stockholm timezone (CET/CEST).
    """
    try:
        import pytz
        stockholm = pytz.timezone("Europe/Stockholm")
        us_tz     = pytz.timezone("America/New_York")
        eu_tz     = pytz.timezone("Europe/Berlin")
        in_tz     = pytz.timezone("Asia/Kolkata")

        now_utc = datetime.now(timezone.utc)

        def _session_info(now_local, open_h, open_m, close_h, close_m, tz_name):
            """Compute state + label for a market given local time and hours."""
            wd = now_local.weekday()   # 0=Mon … 6=Sun
            t  = now_local.hour * 60 + now_local.minute

            # Convert open/close to minutes since midnight
            open_min  = open_h  * 60 + open_m
            close_min = close_h * 60 + close_m

            if wd >= 5:   # Weekend
                # Next open: Monday in Stockholm time
                days_to_mon = (7 - wd) % 7 or 7
                next_open = (now_local + timedelta(days=days_to_mon)).replace(
                    hour=open_h, minute=open_m, second=0, microsecond=0
                )
            elif t < open_min:
                next_open = now_local.replace(
                    hour=open_h, minute=open_m, second=0, microsecond=0
                )
            elif t >= close_min:
                # Next business day
                days_ahead = 3 if wd == 4 else 1   # Friday → Monday
                next_open = (now_local + timedelta(days=days_ahead)).replace(
                    hour=open_h, minute=open_m, second=0, microsecond=0
                )
            else:
                next_open = None   # currently open

            if wd >= 5 or t < open_min or t >= close_min:
                state = "closed"
                if next_open:
                    # Convert to Stockholm for display
                    next_open_sthlm = next_open.astimezone(stockholm)
                    delta_min = int((next_open_sthlm - now_utc.astimezone(stockholm)).total_seconds() / 60)
                    if delta_min < 60:
                        label = f"Closed · Opens in {delta_min}m"
                    else:
                        h, m = divmod(delta_min, 60)
                        label = f"Closed · Opens in {h}h {m}m"
                else:
                    label = "Closed"
            else:
                state = "open"
                close_min_left = close_min - t
                label = "Open"
                next_open = None

            return {
                "state": state,
                "label": label,
                "opens_in_min": None if state == "open" else (
                    int((next_open.astimezone(stockholm) - now_utc.astimezone(stockholm)).total_seconds() / 60)
                    if next_open else None
                ),
            }

        us_local = now_utc.astimezone(us_tz)
        eu_local = now_utc.astimezone(eu_tz)
        in_local = now_utc.astimezone(in_tz)

        return {
            "us": _session_info(us_local, 9, 30, 16, 0,  "US"),
            "eu": _session_info(eu_local, 9,  0, 17, 30, "EU"),
            "in": _session_info(in_local, 9, 15, 15, 30, "India"),
        }
    except Exception:
        # If pytz unavailable or any error, return safe defaults
        return {
            "us": {"state": "unknown", "label": "—", "opens_in_min": None},
            "eu": {"state": "unknown", "label": "—", "opens_in_min": None},
            "in": {"state": "unknown", "label": "—", "opens_in_min": None},
        }


def get_market_data() -> dict:
    """Returns VIX + VSTOXX + India VIX + 4 market indices + session status.
    Primary: Yahoo Finance real indices via cookie+crumb.
    Fallback: Finnhub ETF proxies.
    Includes market_sessions (open/closed per market) so UI can show session state.
    """
    key = "market_data"
    cached = cache_get(key, TTL_MARKET)
    if cached:
        return cached

    result = {}

    # Primary: Yahoo Finance real indices (includes volatility indices)
    yf_map = {
        "vix":       "^VIX",
        "vstoxx":    "^V2TX",      # European Volatility Index
        "india_vix": "^INDIAVIX",  # India NSE VIX
        "sp500":     "^GSPC",
        "nasdaq":    "^IXIC",
        "dax":       "^GDAXI",
        "nifty":     "^NSEI",
    }
    for name, sym in yf_map.items():
        meta = _yf_chart(sym)
        price = float(meta.get("regularMarketPrice") or 0)
        if price > 0:
            prev = float(meta.get("chartPreviousClose") or meta.get("previousClose") or price)
            chg = ((price - prev) / prev * 100) if prev else 0
            result[name] = {"price": round(price, 2), "change_pct": round(chg, 2)}

    # Fallback: Finnhub ETF proxies for any missing index
    fh = _finnhub()
    etf_fallbacks = {
        "vix":    ("VXX",  1.5),  # VXX/1.5 ≈ actual VIX level
        "sp500":  ("SPY",  1.0),
        "nasdaq": ("QQQ",  1.0),
        "dax":    ("EWG",  1.0),
        "nifty":  ("INDA", 1.0),
        # No Finnhub fallback for VSTOXX / India VIX — leave as 0 if yf fails
    }
    if fh:
        for name, (sym, div) in etf_fallbacks.items():
            if name not in result:
                try:
                    q = _fh_call(fh.quote, sym)
                    price = float(q.get("c") or 0)
                    chg = float(q.get("dp") or 0)
                    result[name] = {"price": round(price / div, 2), "change_pct": round(chg, 2)}
                except Exception:
                    result[name] = {"price": 0, "change_pct": 0}

    # Ensure all keys exist (vstoxx/india_vix may be 0 if yf doesn't carry them)
    for name in yf_map:
        result.setdefault(name, {"price": 0, "change_pct": 0})

    vix_level = result.get("vix", {}).get("price", 15)
    if vix_level < 15:
        status = {"label": "Market Calm",   "dot": "calm",   "color": "green"}
    elif vix_level < 25:
        status = {"label": "Market Choppy", "dot": "choppy", "color": "amber"}
    else:
        status = {"label": "Market Alert",  "dot": "alert",  "color": "rose"}

    result["status"] = status
    result["market_sessions"] = _get_market_sessions()
    cache_set(key, result)
    return result


# ── FUNDAMENTALS ──────────────────────────────────────────────────────────────

def _finnhub_fundamentals_for(ticker: str) -> dict:
    """
    Run the Finnhub company_basic_financials call for a given ticker
    and return a fundamentals dict in the standard format.
    Used by ADR routing to fetch data using a US-listed ticker symbol.
    Does NOT cache — caller handles caching under the original ticker key.
    """
    result = {
        "ticker": ticker,
        "revenue_growth": 0.0, "earnings_growth": 0.0,
        "profit_margins": 0.0, "gross_margins": 0.0,
        "pe_ratio": None, "forward_pe": None,
        "debt_to_equity": 0.0, "current_ratio": None,
        "free_cashflow": 0, "total_cash": 0, "total_debt": 0,
        "market_cap": 0, "cash_runway_months": None,
        "earnings_surprise_pct": None, "earnings_history": [],
        "next_earnings_date": None, "gaap_profitable": False,
        "w52_high": None, "w52_low": None,
    }
    fh = _finnhub()
    if not fh:
        return result
    try:
        bf = _fh_call(fh.company_basic_financials, ticker, "all")
        m = (bf or {}).get("metric", {})
        if m:
            rev = float(m.get("revenueGrowthTTMYoy") or m.get("revenueGrowth5Y") or 0)
            result["revenue_growth"] = round(rev / 100, 4)
            eps_g = float(m.get("epsGrowthTTMYoy") or m.get("epsGrowthQuarterlyYoy") or
                          m.get("epsGrowth3Y") or 0)
            result["earnings_growth"] = round(eps_g / 100, 4)
            margin = float(m.get("netProfitMarginTTM") or 0)
            result["profit_margins"] = round(margin / 100, 4)
            result["gaap_profitable"] = margin > 0
            gross = float(m.get("grossMarginTTM") or 0)
            result["gross_margins"] = round(gross / 100, 4)
            pe = m.get("peNormalizedAnnual") or m.get("peTTM")
            result["pe_ratio"] = round(float(pe), 2) if pe else None
            curr = m.get("currentRatioAnnual")
            result["current_ratio"] = round(float(curr), 2) if curr else None
            mktcap = m.get("marketCapitalization")
            result["market_cap"] = int(float(mktcap) * 1_000_000) if mktcap else 0
            result["w52_high"] = float(m["52WeekHigh"]) if m.get("52WeekHigh") else None
            result["w52_low"]  = float(m["52WeekLow"])  if m.get("52WeekLow")  else None
            # Short interest (used by trust_score smart money pillar)
            si = m.get("shortInterestSharesOutstanding")
            if si:
                result["short_interest_pct"] = round(float(si) * 100, 1)
    except Exception:
        pass
    # Earnings history (available on free tier for US-listed tickers)
    try:
        fh2 = _finnhub()
        if fh2:
            eq = _fh_call(fh2.company_earnings, ticker, limit=8)
            if eq:
                result["earnings_history"] = eq[:4]
                last = eq[0]
                est = last.get("estimate")
                act = last.get("actual")
                if est and act is not None and est != 0:
                    result["earnings_surprise_pct"] = round(
                        (act - est) / abs(est) * 100, 1
                    )
    except Exception:
        pass
    # Next earnings date
    try:
        fh3 = _finnhub()
        if fh3:
            today_str  = datetime.now().strftime("%Y-%m-%d")
            ninety_str = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
            cal = _fh_call(fh3.earnings_calendar, _from=today_str, to=ninety_str, symbol=ticker)
            cal_list = (cal or {}).get("earningsCalendar", [])
            if cal_list:
                result["next_earnings_date"] = cal_list[0].get("date")
    except Exception:
        pass
    return result


def get_fmp_profile(ticker: str) -> dict:
    """FMP /stable/profile — display enrichment for stocks with no fundamental coverage.

    Works on FMP free tier for all exchanges (.ST, .AS, .DE, .L etc.).
    Returns company name, sector, industry, market cap, 52W range, beta, CEO.
    Financial fundamentals (revenue, margins) are NOT available on free tier for
    non-US exchanges — this is display-only enrichment, not scoring data.

    Returns {} if FMP key missing, ticker not found, or request fails.
    """
    if not FMP_KEY:
        return {}
    key = f"fmp_profile:{ticker}"
    cached = cache_get(key, 24 * 60 * 60)
    if cached is not None:
        return cached
    try:
        url = (
            f"https://financialmodelingprep.com/stable/profile"
            f"?symbol={ticker}&apikey={FMP_KEY}"
        )
        r = requests.get(url, headers=_HEADERS, timeout=10)
        if r.status_code != 200:
            cache_set(key, {})
            return {}
        data = r.json()
        # stable API returns a single object; v3 returned a list — handle both
        p = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) and data.get("symbol") else None)
        if not p:
            cache_set(key, {})
            return {}

        # Parse 52W range string "110.2-294.4"
        w52_high = w52_low = None
        range_str = str(p.get("range") or "")
        if "-" in range_str:
            parts = range_str.split("-")
            try:
                w52_low  = float(parts[0])
                w52_high = float(parts[1])
            except (ValueError, IndexError):
                pass

        # Market cap from FMP is in absolute currency units (not millions)
        mkt_cap_raw = p.get("marketCap")
        mkt_cap = int(float(mkt_cap_raw)) if mkt_cap_raw else None

        result = {
            "fmp_name":        p.get("companyName") or None,
            "fmp_sector":      p.get("sector") or None,
            "fmp_industry":    p.get("industry") or None,
            "fmp_description": (p.get("description") or "")[:280].strip() or None,
            "fmp_ceo":         p.get("ceo") or None,
            "fmp_employees":   p.get("fullTimeEmployees") or None,
            "fmp_country":     p.get("country") or None,
            "fmp_exchange":    p.get("exchangeFullName") or None,
            "fmp_currency":    p.get("currency") or None,
            "fmp_beta":        float(p["beta"]) if p.get("beta") else None,
            "fmp_isin":        p.get("isin") or None,
            "market_cap":      mkt_cap,
            "w52_high":        w52_high,
            "w52_low":         w52_low,
            "data_source":     "fmp:profile",
        }
        cache_set(key, result)
        return result
    except Exception:
        cache_set(key, {})
        return {}


def get_fundamentals(ticker: str) -> dict:
    """Revenue growth, earnings, profitability — multi-source with regional routing.

    Priority:
    1. ADR/US-listing map → Finnhub with US ticker (full 133-field coverage)
       + Screener.in overlay for India-specific data (promoter/FII holding)
    2. Indian stocks without ADR → Screener.in scraper
    3. Existing Finnhub + Yahoo v10 + yfinance lib chain (US/EU)
    """
    from data.adr_map import get_adr_ticker
    from data.india_fetcher import get_screener_fundamentals
    from data.india import is_indian_stock

    key = f"fundamentals:{ticker}"
    cached = cache_get(key, TTL_FUNDAMENTALS)
    if cached:
        return cached

    # ── Route 1: ADR map → use Finnhub with US-listed ticker ─────────────────
    adr = get_adr_ticker(ticker)
    if adr:
        adr_result = _finnhub_fundamentals_for(adr)
        if adr_result and adr_result.get("market_cap"):
            adr_result["data_source"] = f"finnhub:{adr}"
            # For Indian ADR stocks, overlay Screener.in for India-specific fields
            if is_indian_stock(ticker):
                screener = get_screener_fundamentals(ticker)
                if screener:
                    for k in ["promoter_holding_pct", "fii_holding_pct",
                               "roe", "roce", "pe_ratio", "dividend_yield"]:
                        if screener.get(k) is not None:
                            adr_result[k] = screener[k]
                    adr_result["data_source"] += " + screener.in"
            cache_set(key, adr_result)
            return adr_result

    # ── Route 2: Indian stocks without ADR → Screener.in ─────────────────────
    if is_indian_stock(ticker):
        screener = get_screener_fundamentals(ticker)
        if screener and screener.get("market_cap"):
            cache_set(key, screener)
            return screener

    result = {
        "ticker": ticker,
        "revenue_growth": 0.0,
        "earnings_growth": 0.0,
        "profit_margins": 0.0,
        "gross_margins": 0.0,
        "pe_ratio": None,
        "forward_pe": None,
        "debt_to_equity": 0.0,
        "current_ratio": None,
        "free_cashflow": 0,
        "total_cash": 0,
        "total_debt": 0,
        "market_cap": 0,
        "cash_runway_months": None,
        "earnings_surprise_pct": None,
        "earnings_history": [],
        "next_earnings_date": None,
        "gaap_profitable": False,
        "w52_high": None,
        "w52_low": None,
    }

    fh = _finnhub()

    # Strip exchange suffix for Finnhub
    clean = ticker
    for suffix in (".NS", ".BO", ".ST", ".AS", ".DE", ".PA", ".F", ".MI", ".MC", ".BR", ".L"):
        clean = clean.replace(suffix, "")

    if fh:
        try:
            bf = _fh_call(fh.company_basic_financials, clean, "all")
            m = (bf or {}).get("metric", {})
            if m:
                # Finnhub returns values in PERCENTAGE form (e.g. 65.47 means 65.47%)
                rev = float(m.get("revenueGrowthTTMYoy") or m.get("revenueGrowth5Y") or 0)
                result["revenue_growth"] = round(rev / 100, 4)

                eps_growth = float(
                    m.get("epsGrowthTTMYoy") or m.get("epsGrowthQuarterlyYoy") or
                    m.get("epsGrowth3Y") or 0
                )
                result["earnings_growth"] = round(eps_growth / 100, 4)

                margin = float(m.get("netProfitMarginTTM") or 0)
                result["profit_margins"] = round(margin / 100, 4)
                result["gaap_profitable"] = margin > 0

                gross = float(m.get("grossMarginTTM") or 0)
                result["gross_margins"] = round(gross / 100, 4)

                pe = m.get("peNormalizedAnnual") or m.get("peTTM")
                result["pe_ratio"] = round(float(pe), 2) if pe else None

                curr = m.get("currentRatioAnnual")
                result["current_ratio"] = round(float(curr), 2) if curr else None

                mktcap = m.get("marketCapitalization")
                result["market_cap"] = int(float(mktcap) * 1_000_000) if mktcap else 0

                result["w52_high"] = float(m["52WeekHigh"]) if m.get("52WeekHigh") else None
                result["w52_low"]  = float(m["52WeekLow"])  if m.get("52WeekLow")  else None
        except Exception:
            pass

        # Earnings history + surprise (US & EU only)
        if not ticker.endswith((".NS", ".BO")):
            try:
                eq = _fh_call(fh.company_earnings, clean, limit=8)
                if eq:
                    result["earnings_history"] = eq[:4]
                    last = eq[0]
                    est = last.get("estimate")
                    act = last.get("actual")
                    if est and act is not None and est != 0:
                        result["earnings_surprise_pct"] = round(
                            (act - est) / abs(est) * 100, 1
                        )
            except Exception:
                pass

            # Next earnings date
            try:
                today_str = datetime.now().strftime("%Y-%m-%d")
                ninety_str = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
                cal = _fh_call(fh.earnings_calendar, _from=today_str, to=ninety_str, symbol=clean)
                cal_list = (cal or {}).get("earningsCalendar", [])
                if cal_list:
                    result["next_earnings_date"] = cal_list[0].get("date")
            except Exception:
                pass

    # Yahoo Finance v10 quoteSummary fallback — richer than Finnhub for non-US stocks
    # Covers fundamentals for .ST, .AS, .L, .DE etc. that Finnhub free tier misses.
    has_fundamentals = (result["market_cap"] or 0) > 0 or abs(result["revenue_growth"]) > 0.001
    if not has_fundamentals:
        qs = _yf_quotesummary(ticker)
        if qs:
            # Revenue growth
            rev = qs.get("revenueGrowth")
            if rev is not None:
                result["revenue_growth"] = round(float(rev), 4)

            # Earnings growth
            eg = qs.get("earningsGrowth") or qs.get("revenueGrowth")
            if eg is not None:
                result["earnings_growth"] = round(float(eg), 4)

            # Margins
            pm = qs.get("profitMargins")
            if pm is not None:
                result["profit_margins"] = round(float(pm), 4)
                result["gaap_profitable"] = float(pm) > 0

            gm = qs.get("grossMargins")
            if gm is not None:
                result["gross_margins"] = round(float(gm), 4)

            # Market cap
            mc = qs.get("marketCap")
            if mc:
                result["market_cap"] = int(float(mc))

            # 52W range
            if not result["w52_high"]:
                result["w52_high"] = qs.get("fiftyTwoWeekHigh")
            if not result["w52_low"]:
                result["w52_low"] = qs.get("fiftyTwoWeekLow")

            # Forward PE
            fpe = qs.get("forwardPE")
            if fpe:
                result["forward_pe"] = round(float(fpe), 2)

    # Yahoo Finance v8 chart fallback for 52W range and market cap when all else fails
    if not result["w52_high"] or not result["market_cap"]:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1y&interval=1d"
            r = requests.get(url, headers=_HEADERS, timeout=8)
            if r.status_code == 200:
                meta = r.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
                if not result["w52_high"]:
                    result["w52_high"] = meta.get("fiftyTwoWeekHigh") or meta.get("regularMarketDayHigh")
                if not result["w52_low"]:
                    result["w52_low"] = meta.get("fiftyTwoWeekLow") or meta.get("regularMarketDayLow")
                if not result["market_cap"]:
                    result["market_cap"] = int(meta.get("marketCap") or 0)
        except Exception:
            pass

    # yfinance Python library — run for international stocks AND as universal safety
    # net for any stock where Finnhub + Yahoo v10/v8 returned no core metrics.
    # This prevents US stocks from showing "?" when Finnhub rate-limits a request:
    # without this, an empty result gets cached for 24 hours.
    is_intl = any(ticker.endswith(s) for s in [
        ".ST", ".AS", ".L", ".DE", ".PA", ".MI", ".MC",
        ".BR", ".HE", ".CO", ".OL", ".F",  # Brussels, Helsinki, Copenhagen, Oslo, Frankfurt secondary
    ])
    _needs_yf = is_intl or (
        (result.get("market_cap") or 0) == 0
        or abs(result.get("revenue_growth") or 0) < 0.001
    )
    if _needs_yf:
        yf_data = _yf_lib_fundamentals(ticker)
        if yf_data:
            for k, v in yf_data.items():
                if v is not None and not result.get(k):
                    result[k] = v
            # gaap_profitable: yf might confirm profitable even if our default is False
            if yf_data.get("gaap_profitable") and not result["gaap_profitable"]:
                result["gaap_profitable"] = True
            if not result.get("data_source") and not is_intl:
                result["data_source"] = "yfinance:lib"

    # yfinance patch for earnings_surprise_pct — Finnhub company_earnings often returns
    # empty on Railway free tier for US stocks, costing up to 13 pts (8 business + 5 momentum).
    # Fallback: use earningsQuarterlyGrowth (YoY earnings growth) as a proxy.
    # Not a perfect substitute (growth vs surprise) but far better than None.
    if result.get("earnings_surprise_pct") is None and not ticker.endswith((".NS", ".BO")):
        yf_enrich = _yf_lib_fundamentals(ticker)   # cache hit if already called above
        eg = yf_enrich.get("earnings_qtr_growth") or yf_enrich.get("earnings_growth") or 0
        if eg != 0:
            result["earnings_surprise_pct"] = round(float(eg) * 100, 1)

    # Yahoo Finance calendarEvents fallback for next earnings date.
    # Works for all markets — covers gaps where Finnhub free tier returns nothing.
    if not result["next_earnings_date"]:
        yf_date = _yf_earnings_date(ticker)
        if yf_date:
            result["next_earnings_date"] = yf_date

    # ── Route 4: FMP profile enrichment ──────────────────────────────────────
    # For stocks where all other routes returned no fundamental data
    # (e.g. small Nordic stocks with no ADR, no Screener.in coverage).
    # FMP free tier gives us company name, sector, market cap, 52W range —
    # not enough to score, but enough to enrich the "Data Unavailable" display.
    #
    # Trigger when: no market_cap at all (old condition) OR when we have market_cap
    # from yfinance but lack meaningful fundamental data (revenue/margin/gross all 0).
    # This covers pre-revenue US stocks (NNE, OKLO) and international stocks where
    # yfinance returns market_cap but no operating metrics — both now show "Data
    # Unavailable" in trust_score, and users deserve to see what the company does.
    _no_fundamentals = (
        abs(result.get("revenue_growth") or 0) < 0.001
        and abs(result.get("profit_margins") or 0) < 0.001
        and abs(result.get("gross_margins") or 0) < 0.001
    )
    if FMP_KEY and (not result.get("market_cap") or _no_fundamentals):
        fmp = get_fmp_profile(ticker)
        if fmp:
            result.update(fmp)   # overlays market_cap, w52_high/low, fmp_* fields

    # Use a short retry TTL (5 min) when we got no usable data — prevents an empty
    # fetch from locking out the stock for the full 24-hour fundamentals cache window.
    data_ok = (result.get("market_cap") or 0) > 0
    cache_set(key, result, ttl=TTL_FUNDAMENTALS if data_ok else (5 * 60))
    return result


# ── INSIDER / INSTITUTIONAL ───────────────────────────────────────────────────

def get_insider_data(ticker: str) -> dict:
    """Insider buy/sell signals and institutional data from Finnhub."""
    key = f"insider:{ticker}"
    cached = cache_get(key, TTL_INSIDER)
    # Bypass old cache entries that lack the yfinance short-interest fallback.
    if cached and "_yf_fallback" in cached:
        return cached

    result = {
        "ceo_buying": False,
        "insider_buy_value": 0,
        "insider_sell_value": 0,
        "institutional_buying": False,
        "short_interest_pct": 0,
    }

    fh = _finnhub()
    if not fh:
        cache_set(key, result)
        return result

    # Route through ADR map for Indian/European stocks so we use the US-listed ticker
    from data.adr_map import get_adr_ticker
    adr = get_adr_ticker(ticker)
    clean = adr if adr else ticker
    for suffix in (".NS", ".BO", ".ST", ".AS", ".DE", ".PA", ".F", ".MI", ".MC", ".BR", ".L"):
        clean = clean.replace(suffix, "")

    try:
        cutoff = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        txns = _fh_call(fh.stock_insider_transactions, clean, cutoff, today)
        if txns and txns.get("data"):
            for t in txns["data"]:
                change = t.get("change", 0) or 0
                price = t.get("transactionPrice", 0) or 0
                value = abs(change * price)
                pos = t.get("name", "").upper()
                if change > 0:
                    result["insider_buy_value"] += value
                    if "CEO" in pos or "CHIEF EXEC" in pos:
                        result["ceo_buying"] = True
                elif change < 0:
                    result["insider_sell_value"] += value
    except Exception:
        pass

    try:
        bf = _fh_call(fh.company_basic_financials, clean, "all")
        m = (bf or {}).get("metric", {})
        short_pct = m.get("shortInterestSharesOutstanding")
        if short_pct:
            result["short_interest_pct"] = round(float(short_pct) * 100, 1)
    except Exception:
        pass

    # yfinance fallback for short interest — Finnhub free tier doesn't return
    # shortInterestSharesOutstanding; yfinance info has shortPercentOfFloat
    if result["short_interest_pct"] == 0:
        yf_data = _yf_lib_fundamentals(ticker)   # cached 24h — no extra HTTP call
        yf_short = yf_data.get("short_interest_pct") or 0
        if yf_short > 0:
            result["short_interest_pct"] = yf_short

    try:
        own = _fh_call(fh.ownership, clean, limit=10)
        holders = (own or {}).get("ownership", [])
        if holders:
            total_pct = sum(float(h.get("share", 0) or 0) for h in holders[:5])
            result["institutional_buying"] = total_pct > 0.30
    except Exception:
        pass

    result["_yf_fallback"] = True   # mark so stale cache entries are bypassed next deploy
    cache_set(key, result, ttl=TTL_INSIDER)
    return result


# ── NEWS ──────────────────────────────────────────────────────────────────────

def _yf_rss_news(ticker: str, max_items: int = 8) -> list:
    """Yahoo Finance RSS feed — indexes Globe Newswire / BusinessWire press releases.
    This catches clinical trial announcements, FDA news, and earnings PRs that
    Finnhub free tier misses for small-cap biotech/pharma stocks."""
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime

    # Try the ticker as-is first, then stripped (for .NS/.ST etc)
    clean = ticker.replace(".NS","").replace(".BO","")
    attempts = [ticker] if ticker == clean else [clean, ticker]

    for t in attempts:
        try:
            url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={t}&region=US&lang=en-US"
            r = requests.get(url, headers=_HEADERS, timeout=8)
            if r.status_code != 200 or not r.text.strip():
                continue
            root = ET.fromstring(r.text)
            items = []
            for item in root.findall(".//item")[:max_items]:
                title = (item.findtext("title") or "").strip()
                link  = (item.findtext("link")  or "").strip()
                pub   = (item.findtext("pubDate") or "").strip()
                ts = 0
                if pub:
                    try:
                        ts = int(parsedate_to_datetime(pub).timestamp())
                    except Exception:
                        pass
                if title:
                    items.append({
                        "headline": title,
                        "url": link,
                        "source": "Yahoo Finance",
                        "datetime": ts,
                    })
            if items:
                return items
        except Exception:
            continue
    return []


def get_news(ticker: str, days: int = 7) -> list:
    """Recent news headlines — Finnhub primary, Yahoo Finance RSS supplement.

    Finnhub free tier covers major business media but misses specialized
    press release wires (Globe Newswire, BusinessWire) used by small-cap
    biotech/pharma. Yahoo Finance RSS indexes those and fills the gap.
    Results are merged, deduplicated by headline, sorted newest-first.
    """
    key = f"news:{ticker}:{days}"
    cached = cache_get(key, TTL_NEWS)
    if cached:
        return cached

    finnhub_news = []
    fh = _finnhub()
    if fh:
        try:
            from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            to_date   = datetime.now().strftime("%Y-%m-%d")
            clean = ticker.replace(".NS", "").replace(".BO", "")
            raw = _fh_call(fh.company_news, clean, _from=from_date, to=to_date)
            finnhub_news = raw[:10] if raw else []
        except Exception:
            pass

    # Always supplement with Yahoo Finance RSS — catches press releases Finnhub misses
    yf_news = _yf_rss_news(ticker, max_items=8)

    # Merge: combine both sources, deduplicate by lowercase headline prefix (60 chars)
    seen = set()
    merged = []
    for article in finnhub_news + yf_news:
        h = (article.get("headline") or "").lower()[:60]
        if h and h not in seen:
            seen.add(h)
            merged.append(article)

    # Sort newest-first, keep top 10
    merged.sort(key=lambda x: x.get("datetime", 0), reverse=True)
    result = merged[:10]

    cache_set(key, result)
    return result


# ── ANALYST DATA ──────────────────────────────────────────────────────────────

def get_analyst_data(ticker: str) -> dict:
    """Analyst ratings and price target from Finnhub."""
    key = f"analyst:{ticker}"
    cached = cache_get(key, TTL_ANALYST)
    # Bypass old cache entries that lack the yfinance analyst-consensus fallback.
    if cached and "_yf_fallback" in cached:
        return cached

    result = {
        "target_price": None, "target_high": None, "target_low": None,
        "buy_count": 0, "hold_count": 0, "sell_count": 0,
        "recommendation": "hold", "revenue_estimate": None,
    }

    fh = _finnhub()
    if not fh:
        cache_set(key, result)
        return result

    # Route through ADR map for Indian/European stocks
    from data.adr_map import get_adr_ticker
    adr = get_adr_ticker(ticker)
    clean = adr if adr else ticker
    for suffix in (".NS", ".BO", ".ST", ".AS", ".DE", ".PA", ".F", ".MI", ".MC", ".BR", ".L"):
        clean = clean.replace(suffix, "")

    try:
        pt = fh.price_target(clean)
        if pt:
            result["target_price"] = pt.get("targetMean")
            result["target_high"]  = pt.get("targetHigh")
            result["target_low"]   = pt.get("targetLow")
    except Exception:
        pass

    # Yahoo v10 quoteSummary fallback for target price (Finnhub paywalls this on free tier)
    if result["target_price"] is None:
        try:
            qs = _yf_quotesummary(ticker)
            if qs:
                tp = qs.get("targetMeanPrice")
                if tp:
                    result["target_price"] = float(tp)
                th = qs.get("targetHighPrice")
                if th:
                    result["target_high"] = float(th)
                tl = qs.get("targetLowPrice")
                if tl:
                    result["target_low"] = float(tl)
                # Also get analyst count and recommendation from Yahoo if Finnhub unavailable
                n = qs.get("numberOfAnalystOpinions")
                if n and result["buy_count"] == 0:
                    result["analyst_count_yf"] = int(n)
                rec_key = qs.get("recommendationKey", "")
                if rec_key and result["recommendation"] == "hold":
                    result["recommendation"] = rec_key.lower()
                rev_est = qs.get("revenueEstimate") or qs.get("totalRevenue")
                if rev_est:
                    result["revenue_estimate"] = float(rev_est)
        except Exception:
            pass

    # yfinance library fallback — works on Railway when Yahoo REST is blocked
    if result["target_price"] is None:
        yf_data = _yf_lib_fundamentals(ticker)   # cached 24h — no extra HTTP call if already fetched
        at = yf_data.get("analyst_target")
        if at:
            result["target_price"] = at

    try:
        recs = fh.recommendation_trends(clean)
        if recs and len(recs) > 0:
            latest = recs[0]
            buy  = (latest.get("strongBuy") or 0) + (latest.get("buy") or 0)
            hold = latest.get("hold") or 0
            sell = (latest.get("strongSell") or 0) + (latest.get("sell") or 0)
            result.update({"buy_count": buy, "hold_count": hold, "sell_count": sell})
            total = buy + hold + sell
            if total > 0:
                if buy / total > 0.60:
                    result["recommendation"] = "buy"
                elif sell / total > 0.40:
                    result["recommendation"] = "sell"
    except Exception:
        pass

    # yfinance fallback for analyst consensus buy/hold/sell distribution.
    # Finnhub free tier blocks recommendation_trends for most tickers on Railway.
    # Yahoo REST returns 429. yfinance info has recommendationKey + numberOfAnalystOpinions.
    # We synthesise an approximate buy/hold/sell split from the recommendation key.
    # This is the single biggest missing signal: +15 pts smart money + +6 pts momentum.
    if result["buy_count"] == 0:
        yf_data = _yf_lib_fundamentals(ticker)   # always a cache hit after the call above
        rec_key  = (yf_data.get("recommendation_key") or "").lower().replace(" ", "_")
        total_an = yf_data.get("num_analysts") or 0
        if total_an > 0 and rec_key:
            if rec_key in ("strongbuy", "strong_buy"):
                result.update(buy_count=round(total_an * .90), hold_count=round(total_an * .10),
                               sell_count=0, recommendation="buy")
            elif rec_key == "buy":
                result.update(buy_count=round(total_an * .75), hold_count=round(total_an * .20),
                               sell_count=round(total_an * .05), recommendation="buy")
            elif rec_key == "outperform":
                result.update(buy_count=round(total_an * .65), hold_count=round(total_an * .25),
                               sell_count=round(total_an * .10), recommendation="buy")
            elif rec_key in ("hold", "neutral"):
                result.update(buy_count=round(total_an * .45), hold_count=round(total_an * .45),
                               sell_count=round(total_an * .10))
            elif rec_key in ("underperform", "sell", "strongsell", "strong_sell"):
                result.update(buy_count=round(total_an * .10), hold_count=round(total_an * .30),
                               sell_count=round(total_an * .60), recommendation="sell")
        elif rec_key in ("strongbuy", "strong_buy", "buy", "outperform"):
            result["recommendation"] = "buy"

    result["_yf_fallback"] = True   # mark so stale cache entries are bypassed next deploy
    cache_set(key, result)
    return result


# ── STOCK HISTORY ─────────────────────────────────────────────────────────────

def get_stock_history(ticker: str) -> dict:
    """Performance % for 1W/1M/3M/6M/1Y + full price series for charting."""
    key = f"history:{ticker}"
    cached = cache_get(key, TTL_HISTORY)
    if cached:
        return cached

    empty = {"1W": 0, "1M": 0, "3M": 0, "6M": 0, "1Y": 0, "prices": []}
    session, crumb = _get_yf_auth()
    base = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1y&interval=1d"

    data = None
    for url in [
        f"{base}&crumb={crumb}" if crumb else None,
        base,
    ]:
        if url is None:
            continue
        try:
            r = (session or requests).get(url, headers=_HEADERS, timeout=15)
            if r.status_code == 200:
                results = r.json().get("chart", {}).get("result")
                if results:
                    data = results[0]
                    break
        except Exception:
            continue

    if not data:
        return empty

    try:
        timestamps = data.get("timestamp", [])
        closes = data.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        closes = [c for c in closes if c is not None]

        if len(closes) < 5:
            return empty

        current = closes[-1]

        def pct(days):
            idx = max(0, len(closes) - days)
            past = closes[idx]
            return round((current - past) / past * 100, 1) if past else 0

        # Build price series: subsample to ~52 points for the full year
        prices = []
        step = max(1, len(closes) // 52)
        import datetime as _dt
        for i in range(0, len(closes), step):
            if timestamps and i < len(timestamps):
                try:
                    d = _dt.datetime.utcfromtimestamp(timestamps[i])
                    label = d.strftime("%b %d")
                except Exception:
                    label = str(i)
            else:
                label = str(i)
            prices.append({"date": label, "price": round(closes[i], 2)})
        # Always include last point with accurate final price
        if prices and closes:
            prices[-1]["price"] = round(closes[-1], 2)

        result = {
            "1W": pct(5), "1M": pct(22), "3M": pct(65),
            "6M": pct(130), "1Y": pct(min(252, len(closes) - 1)),
            "prices": prices,
        }
        cache_set(key, result)
        return result
    except Exception:
        return empty


# ── TICKER SEARCH ─────────────────────────────────────────────────────────────

_EXCHANGE_NAMES = {
    "STO": "Stockholm 🇸🇪", "CPH": "Copenhagen 🇩🇰", "HEL": "Helsinki 🇫🇮",
    "OSL": "Oslo 🇳🇴", "FRA": "Frankfurt 🇩🇪", "XETRA": "Xetra 🇩🇪",
    "AMS": "Amsterdam 🇳🇱", "PAR": "Paris 🇫🇷", "LSE": "London 🇬🇧",
    "MIL": "Milan 🇮🇹", "NSI": "NSE India 🇮🇳", "BSE": "BSE India 🇮🇳",
    "NYQ": "NYSE 🇺🇸", "NMS": "NASDAQ 🇺🇸", "NGM": "NASDAQ 🇺🇸",
    "PCX": "NYSE Arca 🇺🇸", "BTS": "NASDAQ 🇺🇸", "TOR": "Toronto 🇨🇦",
    "ASX": "Australia 🇦🇺", "JPX": "Tokyo 🇯🇵",
}


def search_ticker(query: str) -> list:
    """Search for tickers. Yahoo Finance search first, Finnhub as supplement."""
    key = f"search:{query.lower()[:20]}"
    cached = cache_get(key, TTL_SEARCH)
    if cached is not None:
        return cached

    result = []

    try:
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        params = {"q": query, "quotesCount": 12, "newsCount": 0, "enableFuzzyQuery": True}
        r = requests.get(url, params=params, headers=_HEADERS, timeout=5)
        if r.status_code == 200:
            quotes = r.json().get("quotes", [])
            result = [
                {
                    "ticker": q.get("symbol", ""),
                    "name": q.get("shortname") or q.get("longname") or q.get("symbol", ""),
                    "exchange": _EXCHANGE_NAMES.get(
                        q.get("exchange", ""), q.get("exchange") or ""
                    ),
                }
                for q in quotes
                if q.get("symbol") and q.get("quoteType") in ("EQUITY", "ETF")
            ][:10]
    except Exception:
        pass

    if len(result) < 4:
        fh = _finnhub()
        if fh:
            try:
                res = fh.symbol_search(query)
                existing = {r["ticker"] for r in result}
                for item in (res or {}).get("result", [])[:10]:
                    sym = item.get("symbol", "")
                    if sym and sym not in existing:
                        result.append({
                            "ticker": sym,
                            "name": item.get("description", ""),
                            "exchange": "",
                        })
                        existing.add(sym)
                result = result[:10]
            except Exception:
                pass

    if result:
        cache_set(key, result)
    return result
