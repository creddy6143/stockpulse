# Recommendation Engine — Single Source of Truth

## The Rule

Every UI surface that shows a "Ready to Buy" / "Watching" / "Don't Buy" badge for a
watchlist or smart-picks stock **must derive that label from the same threshold**.
Internal contradictions — where Strategy tab says "Ready to Buy" and Stocks screen says
"Watching" for the same stock at the same moment — destroy trust faster than any other
class of bug.

---

## THE canonical verdict function — `get_recommendation_state()`

> `backend/intelligence/recommendation.py`

Portfolio holdings have ONE verdict function. Every badge that describes an **owned**
stock — the My Stocks REC pill, the My Stocks category (Urgent/Monitor/Stable), the
Strategy holdings health badge, and holding alerts — derives from
`get_recommendation_state(stock)`. No surface computes its own verdict from P&L, group,
or score. If two screens can disagree, the wiring is broken.

### Inputs it reads (and only these)

`auto_disqualified`, `verification.suppressed` / `display_score`, `group`
(from classification), `trust_score`, `grade`, `data_quality`.
**It never reads `pnl_pct` or `change_pct`** — P&L is display information, never a verdict.

### Decision order

```
1. auto_disqualified              → SELL · Urgent · "Review Position"
2. no fundamental data            → "—"  · Monitor(neutral) · "Review"
3. verification suppressed        → Review · Monitor(neutral) · "Review"   (never Urgent)
4. group=urgent (confident)       → SELL · Urgent · "Review Position"
5. group=watch                    → HOLD · Monitor · "Monitoring"
6. group=good & trust≥75          → BUY  · Stable · "On Track"
7. else                           → HOLD · Monitor · "Monitoring"
```

### Badge-mapping table

| canonical `rec` | My Stocks pill | `rec_class` | category (`group`) | Strategy `health_label` |
|-----------------|----------------|-------------|--------------------|-------------------------|
| SELL            | SELL           | rr-s        | Urgent             | Review Position         |
| HOLD            | HOLD           | rr-h        | Monitor            | Monitoring              |
| BUY             | BUY            | rr-b        | Stable             | On Track                |
| Review          | Review         | rr-h        | Monitor (neutral)  | Review                  |
| —               | Review         | rr-h        | Monitor (neutral)  | Review                  |

Two invariants enforced by construction:
- **A SELL-class or suppressed stock can NEVER read "Holding Well" / "On Track"**,
  regardless of P&L. (Fixes: LMT "SELL/Urgent on My Stocks" vs "Holding Well on Strategy".)
- **A suppressed ("Review") score can NEVER produce an Urgent category** — recommendation
  confidence can't exceed score confidence. (Fixes: UNH "Review" score + "Urgent" category.)

### Wiring map — who consumes the canonical state

| Surface | File | How it consumes |
|---------|------|-----------------|
| My Stocks REC pill | `tracker.py _build_position` → `pos.rec` / `pos.rec_class`; rendered by `App.jsx mapPosition` | reads `pos.rec` (falls back to legacy `getRecFromGroup` only if the API field is absent) |
| My Stocks category | `classification.py classify_with_hysteresis` → `pos.group` → section bucket | classifier is now suppression-aware (suppressed → `watch`, never `urgent`) |
| Strategy holdings badge | `main.py _detect_situation` | calls `get_recommendation_state(pos)`; label = `health_label`, action from `rec`; P&L is summary text only |
| Holding alerts | `tracker.py get_portfolio_with_pnl` | fire only on `auto_disqualified` (objective) — never on a suppressed score |
| Watchlist / Smart Picks badges | `wl_group` / `smart_picks_strat` (≥75 threshold, below) | separate entry-threshold path — see next section |

> **Note:** Watchlist and Smart Picks describe stocks the user does **not** own, so they use
> the entry-threshold path (≥75) documented below rather than the holdings verdict function.
> The two paths share the same safety overrides (auto_disq, no-data). The −8% daily-drop
> override for entry candidates is documented in the Safety Overrides section.

---

## Entry zone (price fact) vs Recommendation (score threshold)

These are **different things** and must never be shown as contradictory verdicts:

| | What it is | Source |
|---|---|---|
| **Entry zone status** (`signal`) | A **price-level fact**: is the current price inside the computed entry band? True/false regardless of score. | `portfolio/entry_zone.py` → `zone_status_label` |
| **Recommendation** (`wl_group`) | A **full verdict**: "Ready to Buy" = price in zone **AND** score ≥ 75 **AND** not blocked. | `tracker.py` + `verify_watchlist_signal()` |

A stock can legitimately be **in the price zone but score < 75** → it is *not* "ready". In
that case the two must speak the same language, never "✓ In entry zone now" beside "wait":

- The **single choke point** is `verify_watchlist_signal()` (every watchlist item passes
  through it). Invariant it enforces (rule **W5**): *an "in entry zone now" GO signal may
  appear ONLY with a `wl_group == "ready"`.* Otherwise the signal is reconciled to the
  combined truth: **`"Price in zone · score X below 75 — wait"`**.
- `main.py _detect_wl_situation()` (the Strategy compact-list summary) **derives its wording
  from the reconciled `signal`**, so the compact list and the detail table always agree.
- `intelligence/verification.py assert_watchlist_consistent()` + `test_watchlist_consistency.py`
  fail CI if any path emits a GO signal with a non-ready group.

> **Regression history:** this contradiction has bitten twice (RKLB/LMT holdings → Item 13;
> then CLSK/EQIX/HUT.TO watchlist). Root cause both times: a component rendered a verdict from
> a *parallel* field instead of the shared reconciled state. Any new surface that shows a
> buy/wait/ready verdict MUST consume the reconciled `signal`/`wl_group` (watchlist) or
> `get_recommendation_state()` (holdings) — never recompute its own.

