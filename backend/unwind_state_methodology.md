# Unwind State Methodology — Correlated Selloff (Tier 4b)

> `intelligence/unwind_detector.py`

## The distinction

- A **dip** is one stock pulling back while its world is fine.
- A **correlated selloff** ("unwind") is the world falling — a whole theme dropping
  together on a shared macro driver.

Individual dip quality **cannot** be assessed during a correlated selloff, so every
dip-buy flag inside an unwinding theme is suspended. During an unwind the most valuable
output is not a buy signal — it is a measurable, honest answer to *"how close is this
theme to being safe to assess again?"* That answer is the **stabilization tracker**.

## Detection (per theme, tightest theme wins)

Themes come from `data/theme_membership.json`. Themes are evaluated **smallest-first** so
a ticker is claimed by its **tightest** theme (e.g. `storage_memory` [WDC/MU/STX] before
any broader tech grouping). A ticker belongs to exactly one unwind.

Suppress all dip-buy flags in a theme when **ANY** of:

| Trigger | Threshold (`unwind_detector.py`) |
|---|---|
| 3+ theme members down > 5% within the same 1–5 day window | `MIN_MEMBERS_DOWN = 3`, `MEMBER_DROP_PCT = -5.0` |
| Theme average down > 8% over 5 days | `THEME_AVG_DROP = -8.0` |

A theme needs ≥ `MIN_THEME_SIZE = 3` members present in the scan universe to be judged at
all. "Down in the window" = worst of (today %, 5-day %). Members down ≥ `GROUP_DROP_PCT
= -2%` are grouped under the banner as affected.

## While suppressed

- Affected stocks are **NOT removed** — they group under one Unwind banner.
- Their recommendation is **forced to WATCH** (`apply_unwind_suppression`). No BUY-class
  badge is ever emitted in unwind state.
- Their scores are **FROZEN** at pre-unwind values (`frozen_score`, `frozen_dip_tier`) —
  not recomputed during the unwind.
- They are excluded from the grade sections in the Dip Buys tab to avoid duplication.

## Stabilization tracker (4 criteria — "N of 4 met")

All computed from **real theme-aggregate change data**. Criterion 2 is reported as pending
when per-theme volume is unavailable (never guessed); criterion 3 as pending when 3-day
data is missing.

| # | Criterion | Computation |
|---|---|---|
| 1 | No new theme-wide low today | theme avg today > −1.5% |
| 2 | Theme volume < 1.5× average | mean member volume ratio < 1.5 (else "pending") |
| 3 | 3 days without a lower low | theme avg 3-day return > −1.0% (else "pending") |
| 4 | Theme flat-or-up over 5 days | theme avg 5-day return ≥ 0% |

`stabilized = (met_count == 4)`. When stabilized the banner flips to
"✅ THEME STABILIZED · Dip signals resumed" and dip qualification runs normally again.

## Reclaim level (Part 4b — per WATCHING stock)

The nearest meaningful overhead resistance **above** current price, chosen as the closest
of: recent high (last ~6 history points), MA50, MA200. Status is a point-in-time read:

| Status | Condition | Label |
|---|---|---|
| `below` | price < level × 0.995 | "Bounce, not confirmed" |
| `testing` | within ±0.5% of level | "Testing reclaim" |
| `reclaimed_day1` | price ≥ level × 1.005 | "Reclaimed — needs 1 more close + volume confirmation" |
| `above` | no reference level above price | "Above resistance — no overhead level" |

Full `confirmed` (2 closes held on above-average volume) requires multi-day tracking. An up
day of +5% or +15% that stays **below** the level still reads "Bounce, not confirmed" —
the daily % never overrides the level logic.

**Entry signal** fires only when BOTH: stock reclaim = confirmed AND theme stabilization =
4 of 4. Then the stock re-qualifies through normal dip filters using its frozen score.

## Recovery resilience

Uses the shared `intelligence/recovery_resilience.py`. Returns `score`, `label`, and
`median_recovery_days` from **real price history only**; returns "Insufficient history"
when < ~6 months of data exists. Never fabricated.

## Freeze / unfreeze

- **Freeze** on entering unwind: `frozen_score` snapshots `quality_score`; scores are not
  recomputed while suspended.
- **Unfreeze** on stabilization: scores recompute on the next scan, and re-qualified stocks
  are listed by frozen score descending until fresh scores land.

## History log (Part 5)

`data/theme_unwind_state.json` holds open episodes; completed episodes are appended to
`data/theme_unwind_history.json`:

```json
{ "theme": "storage_memory", "name": "Storage / Memory",
  "start_date": "2026-07-24", "end_date": "2026-07-29",
  "max_depth": -14.0, "members": ["STX","WDC","MU"], "driver": "..." }
```

On each scan: open/extend episodes for currently-unwinding themes; any theme that was
unwinding but no longer is → close the episode and append to history. This feeds future
calibration.

## Day count

Estimated from today's move vs the 5-day move (we don't store daily history for every
member). Labelled `day_count_estimated: true` and shown as "~Nd" — never presented as an
exact figure.
