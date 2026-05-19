# StockPulse Verification Rules
## The Real Money Test — Complete Audit Reference
**File:** `backend/intelligence/verification.py`
**Integrated into:** `trust_score.py`, `tracker.py`, `main.py`, `claude_ai.py`
**Last updated:** 2026-05-19

---

## Design Principle

> A missing output is honest. A wrong output destroys trust.

Every score, signal, recommendation, and AI text must pass this test before
being shown to the user:

**"Would a professional trader looking at this output find it defensible
based on the data we have?"**

- YES → show it (HIGH confidence)
- UNSURE → show it with a `~verify` caveat (MEDIUM confidence)
- NO → suppress it, show "Review manually" (SUPPRESSED)

---

## Confidence Levels

| Level | Symbol | Meaning | User sees |
|-------|--------|---------|-----------|
| HIGH | ✓ | All checks passed | Score number, normal colour |
| MEDIUM | ~ | Minor warnings | Score + amber `~verify` label |
| SUPPRESSED | — | Critical failure | "—" with "review" label |

---

## LAYER 1 — Data Verification

Runs before any scoring logic. Verifies the input data is real.

### L1.1 — data_quality check
- **Trigger:** `trust["data_quality"] == "unavailable"` (< 70% required fields populated)
- **Action:** Tag as SUPPRESSED in log. `total_score` is already `None` upstream.
- **Rationale:** Scoring with < 70% field coverage produces a number based on zero-defaults, not real company data. The trust engine already handles this — L1.1 ensures it's logged and surfaced clearly.

### L1.2 — Zero fundamentals with inflated score
- **Trigger:** ALL of `revenue_growth`, `profit_margins`, `gross_margins` ≈ 0 AND `market_cap` == 0, AND `business_score > 5`
- **Action:** SUPPRESSED
- **Rationale:** If all metric fields are zero yet the business pillar produced > 5 points, the score was computed on empty defaults. This is a data integrity failure — the algorithm awarded partial credit for missing data.

### L1.3 — Data source not documented
- **Trigger:** No `data_source` field in trust or fundamentals dict
- **Action:** MEDIUM (warning only)
- **Rationale:** Unattributed scores are harder to audit. This is a soft warning, not a suppression, because some routes (yfinance lib) don't set a source tag.

---

## LAYER 2 — Logic Verification

Runs after computation. Checks the output is internally consistent.

### L2.1 — Score range validation
- **Trigger:** `score < 0` or `score > 100`
- **Action:** SUPPRESSED (critical)
- **Rationale:** Any score outside 0–100 means a calculation bug. Must not be displayed.

### L2.2 — Large-cap sanity floor ⭐ (highest-impact check)
- **Trigger:** `market_cap > $50B` AND `score < 30` AND `auto_disqualified == False`
- **Action:** SUPPRESSED (critical)
- **Rationale:** A Fortune 500 / Nifty 50 / DAX stock with no active disqualifier cannot legitimately score below 30. The only realistic explanation is a data-fetch failure — Screener.in timed out, Finnhub rate-limited, etc. Displaying a score of 19 for Infosys or 22 for HDFC Bank would be credibility-destroying. This check suppresses those outputs and retries when data improves (5-min cache TTL on failed fetches).
- **Examples caught:** INFY.NS scoring 19 (Screener.in timeout), HDFC scoring 22 (Finnhub rate limit), MSFT scoring 8 (API completely down)

### L2.3 — Auto-disqualified score above 45
- **Trigger:** `auto_disqualified == True` AND `score > 45`
- **Action:** MEDIUM (warning, not suppression)
- **Rationale:** BLOCKED_OVERRIDES cap scores at ≤ 18. If an auto-disq stock somehow arrives with score > 45, there's a possible override conflict. Not suppressed because the auto-disq flag is the critical signal — the score inconsistency is secondary.

### L2.4 — Grade vs score band mismatch
- **Trigger:** Grade label doesn't match the score according to fixed thresholds
  - Exceptional: 90–100, Strong: 75–89, Moderate: 60–74, Weak: 40–59, Blocked: 0–39
