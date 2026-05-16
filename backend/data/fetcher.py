import os
import time
import yfinance as yf
import finnhub
from datetime import datetime, timedelta
from .cache import cache_get, cache_set

FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")
_fh_client = None


def _finnhub():
    global _fh_client
    if _fh_client is None and FINNHUB_KEY:
        _fh_client = finnhub.Client(api_key=FINNHUB_KEY)
    return _fh_client


# ── PRICE DATA ───────────────────────────────────────────────────────────────

def get_stock_price(ticker: str) -> dict:
    """Returns current price, change %, volume for a ticker."""
    key = f"price:{ticker}"
    cached = cache_get(key)
    if cached:
        return cached

    try:
        t = yf.Ticker(ticker)
        info = t.info
        price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose", 0)
        prev = info.get("previousClose") or info.get("regularMarketPreviousClose", price)
        change_pct = ((price - prev) / prev * 100) if prev else 0
        volume = info.get("volume") or info.get("regularMarketVolume", 0)

        result = {
            "ticker": ticker,
            "price": round(float(price), 4),
            "change_pct": round(float(change_pct), 2),
            "volume": int(volume) if volume else 0,
            "prev_close": round(float(prev), 4),
            "currency": info.get("currency", "USD"),
            "name": info.get("shortName") or info.get("longName", ticker),
            "market_cap": info.get("marketCap"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
        }
        cache_set(key, result)
        return result
    except Exception as e:
        return {"ticker": ticker, "price": 0, "change_pct": 0, "volume": 0,
                "error": str(e)}


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
            t = yf.Ticker(sym)
            info = t.info
            price = info.get("regularMarketPrice") or info.get("previousClose", 0)
            prev = info.get("regularMarketPreviousClose") or info.get("previousClose", price)
            chg = ((price - prev) / prev * 100) if prev else 0
            result[name] = {"price": round(float(price), 2), "change_pct": round(float(chg), 2)}
        except Exception:
            result[name] = {"price": 0, "change_pct": 0}

    vix = result.get("vix", {}).get("price", 15)
    if vix < 15:
        status = {"label": "Market Calm", "dot": "calm", "color": "green"}
    elif vix < 25:
        status = {"label": "Market Choppy", "dot": "choppy", "color": "amber"}
    else:
        status = {"label": "Market Alert", "dot": "alert", "color": "rose"}

    result["status"] = status
    cache_set(key, result)
    return result


# ── FUNDAMENTALS ─────────────────────────────────────────────────────────────

def get_fundamentals(ticker: str) -> dict:
    """Returns revenue growth, earnings, profitability signals."""
    key = f"fundamentals:{ticker}"
    cached = cache_get(key)
    if cached:
        return cached

    try:
        t = yf.Ticker(ticker)
        info = t.info

        revenue_growth = info.get("revenueGrowth", 0) or 0
        earnings_growth = info.get("earningsGrowth", 0) or 0
        profit_margins = info.get("profitMargins", 0) or 0
        pe_ratio = info.get("trailingPE")
        forward_pe = info.get("forwardPE")
        gross_margins = info.get("grossMargins", 0) or 0
        debt_to_equity = info.get("debtToEquity", 0) or 0
        current_ratio = info.get("currentRatio", 0)
        free_cashflow = info.get("freeCashflow", 0)
        total_cash = info.get("totalCash", 0)
        total_debt = info.get("totalDebt", 0)
        market_cap = info.get("marketCap", 0)

        # Cash runway estimate (months)
        operating_cashflow = info.get("operatingCashflow", 0) or 0
        cash_runway_months = None
        if total_cash and operating_cashflow < 0:
            cash_runway_months = round((total_cash / abs(operating_cashflow)) * 12)

        # Quarterly earnings surprise via Finnhub
        earnings_history = []
        surprise_pct = None
        fh = _finnhub()
        if fh and not ticker.endswith((".NS", ".BO")):
            try:
                eq = fh.company_earnings(ticker, limit=8)
                if eq:
                    earnings_history = eq[:4]
                    if earnings_history:
                        last = earnings_history[0]
                        if last.get("estimate") and last.get("actual") is not None:
                            est = last["estimate"]
                            act = last["actual"]
                            if est != 0:
                                surprise_pct = round((act - est) / abs(est) * 100, 1)
            except Exception:
                pass

        # Next earnings date
        try:
            cal = t.calendar
            next_earnings = None
            if cal is not None and hasattr(cal, 'get'):
                next_earnings = cal.get("Earnings Date")
                if isinstance(next_earnings, list) and next_earnings:
                    next_earnings = str(next_earnings[0].date()) if hasattr(next_earnings[0], 'date') else str(next_earnings[0])
            elif cal is not None and hasattr(cal, 'iloc'):
                try:
                    val = cal.iloc[0, 0]
                    next_earnings = str(val) if val else None
                except Exception:
                    pass
        except Exception:
            next_earnings = None

        result = {
            "ticker": ticker,
            "revenue_growth": round(float(revenue_growth), 4),
            "earnings_growth": round(float(earnings_growth), 4),
            "profit_margins": round(float(profit_margins), 4),
            "gross_margins": round(float(gross_margins), 4),
            "pe_ratio": round(float(pe_ratio), 2) if pe_ratio else None,
            "forward_pe": round(float(forward_pe), 2) if forward_pe else None,
            "debt_to_equity": round(float(debt_to_equity), 2),
            "current_ratio": round(float(current_ratio), 2) if current_ratio else None,
            "free_cashflow": free_cashflow,
            "total_cash": total_cash,
            "total_debt": total_debt,
            "market_cap": market_cap,
            "cash_runway_months": cash_runway_months,
            "earnings_surprise_pct": surprise_pct,
            "earnings_history": earnings_history,
            "next_earnings_date": next_earnings,
            "gaap_profitable": profit_margins > 0,
            "w52_high": info.get("fiftyTwoWeekHigh"),
            "w52_low": info.get("fiftyTwoWeekLow"),
        }
        cache_set(key, result)
        return result
    except Exception as e:
        return {"ticker": ticker, "revenue_growth": 0, "earnings_growth": 0,
                "profit_margins": 0, "gross_margins": 0, "error": str(e)}


# ── INSIDER / INSTITUTIONAL ──────────────────────────────────────────────────

def get_insider_data(ticker: str) -> dict:
    """Returns insider buy/sell signals and institutional data."""
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
    if fh and not ticker.endswith((".NS", ".BO")):
        try:
            cutoff = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
            today = datetime.now().strftime("%Y-%m-%d")
            txns = fh.stock_insider_transactions(ticker, cutoff, today)
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
            t_obj = yf.Ticker(ticker)
            info = t_obj.info
            short_pct = info.get("shortPercentOfFloat", 0) or 0
            result["short_interest_pct"] = round(float(short_pct) * 100, 1)
            inst_pct = info.get("institutionPercentHeld", 0) or 0
            result["institutional_buying"] = inst_pct > 0.50
        except Exception:
            pass

    cache_set(key, result)
    return result


# ── NEWS ─────────────────────────────────────────────────────────────────────

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


# ── ANALYST DATA ─────────────────────────────────────────────────────────────

def get_analyst_data(ticker: str) -> dict:
    """Returns analyst ratings and price target."""
    key = f"analyst:{ticker}"
    cached = cache_get(key)
    if cached:
        return cached

    try:
        t = yf.Ticker(ticker)
        info = t.info
        result = {
            "target_price": info.get("targetMeanPrice"),
            "target_high": info.get("targetHighPrice"),
            "target_low": info.get("targetLowPrice"),
            "buy_count": info.get("numberOfAnalystOpinions", 0),
            "hold_count": 0,
            "sell_count": 0,
            "recommendation": info.get("recommendationKey", "hold"),
        }
        # Try to get buy/hold/sell breakdown from recommendations
        try:
            recs = t.recommendations
            if recs is not None and not recs.empty:
                recent = recs.tail(1)
                buy = 0
                hold = 0
                sell = 0
                for col in recent.columns:
                    val = int(recent[col].iloc[0] or 0)
                    cl = col.lower()
                    if "strong_buy" in cl or "strongbuy" in cl or cl == "buy":
                        buy += val
                    elif "hold" in cl or "neutral" in cl:
                        hold += val
                    elif "sell" in cl or "underperform" in cl or "underweight" in cl:
                        sell += val
                if buy + hold + sell > 0:
                    result["buy_count"] = buy
                    result["hold_count"] = hold
                    result["sell_count"] = sell
        except Exception:
            pass
        cache_set(key, result)
        return result
    except Exception:
        return {"target_price": None, "recommendation": "hold",
                "buy_count": 0, "hold_count": 0, "sell_count": 0}


# ── STOCK HISTORY ─────────────────────────────────────────────────────────────

def get_stock_history(ticker: str) -> dict:
    """Returns performance % for 1W, 1M, 3M, 6M, 1Y timeframes."""
    key = f"history:{ticker}"
    cached = cache_get(key)
    if cached:
        return cached

    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="1y")
        if hist.empty or len(hist) < 5:
            return {"1W": 0, "1M": 0, "3M": 0, "6M": 0, "1Y": 0}

        current = float(hist['Close'].iloc[-1])

        def pct(days):
            idx = max(0, len(hist) - days)
            past = float(hist['Close'].iloc[idx])
            return round((current - past) / past * 100, 1) if past else 0

        result = {
            "1W": pct(5),
            "1M": pct(22),
            "3M": pct(65),
            "6M": pct(130),
            "1Y": pct(min(252, len(hist) - 1)),
        }
        cache_set(key, result)
        return result
    except Exception:
        return {"1W": 0, "1M": 0, "3M": 0, "6M": 0, "1Y": 0}
