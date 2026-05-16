"""Portfolio P&L and positions management — all values in native currency + SEK."""
from database.db import get_portfolio, get_watchlist
from data.fetcher import get_stock_price, get_exchange_rates
from intelligence.trust_score import get_trust_score_with_fallback


def _detect_currency(ticker: str) -> str:
    """Infer native currency from ticker suffix."""
    if ticker.endswith(".NS") or ticker.endswith(".BO"):
        return "INR"
    if ticker.endswith(".ST"):           # Stockholm — Swedish kronor
        return "SEK"
    if any(ticker.endswith(s) for s in [".AS", ".DE", ".PA", ".F", ".MI", ".MC", ".BR"]):
        return "EUR"
    if ticker.endswith(".L"):
        return "GBP"
    return "USD"


def _sek_rate(currency: str, rates: dict) -> float:
    """How many SEK per 1 unit of the given currency."""
    mapping = {
        "USD": rates.get("USDSEK", 10.4),
        "EUR": rates.get("EURSEK", 11.2),
        "INR": rates.get("INRSEK", 0.124),
        "SEK": 1.0,
        "GBP": rates.get("GBPSEK", 13.2),
    }
    return mapping.get((currency or "USD").upper(), rates.get("USDSEK", 10.4))


def get_portfolio_with_pnl() -> dict:
    """Returns all positions with live prices, P&L in native currency, and SEK values."""
    positions = get_portfolio()
    rates = get_exchange_rates()
    result = []

    for pos in positions:
        ticker = pos["ticker"]
        price_data = get_stock_price(ticker)

        # Use live price; fall back to buy_price if yfinance returns nothing
        price = price_data.get("price") or pos["buy_price"]
        currency = pos.get("currency") or _detect_currency(ticker)
        rate = _sek_rate(currency, rates)

        shares = pos["shares"]
        buy_price = pos["buy_price"]

        pnl = (price - buy_price) * shares
        pnl_pct = ((price - buy_price) / buy_price * 100) if buy_price else 0
        value_sek = price * shares * rate
        invested_sek = buy_price * shares * rate
        pnl_sek = value_sek - invested_sek

        trust = get_trust_score_with_fallback(ticker, price_data)
        group = _classify_position(trust, pnl_pct)

        result.append({
            "id": pos["id"],
            "ticker": ticker,
            "name": pos.get("name") or price_data.get("name", ticker),
            "shares": shares,
            "buy_price": buy_price,
            "current_price": round(float(price), 4),
            "change_pct": round(float(price_data.get("change_pct", 0)), 2),
            "pnl": round(float(pnl), 2),
            "pnl_pct": round(float(pnl_pct), 2),
            "value_sek": round(value_sek, 0),
            "invested_sek": round(invested_sek, 0),
            "pnl_sek": round(pnl_sek, 0),
            "sek_rate": rate,
            "market": pos.get("market", "US"),
            "currency": currency,
            "trust_score": trust["total_score"],
            "grade": trust["grade"],
            "auto_disqualified": trust["auto_disqualified"],
            "disqualify_reason": trust["disqualify_reason"],
            "group": group,
        })

    # Sort: auto-disqualified first, then worst P&L first
    result.sort(key=lambda x: (not x["auto_disqualified"], x["pnl_pct"]))

    total_value_sek = sum(p["value_sek"] for p in result)
    total_invested_sek = sum(p["invested_sek"] for p in result)
    total_pnl_sek = total_value_sek - total_invested_sek
    pnl_pct_sek = (total_pnl_sek / total_invested_sek * 100) if total_invested_sek else 0

    return {
        "positions": result,
        "summary": {
            "total_value_sek": round(total_value_sek, 0),
            "total_invested_sek": round(total_invested_sek, 0),
            "total_pnl_sek": round(total_pnl_sek, 0),
            "total_pnl_pct": round(pnl_pct_sek, 2),
            "position_count": len(result),
            "exchange_rates": rates,
        },
    }


def _classify_position(trust: dict, pnl_pct: float) -> str:
    if trust["auto_disqualified"] or trust["total_score"] < 40:
        return "urgent"
    if pnl_pct < -20 or trust["total_score"] < 60:
        return "watch"
    return "good"


def get_watchlist_with_signals() -> list:
    """Returns watchlist items with trust scores and signals."""
    items = get_watchlist()
    result = []

    for item in items:
        ticker = item["ticker"]
        price_data = get_stock_price(ticker)
        trust = get_trust_score_with_fallback(ticker, price_data)

        if trust["total_score"] >= 75 and not trust["auto_disqualified"]:
            wl_group = "ready"
            signal = "Entry zone now"
        elif trust["auto_disqualified"] or trust["total_score"] < 40:
            wl_group = "avoid"
            signal = "Not yet"
        else:
            wl_group = "watching"
            signal = "Still watching"

        result.append({
            "id": item["id"],
            "ticker": ticker,
            "name": item.get("name") or price_data.get("name", ticker),
            "current_price": price_data.get("price", 0),
            "change_pct": price_data.get("change_pct", 0),
            "trust_score": trust["total_score"],
            "grade": trust["grade"],
            "wl_group": wl_group,
            "signal": signal,
            "added_at": item.get("added_at"),
            "market": item.get("market", "US"),
        })

    return result
