"""Data fetcher.

Primary sources:
  - Stock prices:   Finnhub quote()
  - Forex rates:    Frankfurter.app (ECB rates, free, no key)
  - Market indices: Yahoo Finance v8 (cookie+crumb auth) → Finnhub ETF proxies

Yahoo Finance cookie+crumb auth lets us get real ^VIX, ^GSPC, ^IXIC, ^GDAXI, ^NSEI.
Falls back to Finnhub ETF proxies (SPY, QQQ, EWG, INDA, VXX) if Yahoo is blocked.
"""
import os
import time as _time
import requests
import finnhub
from datetime import datetime, timedelta
from .cache import (cache_get, cache_set,
                     TTL_PRICE, TTL_MARKET, TTL_RATES, TTL_FUNDAMENTALS,
                     TTL_ANALYST, TTL_INSIDER, TTL_HISTORY, TTL_NEWS,
                     TTL_SEARCH, TTL_TRUST, TTL_STRATEGY)

FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")
_fh_client = None

# Yahoo Finance authenticated session (cookie+crumb, refreshed every 30 min)
_yf_session = None
_yf_crumb = None
_yf_crumb_ts = 0.0

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
    """Yahoo Finance v8 chart. Tries cookie+crumb auth first, then unauthenticated."""
    session, crumb = _get_yf_auth()
    base = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=5m"
    for url in [
        f"{base}&crumb={crumb}" if crumb else None,
        base,
    ]:
        if url is None:
            continue
        try:
            r = (session or requests).get(url, headers=_HEADERS, timeout=10)
            if r.status_code == 200:
                results = r.json().get("chart", {}).get("result")
                if results:
                    return results[0].get("meta", {})
        except Exception:
            continue
    return {}


