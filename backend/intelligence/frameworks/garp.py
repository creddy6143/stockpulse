"""GARP (Growth At a Reasonable Price) — PEG ratio.

Question: is this growth already paid for?
PEG = P/E ÷ EPS growth rate (%). Prefer forward P/E + forward EPS growth;
fall back to trailing P/E + trailing EPS CAGR.
"""
from ._util import at


def compute_garp(ctx: dict) -> dict:
    fund = ctx["fundamentals"] or {}
    meta = ctx["meta"] or {}
    s = ctx["statements"] or {}

    pe = fund.get("forward_pe") or fund.get("pe_ratio")
    pe_src = "Forward P/E" if fund.get("forward_pe") else "Trailing P/E"

    # EPS series (net income ÷ shares), period-aligned.
    periods = s.get("periods") or []
    ni = s.get("net_income") or []
    sh = s.get("shares_outstanding") or []
    eps_series = []
    for i in range(len(periods)):
        n = ni[i] if i < len(ni) else None
        q = sh[i] if i < len(sh) else None
        eps_series.append((n / q) if (n is not None and q) else None)
    eps_vals = [(i, e) for i, e in enumerate(eps_series) if e is not None]
    eps_latest = eps_vals[-1][1] if eps_vals else None

    # Growth rate. Prefer the analyst FORWARD EPS growth (forward vs trailing EPS,
    # both from Yahoo so they're on a consistent scale) — this is the growth GARP
    # is really about, and it captures companies whose trailing EPS is flat on the
    # endpoints but are expected to grow (e.g. LMT: trailing ~flat, forward +20%).
    # Fall back to the self-consistent trailing EPS CAGR from the statements.
    growth = None
    growth_src = None
    fwd_eps = fund.get("forward_eps")
    trail_eps = fund.get("trailing_eps")
    if fwd_eps and trail_eps and trail_eps > 0:
        g = (float(fwd_eps) / float(trail_eps) - 1) * 100
        if g > 0:
            growth, growth_src = g, "Forward EPS growth (analyst est.)"
    if growth is None and len(eps_vals) >= 2 and eps_vals[0][1] and eps_vals[0][1] > 0 \
            and eps_latest and eps_latest > 0:
        e_old = eps_vals[0][1]
        span = eps_vals[-1][0] - eps_vals[0][0]
        if span > 0:
            growth = ((eps_latest / e_old) ** (1.0 / span) - 1) * 100
            growth_src = f"Trailing {span}yr EPS CAGR"

    # PEG needs a positive P/E to even form the ratio.
    if pe is None or pe <= 0:
        return {"status": "na", "label": "N/A — no positive P/E", "value": None,
                "applicability": "No positive P/E available — a PEG ratio can't be formed.",
                "inputs_used": [], "caveats": []}

    # Negative latest earnings — PEG can't apply. But WHY it's loss-making matters:
    # a large cyclical company at a down-cycle trough is NOT "pre-profit" the way an
    # early-stage startup is. Pick the honest label dynamically from the company's own
    # data — revenue scale + whether it was ever profitable + the cyclical flag — so
    # this stays correct for any ticker without hard-coding names.
    if eps_latest is not None and eps_latest <= 0:
        rev_latest = at(s, "revenue", -1)
        if rev_latest is None:
            rev_latest = fund.get("revenue")
        try:
            rev_latest = float(rev_latest) if rev_latest is not None else None
        except (TypeError, ValueError):
            rev_latest = None
        ever_profitable = any(e is not None and e > 0 for e in eps_series)
        # "Established" = real scale (≥ $1B revenue) or a track record of past profits.
        established = (rev_latest is not None and rev_latest >= 1e9) or ever_profitable

        if established and meta.get("is_cyclical"):
            label = "N/A — unprofitable (cyclical trough)"
            appl = ("Loss-making at a low point in its industry cycle, not an "
                    "early-stage company — PEG needs positive earnings, so it "
                    "doesn't apply right now. Revisit as the cycle turns.")
        elif established:
            label = "N/A — currently unprofitable"
            appl = ("An established business (meaningful revenue or past profits) "
                    "that is currently loss-making — PEG needs positive earnings "
                    "to apply.")
        else:
            label = "N/A — pre-profit"
            appl = "Pre-profit — GARP doesn't apply without positive earnings."
        return {"status": "na", "label": label, "value": None,
                "applicability": appl, "inputs_used": [], "caveats": []}
    if growth is None or growth <= 0:
        return {"status": "na", "label": "N/A — not growing", "value": None,
                "applicability": "Earnings not growing — PEG isn't meaningful.",
                "inputs_used": [], "caveats": []}

    g = min(growth, 50.0)   # cap runaway growth for the math
    peg = pe / g

    if peg <= 1.0:
        verdict, label, color = "STRONG", "GARP STRONG — growth is cheap", "emerald"
    elif peg <= 1.5:
        verdict, label, color = "OK", "GARP OK — reasonable price", "indigo"
    elif peg <= 2.0:
        verdict, label, color = "STRETCHED", "Stretched", "amber"
    else:
        verdict, label, color = "EXPENSIVE", "Expensive — paying up", "rose"

    caveats = []
    if growth > 50:
        caveats.append("Growth capped at 50% for the PEG math.")
    if meta.get("is_cyclical"):
        caveats.append("⚠️ PEG unreliable at cycle extremes — peak earnings make "
                       "cyclicals look deceptively cheap.")

    inputs = [
        {"label": pe_src, "value": round(pe, 1), "period": "current"},
        {"label": growth_src, "value": f"{growth:.0f}%", "period": "est."},
        {"label": "PEG ratio", "value": round(peg, 2), "period": "computed"},
    ]
    return {"status": "ok", "value": round(peg, 2), "verdict": verdict, "label": label,
            "color": color, "inputs_used": inputs, "applicability": None, "caveats": caveats}
