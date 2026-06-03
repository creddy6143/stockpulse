# Recommendation Engine — Single Source of Truth

## The Rule

Every UI surface that shows a "Ready to Buy" / "Watching" / "Don't Buy" badge for a
watchlist or smart-picks stock **must derive that label from the same threshold**.
Internal contradictions — where Strategy tab says "Ready to Buy" and Stocks screen says
"Watching" for the same stock at the same moment — destroy trust faster than any other
class of bug.

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
