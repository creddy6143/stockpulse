"""Data fetcher — uses Yahoo Finance v8 chart API directly (bypasses rate limiting)."""
import os
import requests
import finnhub
from datetime import datetime, timedelta
from .cache import cache_get, cache_set

FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")
_fh_client = None

# Mimic a real browser to avoid Yahoo Finance 429s on v8 chart endpoint
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
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
    """Fetch price meta from Yahoo Finance v8 chart API.
    Works reliably even when yfinance .info hits 429 rate limits.
    Returns the 'meta' dict from the chart response, or {} on failure.
    """
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?range=1d&interval=5m"
    )
    try:
        r = requests.get(url, headers=_HEADERS, timeout=10)
        if r.status_code != 200:
            return {}
        data = r.json()
        results = data.get("chart", {}).get("result")
        if not results:
            return {}
        return results[0].get("meta", {})
    except Exception:
        return {}


# ── EXCHANGE RATES ────────────────────────────────────────────────────────────

def get_exchange_rates() -> dict:
    """Returns live SEK per 1 unit of each major currency.
    INRSEK is derived from USDSEK / USDINR (INRSEK=X returns 404 on Yahoo).
    Cached 15 minutes. Falls back to sensible defaults if live fetch fails.
    """
    key = "exchange_rates"
    cached = cache_get(key)
    if cached:
        return cached

    rates = {"USDSEK": 10.4, "EURSEK": 11.2, "INRSEK": 0.124, "GBPSEK": 13.2}

    for rate_key, symbol in [
        ("USDSEK", "USDSEK=X"),
        ("EURSEK", "EURSEK=X"),
        ("GBPSEK", "GBPSEK=X"),
    ]:
        try:
            meta = _yf_chart(symbol)
            price = float(meta.get("regularMarketPrice") or 0)
            if price > 0:
                rates[rate_key] = round(price, 6)
        except Exception:
            pass

    # INRSEK=X returns 404 on Yahoo — derive from USDINR=X
    try:
        meta = _yf_chart("USDINR=X")
        usdinr = float(meta.get("regularMarketPrice") or 0)
        if usdinr > 0:
            rates["INRSEK"] = round(rates["USDSEK"] / usdinr, 6)
    except Exception:
        pass

    cache_set(key, rates)
    return rates


# ── PRICE DATA ────────────────────────────────────────────────────────────────

def get_stock_price(ticker: str) -> dict:
    """Returns current price, change %, volume for a ticker."""
    key = f"price:{ticker}"
    cached = cache_get(key)
    if cached:
        return cached

    try:
        meta = _yf_chart(ticker)
        if not meta:
            return {"ticker": ticker, "price": 0, "change_pct": 0, "volume": 0}

        price = float(meta.get("regularMarketPrice") or 0)
        prev = float(
            meta.get("chartPreviousClose")
            or meta.get("previousClose")
            or price
        )
        change_pct = ((price - prev) / prev * 100) if prev else 0

        result = {
            "ticker": ticker,
            "price": round(price, 4),
            "change_pct": round(change_pct, 2),
            "volume": int(meta.get("regularMarketVolume") or 0),
            "prev_close": round(prev, 4),
            "currency": meta.get("currency", "USD"),
            "name": meta.get("shortName") or meta.get("longName") or ticker,
            "market_cap": None,
            "sector": None,
            "industry": None,
        }
        if price > 0:
            cache_set(key, result)
        return result
    except Exception as e:
        return {
            "ticker": ticker, "price": 0, "change_pct": 0,
            "volume": 0, "error": str(e),
        }


