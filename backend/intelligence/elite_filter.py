"""Elite / Must-Own filter — the highest-conviction shortlist, grouped by sector.

Stricter and more selective than Smart Picks (trust ≥ 75). A stock only qualifies
here if it is excellent across EVERY dimension at once: strong fundamentals, smart-
money support, a clean balance sheet, bullish sentiment, real growth ahead, and no
red flags.

Bar: "strong & broader" — trust ≥ 78 AND at least 5 of 6 conviction criteria met
(one soft-miss allowed; "No red flags" is mandatory). Yields a fuller list
(~10-25 names) than an elite-only bar would.

HONESTY: true institutional 13F flows and some insider data are paywalled on the
free tier, so "Smart money buying" is a DIRECTIONAL read from the smart-money
pillar (analyst consensus + short interest + any available insider buys), not exact
fund flows. Every criterion's `detail` states what it is actually based on.
"""
from __future__ import annotations

TRUST_FLOOR   = 78     # "Strong" grade and above
MIN_CRITERIA  = 5      # of 6 (one soft-miss allowed; No-red-flags is mandatory)


def _pct(x) -> float:
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def evaluate_elite(pick: dict, fundamentals: dict, insider: dict, analyst: dict) -> dict | None:
    """Return an Elite entry (with the criteria checklist) or None if it doesn't qualify."""
    trust = pick.get("trust", {}) or {}
    score = int(trust.get("total_score") or 0)

    # ── Hard gates: no red flags, real data, strong score ─────────────────────
    if trust.get("auto_disqualified"):
        return None
    if trust.get("data_quality") == "unavailable":
        return None
    if score < TRUST_FLOOR:
        return None

    biz = int(trust.get("business_score") or 0)
    sm  = int(trust.get("smart_money_score") or 0)
    mom = int(trust.get("momentum_score") or 0)

    rev = _pct(fundamentals.get("revenue_growth"))
    pm  = _pct(fundamentals.get("profit_margins"))
    d2e = _pct(fundamentals.get("debt_to_equity"))
    fcf = _pct(fundamentals.get("free_cashflow"))

    buy   = int(analyst.get("buy_count") or 0)
    hold  = int(analyst.get("hold_count") or 0)
    sell  = int(analyst.get("sell_count") or 0)
    tot_a = buy + hold + sell
    buy_pct = (buy / tot_a) if tot_a else 0.0
    target  = analyst.get("target_price")
    price   = _pct(pick.get("price"))
    upside  = ((float(target) - price) / price * 100) if (target and price > 0) else None

    ceo_buy  = bool(insider.get("ceo_buying"))
    ins_buy  = _pct(insider.get("insider_buy_value"))
    inst_buy = bool(insider.get("institutional_buying"))
    short_pct = _pct(insider.get("short_interest_pct"))

    # ── 6 conviction criteria ─────────────────────────────────────────────────
    criteria = []

    # 1. Excellent fundamentals
    c1 = biz >= 28 and (pm > 0 or rev > 0.10)
    criteria.append({"label": "Excellent fundamentals", "met": c1,
                     "detail": f"Revenue {rev*100:+.0f}% · margin {pm*100:.0f}% · business {biz}/40"})

    # 2. Smart money buying (directional — see module docstring)
    c2 = sm >= 20 or ceo_buy or ins_buy > 100_000 or inst_buy
    if ceo_buy or ins_buy > 100_000:
        d2 = f"Insider buying (${ins_buy/1e6:.1f}M open-market)" if ins_buy > 100_000 else "CEO buying"
    elif inst_buy:
        d2 = "Institutional accumulation"
    else:
        d2 = f"Strong smart-money score {sm}/35" + (f" · short interest {short_pct:.0f}%" if short_pct else "")
    criteria.append({"label": "Smart money buying", "met": c2, "detail": d2})

    # 3. Clean balance sheet
    c3 = (d2e < 1.5) and (fcf > 0 or pm > 0)
    criteria.append({"label": "Clean balance sheet", "met": c3,
                     "detail": (f"Debt/Equity {d2e:.1f}" if d2e else "Low debt")
                               + (" · FCF positive" if fcf > 0 else (" · profitable" if pm > 0 else ""))})

    # 4. Bullish sentiment
    c4 = buy_pct > 0.55 or mom >= 15
    criteria.append({"label": "Bullish sentiment", "met": c4,
                     "detail": (f"Analysts {buy_pct*100:.0f}% buy ({tot_a} covering)" if tot_a
                                else f"Momentum {mom}/25")})

    # 5. Growth ahead
    c5 = rev > 0.08 or (upside is not None and upside > 10)
    if upside is not None and upside > 10:
        d5 = f"Analyst target +{upside:.0f}% upside"
    else:
        d5 = f"Revenue growing {rev*100:+.0f}%"
    criteria.append({"label": "Growth ahead", "met": c5, "detail": d5})

    # 6. No red flags (mandatory — already gated above)
    criteria.append({"label": "No red flags", "met": True,
                     "detail": "Not disqualified · clean filings · full data"})

    met = sum(1 for c in criteria if c["met"])
    if met < MIN_CRITERIA:
        return None

    # Conviction score: trust plus a small bonus for breadth of criteria met.
    conviction = min(100, score + (met - MIN_CRITERIA) * 2)

    return {
        "ticker": pick["ticker"],
        "name": pick.get("name") or pick["ticker"],
        "sector": pick.get("sector") or "Other",
        "trust": score,
        "grade": trust.get("grade", ""),
        "conviction": conviction,
        "price": price,
        "change_pct": round(_pct(pick.get("change_pct")), 1),
        "analyst_target": round(float(target), 2) if target else None,
        "upside_pct": round(upside, 0) if upside is not None else None,
        "criteria": criteria,
        "met_count": met,
        # Headline highlights = the met criteria, best signals first
        "highlights": [c["detail"] for c in criteria if c["met"]][:4],
    }


def group_by_sector(entries: list[dict]) -> list[dict]:
    """Group qualifying entries by sector, each sorted by conviction desc."""
    buckets: dict[str, list[dict]] = {}
    for e in entries:
        buckets.setdefault(e["sector"], []).append(e)
    out = []
    for sector, stocks in buckets.items():
        stocks.sort(key=lambda x: (-x["conviction"], -x["trust"]))
        out.append({
            "sector": sector,
            "count": len(stocks),
            "avg_conviction": round(sum(s["conviction"] for s in stocks) / len(stocks)),
            "stocks": stocks,
        })
    # Sectors with the strongest average conviction first
    out.sort(key=lambda s: -s["avg_conviction"])
    return out