- **Action:** MEDIUM (warning)
- **Rationale:** A grade of "Strong" on a score of 45 is a mapping error. Users trust the grade label more than the number — a mismatch misleads them.

### L2.5 — Speculative stock with high grade
- **Trigger:** `is_speculative == True` AND grade in ("Strong", "Exceptional")
- **Action:** MEDIUM (warning)
- **Rationale:** Pre-revenue speculative companies have no earnings history to justify Strong or Exceptional grades. The grade would mislead users into treating them like established businesses.

---

## LAYER 3 — External Benchmark

Cross-references internal score against analyst consensus. Uses data already
fetched by the trust engine — zero additional API calls.

### L3.1 — Strong analyst buy vs low internal score
- **Trigger:** ≥ 75% of covering analysts rate Buy AND internal score < 35 AND coverage ≥ 3 analysts
- **Action:** MEDIUM (warning)
- **Rationale:** If professional analysts covering the stock are strongly bullish but our system scores it below 35, there is an unexplained 40+ point gap. This usually means our data source for that stock is incomplete. We don't suppress (our score might be right — analysts are sometimes wrong), but we flag it prominently.

### L3.2 — Strong analyst sell vs high internal score
- **Trigger:** ≥ 75% of covering analysts rate Sell AND internal score > 65 AND coverage ≥ 3 analysts
- **Action:** MEDIUM (warning)
- **Rationale:** If professional analysts are strongly bearish but our system scores the stock above 65, our score may be inflated — possibly by positive momentum signals ignoring deteriorating fundamentals.

---

## RECOMMENDATION VERIFICATION

Applied after trust score verification. Ensures the displayed recommendation
is consistent with the score.

### R1 — Auto-disqualified always SELL
- **Trigger:** `auto_disqualified == True` AND rec ≠ "SELL"
- **Action:** Force rec to "SELL", log the correction
- **Rationale:** No recommendation other than SELL is defensible for an auto-disqualified stock. This is a hard rule.

### R2 — Score None → no recommendation
- **Trigger:** `score is None`
- **Action:** Rec becomes "—"
- **Rationale:** Cannot recommend action without a score.

### R3 — BUY with low score
- **Trigger:** rec in ("BUY", "STRONG BUY") AND score < 40
- **Action:** Downgrade to "HOLD", log the correction
- **Rationale:** A BUY recommendation on a Blocked/Weak stock is internally contradictory. The trust score explicitly says the stock has significant problems.

### R4 — SELL with high score
- **Trigger:** rec == "SELL" AND score ≥ 70
- **Action:** Upgrade to "HOLD", log the correction
- **Rationale:** A SELL recommendation on a Strong/Exceptional stock is internally contradictory. Something in the signal chain conflated today's price movement with long-term position management.

---

## SMART PICKS GATE

Every candidate passes 5 checks before appearing in /api/picks.

### P1 — Data quality
- **Trigger:** data_quality == "unavailable"
- **Action:** Reject
- **Rationale:** Cannot verify a pick we don't have data for.

### P2 — Score threshold (strict)
- **Trigger:** score < 75 (not 74, not None)
- **Action:** Reject
- **Rationale:** The threshold is intentionally strict. A pick appearing on this screen implies conviction. 74 is not conviction.

### P3 — No auto-disqualified picks
- **Trigger:** auto_disqualified == True
- **Action:** Reject
- **Rationale:** Auto-disqualified stocks go to the Blocked section, never Smart Picks.

### P4 — Market cap present
- **Trigger:** market_cap == 0
- **Action:** Reject
- **Rationale:** Cannot validate a pick without pricing/sizing data. This screens out unlisted or pre-IPO stocks that occasionally appear in data feeds.

### P5 — Large-cap sanity (redundant with L2.2 but belt-and-suspenders)
- **Trigger:** market_cap > $50B AND score < 30
- **Action:** Reject
- **Rationale:** Double-gate. If L2.2 didn't catch it, P5 will.

---

## AI TEXT VERIFICATION

Applied to all AI-generated verdicts and strategy playbooks.

