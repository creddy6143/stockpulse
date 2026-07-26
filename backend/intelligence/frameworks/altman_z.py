"""Altman Z-Score — is there balance-sheet survival risk?

Z = 1.2·(WC/TA) + 1.4·(RE/TA) + 3.3·(EBIT/TA) + 0.6·(MktCap/TL) + 1.0·(Rev/TA)
NOT valid for financial companies (banks/insurers) → N/A.
"""
from ._util import at


def compute_altman_z(ctx: dict) -> dict:
    meta = ctx["meta"] or {}
    s = ctx["statements"] or {}
    fund = ctx["fundamentals"] or {}

    if meta.get("is_financial"):
        return {"status": "na", "label": "N/A — financials", "value": None,
                "applicability": "Z-Score isn't designed for financial companies "
                                 "(banks/insurers).",
                "inputs_used": [], "caveats": []}

    ca = at(s, "current_assets", -1)
    cl = at(s, "current_liabilities", -1)
    re = at(s, "retained_earnings", -1)
    ebit = at(s, "ebit", -1)
    ta = at(s, "total_assets", -1)
    tl = at(s, "total_liabilities", -1)
    rev = at(s, "revenue", -1)
    mc = fund.get("market_cap")

    if None in (ca, cl, re, ebit, rev) or not ta or not tl or not mc:
        return {"status": "insufficient", "label": "Insufficient data", "value": None,
                "inputs_used": [], "applicability": None,
                "caveats": ["Missing balance-sheet lines needed for the Z-Score."]}

    wc = ca - cl
    z = (1.2 * (wc / ta) + 1.4 * (re / ta) + 3.3 * (ebit / ta)
         + 0.6 * (float(mc) / tl) + 1.0 * (rev / ta))

    if z > 2.99:
        verdict, label, color = "SAFE", f"{z:.1f} — SAFE", "emerald"
    elif z >= 1.81:
        verdict, label, color = "GREY", f"{z:.1f} — GREY ZONE", "amber"
    else:
        verdict, label, color = "DISTRESS", f"{z:.1f} — DISTRESS RISK", "rose"

    caveats = []
    if rev <= 0 or (ta and rev < abs(ta) * 0.02):
        caveats.append("Early-stage — Z-Score skews harsh for pre-revenue / pre-profit "
                       "companies.")

    inputs = [
        {"label": "Working capital / Assets", "value": f"{wc/ta:.2f}", "period": "×1.2"},
        {"label": "Retained earnings / Assets", "value": f"{re/ta:.2f}", "period": "×1.4"},
        {"label": "EBIT / Assets", "value": f"{ebit/ta:.2f}", "period": "×3.3"},
        {"label": "Market cap / Liabilities", "value": f"{float(mc)/tl:.2f}", "period": "×0.6"},
        {"label": "Revenue / Assets", "value": f"{rev/ta:.2f}", "period": "×1.0"},
        {"label": "Z-Score", "value": round(z, 2), "period": "computed"},
    ]
    return {"status": "ok", "value": round(z, 2), "verdict": verdict, "label": label,
            "color": color, "inputs_used": inputs, "applicability": None, "caveats": caveats}
