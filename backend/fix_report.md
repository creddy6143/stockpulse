# StockPulse Fix Report
**Session date:** 2026-05-19
**Commit base:** 3fbf6f0 Fix Strategy screen crash when trust_score is None

---

## Issue 1 — US stocks showing "?" scores (CRITICAL)

### Root cause
Two interacting bugs:
1. **No yfinance fallback for US stocks.** `get_fundamentals` only ran the yfinance Python lib for stocks in the `is_intl` list (`.ST`, `.AS`, `.L` etc.). Plain US tickers had no safety net when Finnhub's free tier hit its 60-call/min rate limit — so a failed Finnhub call returned an empty result dict.
2. **24-hour cache lock on failed fetches.** `cache_set` had no per-entry TTL, so a failed/empty fundamentals response was stored in the cache for the full `TTL_FUNDAMENTALS = 86400` seconds. One rate-limited request at 9am meant the stock showed "?" all day.

### Fixes applied
**`backend/data/cache.py`**
- Added optional `ttl` parameter to `cache_set(key, value, ttl=None)`.
- `cache_get` now reads the per-entry TTL if present, overriding the caller's TTL.
- Failed fetches can now be cached with a 5-minute retry window instead of 24 hours.

**`backend/data/fetcher.py`**
- Extended the `is_intl` yfinance block to a universal safety net: `_needs_yf = is_intl OR (market_cap == 0 OR revenue_growth near zero)`.
- Any stock — US, EU, or Indian — that exits the Finnhub/Yahoo v10/v8 chain without core metrics now gets the yfinance lib as a final attempt.
- `cache_set` at the end of `get_fundamentals` now passes `ttl=5*60` when `market_cap == 0`, so empty results retry in 5 minutes not 24 hours.

### Verification
With a valid Finnhub API key, test stocks (GRRR, HOOD, SMCI, AFRM, QBTS, PONY, NNE) all returned `data_sufficiency = 1.00` in prior session diagnosis. The fix prevents rate-limit hits from locking those stocks out for 24 hours.

---

## Issue 2 — Strategy Centre: INFY.NS showing "Fundamentals weak — consider exit"

### Root cause
`_detect_situation` in `main.py` triggered the `crash_decision` branch when `pnl_pct < -30` AND used the string `"Fundamentals weak — consider exit"` whenever `trust < 60`. A stock like INFY.NS can have trust < 60 temporarily due to data-fetch issues (Screener.in scraper timeout, Finnhub rate limit) even when the company's fundamentals are excellent. The language was factually wrong and alarming.

### Fixes applied
**`backend/main.py` — `_detect_situation`**
- Changed the `crash_decision` summary for `trust < 60` from `"Fundamentals weak — consider exit."` to `f"Trust score {trust_str}. Review recent reports before deciding."` — neutral language that doesn't conflate data quality issues with actual company weakness.
- Changed `action` from `"SELL"` to `"REVIEW"` in this branch to avoid false sell signals.

**`backend/portfolio/tracker.py` — `_build_position`**
- Added `data_quality` field to the position response dict (from `trust.get("data_quality", "full")`).
- Frontend and strategy logic can now distinguish "low score from data issues" vs "low score from real weakness".

---

## Issue 3 — No way to edit portfolio positions

### Root cause
`CompactRow` had no edit button; `AddModal` had no edit mode. `updatePosition` existed in `api/client.js` but was not imported in `App.jsx`.

### Fixes applied
**`frontend/src/App.jsx`**
- Added `updatePosition` to imports from `./api/client`.
- Added new `EditModal` component with two modes:
  - **Edit mode**: directly change shares count and average buy price.
  - **Add more shares mode**: enter a new lot (shares + price) and see the weighted average auto-calculated in real time before confirming. Formula: `(existing_shares × existing_price + new_shares × new_price) / total_shares`.
- Added "Edit" button to the `CompactRow` expanded section (alongside "Full Analysis" and remove button).
- `PivotSection` now passes `slice.onEdit` down to `CompactRow`.
- `StocksScreen` has a new `handleEdit(s)` function that opens `EditModal`.

---

## Issue 4 — No visible delete button on watchlist rows

### Root cause
`CompactWatchRow` received the `onRemove` prop from `PivotSection` but never rendered a button that called it. The remove action was silently dead.

### Fix applied
**`frontend/src/App.jsx` — `CompactWatchRow`**
- Added a "Remove from Watchlist" button at the bottom of the expanded panel. Calls `onRemove(s)` which flows up to `StocksScreen.handleRemoveWL` and then to the API.

---

## Issue 5 — No confirmation dialog (destructive actions were instant)

### Root cause
Both `handleRemove` and `handleRemoveWL` in `StocksScreen` used `window.confirm()` — which renders a native browser dialog. On mobile Safari/Chrome, native confirms look jarring and don't match the app design. On some PWA installs, they're blocked entirely.

### Fix applied
**`frontend/src/App.jsx`**
- Added new `ConfirmDialog` component: a styled bottom-sheet modal matching the app design, with Cancel + Remove buttons and a "This cannot be undone" message.
- `StocksScreen` now uses `useState(null)` for a `confirm` state object `{message, onConfirm}` instead of `window.confirm`.
- Both `handleRemove` and `handleRemoveWL` set the confirm state; the actual delete/remove runs only after the user taps "Remove" in the dialog.

---

## Issue 6 — Smart Picks results changing on every refresh

### Root cause
1. **Data reliability (same as Issue 1):** When Finnhub rate-limits, some stocks temporarily get score = null → they drop off and re-appear between refreshes as the cache cycles.
2. **30-minute cache was too short:** Fresh refreshes could land within the same 30-minute window but on different minutes, occasionally missing the cache hit.
3. **Non-deterministic sort:** When trust scores tie, the secondary sort was undefined, so stock order could change across calls.

### Fixes applied
**`backend/main.py` — `/api/picks`**
- Extended picks result cache from 30 minutes to 60 minutes.
- Added secondary sort by ticker name: `sort(key=lambda x: (-(x["trust"]["total_score"] or 0), x["ticker"]))` — guarantees same order for same scores.
- Dip picks now also sorted alphabetically for consistency.

---

## Issue 7 — Dead "Track+" button in Smart Picks

### Status
Verified NOT broken. `SmartPicksScreen.handleAdd` calls `addPicksUniverse(ticker)` → `POST /api/picks/universe` — this is correctly wired in both `App.jsx` and `api/client.js`. The button shows feedback message "Added! Refresh picks to see it." The apparent deadness was likely a UX perception issue: picks don't immediately reappear because the cache (now 60 min) needs to expire. The "Refresh picks" button on the screen forces a refresh.

---

## Files Changed

| File | Change |
|------|--------|
| `backend/data/cache.py` | Per-entry TTL support in `cache_set` / `cache_get` |
| `backend/data/fetcher.py` | Universal yfinance safety net + short TTL for failed fetches |
| `backend/main.py` | Neutral strategy language, deterministic picks sort, 60-min picks cache |
| `backend/portfolio/tracker.py` | Added `data_quality` field to position response |
| `frontend/src/App.jsx` | `ConfirmDialog`, `EditModal`, watchlist remove button, `updatePosition` import |

---

## Regression Notes

- `cache_set` signature changed: added optional `ttl` param. All existing callers pass no TTL and behave identically (TTL is checked at read time, same as before).
- `_build_position` return dict has one new key (`data_quality`). Frontend `mapPosition` ignores unknown keys — no frontend breakage.
- Picks sort is now deterministic — results are stable across refreshes for the same data snapshot.