def get_market_data() -> dict:
    """Returns VIX + 4 major market indices."""
    key = "market_data"
    cached = cache_get(key)
    if cached:
        return cached

    indices = {
        "vix":    "^VIX",
        "sp500":  "^GSPC",
        "nasdaq": "^IXIC",
        "dax":    "^GDAXI",
        "nifty":  "^NSEI",
    }
    result = {}
    for name, sym in indices.items():
        try:
            meta = _yf_chart(sym)
            price = float(meta.get("regularMarketPrice") or 0)
            prev = float(
                meta.get("chartPreviousClose")
                or meta.get("previousClose")
                or price
            )
            chg = ((price - prev) / prev * 100) if prev else 0
            result[name] = {"price": round(price, 2), "change_pct": round(chg, 2)}
        except Exception:
            result[name] = {"price": 0, "change_pct": 0}

    vix_price = result.get("vix", {}).get("price", 15)
    if vix_price < 15:
        status = {"label": "Market Calm", "dot": "calm", "color": "green"}
    elif vix_price < 25:
        status = {"label": "Market Choppy", "dot": "choppy", "color": "amber"}
    else:
        status = {"label": "Market Alert", "dot": "alert", "color": "rose"}

    result["status"] = status
    cache_set(key, result)
    return result


# ── FUNDAMENTALS ──────────────────────────────────────────────────────────────

def get_fundamentals(ticker: str) -> dict:
    """Returns revenue growth, earnings, profitability signals.
    Uses Finnhub company_basic_financials as primary source.
    """
    key = f"fundamentals:{ticker}"
    cached = cache_get(key)
    if cached:
        return cached

    result = {
        "ticker": ticker,
        "revenue_growth": 0,
        "earnings_growth": 0,
        "profit_margins": 0,
        "gross_margins": 0,
        "pe_ratio": None,
        "forward_pe": None,
        "debt_to_equity": 0,
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
    # Clean ticker for Finnhub (no exchange suffixes)
    clean = ticker.replace(".NS", "").replace(".BO", "").replace(".ST", "")
    clean = clean.replace(".AS", "").replace(".DE", "").replace(".L", "")

    if fh:
        try:
            bf = fh.company_basic_financials(clean, "all")
            metric = bf.get("metric", {}) if bf else {}
            if metric:
                # Revenue growth — Finnhub returns in % form (e.g. 122 = 122%)
                rev = metric.get("revenueGrowthTTMYoy") or metric.get("revenueGrowth5Y") or 0
                result["revenue_growth"] = round(float(rev) / 100, 4)

                # Profit margins in % form
                margin = metric.get("netProfitMarginTTM") or 0
                result["profit_margins"] = round(float(margin) / 100, 4)
                result["gaap_profitable"] = result["profit_margins"] > 0

                gross = metric.get("grossMarginTTM") or 0
                result["gross_margins"] = round(float(gross) / 100, 4)

                pe = metric.get("peNormalizedAnnual") or metric.get("peTTM")
                result["pe_ratio"] = round(float(pe), 2) if pe else None

                curr_ratio = metric.get("currentRatioAnnual")
                result["current_ratio"] = round(float(curr_ratio), 2) if curr_ratio else None

                mktcap = metric.get("marketCapitalization")
                result["market_cap"] = int(float(mktcap) * 1_000_000) if mktcap else 0

                w52h = metric.get("52WeekHigh")
                w52l = metric.get("52WeekLow")
                result["w52_high"] = float(w52h) if w52h else None
                result["w52_low"] = float(w52l) if w52l else None
        except Exception:
            pass

        # Earnings surprise + history (US & EU only)
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
                cal = fh.earnings_calendar(
                    symbol=clean, from_=today_str, to=ninety_str
                )
                cal_list = (cal or {}).get("earningsCalendar", [])
                if cal_list:
                    result["next_earnings_date"] = cal_list[0].get("date")
            except Exception:
                pass

    cache_set(key, result)
    return result


# ── INSIDER / INSTITUTIONAL ───────────────────────────────────────────────────

def get_insider_data(ticker: str) -> dict:
    """Returns insider buy/sell signals and institutional data (Finnhub only)."""
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

    clean = ticker.replace(".ST", "").replace(".AS", "").replace(".DE", "")
    clean = clean.replace(".L", "").replace(".NS", "").replace(".BO", "")

    # Insider transactions (last 90 days)
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

    # Short interest from Finnhub basic financials
    try:
        bf = fh.company_basic_financials(clean, "all")
        metric = (bf or {}).get("metric", {})
        short_pct = metric.get("shortInterestSharesOutstanding")
        if short_pct:
            result["short_interest_pct"] = round(float(short_pct) * 100, 1)
    except Exception:
        pass

    # Institutional ownership from Finnhub
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
    """Returns recent news headlines for a ticker."""
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
    """Returns analyst ratings and price target from Finnhub."""
    key = f"analyst:{ticker}"
    cached = cache_get(key)
    if cached:
        return cached

    result = {
        "target_price": None,
        "target_high": None,
        "target_low": None,
        "buy_count": 0,
        "hold_count": 0,
        "sell_count": 0,
        "recommendation": "hold",
    }

    fh = _finnhub()
    if not fh or ticker.endswith((".NS", ".BO")):
        cache_set(key, result)
        return result

    clean = ticker.replace(".ST", "").replace(".AS", "").replace(".DE", "")
    clean = clean.replace(".L", "")

    try:
        pt = fh.price_target(clean)
        if pt:
            result["target_price"] = pt.get("targetMean")
            result["target_high"] = pt.get("targetHigh")
            result["target_low"] = pt.get("targetLow")
    except Exception:
        pass

    try:
        recs = fh.recommendation_trends(clean)
        if recs and len(recs) > 0:
            latest = recs[0]
            buy = (latest.get("strongBuy") or 0) + (latest.get("buy") or 0)
            hold = latest.get("hold") or 0
            sell = (latest.get("strongSell") or 0) + (latest.get("sell") or 0)
            result["buy_count"] = buy
            result["hold_count"] = hold
            result["sell_count"] = sell
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
    """Returns performance % for 1W, 1M, 3M, 6M, 1Y timeframes."""
    key = f"history:{ticker}"
    cached = cache_get(key)
    if cached:
        return cached

    empty = {"1W": 0, "1M": 0, "3M": 0, "6M": 0, "1Y": 0}
    try:
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            f"?range=1y&interval=1d"
        )
        r = requests.get(url, headers=_HEADERS, timeout=15)
        if r.status_code != 200:
            return empty
        data = r.json()
        results = data.get("chart", {}).get("result")
        if not results:
            return empty

        closes = (
            results[0]
            .get("indicators", {})
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
            "1W": pct(5),
            "1M": pct(22),
            "3M": pct(65),
            "6M": pct(130),
            "1Y": pct(min(252, len(closes) - 1)),
        }
        cache_set(key, result)
        return result
    except Exception:
        return empty


