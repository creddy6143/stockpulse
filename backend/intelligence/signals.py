"""Signal quality gates — filters patterns before firing an alert."""
from .patterns import detect_all_patterns
from .trust_score import get_trust_score_with_fallback
from database.db import save_signal, create_alert


def evaluate_and_fire_signals(ticker: str, price_data: dict,
                               fundamentals: dict = None,
                               insider_data: dict = None) -> list:
    """
    Runs patterns against quality gates:
      - Trust score < 40 blocks all bullish signals
      - Auto-disqualified blocks all signals
    Returns list of signals that passed the gate.
    """
    trust = get_trust_score_with_fallback(ticker, price_data)

    if trust["auto_disqualified"]:
        # Fire EXIT alert
        create_alert(ticker, "urgent",
                     f"Auto-disqualified: {trust['disqualify_reason']} — exit now")
        return []

    patterns = detect_all_patterns(
        ticker, trust["total_score"], price_data, fundamentals, insider_data
    )

    fired = []
    for p in patterns:
        # Gate: no bullish signals if trust < 40
        if trust["total_score"] < 40 and p["recommendation"] in ("buy", "strong_buy"):
            continue

        sig_id = save_signal(
            ticker=ticker,
            pattern=p["pattern"],
            confidence=p["confidence"],
            plain_english=p["plain_english"],
            recommendation=p["recommendation"],
            stop_loss_pct=p.get("stop_loss_pct"),
            time_horizon_days=p.get("time_horizon_days"),
        )

        alert_type = "signal"
        conf = p["confidence"]
        level = "HIGH" if conf >= 0.70 else "MED-HIGH" if conf >= 0.60 else "MEDIUM"
        create_alert(ticker, alert_type,
                     f"{level}: {p['plain_english']}")

        fired.append({**p, "signal_id": sig_id, "ticker": ticker,
                      "trust_score": trust["total_score"]})

    return fired
