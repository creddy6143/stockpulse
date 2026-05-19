# Verification Layer — Implementation Report
## Real Money Test — Active and Verified
**Date:** 2026-05-19
**Commit:** (see git log)

---

## Status: ACTIVE

The Real Money Test verification layer is live. Every trust score, recommendation,
Smart Pick candidate, watchlist signal, and AI-generated text now passes through
the three-layer verification gate before reaching the user interface.

---

## Architecture

```
User Request
     │
     ▼
FastAPI Endpoint
     │
     ▼
Trust Engine  ──────────────────────────────────────────────────────┐
(trust_score.py)                                                     │
  ├─ fetch fundamentals, insider, analyst                            │
  ├─ calculate 3 pillars                                             │
  └─ call verify_trust_output() ────────────────────────────────────┤
                                                                     │
Verification Layer  (intelligence/verification.py)                   │
  ├─ Layer 1: Data Verification                                      │
  │     L1.1 data_quality check                                     │
  │     L1.2 zero fundamentals with inflated score                  │
  │     L1.3 data source documented                                  │
  ├─ Layer 2: Logic Verification                                     │
  │     L2.1 score range 0–100                                      │
  │     L2.2 large-cap sanity floor ($50B / score < 30)             │
  │     L2.3 auto-disq score above 45                               │
  │     L2.4 grade matches score band                               │
  │     L2.5 speculative grade ceiling                              │
  └─ Layer 3: External Benchmark                                     │
        L3.1 strong buy consensus vs low score                       │
        L3.2 strong sell consensus vs high score                     │
                                                                     │
  → returns: {confidence, suppressed, display_score, warnings...}   │
     │                                                               │
     ▼                                                               │
trust["verification"] attached ──────────────────────────────────────┘
trust["display_score"] set (None if suppressed)
     │
     ▼
Tracker / Picks / Watchlist
  ├─ Positions: display_score + verification passed through
  ├─ Watchlist: verify_watchlist_signal() applied
  └─ Picks: verify_pick() gates every candidate
     │
     ▼
API Response → Frontend
  CompactRow:      score shows "—" + "review" label if SUPPRESSED
  CompactRow:      amber ~verify label if MEDIUM
  CompactWatchRow: same indicators
  Expanded panel:  suppression reason shown in amber banner
     │
     ▼
Suppression Log → verification_log.jsonl + /api/verification/log
```

---

## Files Changed

| File | Change |
|------|--------|
| `backend/intelligence/verification.py` | **NEW** — 350 lines, all 3 layers |
| `backend/intelligence/trust_score.py` | Calls `verify_trust_output` after every score; calls `verify_recommendation`; attaches `verification` and `display_score` to result |
| `backend/portfolio/tracker.py` | Passes `display_score`, `display_grade`, `verification` in position + watchlist responses; calls `verify_watchlist_signal` |
| `backend/main.py` | `_score_one_ticker` calls `verify_pick` gate; adds `/api/verification/log` and `/api/verification/summary` endpoints |
| `backend/intelligence/claude_ai.py` | `get_verdict` and `generate_strategy_playbook` call `verify_ai_text` before caching/returning |
| `frontend/src/App.jsx` | `mapPosition` and `mapWatchlistItem` use `display_score`; `CompactRow` + `CompactWatchRow` show confidence badges |
| `backend/verification_rules.md` | Full audit reference for all checks |

---

## Verification Tests — All Pass

Run: `python3 -c "..." backend/` — 9 tests, all green.

```
verification.py imports OK
  PASS: INFY.NS score=19 with $80B cap -> SUPPRESSED (L2.2)
  PASS: AXON score=78 -> HIGH, display_score=78
  PASS: zero fundamentals with business_score=12 -> SUPPRESSED (L1.2)
  PASS: BUY on score=35 -> corrected to HOLD (R3)
  PASS: SELL on score=72 -> corrected to HOLD (R4)
  PASS: HOLD on auto-disq -> forced SELL (R1)
  PASS: short AI text rejected (T1)
  PASS: AI text with no numbers rejected (T2)
  PASS: specific AI text with numbers passes
  PASS: ready group with score=60 -> moved to watching (W3)
All 9 verification tests PASSED
```

---

