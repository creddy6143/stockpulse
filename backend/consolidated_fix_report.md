# StockPulse — Consolidated 8-Issue Fix Report

**Commit:** a559d82
**Date:** 2026-05-19
**Branch:** main

---

## Issue 1 — Top 15 Smart Picks + Sector Grouping

### Root cause
`_CURATED_UNIVERSE` contained only 30 tickers, many high-PE growth names that fail the score ≥ 75 gate. The result was 1–3 picks in most sessions. No sector metadata existed.

### Files changed
- `backend/main.py`: Expanded `_CURATED_UNIVERSE` to 118 tickers across 11 GICS sectors. Added `_SECTOR_MAP` dict mapping each ticker to its sector. Modified `_score_one_ticker()` to include `sector`. Modified `/api/picks` to return top 15 non-dip picks. Modified `/api/picks/disqualified` to scan curated universe and add `unblock_condition` field (derived from `disqualify_reason`).
- `frontend/src/App.jsx`: `mapPick` extracts `sector`. `SmartPicksScreen` adds `sectF` filter state, sector pills row, sector-grouped view (All) and flat filtered view (specific sector). Blocked section shows `unblock_condition`. Loading text updated to "Scanning 120+ quality stocks…".

### Verification
Every pick passes existing `verify_pick()` P1–P5 gates inside `_score_one_ticker()`. No change to gate logic.

### Before / After
- Before: 1–3 picks, no sectors, blocked section showed only reason.
- After: Up to 15 picks, sector pills filter, sector headers in grouped view, blocked shows "What would unblock" context.

---

## Issue 2 — Price Alerts (In-App Delivery)

### Root cause
No `price_alerts` table, no alert creation UI, no trigger logic.

### Files changed
- `backend/database/models.py`: Added `price_alerts` table (id, ticker, alert_name, alert_type, threshold, entry_low, entry_high, is_active, triggered_at, created_at).
- `backend/database/db.py`: Added `get_price_alerts()`, `create_price_alert()`, `delete_price_alert()`, `toggle_price_alert()`, `mark_price_alert_triggered()`, `recent_alert_exists()`.
- `backend/main.py`: Added `GET/POST /api/price-alerts`, `DELETE/PUT /api/price-alerts/{id}`. Added `_check_price_alerts()` helper that evaluates active alerts against current price/trust and fires `create_alert()` + `mark_price_alert_triggered()`.
- `backend/portfolio/tracker.py`: Added `_fire_price_alerts()` call at end of portfolio refresh loop. Added auto-disq alert generation (once per 24h).
- `frontend/src/api/client.js`: Added `getPriceAlerts`, `createPriceAlert`, `deletePriceAlert`, `togglePriceAlert`.
- `frontend/src/App.jsx`: New `PriceAlertModal` component (type selector, threshold input, name field). `CompactRow` and `CompactWatchRow` get "🔔 Set Alert" buttons. App state has `priceAlerts`, `alertSubject`, `showBellPanel`. Bell icon opens notification panel.

### Verification
Price alert trigger in `_check_price_alerts()` skips firing if `display_score` is `None` (suppressed score = data insufficient, no alerts).

### Before / After
- Before: No price alert functionality.
- After: Full in-app price alert CRUD. Alerts checked on every portfolio/watchlist refresh. Bell panel shows active alerts + history.

---

## Issue 3 — Strategy Centre Smart Picks Playbooks

### Root cause
`/api/strategy` hard-coded `"smart_picks": []`. The cached picks result was never consulted.

### Files changed
- `backend/main.py`: In `/api/strategy`, after building `my_stocks` and `wl_situations`, reads cached picks (60-min TTL) and builds `smart_picks_strat` list from top 5 qualifying picks. `total_situations` now includes `len(smart_picks_strat)`.

### Verification
Reuses picks output already validated by `verify_pick()`. No additional verification gate needed.

### Before / After
- Before: Strategy "Smart Picks" sub-tab always empty.
- After: Shows up to 5 qualifying picks with expand + AI playbook flow.

---

## Issue 4 — Market-Aware Conditions + Multi-VIX

### Root cause
Single US VIX shown with no label. No European or Indian volatility. No market session (open/closed) awareness.

### Files changed
- `backend/data/fetcher.py`: Added `_get_market_sessions()` function — returns `{state, label, opens_in_min}` for US (Eastern), EU (CET/CEST), India (IST) sessions. Extended `yf_map` to include `^V2TX` (VSTOXX) and `^INDIAVIX`. Added `market_sessions`, `vstoxx`, `india_vix` to `get_market_data()` return dict.
- `backend/requirements.txt`: Added `pytz>=2024.1`.
- `frontend/src/App.jsx`: `HomeScreen` computes `vstoxx`, `indiaVix`, `vstoxxLabel/Color`, `indiaVixLabel/Color`, `openCount`. Market Conditions replaced with `.vix-scroll` row of 3 VIX cards + full-width Markets Today card with session-aware labels (live % when open, countdown when closed).

### Verification
Market conditions are display-only (no score/recommendation). No verification gate needed.

### Before / After
- Before: Single VIX card, no session awareness, same data shown 24/7.
- After: 3 VIX cards (US, EU, India), market session open/closed status per index, countdown to open when closed.