### Components that render a watchlist verdict (all consume the shared state)

| Component | Field consumed | Path |
|---|---|---|
| Stocks → Watchlist detail (`CompactWatchRow`) | `signal` (reconciled) | `verify_watchlist_signal()` |
| Strategy → Watchlist compact list (`_detect_wl_situation`) | derived from `signal` + `wl_group` | `verify_watchlist_signal()` |
| Expanded watchlist row (`WatchRow`) | `signal`, `zone_reason` | `verify_watchlist_signal()` |

Verdict systems in the app: **holdings** → `get_recommendation_state()`; **watchlist** →
`verify_watchlist_signal()`; **dip buys** → `dip_rec` (separate, dip-candidate context).
Frameworks and Pulse are **research lenses only** — they emit no buy/sell/ready verdict.

---

## The One Threshold

```
Entry threshold: trust score ≥ 75  (grade "Strong" or "Exceptional")
```

This threshold appears in exactly three places and must stay consistent across all three:

| File | Location | Rule |
|------|----------|------|
| `portfolio/tracker.py` | `_build_watchlist_item()` | `zone_status == "in_zone" AND score >= 75` → `wl_group = "ready"` |
| `intelligence/verification.py` | `verify_watchlist_signal()` | W3 backstop: `wl_group == "ready" AND score < 75` → override to "watching" |
| `main.py` | `/api/strategy` smart_picks_strat builder | `score >= 75` → "Ready to Buy"; `score 70-74` → "Still Watching"; `auto_disq or score < 70` → skip |

If you change the threshold in one place, change it in all three.

---

## Decision Flow

```
For each watchlist / picks stock:

1. tracker.py _build_watchlist_item()
   ├── auto_disqualified?  → wl_group = "avoid"
   ├── score < 30?         → wl_group = "avoid"
   ├── in_zone AND score ≥ 75?  → wl_group = "ready"
   └── everything else     → wl_group = "watching"

2. verify_watchlist_signal() — backstop correction
   ├── data_quality = unavailable  → wl_group = "watching" (no data)
   ├── auto_disqualified           → wl_group = "avoid"
   ├── wl_group = "ready" AND score < 75  → wl_group = "watching" [W3]
   ├── wl_group = "avoid" AND score ≥ 70 AND no disq  → wl_group = "watching" [W4]
   └── otherwise → unchanged

3. _detect_wl_situation() — Strategy tab watchlist label
   ├── wl_group = "ready"   → "Ready to Buy" (emerald)
   ├── wl_group = "avoid"   → "Don't Buy Yet" (rose)
   └── wl_group = "watching" → "Watching — Wait for ≥75 score" (indigo)

4. smart_picks_strat builder — Strategy tab Smart Picks label
   ├── auto_disq → skip entirely
   ├── score < 70 → skip entirely
   ├── change_pct ≤ -8.0% (any score) → "Watch — Major Drop" (amber, WAIT)
   ├── score ≥ 75 → "Ready to Buy" (emerald, BUY/WATCH)
   └── score 70-74 → "Still Watching" (indigo, WAIT)
```

---

## Safety Overrides

These override the label to "Watch / Wait" regardless of trust score:

| Override | Condition | Reason |
|----------|-----------|--------|
| Catastrophic daily drop | `change_pct ≤ -8.0%` | Major selloff on news. Even strong stocks need to stabilise before entry. |
| Auto-disqualified | `auto_disqualified = True` | Always skip from any entry suggestion. |
| No fundamental data | `data_quality = "unavailable"` | Can't assess entry without data. |

---

## Known Failure History

### RKLB — June 2026

**Symptom:** RKLB (Rocket Lab, trust=61, -14.7% on explosion news) showed:
- Strategy → Smart Picks: **"Ready to Buy"** (green)
- Strategy → Watchlist: **"Watching"** / "Wait for ≥75 score" (correct)
- AI commentary: **"does not meet criteria"** (correct)

**Root cause:** `smart_picks_strat` builder (main.py) mapped ALL cached picks to
`situation_type: "ready_to_buy"` without any threshold check. It only used `score ≥ 80`
to choose between action "BUY" vs "WATCH" — but always labelled "Ready to Buy".

**Fix:**
- `main.py` smart_picks_strat: score < 70 → skip; change ≤ -8% → "Watch — Major Drop";
  score 70-74 → "Still Watching"; score ≥ 75 → "Ready to Buy"
- `tracker.py`: raised `wl_group = "ready"` threshold from 60 → 75
- `verification.py`: raised W3 backstop from `< 70` → `< 75`

---

## Rules for Adding New UI Surfaces

1. **Never invent a threshold.** Copy the entry threshold (75) from this document.
2. **Never call score ≥ 80 "Ready to Buy"** unless score ≥ 75 is also satisfied — the
   ≥ 80 check only determines BUY vs WATCH action within the already-qualified set.
3. **Always apply safety overrides** (auto_disq, -8% daily drop, no data) before labelling
   any stock "Ready to Buy".
4. **Run the audit query after shipping** any new surface:
   ```python
   # Check for any stock showing "ready_to_buy" with score < 75
   # in the /api/strategy response
   ```
5. **Write to this file** whenever the threshold changes — it is the contract between
   all surfaces.

---

## Audit Checklist

For any new component that shows a buy/watch/avoid badge:

| Question | Required answer |
|----------|----------------|
| What is the entry threshold? | trust ≥ 75 |
| Does auto_disq skip the stock? | Yes |
| Does a -8% daily drop override "Ready"? | Yes |
| Does no-data override "Ready"? | Yes |
| Does the threshold match tracker.py, verification.py, and main.py? | Yes |
