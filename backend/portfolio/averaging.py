"""Averaging down intelligence."""
from intelligence.trust_score import get_trust_score_with_fallback


def should_average_down(ticker: str, buy_price: float, current_price: float,
                         shares: float, price_data: dict) -> dict:
    """
    Determines whether averaging down is advisable.
    Returns recommendation and reasoning.
    """
    trust = get_trust_score_with_fallback(ticker, price_data)
    drop_pct = ((current_price - buy_price) / buy_price * 100) if buy_price else 0

    if trust["auto_disqualified"]:
        return {
            "recommend": False,
            "action": "EXIT",
            "reason": f"Auto-disqualified: {trust['disqualify_reason']}. Do not add more.",
            "new_avg_if_added": None,
        }

    if trust["total_score"] < 40:
        return {
            "recommend": False,
            "action": "HOLD",
            "reason": "Trust score too low to add. Wait for fundamentals to improve.",
            "new_avg_if_added": None,
        }

    if drop_pct > -50:
        return {
            "recommend": False,
            "action": "WAIT",
            "reason": f"Down {abs(drop_pct):.0f}%. Consider adding only if fundamentals confirm the thesis.",
            "new_avg_if_added": None,
        }

    # Calculate new average if doubled
    double_shares = shares
    total_cost = buy_price * shares + current_price * double_shares
    total_shares = shares + double_shares
    new_avg = total_cost / total_shares

    return {
        "recommend": trust["total_score"] >= 65,
        "action": "BUY_MORE" if trust["total_score"] >= 65 else "WAIT",
        "reason": f"Trust score {trust['total_score']} supports averaging. New average would be ${new_avg:.2f}.",
        "new_avg_if_added": round(new_avg, 2),
        "breakeven_change_pct": round(((new_avg - current_price) / current_price * 100), 1),
    }
