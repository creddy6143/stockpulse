# Dip Filter Methodology

> `intelligence/dip_filter.py` · see also `dip_filter_calibration_report.md`

The dip stack runs 28 filters across 4 tiers and grades qualifying pullbacks A / B / C.
This document records the **integrity overrides** that sit on top of the score — the rules
that can cap or suspend a dip verdict regardless of how good the setup looks.

## Grades (recap)

| Grade | Rule |
|---|---|
| A | trust ≥ 78, all 28 filters pass |
| B | trust ≥ 78, only trend/valuation filters soft-fail (quality in a downtrend) |
| C | trust 70–77, all 28 pass |

## Tier 4 — the qualifying window (label must match the number)

A dip qualifies on a **multi-day** drop, computed as:

- `cumulative` = 5-day return (`1W`) when the pattern is a weekly slide, else the 3-day
  return (`3D`) for a post-peak selloff.
- `dip_pct` / `dip_window` expose that qualifying drop and its window ("1W"/"3D").

**Rule (number consistency):** any UI that shows the word "dip" must display `dip_pct` /
`dip_window` beside it — **never** today's daily `change_pct`. A green +1% today can never
sit next to the word "dip" (e.g. RR.L +1.0% qualified on a −6% weekly slide → the row shows
"−6.2% / 1w", not "+1.0% dip"). See `number_consistency.md`.

## Tier 4a — −8% single-day safety override

A daily `change_pct` **worse than −8%** can never be a BUY or STRONG BUY on **any** screen.
This executes **after** all quality scoring, inside `evaluate_dip_candidate`:

```
safety_capped = change_pct <= -8.0
dip_rec = "WATCH" if safety_capped else "BUY"
```

Even a Grade-A, high-conviction setup is capped to **WATCH** with reason "sharp single-day
drop — wait for stabilization." Consumers (Smart Picks `mapPick`, Strategy Dip Buys tab)
must honour `dip_rec` / `safety_capped`. STX at −10.4% and GLW at −10.8% render WATCH.

## Tier 4b — correlated selloff (Unwind)

When a whole theme is falling together, individual dip quality is not assessable. The
`unwind_detector` suppresses every dip in an unwinding theme, forces WATCH, and freezes
scores. Full methodology: **`unwind_state_methodology.md`**.

Thresholds:

| Trigger | Threshold |
|---|---|
| 3+ theme members down > 5% in a 1–5 day window | `MIN_MEMBERS_DOWN=3`, `MEMBER_DROP_PCT=-5.0` |
| theme average down > 8% over 5 days | `THEME_AVG_DROP=-8.0` |

Themes are evaluated **tightest-first** (from `theme_membership.json`) so a stock is grouped
under its most specific theme (Storage/Memory, not a broad tech bucket).

## Override precedence

```
1. Hard filter FAILs        → not a dip at all (return None)
2. Unwind (Tier 4b)         → WATCH · scores frozen · grouped under banner
3. -8% single-day (Tier 4a) → WATCH · "wait for stabilization"
4. Grade A/B/C              → normal dip verdict (BUY-class allowed)
```

Overrides 2 and 3 never produce a BUY-class badge. They are integrity gates, not scores.
