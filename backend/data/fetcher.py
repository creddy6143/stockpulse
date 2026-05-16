"""Data fetcher.

Primary sources (no Yahoo Finance dependency):
  - Stock prices:   Finnhub quote()
  - Forex rates:    Frankfurter.app (ECB rates, free, no key)
  - Market indices: Finnhub ETF proxies (SPY, QQQ, EWG, INDA, VXX)

Fallback:
  - Yahoo Finance v8 chart API (works on fresh IPs; used for non-US tickers)
"""
import os
import requests
import finnhub
from datetime import datetime, timedelta
from .cache import cache_get, cache_set

FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")
_fh_client = None

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
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


def _yf_chart(symbol: str) -> dict:
    """Yahoo Finance v8 chart API fallback — works on Railway's fresh IP."""
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        "?range=1d&interval=5m"
    )
    try:
        r = requests.get(url, headers=_HEADERS, timeout=10)
        if r.status_code != 200:
            return {}
        results = r.json().get("chart", {}).get("result")
        if not results:
            return {}
        return results[0].get("meta", {})
    except Exception:
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
    cached = cache_get(key)
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
    cached = cache_get(key)
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
    """Returns VIX proxy + 4 major market indices via Finnhub ETF proxies.
    VIX: VXX (VIX futures ETF) — VXX/1.5 ≈ actual VIX level.
    S&P 500: SPY, Nasdaq: QQQ, DAX: EWG, Nifty: INDA.
    """
    key = "market_data"
    cached = cache_get(key)
    if cached:
        return cached

    fh = _finnhub()
    # ETF proxies: (internal key, Finnhub symbol, divisor for display)
    proxies = [
        ("vix",    "VXX",  1.5),   # VXX/1.5 ≈ VIX level
        ("sp500",  "SPY",  1.0),
        ("nasdaq", "QQQ",  1.0),
        ("dax",    "EWG",  1.0),
        ("nifty",  "INDA", 1.0),
    ]
    result = {}
    for name, sym, divisor in proxies:
        try:
            q = fh.quote(sym) if fh else {}
            price = float(q.get("c") or 0)
            change_pct = float(q.get("dp") or 0)
            display_price = round(price / divisor, 2) if price else 0
            result[name] = {"price": display_price, "change_pct": round(change_pct, 2)}
        except Exception:
            result[name] = {"price": 0, "change_pct": 0}

    # Market status based on derived VIX level (VXX / 1.5)
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
    cached = cache_get(key)
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
    if not fh:
        return result

    # Strip exchange suffix for Finnhub
    clean = ticker
    for suffix in (".NS", ".BO", ".ST", ".AS", ".DE", ".PA", ".F", ".MI", ".MC", ".BR", ".L"):
        clean = clean.replace(suffix, "")

    try:
        bf = fh.company_basic_financials(clean, "all")
        m = (bf or {}).get("metric", {})
        if m:
            # Finnhub returns these values in PERCENTAGE form (e.g. 65.47 means 65.47%)
            rev = float(m.get("revenueGrowthTTMYoy") or m.get("revenueGrowth5Y") or 0)
            result["revenue_growth"] = round(rev / 100, 4)

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

    cache_set(key, result)
    return result


# ── INSIDER / INSTITUTIONAL ───────────────────────────────────────────────────

def get_insider_data(ticker: str) -> dict:
    """Insider buy/sell signals and institutional data from Finnhub."""
    key = f"insider:{ticker}"
    cached = cache_get(key)
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

def get_news(ticker: str, days: int = 7) -> list:
    """Recent news headlines from Finnhub."""
    key = f"news:{ticker}:{days}"
    cached = cache_get(key)
    if cached:
        return cached

    fh = _finnhub()
    if not fh:
        return []

    try:
        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")
        clean = ticker.replace(".NS", "").replace(".BO", "")
        news = fh.company_news(clean, _from=from_date, to=to_date)
        result = news[:10] if news else []
        cache_set(key, result)
        return result
    except Exception:
        return []


# ── ANALYST DATA ──────────────────────────────────────────────────────────────

def get_analyst_data(ticker: str) -> dict:
    """Analyst ratings and price target from Finnhub."""
    key = f"analyst:{ticker}"
    cached = cache_get(key)
    if cached:
        return cached

    result = {
        "target_price": None, "target_high": None, "target_low": None,
        "buy_count": 0, "hold_count": 0, "sell_count": 0,
        "recommendation": "hold",
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
    """Performance % for 1W, 1M, 3M, 6M, 1Y via Yahoo v8 chart (1y range)."""
    key = f"history:{ticker}"
    cached = cache_get(key)
    if cached:
        return cached

    empty = {"1W": 0, "1M": 0, "3M": 0, "6M": 0, "1Y": 0}
    try:
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            "?range=1y&interval=1d"
        )
        r = requests.get(url, headers=_HEADERS, timeout=15)
        if r.status_code != 200:
            return empty
        results = r.json().get("chart", {}).get("result")
        if not results:
            return empty

        closes = (
            results[0].get("indicators", {})
            .get("quote", [{}])[0]
            .get("close", [])
        )
        closes = [c for c in closes if c is not None]
        if len(closes) < 5:
            return empty

        current = closes[-1]

        def pct(days):
            idx = max(0, len(closes) - days)
            past = closes[idx]
            return round((current - past) / past * 100, 1) if past else 0

        result = {
            "1W": pct(5), "1M": pct(22), "3M": pct(65),
            "6M": pct(130), "1Y": pct(min(252, len(closes) - 1)),
        }
        cache_set(key, result)
        return result
    except Exception:
        return empty


# ── TICKER SEARCH ─────────────────────────────────────────────────────────────

def search_ticker(query: str) -> list:
    """Search for tickers. Yahoo Finance search first, Finnhub as supplement."""
    key = f"search:{query.lower()[:20]}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    result = []

    try:
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        params = {"q": query, "quotesCount": 8, "newsCount": 0, "enableFuzzyQuery": True}
        r = requests.get(url, params=params, headers=_HEADERS, timeout=5)
        if r.status_code == 200:
            quotes = r.json().get("quotes", [])
            result = [
                {
                    "ticker": q.get("symbol", ""),
                    "name": q.get("shortname") or q.get("longname") or q.get("symbol", ""),
                }
                for q in quotes
                if q.get("symbol") and q.get("quoteType") in ("EQUITY", "ETF")
            ][:8]
    except Exception:
        pass

    if len(result) < 4:
        fh = _finnhub()
        if fh:
            try:
                res = fh.symbol_search(query)
                existing = {r["ticker"] for r in result}
                for item in (res or {}).get("result", [])[:8]:
                    sym = item.get("symbol", "")
                    if sym and sym not in existing:
                        result.append({"ticker": sym, "name": item.get("description", "")})
                        existing.add(sym)
                result = result[:8]
            except Exception:
                pass

    if result:
        cache_set(key, result)
    return result