def search_ticker(query: str) -> list:
    """Search for tickers by name or symbol. Yahoo Finance first, Finnhub as supplement."""
    key = f"search:{query.lower()[:20]}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    result = []

    # Primary: Yahoo Finance search API (no auth required)
    try:
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        params = {
            "q": query, "quotesCount": 8,
            "newsCount": 0, "enableFuzzyQuery": True,
        }
        r = requests.get(url, params=params, headers=_HEADERS, timeout=5)
        if r.status_code == 200:
            quotes = r.json().get("quotes", [])
            result = [
                {
                    "ticker": q.get("symbol", ""),
                    "name": (
                        q.get("shortname") or q.get("longname") or q.get("symbol", "")
                    ),
                }
                for q in quotes
                if q.get("symbol") and q.get("quoteType") in ("EQUITY", "ETF")
            ][:8]
    except Exception:
        pass

    # Supplement: Finnhub symbol search
    if len(result) < 4:
        fh = _finnhub()
        if fh:
            try:
                res = fh.symbol_search(query)
                existing = {r["ticker"] for r in result}
                for item in (res or {}).get("result", [])[:8]:
                    sym = item.get("symbol", "")
                    if sym and sym not in existing:
                        result.append({
                            "ticker": sym,
                            "name": item.get("description", ""),
                        })
                        existing.add(sym)
                result = result[:8]
            except Exception:
                pass

    if result:
        cache_set(key, result)
    return result