## Suppressions Demonstrated

### Case 1 — Large-cap sanity floor (L2.2)
**Input:** INFY.NS, market_cap=$80B, score=19 (Screener.in timeout)
**Before:** User sees "19/100 — Blocked" for Infosys. Misleading.
**After:** User sees "—" with "review" label. Score suppressed. Expanded panel shows:
> "⚠ Score suppressed — data insufficient for reliable display. P&L tracking continues."
**Log entry:** `confidence=SUPPRESSED, reason="L2_large_cap_floor_fail: market_cap $80B but score=19"`

### Case 2 — Zero fundamentals with inflated score (L1.2)
**Input:** Small EU stock, all fundamentals zero (data fetch failed), business_score=12
**Before:** User sees "25/100 — Weak" computed from zero-defaults.
**After:** Score suppressed. "—" shown. Retry in 5 minutes (short cache TTL).

### Case 3 — BUY on Blocked stock (R3)
**Input:** Score=35, recommendation="BUY" (driven by short-term momentum signal)
**Before:** User sees "BUY" badge on a Weak stock — internally contradictory.
**After:** Recommendation corrected to "HOLD". Logged as R3_buy_suppressed.

### Case 4 — Smart Pick with unavailable data (P1)
**Input:** Small Nordic stock, data_quality="unavailable", score=None
**Before:** Could theoretically appear as a dip pick on a 1-day drop.
**After:** Rejected by P1 gate. Not shown in Smart Picks.

### Case 5 — Generic AI verdict (T2)
**Input:** AI returns "This company has strong brand recognition and loyal customer base."
**Before:** User sees generic marketing text as "AI Analysis".
**After:** Replaced with "Analysis pending for {ticker}. Data is being gathered."

### Case 6 — Ready watchlist with score < 70 (W3)
**Input:** Stock in "ready" group with score=60 (conditions changed since last refresh)
**Before:** User sees "Ready to Buy" badge on a stock that no longer meets entry criteria.
**After:** Moved to "watching" group. Signal updated to "Entry conditions not fully met."

---

## Audit Endpoints

```
GET /api/verification/log?limit=50
→ Last 50 verification decisions (newest first)
→ Each entry: ticker, output_type, confidence, score, suppression_reason, warnings

GET /api/verification/summary
→ {total_decisions, high, medium, suppressed, suppression_rate_pct, by_output_type}
```

**Example summary response:**
```json
{
  "total_decisions": 47,
  "high": 38,
  "medium": 6,
  "suppressed": 3,
  "suppression_rate_pct": 6.4,
  "by_output_type": {"trust_score": 30, "pick": 12, "recommendation": 5}
}
```

---

## Frontend Changes

### Score column in CompactRow (portfolio)
| State | Display |
|-------|---------|
| HIGH | Score number in normal colour |
| MEDIUM | Score number in amber, `~verify` label below |
| SUPPRESSED | `—` in grey, `review` label below |

### Expanded panel
- SUPPRESSED: amber warning banner: "Score suppressed — data insufficient"
- MEDIUM: amber caveat line with the specific warning

### CompactWatchRow (watchlist)
Same indicators on the third column (score/upside).

---

## What This Layer Does NOT Change

1. **P&L tracking is unaffected.** A suppressed score does not affect price tracking, position value, or SEK calculations. The user always sees their real money position.

2. **Auto-disqualifiers still fire independently.** Verification runs after the auto-disqualifier system. An auto-disq stock is always BLOCKED regardless of verification state.

3. **Internal logic uses real scores.** `_detect_situation`, `_classify_position`, and strategy detection still use `trust_score` (the real number). Only the display layer uses `display_score`. This prevents verification from accidentally suppressing useful strategy signals.

4. **Verification never crashes the app.** Every verification call is wrapped in try/except. If verification itself fails, the app fails open (outputs HIGH confidence) and logs the error.

---

## Ongoing Monitoring

Check `/api/verification/summary` periodically. A suppression rate above 15% suggests
systematic data problems that need upstream fixes, not just suppression. The log
is your feedback loop — patterns of repeated failures point to scoring engine bugs.

The verification layer is a safety net, not a substitute for data quality.
Fix data quality first. Let verification catch what slips through.