### T1 — Text too short
- **Trigger:** text length < 50 characters
- **Action:** Replace with "Analysis pending for {ticker}" message
- **Rationale:** A verdict under 50 chars is either a truncation error or an empty response.

### T2 — No numbers (no specifics)
- **Trigger:** text contains zero digit characters
- **Action:** Replace with "Insufficient specific data" message
- **Rationale:** Any defensible verdict for a real stock must contain at least one specific number — a price, a percentage, a date, a score. Pure text with no numbers is almost certainly generic.

### T3 — Generic boilerplate detected
- **Trigger:** text contains known generic advisory phrases
  ("consult a financial advisor", "past performance is not indicative", etc.)
- **Action:** MEDIUM — pass through with log entry, don't suppress
- **Rationale:** Generic disclaimers don't necessarily invalidate the rest of the analysis. We flag but don't remove the full text.

---

## WATCHLIST SIGNAL VERIFICATION

### W1 — Data unavailable
- **Trigger:** data_quality == "unavailable" OR score is None
- **Action:** Signal → "No fundamental data — monitor manually", group → "watching"

### W2 — Auto-disqualified
- **Trigger:** auto_disqualified == True
- **Action:** Signal → "Auto-disqualified — do not buy", group → "avoid"

### W3 — "Ready" with low score
- **Trigger:** wl_group == "ready" AND score < 70
- **Action:** Move to "watching", update signal text
- **Rationale:** "Ready to Buy" implies all conditions are met. Score < 70 means they aren't.

### W4 — "Avoid" with high score
- **Trigger:** wl_group == "avoid" AND score ≥ 70 AND no auto-disq
- **Action:** Move to "watching", update signal text
- **Rationale:** "Don't Buy" group is for red flags. A score ≥ 70 with no disqualifier means conditions improved — the avoid label would mislead.

---

## SUPPRESSION LOG

Every verification decision is written to:
- **In-memory:** `_MEMORY_LOG` (ring buffer, 500 entries) — for API audit endpoint
- **File:** `backend/verification_log.jsonl` (append-only) — for post-session analysis

**API endpoints:**
- `GET /api/verification/log?limit=100` — last N decisions (newest first)
- `GET /api/verification/summary` — aggregate stats (total, HIGH/MEDIUM/SUPPRESSED counts, by type)

**Log entry schema:**
```json
{
  "ts": 1716111600.0,
  "ticker": "INFY.NS",
  "output_type": "trust_score",
  "confidence": "SUPPRESSED",
  "score": 19,
  "suppression_reason": "L2_large_cap_floor_fail: market_cap $80B but score=19",
  "warnings": ["L2_large_cap_floor_fail: ..."]
}
```

---

## THRESHOLDS (configurable in verification.py)

| Constant | Value | Purpose |
|----------|-------|---------|
| `LARGE_CAP_USD` | $50B | Market cap above which L2.2 floor applies |
| `LARGE_CAP_SCORE_FLOOR` | 30 | Minimum score for large-cap without disqualifier |
| `MIN_ANALYST_COVERAGE` | 3 | Minimum analysts for L3 consensus check |
| `ANALYST_CONSENSUS_THRESHOLD` | 0.75 | Fraction for "strong consensus" |
| `ANALYST_SCORE_GAP` | 30 | Max unexplained score deviation from consensus |

---

## WHAT THIS LAYER DOES NOT DO

1. **It does not call new external APIs.** All data used for verification was already fetched by the trust engine. Adding API calls would slow every request unacceptably.

2. **It does not override auto-disqualifiers.** The auto-disqualifier system in `_check_auto_disqualifiers` is a separate, independent layer. Verification runs after it.

3. **It does not guarantee correctness.** It reduces the probability of misleading outputs. A stock with $51B market cap and a legitimate score of 28 (e.g. deep distress, near-bankruptcy) would currently trigger L2.2. The fix is an active auto-disqualifier — "going concern warning" should fire before a large-cap reaches score 28 legitimately.

4. **It does not replace fundamental data quality improvements.** The verification layer is a safety net, not a substitute for fixing data-fetch reliability. Data quality fixes (yfinance fallback, short TTL for failed fetches) are the primary defense.
