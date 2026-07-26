"""Piotroski F-Score (0–9) — is the business getting healthier?

One point per TRUE check, latest fiscal year vs prior. The 9-check breakdown IS
the value. Requires 2 full fiscal years.
"""
from ._util import n_periods, at, safe_div


def compute_piotroski(ctx: dict) -> dict:
    s = ctx["statements"] or {}
    meta = ctx["meta"] or {}

    if n_periods(s) < 2:
        return {"status": "insufficient", "label": "Insufficient history", "value": None,
                "applicability": None, "inputs_used": [],
                "caveats": ["Needs 2 full fiscal years of statements."]}

    # Latest (-1) vs prior (-2), period-aligned.
    ni_l, ni_p = at(s, "net_income", -1), at(s, "net_income", -2)
    ta_l, ta_p = at(s, "total_assets", -1), at(s, "total_assets", -2)
    ocf_l = at(s, "operating_cash_flow", -1)
    ltd_l, ltd_p = at(s, "long_term_debt", -1), at(s, "long_term_debt", -2)
    ca_l, ca_p = at(s, "current_assets", -1), at(s, "current_assets", -2)
    cl_l, cl_p = at(s, "current_liabilities", -1), at(s, "current_liabilities", -2)
    sh_l, sh_p = at(s, "shares_outstanding", -1), at(s, "shares_outstanding", -2)
    gp_l, gp_p = at(s, "gross_profit", -1), at(s, "gross_profit", -2)
    rev_l, rev_p = at(s, "revenue", -1), at(s, "revenue", -2)

    roa_l, roa_p = safe_div(ni_l, ta_l), safe_div(ni_p, ta_p)
    cr_l, cr_p = safe_div(ca_l, cl_l), safe_div(ca_p, cl_p)
    lev_l, lev_p = safe_div(ltd_l, ta_l), safe_div(ltd_p, ta_p)
    gm_l, gm_p = safe_div(gp_l, rev_l), safe_div(gp_p, rev_p)
    to_l, to_p = safe_div(rev_l, ta_l), safe_div(rev_p, ta_p)

    def cmp(a, b, op):
        if a is None or b is None:
            return None
        return op(a, b)

    checks = [
        {"n": 1, "group": "Profitability", "label": "ROA positive",
         "met": (roa_l > 0) if roa_l is not None else None},
        {"n": 2, "group": "Profitability", "label": "Operating cash flow positive",
         "met": (ocf_l > 0) if ocf_l is not None else None},
        {"n": 3, "group": "Profitability", "label": "ROA improved vs prior year",
         "met": cmp(roa_l, roa_p, lambda a, b: a > b)},
        {"n": 4, "group": "Profitability", "label": "Cash flow > net income (earnings quality)",
         "met": cmp(ocf_l, ni_l, lambda a, b: a > b)},
        {"n": 5, "group": "Leverage & liquidity", "label": "Long-term debt ratio decreased",
         "met": cmp(lev_l, lev_p, lambda a, b: a < b)},
        {"n": 6, "group": "Leverage & liquidity", "label": "Current ratio improved",
         "met": cmp(cr_l, cr_p, lambda a, b: a > b)},
        {"n": 7, "group": "Leverage & liquidity", "label": "No dilution (shares not up >2%)",
         "met": (sh_l <= sh_p * 1.02) if (sh_l is not None and sh_p) else None},
        {"n": 8, "group": "Efficiency", "label": "Gross margin improved",
         "met": cmp(gm_l, gm_p, lambda a, b: a > b)},
        {"n": 9, "group": "Efficiency", "label": "Asset turnover improved",
         "met": cmp(to_l, to_p, lambda a, b: a > b)},
    ]

    evaluable = [c for c in checks if c["met"] is not None]
    if len(evaluable) < 5:
        return {"status": "insufficient", "label": "Insufficient data", "value": None,
                "checks": checks, "inputs_used": [], "applicability": None,
                "caveats": ["Too many statement lines missing to score reliably."]}

    score = sum(1 for c in checks if c["met"] is True)
    unknown = sum(1 for c in checks if c["met"] is None)

    if score >= 8:
        verdict, label, color = "STRONG", f"{score}/9 STRONG", "emerald"
    elif score >= 6:
        verdict, label, color = "SOLID", f"{score}/9 SOLID", "indigo"
    elif score >= 4:
        verdict, label, color = "MIXED", f"{score}/9 MIXED", "amber"
    else:
        verdict, label, color = "WEAK", f"{score}/9 WEAK", "rose"

    caveats = []
    if unknown:
        caveats.append(f"{unknown} of 9 checks couldn't be evaluated (missing lines) "
                       f"— counted as not-passed.")
    if meta.get("is_financial"):
        caveats.append("Interpret with care for financials — current-ratio and leverage "
                       "checks are less meaningful for banks/insurers.")

    return {"status": "ok", "value": score, "verdict": verdict, "label": label, "color": color,
            "checks": checks, "inputs_used": [], "applicability": None, "caveats": caveats}