def _yf_quotesummary(ticker: str) -> dict:
    """Yahoo Finance v10 quoteSummary — returns rich fundamentals + analyst target price.
    More reliable than Finnhub for international stocks (.ST, .AS, .L etc.).
    Uses cookie+crumb auth. Returns merged financialData + defaultKeyStatistics dict.
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
    for url in [
        f"{base}&crumb={crumb}" if crumb else None,
        base,
    ]:
        if url is None:
            continue
        try:
            r = (session or requests).get(url, headers=_HEADERS, timeout=10)
            if r.status_code == 200:
                qs = r.json().get("quoteSummary", {})
                if qs.get("error"):
                    break
                results = qs.get("result") or []
                if results:
                    fd = results[0].get("financialData", {})
                    ks = results[0].get("defaultKeyStatistics", {})
                    # Merge both modules into one flat dict of raw values
                    merged = {}
                    for d in (fd, ks):
                        for k, v in d.items():
                            merged[k] = v.get("raw") if isinstance(v, dict) else v
                    cache_set(key, merged)
                    return merged
        except Exception:
            continue

    empty = {}
    cache_set(key, empty)
    return empty


def _yf_lib_fundamentals(ticker: str) -> dict:
    """Use yfinance Python library for better international stock data (.ST, .AS, .L etc.).
    Only called when Finnhub + Yahoo quoteSummary HTTP calls both fail to return data.
    """
    key = f"yf_lib:{ticker}"
    cached = cache_get(key, TTL_FUNDAMENTALS)
    if cached is not None:
        return cached
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.info or {}
        if not info.get("regularMarketPrice") and not info.get("currentPrice"):
            cache_set(key, {})
            return {}
        result = {
            "revenue_growth":  round(float(info.get("revenueGrowth") or 0), 4),
            "profit_margins":  round(float(info.get("profitMargins") or 0), 4),
            "gross_margins":   round(float(info.get("grossMargins") or 0), 4),
            "gaap_profitable": (info.get("profitMargins") or 0) > 0,
            "market_cap":      int(info.get("marketCap") or 0),
            "pe_ratio":        round(float(p), 2) if (p := info.get("trailingPE") or info.get("forwardPE")) else None,
            "w52_high":        info.get("fiftyTwoWeekHigh"),
            "w52_low":         info.get("fiftyTwoWeekLow"),
            "earnings_growth": round(float(info.get("earningsGrowth") or 0), 4),
        }
        cache_set(key, result)
        return result
    except Exception:
        cache_set(key, {})
        return {}


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

    # Primary: Finnhub
    if fh and fh_sym:
        try:
            q = fh.quote(fh_sym)
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


def get_market_data() -> dict:
    """Returns VIX + 4 major market indices.
    Primary: Yahoo Finance real indices via cookie+crumb (^VIX, ^GSPC, ^IXIC, ^GDAXI, ^NSEI).
    Fallback: Finnhub ETF proxies (VXX/1.5, SPY, QQQ, EWG, INDA).
    """
    key = "market_data"
    cached = cache_get(key, TTL_MARKET)
    if cached:
        return cached

    result = {}

    # Primary: Yahoo Finance real indices
    yf_map = {
        "vix":    "^VIX",
        "sp500":  "^GSPC",
        "nasdaq": "^IXIC",
        "dax":    "^GDAXI",
        "nifty":  "^NSEI",
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
    }
    if fh:
        for name, (sym, div) in etf_fallbacks.items():
            if name not in result:
                try:
                    q = fh.quote(sym)
                    price = float(q.get("c") or 0)
                    chg = float(q.get("dp") or 0)
                    result[name] = {"price": round(price / div, 2), "change_pct": round(chg, 2)}
                except Exception:
                    result[name] = {"price": 0, "change_pct": 0}

    # Ensure all keys exist
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
    cache_set(key, result)
    return result


# ── FUNDAMENTALS ──────────────────────────────────────────────────────────────

def get_fundamentals(ticker: str) -> dict:
    """Revenue growth, earnings, profitability from Finnhub company_basic_financials."""
    key = f"fundamentals:{ticker}"
    cached = cache_get(key, TTL_FUNDAMENTALS)
    if cached:
        return cached

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
            bf = fh.company_basic_financials(clean, "all")
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
                eq = fh.company_earnings(clean, limit=8)
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
                cal = fh.earnings_calendar(symbol=clean, from_=today_str, to=ninety_str)
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

    # yfinance Python library fallback — most reliable for international stocks (.ST, .AS, .L etc.)
    # Only runs when fundamentals are still missing after all HTTP-based sources
    is_intl = any(ticker.endswith(s) for s in [".ST", ".AS", ".L", ".DE", ".PA", ".MI", ".MC"])
    still_missing = not (result["market_cap"] or 0) > 0 or abs(result["revenue_growth"]) < 0.001
    if is_intl and still_missing:
        yf_data = _yf_lib_fundamentals(ticker)
        if yf_data:
            for k, v in yf_data.items():
                if v and not result.get(k):
                    result[k] = v

    cache_set(key, result)
    return result


# ── INSIDER / INSTITUTIONAL ───────────────────────────────────────────────────

def get_insider_data(ticker: str) -> dict:
    """Insider buy/sell signals and institutional data from Finnhub."""
    key = f"insider:{ticker}"
    cached = cache_get(key, TTL_INSIDER)
    if cached:
        return cached

    result = {
        "ceo_buying": False,
        "insider_buy_value": 0,
        "insider_sell_value": 0,
        "institutional_buying": False,
        "short_interest_pct": 0,
    }

    fh = _finnhub()
    if not fh or ticker.endswith((".NS", ".BO")):
        cache_set(key, result)
        return result

    clean = ticker
    for suffix in (".ST", ".AS", ".DE", ".PA", ".F", ".MI", ".MC", ".BR", ".L"):
        clean = clean.replace(suffix, "")

    try:
        cutoff = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        txns = fh.stock_insider_transactions(clean, cutoff, today)
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
        bf = fh.company_basic_financials(clean, "all")
        m = (bf or {}).get("metric", {})
        short_pct = m.get("shortInterestSharesOutstanding")
        if short_pct:
            result["short_interest_pct"] = round(float(short_pct) * 100, 1)
    except Exception:
        pass

    try:
        own = fh.ownership(clean, limit=10)
        holders = (own or {}).get("ownership", [])
        if holders:
            total_pct = sum(float(h.get("share", 0) or 0) for h in holders[:5])
            result["institutional_buying"] = total_pct > 0.30
    except Exception:
        pass

    cache_set(key, result)
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
            raw = fh.company_news(clean, _from=from_date, to=to_date)
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
    if cached:
        return cached

    result = {
        "target_price": None, "target_high": None, "target_low": None,
        "buy_count": 0, "hold_count": 0, "sell_count": 0,
        "recommendation": "hold", "revenue_estimate": None,
    }

    fh = _finnhub()
    if not fh or ticker.endswith((".NS", ".BO")):
        cache_set(key, result)
        return result

    clean = ticker
    for suffix in (".ST", ".AS", ".DE", ".PA", ".F", ".MI", ".MC", ".BR", ".L"):
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
