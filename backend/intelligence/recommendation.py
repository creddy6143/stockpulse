"""Single source of truth for every recommendation / category / health badge.

THE CONTRACT
------------
Every UI surface that shows a recommendation (SELL/HOLD/BUY), a portfolio
category (Urgent/Monitor/Stable), a Strategy health badge (On Track / Holding
Well / Review Position), or an alert MUST derive that verdict from
`get_recommendation_state()`.  No surface may compute its own verdict.

If two screens can disagree about the same stock at the same moment, the
architecture is broken — not the display.  This module exists so they cannot.

PRINCIPLES (from the product spec)
----------------------------------
1. Single source of truth — one function, one verdict.
2. P&L is DISPLAY information, never a verdict input.  "Up 14%" does not mean
   "holding well" when the quality signals say otherwise.
3. Recommendation confidence can never exceed score confidence.  A suppressed
   ("Review") score can never produce a confident directional call, and can
   never produce an "Urgent" category.  Missing data → "unknown", never "bad".
4. Auto-disqualified is an objective categorical fact and always wins → SELL.

INPUTS (a portfolio-position or watchlist trust dict)
-----------------------------------------------------
    auto_disqualified : bool
    verification      : {"suppressed": bool, ...}   (may be absent)
    display_score     : int | None   (None ⇒ suppressed)
    trust_score       : int | None
    group             : "urgent" | "watch" | "good"  (from classification)
    grade             : str
    data_quality      : "full" | "limited" | "unavailable"

`pnl_pct` and `change_pct` are intentionally NOT read here.  They are display
facts, handed to the UI separately.
"""


# ── Canonical states ──────────────────────────────────────────────────────────
# REC        : the directional call shown on My Stocks / everywhere
# CATEGORY   : portfolio bucket  urgent → Urgent, watch → Monitor, good → Stable
# HEALTH     : Strategy holdings badge
SELL, HOLD, BUY, REVIEW, NODATA = "SELL", "HOLD", "BUY", "Review", "—"

_REC_CLASS = {
    "SELL": "rr-s",
    "HOLD": "rr-h",
    "BUY":  "rr-b",
    "Review": "rr-h",
    "—":    "rr-h",
}

# Strategy health-badge mapping — never contradicts REC.
# A SELL-class / suppressed / avoid stock can NEVER read "On Track" or
# "Holding Well", regardless of P&L.
_HEALTH = {
    "SELL":   "Review Position",
    "Review": "Review",
    "—":      "Review",
    "HOLD":   "Monitoring",
    "BUY":    "On Track",
}


def _is_suppressed(stock: dict) -> bool:
    """True when verification suppressed the score → 'Review'.

    Auto-disqualified stocks are an objective SELL, not a suppression, so they
    are excluded here.
    """
    if stock.get("auto_disqualified"):
        return False
    verif = stock.get("verification") or {}
    if verif.get("suppressed"):
        return True
    # display_score is explicitly None only when the score was suppressed.
    if "display_score" in stock and stock.get("display_score") is None:
        return True
    return False


def _is_no_data(stock: dict) -> bool:
    return (
        stock.get("grade") == "Data Unavailable"
        or stock.get("data_quality") == "unavailable"
    )


def get_recommendation_state(stock: dict) -> dict:
    """Return the canonical verdict for a stock.  The ONLY verdict function.

    Returns::

        {
          "rec":            "SELL"|"HOLD"|"BUY"|"Review"|"—",
          "rec_class":      "rr-s"|"rr-h"|"rr-b",
          "category":       "urgent"|"watch"|"good",   # suppression-aware
          "category_label": "Urgent"|"Monitor"|"Stable",
          "health_label":   "Review Position"|"Monitoring"|"On Track"|"Review",
          "suppressed":     bool,
          "no_data":        bool,
          "reason":         str,   # plain-English, why this verdict
        }
    """
    auto_disq = bool(stock.get("auto_disqualified"))
    suppressed = _is_suppressed(stock)
    no_data = _is_no_data(stock)
    group = stock.get("group") or "watch"
    trust = stock.get("trust_score")

    # ── 1. Auto-disqualified — objective fact, always SELL / Urgent ───────────
    if auto_disq:
        rec, category, reason = SELL, "urgent", (
            stock.get("disqualify_reason") or "Auto-disqualified — exit."
        )

    # ── 2. No fundamental data — unknown, never bad ───────────────────────────
    elif no_data:
        rec, category, reason = NODATA, "watch", (
            "No fundamental data available for this exchange — price tracking only."
        )

    # ── 3. Suppressed score — Review.  Confidence can't exceed the score, so
    #        no directional call and NEVER an Urgent category. ────────────────
    elif suppressed:
        rec, category, reason = REVIEW, "watch", (
            "Score under review — insufficient confidence for a directional call."
        )

    # ── 4. Confident path — derive from the fundamental classification ────────
    else:
        if group == "urgent":
            rec = SELL
        elif group == "watch":
            rec = HOLD
        elif group == "good" and trust is not None and trust >= 75:
            rec = BUY
        else:
            rec = HOLD
        category = group
        reason = {
            "urgent": "Weak fundamentals — review before holding further.",
            "watch":  "Moderate fundamentals — monitor.",
            "good":   "Strong fundamentals.",
        }.get(group, "Monitoring.")

    category_label = {"urgent": "Urgent", "watch": "Monitor", "good": "Stable"}[category]

    return {
        "rec": rec,
        "rec_class": _REC_CLASS[rec],
        "category": category,
        "category_label": category_label,
        "health_label": _HEALTH[rec],
        "suppressed": suppressed,
        "no_data": no_data,
        "reason": reason,
    }
