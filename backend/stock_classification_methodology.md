# Stock Classification Methodology

## Problem Solved

Portfolio stocks were flipping between **Urgent / Monitor / Stable** categories
within a single trading session even when company fundamentals had not changed.

**Root causes:**
1. `pnl_pct` (user's P&L from entry price) changes on every API call as live
   prices update. A stock down -19.9% today can cross the -20% threshold and
   flip Stable → Monitor the next hour.
2. `momentum_score` (0-25 pts) includes price vs MA200 and price vs 52-week
   high — both change daily.
3. No hysteresis at all: classification was a stateless pure function
   recalculated on every API call.

---

## What Drives Each Category

### Slow signals only

Classification uses **only** the two fundamental pillars:

| Pillar | Max | Included signals |
|--------|-----|-----------------|
| Business Quality | 40 | Revenue growth, earnings quality, profitability, guidance |
| Smart Money | 35 | CEO/insider buying, institutional 13F changes, short interest trend |
| **Fundamental Score** | **75** | Sum of the two above |

**Excluded** from classification:
- `momentum_score` (price vs MA200, price vs 52W high, news catalyst)
- `pnl_pct` (user's unrealised P&L from their entry price)
- `change_pct` (today's price move)

These excluded inputs are still **displayed** in the UI — they just don't
affect which accordion group a stock appears in.

### Category thresholds

| Fundamental Score (0-75) | Group | UI label |
|--------------------------|-------|----------|
| auto_disqualified=True | urgent | Urgent |
| < 30 (≈ 40% of max) | urgent | Urgent |
| 30-44 | watch | Monitor |
| ≥ 45 (≈ 60% of max) | good | Stable |

The 30/45 thresholds on the 0-75 scale mirror the old 40/60 thresholds on the
0-100 scale (momentum was contributing ~15 pts on an average stock).

---

## International / Indian Stocks with No Analyst Coverage (SBIN Fix)

**Problem:** Finnhub free tier returns 0 analyst ratings for NSE, BSE, and
many EU stocks. Zero analysts → `smart_money_score` defaults to near-zero →
total score is synthetically low → stock wrongly classified Urgent.

**Fix** (`trust_score.py`): After computing all three pillar scores, check:

```python
if analyst_count == 0 and is_international and base_quality == "full":
    base_quality = "limited"
```

`is_international` applies to these suffixes: `.NS .BO .PA .AS .DE .MC .L .MI .BR .ST .F`

Effect on classification:
- `data_quality = "limited"` → `_classify_slow()` routes to **watch** (not
  urgent) when `fundamental_score < 45`, regardless of how low smart_money is.
- The verification layer already suppresses SELL recommendations when
  `data_quality = "limited"` and score is below threshold.

---

## Hysteresis Engine

### Tables

```sql
classification_state   -- current stable group + pending timer per (ticker, user_id)
classification_audit   -- immutable log of every committed group change
```

### Delay table

| Transition | Required trading days |
|---|---|
| good → watch | 3 |
| good → urgent | 1 (immediate danger) |
| watch → urgent | 2 |
| watch → good | 1 (fast recovery) |
| urgent → watch | 5 |
| urgent → good | 5 |

### Algorithm (per API call, per ticker)

1. Compute `new_group` from slow signals.
2. Load `state` from `classification_state`.
3. **No history** → bootstrap: write `new_group` as stable, return it.
4. **Unchanged** (`new_group == stable_group`) → clear any stale pending,
   return `stable_group`.
5. **Changed**:
   - Look up `required_days = HYSTERESIS_DAYS[(stable_group, new_group)]`.
   - If `pending_group != new_group`: start/restart timer, return `stable_group`.
   - Else: count trading days elapsed since `pending_since`.
     - `elapsed < required_days` → return `stable_group` (cooling off).
     - `elapsed >= required_days` → log to audit, commit `new_group`, return it.

"Trading days" are Mon-Fri weekdays counted with `numpy.busday_count`.

---

## Reading the Audit Log

```
GET /api/portfolio/classification-audit
GET /api/portfolio/classification-audit?ticker=SBIN.NS
GET /api/portfolio/classification-audit?limit=10
```

Response fields:

| Field | Meaning |
|---|---|
| `old_group` | Group before the change |
| `new_group` | Group after the change |
| `trigger_signal` | Why the change fired (e.g. `"auto_disqualifier"`, `"strong_fundamentals"`) |
| `hysteresis_days_required` | How many trading days were needed |
| `hysteresis_days_elapsed` | How many actually elapsed before the commit |
| `changed_at` | UTC timestamp of the commit |

A quiet audit log (few or no entries) means classifications are stable —
which is the intended behaviour.

---

## Testing Checklist

1. `python3 -c "from database.db import init_db; init_db()"` — confirms new tables.
2. `GET /api/portfolio` — SBIN shows `group: "watch"` not `"urgent"`.
3. `GET /api/portfolio` multiple times rapidly — group does not flip between calls.
4. `GET /api/portfolio/classification-audit` — returns entries after first portfolio load.
5. `pnl_pct` still present in position payload (displayed but not used for grouping).
6. `change_pct` (daily %) still present and displayed.
7. Auto-disqualified stocks (TNXP, XGN) still appear in Urgent immediately
   (`good → urgent` requires only 1 day; `urgent` is the first write for new stocks).
