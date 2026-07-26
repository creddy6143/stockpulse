# Number Consistency — Single Source of Truth

## The Rule

Every numerical fact that appears more than once on the same screen must come
from **one shared variable** computed once per page load. If two UI elements
show the same data point (price, % change, score, etc.) they must reference
the same value, not independently fetch or compute it.

Internal contradictions — where the header says -3.9% and the commentary says
-2.4% for the same stock at the same moment — destroy credibility faster than
any other class of bug.

---

## Label must match the number beside it

A **label and the number next to it can never contradict.** The word describing a data
point must agree in direction with the figure shown.

### Dip label / number rule

The word "dip" implies a *decline*. It must sit next to the **qualifying multi-day drop**
(`dip_pct` / `dip_window`, e.g. "−6.2% / 1w"), never next to today's daily `change_pct`.

| Bug | Wrong | Right |
|-----|-------|-------|
| RR.L +1.0% today, qualified on −6% weekly slide | "+1.0% dip" (green % beside "dip") | "−6.2% / 1w" |

Rules:
1. If a dip qualified on a multi-day window, show **that window's** number beside the dip
   tag. Never a green positive daily % next to the word "dip".
2. If a dip was daily-based and today is positive, the dip tag is removed.
3. Every DIP-tagged row: the label and its adjacent number must never contradict.

Enforced by exposing `dip_pct` / `dip_window` from `evaluate_dip_candidate`
(`dip_filter.py`) and rendering those — not `change_pct` — beside the "DIP" badge in
`mapPick` and the Dip Buys tab. Today's daily % may still appear, but only on the
clearly-labelled live price line, never as the dip figure.

---

## Known Failure Patterns (Historical)

| Bug | Root Cause | Fixed in |
|-----|-----------|----------|
| Recommendation badge contradicting suppressed score | Display score vs raw score used in two different places | verification.py |
| "Choppy" header pill contradicting calm VIX card | VIX fetched twice via different cache layers | market_cache |
| Picks daily % contradicting live % | Stale scan-cache `change_pct` vs live price in header | dip_filter.py |
| Portfolio categories flipping within a session | `pnl_pct` and `momentum_score` used in classification | classification.py |
| AI commentary % contradicting header % | Verdict cached 2hr with stale `change_pct` baked in; live header fetches fresh | claude_ai.py |
| Smart Picks row % contradicting expanded verdict text % | Row gets live price overlay every 90s; verdict prose was baked at scan time (hours ago) | main.py `_apply_live` |

---

## AI Verdict — Change % Consistency

### The problem

`get_verdict()` passes `change_pct` from `price_data` to the LLM prompt:
```
Change Today: -2.4%
```
Claude's prose output says: "WELL is down about 2.4% today."
This response is cached for **2 hours**.

The header fetches a fresh price every **60 seconds**.
After an hour, header shows -3.9% while commentary still says -2.4%.

### The fix (claude_ai.py)

```python
# On every verdict request, compare live change_pct with the value
# that was baked into the cached prose.
live_chg = float(price_data.get("change_pct") or 0)
cached_chg = _cached.get("_change_pct_at_generation")

# Tolerate up to 0.5pp drift (normal micro-movement).
# Beyond 0.5pp the prose is factually wrong vs the header — regenerate.
if cached_chg is None or abs(live_chg - float(cached_chg)) <= 0.5:
    return _cached   # still consistent
# else: fall through and regenerate with current data
```

Every cached verdict now includes:
- `_change_pct_at_generation` — the live change_pct when Claude was called
- `_generated_at` — UTC ISO timestamp of generation

### The frontend timestamp

The StockDetail component renders "AI analysis updated N min ago" using
`verdict._generated_at`. This makes staleness explicit instead of invisible.

---

## Rules for Adding New Commentary Features

1. **Never let the LLM choose its own numbers.** Any numerical fact mentioned
   in AI-generated text must be passed explicitly in the prompt, taken from
   the same source the UI uses for that same number.

2. **Tag every cached AI text with the data snapshot it was generated from.**
   At minimum: the most volatile input (change_pct, trust_score). Store this
   alongside the cached text, not just inside the prose.

3. **Invalidate the cache when the tagged input drifts beyond tolerance.**
   For prices: 0.5 percentage point tolerance.
   For trust scores: 5 point tolerance.
   For fundamental data (revenue, margins): quarterly update is fine — no
   intraday drift check needed.

4. **Always return `_generated_at` to the frontend.**
   The user should always be able to see how fresh an AI analysis is. If the
   component shows AI text, it must also show an "updated N min ago" timestamp.

5. **Audit before shipping any new expanded-view component:**
   - List every number shown in the UI
   - List every number mentioned in generated text
   - Confirm they trace to the same source variable
   - If they can drift independently, add a drift check

---

## Audit Checklist for Expanded Views

For each stock detail / expanded panel, verify:

| Data point | UI source | Commentary source | Same? |
|-----------|-----------|------------------|-------|
| Daily % change | `price_data.change_pct` (60s cache) | Passed as `Change Today` in prompt | ✅ after fix |
| Current price | `price_data.price` (60s cache) | Passed as `Current Price` in prompt | ✅ same fetch |
| Revenue growth | `fundamentals.revenue_growth` | Passed in prompt | ✅ quarterly data, no intraday risk |
| Trust score | `trust.total_score` | Passed in prompt | ✅ same call |
| Earnings surprise | `fundamentals.earnings_surprise_pct` | Passed in prompt | ✅ quarterly data |
| Analyst target | `analyst.target_price` | Not in verdict prompt | ✅ shown separately, not in prose |
| Entry zone | `zone.zone_str` | Not in verdict prompt | ✅ shown separately, not in prose |

All high-volatility inputs (price, change_pct) are passed from the same
`price_data` dict that the header uses. The drift check ensures cached prose
is invalidated when these drift beyond tolerance.
