"""Slow-signal portfolio classification with hysteresis engine.

Uses ONLY fundamental data (business_score + smart_money_score) and
auto_disqualified flags for classification.  No P&L, no price-based
momentum signals.  Hysteresis prevents rapid group flipping by requiring N
consecutive trading days with a consistent new signal before committing a
category change.
"""
from datetime import datetime


# ── Hysteresis delay table ────────────────────────────────────────────────────
# (current_stable_group, new_signal_group) → required trading days before apply
HYSTERESIS_DAYS: dict = {
    ("good",   "watch"):  3,   # 3 days before demoting a good stock
    ("good",   "urgent"): 1,   # immediate danger — fast escalation
    ("watch",  "urgent"): 2,   # 2 days before escalating to urgent
    ("watch",  "good"):   1,   # quick recovery: 1 day to promote
    ("urgent", "watch"):  5,   # slow to recover from urgent
    ("urgent", "good"):   5,   # slow to recover from urgent
}


def _fundamental_score(trust: dict):
    """Return business_score + smart_money_score, or None if either is missing.

    Excludes the momentum pillar (price vs MA200, price vs 52W high, news
    catalyst) because those inputs change every trading day and would cause
    rapid group flipping within a single session.

    Max value: 40 (business) + 35 (smart_money) = 75.
    """
    b = trust.get("business_score")
    s = trust.get("smart_money_score")
    if b is None or s is None:
        return None
    return int(b) + int(s)


def _classify_slow(trust: dict) -> tuple:
    """Classify using only slow-moving signals.

    Returns (group, trigger_signal):
      group          — "urgent" | "watch" | "good"
      trigger_signal — plain string describing the reason

    UI label mapping:
      urgent → Urgent
      watch  → Monitor
      good   → Stable

    Threshold mapping against 0-75 scale:
      < 30  (~40% of max)  → mirrors old total_score < 40 Blocked threshold
      30-44               → mirrors old total_score 40-59 Moderate/Weak
      >= 45 (~60% of max) → mirrors old total_score >= 60 Strong threshold
    """
    auto_disq    = trust.get("auto_disqualified", False)
    data_quality = trust.get("data_quality", "full")
    fscore       = _fundamental_score(trust)

    # Auto-disqualified always → urgent (objective categorical fact)
    if auto_disq:
        return "urgent", "auto_disqualifier"

    # Missing either pillar → insufficient data → Watch (never Urgent)
    if fscore is None:
        return "watch", "insufficient_data"

    # Data quality gate: only escalate to Urgent when we have full confidence.
    # Catches SBIN / international stocks with zero analyst coverage that would
    # otherwise produce a synthetically low smart_money score → false Urgent.
    if data_quality != "full" and fscore < 45:
        return "watch", "limited_data_moderate_score"

    # Full data path — strict thresholds
    if fscore < 30:
        return "urgent", "low_fundamental_score"

    if fscore < 45:
        return "watch", "moderate_fundamental_score"

    return "good", "strong_fundamentals"


def trading_days_elapsed(since: datetime) -> float:
    """Count weekday (Mon-Fri) trading days from `since` to now (UTC).

    Uses numpy.busday_count when available; falls back to calendar-day
    estimate if numpy is not installed.

    Returns 0.0 if `since` is today or in the future.
    """
    now = datetime.utcnow()
    if since.date() >= now.date():
        return 0.0
    try:
        import numpy as np
        count = int(np.busday_count(since.date(), now.date()))
        return max(0.0, float(count))
    except ImportError:
        # Rough estimate: calendar days ÷ 1.4  ≈  trading days
        delta = (now - since).total_seconds() / 86400
        return max(0.0, delta / 1.4)


def classify_with_hysteresis(ticker: str, user_id: str, trust: dict) -> str:
    """Classify a portfolio stock's group with hysteresis protection.

    Algorithm:
      1. Compute new_group from slow-signals only (_classify_slow).
      2. Load last committed ("stable") classification from DB.
      3. No history → bootstrap with new_group immediately.
      4. Unchanged → clear any stale pending state, return stable.
      5. Changed → start or advance a pending timer.
         Commit only when required trading days have elapsed.

    Returns: "urgent" | "watch" | "good"
    """
    from database.db import (
        get_classification_state,
        set_pending_classification,
        clear_pending_classification,
        update_stable_classification,
        log_classification_change,
    )

    new_group, trigger = _classify_slow(trust)
    state = get_classification_state(ticker, user_id)

    # ── First time ──────────────────────────────────────────────────────────
    if state is None:
        update_stable_classification(ticker, user_id, new_group)
        return new_group

    stable_group  = state["stable_group"]
    pending_group = state.get("pending_group")
    pending_since_raw = state.get("pending_since")

    # ── No change ───────────────────────────────────────────────────────────
    if new_group == stable_group:
        if pending_group is not None:
            clear_pending_classification(ticker, user_id)
        return stable_group

    # ── Change detected — apply hysteresis ──────────────────────────────────
    required_days = HYSTERESIS_DAYS.get((stable_group, new_group), 3)

    if pending_group != new_group:
        # New direction — start (or restart) the timer
        set_pending_classification(ticker, user_id, new_group, datetime.utcnow())
        return stable_group  # not yet committed

    # Continuing in same pending direction — measure elapsed trading days
    if pending_since_raw:
        if isinstance(pending_since_raw, str):
            try:
                pending_since = datetime.fromisoformat(pending_since_raw)
            except Exception:
                pending_since = datetime.utcnow()
        else:
            pending_since = pending_since_raw
        elapsed = trading_days_elapsed(pending_since)
    else:
        elapsed = 0.0

    if elapsed >= required_days:
        # Cooling-off period complete — promote pending → stable
        log_classification_change(
            ticker, user_id,
            old_group=stable_group,
            new_group=new_group,
            trigger=trigger,
            days_req=float(required_days),
            days_elapsed=elapsed,
        )
        update_stable_classification(ticker, user_id, new_group)
        return new_group

    # Still in cooling-off period — hold current stable group
    return stable_group
