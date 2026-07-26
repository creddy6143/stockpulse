"""Rule of 40 — is this SaaS balancing growth and profit?

Score = revenue growth YoY % + FCF margin % (operating margin fallback).
Applies ONLY to software/SaaS-type businesses (from theme membership).
"""
from ._util import at


def compute_rule_of_40(ctx: dict) -> dict:
    meta = ctx["meta"] or {}
    s = ctx["statements"] or {}
    fund = ctx["fundamentals"] or {}

    if not meta.get("is_saas"):
        return {"status": "na", "label": "N/A — SaaS metric", "value": None,
                "applicability": "SaaS metric — doesn't apply to this business model.",
                "inputs_used": [], "caveats": []}

    # Revenue growth YoY (statements preferred, fundamentals fallback).
    rev_l, rev_p = at(s, "revenue", -1), at(s, "revenue", -2)
    growth = None
    if rev_l is not None and rev_p and rev_p > 0:
        growth = (rev_l - rev_p) / rev_p * 100
    elif fund.get("revenue_growth"):
        growth = float(fund["revenue_growth"]) * 100

    # FCF margin, fallback operating margin.
    fcf = fund.get("free_cashflow")
    margin = None
    margin_src = None
    if fcf and rev_l:
        margin = float(fcf) / rev_l * 100
        margin_src = "FCF margin"
    else:
        ebit = at(s, "ebit", -1)
        if ebit is not None and rev_l:
            margin = ebit / rev_l * 100
            margin_src = "Operating margin"

    if growth is None or margin is None:
        return {"status": "insufficient", "label": "Insufficient data", "value": None,
                "inputs_used": [], "applicability": None,
                "caveats": ["Missing revenue growth or margin data."]}

    score = growth + margin
    if score >= 40:
        verdict, label, color = "PASSES", f"{score:.0f} — PASSES", "emerald"
    elif score >= 30:
        verdict, label, color = "NEAR", f"{score:.0f} — NEAR", "amber"
    else:
        verdict, label, color = "BELOW", f"{score:.0f} — BELOW", "rose"

    inputs = [
        {"label": "Revenue growth", "value": f"{growth:.0f}%", "period": "YoY"},
        {"label": margin_src, "value": f"{margin:.0f}%", "period": "latest"},
        {"label": "Rule of 40 score", "value": round(score), "period": "computed"},
    ]
    caveats = [] if margin_src == "FCF margin" else \
        ["Used operating margin (free cash flow unavailable)."]
    return {"status": "ok", "value": round(score), "verdict": verdict, "label": label,
            "color": color, "inputs_used": inputs, "applicability": None, "caveats": caveats}
