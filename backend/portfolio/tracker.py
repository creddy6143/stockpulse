"""Portfolio P&L and positions management."""
from database.db import get_portfolio, get_watchlist
from data.fetcher import get_stock_price
from intelligence.trust_score import get_trust_score_with_fallback
from intelligence.claude_ai import get_verdict

# Demo prices for when live data is unavailable
DEMO_PRICES = {
    "TNXP":       {"price": 13.50,  "change_pct": -71.2, "name": "Tonix Pharma"},
    "XGN":        {"price": 3.39,   "change_pct": +13.0,  "name": "Exagen Inc"},
    "GRRR":       {"price": 13.06,  "change_pct": -68.1,  "name": "Gorilla Technology"},
    "INSM":       {"price": 103.0,  "change_pct": -10.4,  "name": "Insmed Inc"},
    "CVNA":       {"price": 198.4,  "change_pct": +2.1,   "name": "Carvana Co"},
    "NVDA":       {"price": 875.2,  "change_pct": +3.2,   "name": "NVIDIA Corp"},
    "AXON":       {"price": 298.4,  "change_pct": +1.8,   "name": "Axon Enterprise"},
    "PLTR":       {"price": 23.60,  "change_pct": +0.9,   "name": "Palantir"},
    "MSFT":       {"price": 418.3,  "change_pct": +0.8,   "name": "Microsoft Corp"},
    "ASML.AS":    {"price": 876.4,  "change_pct": +1.4,   "name": "ASML Holding"},
    "HDFCBANK.NS":{"price": 1623.0, "change_pct": +0.4,   "name": "HDFC Bank"},
    "RELIANCE.NS":{"price": 2847.0, "change_pct": +1.1,   "name": "Reliance Industries"},
    "TSLA":       {"price": 172.3,  "change_pct": -2.1,   "name": "Tesla Inc"},
}


def get_portfolio_with_pnl() -> dict:
    """Returns all positions with live prices and P&L."""
    positions = get_portfolio()
    result = []

    for pos in positions:
        ticker = pos["ticker"]
        price_data = get_stock_price(ticker)
        # Fall back to demo prices if live data unavailable
        if not price_data.get("price"):
            price_data = {**price_data, **DEMO_PRICES.get(ticker, {})}
        price = price_data.get("price", pos["buy_price"])
        pnl = (price - pos["buy_price"]) * pos["shares"]
        pnl_pct = ((price - pos["buy_price"]) / pos["buy_price"] * 100) if pos["buy_price"] else 0

        trust = get_trust_score_with_fallback(ticker, price_data)

        # Determine group
        group = _classify_position(trust, pnl_pct)

        result.append({
            "id": pos["id"],
            "ticker": ticker,
            "name": pos.get("name") or price_data.get("name", ticker),
            "shares": pos["shares"],
            "buy_price": pos["buy_price"],
            "current_price": round(price, 4),
            "change_pct": price_data.get("change_pct", 0),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "market": pos.get("market", "US"),
            "currency": pos.get("currency", "USD"),
            "trust_score": trust["total_score"],
            "grade": trust["grade"],
            "auto_disqualified": trust["auto_disqualified"],
            "disqualify_reason": trust["disqualify_reason"],
            "group": group,
        })

    # Sort: auto-disqualified first, then by P&L
    result.sort(key=lambda x: (not x["auto_disqualified"], x["pnl_pct"]))

    total_value = sum(p["current_price"] * p["shares"] for p in result)
    total_invested = sum(p["buy_price"] * p["shares"] for p in result)
    total_pnl = total_value - total_invested

    return {
        "positions": result,
        "summary": {
            "total_value": round(total_value, 2),
            "total_invested": round(total_invested, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round((total_pnl / total_invested * 100) if total_invested else 0, 2),
            "position_count": len(result),
        },
    }


def _classify_position(trust: dict, pnl_pct: float) -> str:
    if trust["auto_disqualified"] or trust["total_score"] < 40:
        return "urgent"
    if pnl_pct < -20 or trust["total_score"] < 60:
        return "watch"
    return "good"


def get_watchlist_with_signals() -> list:
    """Returns watchlist items with trust scores and AI signals."""
    items = get_watchlist()
    result = []

    for item in items:
        ticker = item["ticker"]
        price_data = get_stock_price(ticker)
        if not price_data.get("price"):
            price_data = {**price_data, **DEMO_PRICES.get(ticker, {})}
        trust = get_trust_score_with_fallback(ticker, price_data)

        # Watchlist grouping
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
        })

    return result