### Known limitations
- `^V2TX` (VSTOXX) and `^INDIAVIX` may return 0 if yfinance free tier doesn't carry them → displays "—" with "Data unavailable" label.

---

## Issue 5 — Watchlist Current Price

### Root cause
`_build_watchlist_item()` returned `current_price` and `change_pct` and `mapWatchlistItem` mapped them as `price` and `change`, but `CompactWatchRow` didn't display them in compact view.

### Files changed
- `frontend/src/App.jsx`: `CompactWatchRow` compact row name line now shows live price + change% when `s.price > 0`. Expanded panel adds "Current vs Entry" comparison row.

### Verification
Display-only. Price data is real (yfinance), no inference. No verification gate needed.

### Before / After
- Before: Watchlist compact row showed only ticker + name.
- After: Shows `$298.40 +1.8%` below ticker; expanded shows "Current $298.40 → Entry Zone $285–310".

---

## Issue 6 — Stock Detail Readability + Trust

### Root cause
`StockDetail` rendered `verdict.verdict` as a plain paragraph with no structure. Key risk was buried inline with recommendation badges.

### Files changed
- `frontend/src/App.jsx`: AI Analysis section header now shows data source tags (Finnhub, yfinance, NSE if Indian). Border-left colour uses `c` (trust-level colour) instead of hardcoded indigo. `verdict.key_risk` shown as labeled row. `verdict.stop_loss_explanation` shown as labeled row. Verification confidence badge: MEDIUM shows amber caveat, SUPPRESSED shows "Analysis pending" message.

### Verification
No backend changes. Verification already applied by `verify_ai_text()` in `get_verdict()`.

### Before / After
- Before: Single paragraph, key risk inline with badges.
- After: Structured section with data sources, colour-coded border, labeled Key Risk + Stop Loss rows.

---

## Issue 7 — Home Screen Inline Earnings + Signals

### Root cause
Earnings Watch had no fallback for empty state. Signals feed was empty unless alerts had previously been created.

### Files changed
- `backend/portfolio/tracker.py`: At end of `get_portfolio_with_pnl()`, iterates results and calls `db.create_alert()` for auto-disqualified positions not alerted in past 24h (using `db.recent_alert_exists()`).
- `frontend/src/App.jsx`: `HomeScreen` adds `upcomingEarnings` variable (next 14 days, non-today). Earnings Watch card shows upcoming preview when no today earnings. "No earnings this week for your tracked stocks" fallback shown when both `todayEarnings` and `upcomingEarnings` are empty.

### Verification
Auto-disq alert generation only fires for stocks where `auto_disqualified = True` (already verified by trust score engine).

### Before / After
- Before: Signals feed empty on fresh install; Earnings Watch blank when no today events.
- After: Signals feed populated as soon as any auto-disq stock is in portfolio; Earnings Watch shows upcoming events with fallback text.

---

## Issue 8 — Track+ Button Fix

### Root cause
No visual state for already-tracked stocks. `handleAdd` guard only checked `PICKS` array, not user's custom universe.

### Files changed
- `frontend/src/App.jsx`: `SmartPicksScreen` loads `getPicksUniverse()` into `trackedSet` state on mount (and when `picks` changes). Sector-grouped pick rows show a green "✓" badge when `trackedSet.has(s.ticker)`. `handleAdd` guard checks both `PICKS`, `DISQ` and now also updates `trackedSet` immediately (optimistic update). `handleRemove` removes from `trackedSet` immediately. Add message: "XYZ added — will appear when score ≥ 75".

### Verification
No verification gate for UI tracking state. Track+ just adds to `picks_universe` table; actual pick eligibility is still gated by `verify_pick()` on each score cycle.

### Before / After
- Before: No visual feedback for tracked stocks; add/remove didn't update local state.
- After: Tracked stocks show "✓" badge; add/remove are optimistic and immediate.

---

## Summary of Files Changed

| File | Change summary |
|------|---------------|
| `backend/database/models.py` | Add `price_alerts` table |
| `backend/database/db.py` | Price alerts CRUD + `recent_alert_exists` |
| `backend/main.py` | 118-ticker universe + sector map; picks/strategy/disq endpoints; price alerts endpoints; `_check_price_alerts` |
| `backend/data/fetcher.py` | `_get_market_sessions()`; VSTOXX + India VIX; market sessions in return dict |
| `backend/portfolio/tracker.py` | `_fire_price_alerts()` call; auto-disq alert generation |
| `backend/requirements.txt` | Added `pytz>=2024.1` |
| `frontend/src/api/client.js` | Price alerts CRUD functions |
| `frontend/src/App.jsx` | SmartPicksScreen (sector), PriceAlertModal, CompactRow/WatchRow (set alert), HomeScreen (multi-VIX, sessions, earnings), StockDetail (structured AI), App state (priceAlerts, bell panel) |

---

## Verification Integration

| Output | Verification check applied |
|--------|---------------------------|
| Picks (Top 15) | `verify_pick()` P1–P5 gates in `_score_one_ticker()` |
| Strategy smart picks | Reuses cached verified picks output |
| Price alert trigger | Skips if `display_score` is None (suppressed) |
| AI analysis (stock detail) | `verify_ai_text()` T1–T3 in `get_verdict()` |
| Market conditions | Display-only, no score/recommendation gate needed |
| Watchlist price | Real price data, no inference gate needed |

---

*Report generated 2026-05-19*
