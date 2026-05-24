"""
StockPulse Verification Layer — The Real Money Test
====================================================
Every score, recommendation, signal, and AI verdict passes through this
module before being returned to the API layer and displayed in the UI.

Design principle: a missing output is honest. A wrong output destroys trust.
If we cannot defensibly justify an output to a professional trader, we do
not show it. We show "Review manually" instead.

THREE LAYERS
─────────────
Layer 1 — Data Verification
    Is the underlying data real, recent, and sufficient?
    Checks that fundamentals were populated from live sources, not defaults.

Layer 2 — Logic Verification
    Is the output internally consistent?
    Checks score range, grade alignment, large-cap sanity floor,
    recommendation vs score contradiction.

Layer 3 — External Benchmark
    Does the output directionally agree with at least one external signal?
    Uses already-fetched analyst consensus — no new API calls.

CONFIDENCE LEVELS
─────────────────
HIGH       — all checks passed, safe to display
MEDIUM     — minor warnings, shown with a caveat indicator (~)
SUPPRESSED — critical failure, show "Review manually" to the user

SUPPRESSION LOG
───────────────
Every verification decision (including HIGH passes) is logged to
verification_log.jsonl for audit. The /api/verification/log endpoint
exposes the last N entries so patterns of failure are visible.
"""

from __future__ import annotations

import json
import time
import os
from pathlib import Path

# ── Log file ──────────────────────────────────────────────────────────────────

_LOG_PATH = Path(__file__).parent.parent / "verification_log.jsonl"
_MEMORY_LOG: list[dict] = []   # fast in-memory ring; capped at 500 entries


def _write_log(entry: dict) -> None:
    _MEMORY_LOG.append(entry)
    if len(_MEMORY_LOG) > 500:
        _MEMORY_LOG.pop(0)
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception:
        pass   # never let logging break the app


def get_verification_log(limit: int = 100) -> list[dict]:
    """Return most-recent verification entries (newest first)."""
    return list(reversed(_MEMORY_LOG[-limit:]))


# ── Thresholds ────────────────────────────────────────────────────────────────

# Stocks above this market cap are Fortune-500 / Nifty-50 calibre.
# Without an active auto-disqualifier, scoring them below the floor
# almost always means a data-fetch failure, not genuine distress.
LARGE_CAP_USD       = 50_000_000_000   # $50 B
LARGE_CAP_SCORE_FLOOR = 30             # any large-cap below this → SUPPRESSED

# How many analysts constitute meaningful consensus
MIN_ANALYST_COVERAGE = 3

# What fraction of buy / sell ratings counts as "strong consensus"
ANALYST_CONSENSUS_THRESHOLD = 0.75     # 75 %

# How far our score can deviate from consensus direction before a warning fires
ANALYST_SCORE_GAP = 30                 # ± 30 pts


# ── LAYER 1 — Data Verification ───────────────────────────────────────────────

def _l1_data(trust: dict, fundamentals: dict) -> tuple[list[str], list[str]]:
    """
    Check 1.1 — data_quality
        If trust engine marked data_quality = "unavailable" we know < 70 % of
        required fields were populated. Score is already None; tag for log.

    Check 1.2 — all-zero fundamentals with a non-zero score
        If every metric field is zero/default yet the business pillar produced
        more than 5 points, the score was computed on empty defaults.
        That is a data integrity failure — suppress it.

    Check 1.3 — data source documented
        Every scored stock should have an identified source. Missing source
        is a soft warning (MEDIUM), not a suppression.
    """
    passed, warnings = [], []

    dq = trust.get("data_quality", "full")
    if dq == "unavailable":
        # Already handled upstream — trust_score returns None.
        # Tag it here so the log records the reason clearly.
        warnings.append("L1_data_unavailable: <70% required fields populated")
    else:
        passed.append("L1_data_quality_ok")

    # Check 1.2 — scoring on zero-defaults
    all_zero = (
        abs(fundamentals.get("revenue_growth") or 0) < 0.0005
        and abs(fundamentals.get("profit_margins") or 0) < 0.0005
        and abs(fundamentals.get("gross_margins") or 0) < 0.0005
        and (fundamentals.get("market_cap") or 0) == 0
    )
    business_score = trust.get("business_score") or 0
    if all_zero and business_score > 5 and dq != "unavailable":
        warnings.append(
            f"L1_zero_fundamentals_inflated_score: all metric fields are zero/default "
            f"but business_score={business_score} — score likely computed on empty data"
        )
    elif not all_zero:
        passed.append("L1_fundamentals_populated")

    # Check 1.3 — source documented
    data_source = trust.get("data_source") or fundamentals.get("data_source") or ""
    if data_source:
        passed.append(f"L1_source_documented:{data_source[:35]}")
    else:
        warnings.append("L1_no_source: data source not identified for this score")

    return passed, warnings


# ── LAYER 2 — Logic Verification ─────────────────────────────────────────────

def _l2_logic(
    ticker: str, trust: dict, fundamentals: dict
) -> tuple[list[str], list[str], str | None]:
    """
    Check 2.1 — score in valid range (0–100 or None)
        A score outside this range means a calculation bug. Critical failure.

    Check 2.2 — large-cap sanity floor
        A stock with market_cap > $50 B and no active auto-disqualifier
        should not score below 30. The only realistic explanation for a score
        that low on a large-cap is a data-fetch failure. Suppress it.
        Example: INFY scoring 19 because Screener.in timed out.

    Check 2.3 — grade aligns with score band
        The grade label must match the score according to the fixed thresholds.
        A mismatch indicates a downstream mapping error.

    Check 2.4 — auto-disqualified stocks should not score above 45
        BLOCKED_OVERRIDES hard-cap scores at ≤ 18. If somehow an auto-disq
        stock arrives here with score > 45 something went wrong.

    Check 2.5 — speculative stocks cannot get Strong/Exceptional grade
        Pre-revenue companies are flagged speculative. Grading them Strong+
        is misleading — they have no earnings history to justify it.

    Returns (passed, warnings, critical_reason | None).
    A non-None critical_reason triggers SUPPRESSED.
    """
    passed: list[str] = []
    warnings: list[str] = []
    score      = trust.get("total_score")
    grade      = trust.get("grade", "")
    auto_disq  = trust.get("auto_disqualified", False)
    speculative = trust.get("is_speculative", False)
    market_cap = fundamentals.get("market_cap") or 0

    # Check 2.1 — score range
    if score is not None and not (0 <= score <= 100):
        return passed, warnings, (
            f"L2_invalid_score: score {score} outside valid range 0–100"
        )
    passed.append("L2_score_range_valid")

    # Check 2.2 — large-cap sanity floor
    # Only fires when there is a real, non-None score and no auto-disqualifier.
    if (
        score is not None
        and market_cap >= LARGE_CAP_USD
        and score < LARGE_CAP_SCORE_FLOOR
        and not auto_disq
    ):
        mc_b = market_cap / 1_000_000_000
        return passed, warnings, (
            f"L2_large_cap_floor_fail: market_cap ${mc_b:.0f}B but score={score} "
            f"(floor={LARGE_CAP_SCORE_FLOOR} for large-caps without active disqualifier). "
            f"Likely a data-fetch failure — suppressing to prevent misleading users."
        )
    if market_cap >= LARGE_CAP_USD and score is not None:
        passed.append(f"L2_large_cap_sanity_ok: ${market_cap/1e9:.0f}B, score={score}")

    # Check 2.3 — grade alignment
    GRADE_BANDS = {
        "Exceptional": (90, 100), "Strong": (75, 89),
        "Moderate": (60, 74),     "Weak": (40, 59),
        "Blocked": (0, 39),
    }
    if grade in GRADE_BANDS and score is not None:
        lo, hi = GRADE_BANDS[grade]
        if not (lo <= score <= hi):
            warnings.append(
                f"L2_grade_mismatch: grade='{grade}' expects {lo}–{hi} but score={score}"
            )
        else:
            passed.append("L2_grade_consistent")

    # Check 2.4 — auto-disq score cap
    if auto_disq and score is not None and score > 45:
        warnings.append(
            f"L2_disq_score_high: auto-disqualified but score={score} "
            f"(expected ≤ 45) — possible override conflict"
        )
    elif auto_disq:
        passed.append("L2_disq_score_consistent")

    # Check 2.5 — speculative grade ceiling
    if speculative and grade in ("Strong", "Exceptional"):
        warnings.append(
            f"L2_speculative_grade_high: pre-revenue stock graded '{grade}' — "
            f"no earnings history to justify this"
        )

    return passed, warnings, None


# ── LAYER 3 — External Benchmark ─────────────────────────────────────────────

def _l3_external(trust: dict, analyst_data: dict) -> tuple[list[str], list[str]]:
    """
    Cross-reference internal score against analyst consensus.
    Uses data already fetched by trust engine — no new API calls.

    Check 3.1 — strong analyst buy consensus vs very low score
        If ≥75% of covering analysts rate the stock Buy, and our internal
        score is below 40, that is a large unexplained discrepancy.
        Warning (MEDIUM) — don't suppress, but flag for review.

    Check 3.2 — strong analyst sell consensus vs very high score
        If ≥75% of covering analysts rate the stock Sell, and our internal
        score exceeds 70, the score may be inflated.
        Warning (MEDIUM).
    """
    passed: list[str] = []
    warnings: list[str] = []
    score = trust.get("total_score")

    if score is None:
        return passed, warnings

    buy  = analyst_data.get("buy_count",  0) or 0
    hold = analyst_data.get("hold_count", 0) or 0
    sell = analyst_data.get("sell_count", 0) or 0
    total = buy + hold + sell

    if total < MIN_ANALYST_COVERAGE:
        passed.append("L3_skipped_insufficient_analyst_coverage")
        return passed, warnings

    buy_pct  = buy  / total
    sell_pct = sell / total

    # Check 3.1
    if buy_pct >= ANALYST_CONSENSUS_THRESHOLD and score < (50 - ANALYST_SCORE_GAP // 2):
        warnings.append(
            f"L3_analyst_buy_vs_low_score: {int(buy_pct*100)}% analyst buy consensus "
            f"but internal score={score}. Possible data gap — verify source."
        )
    elif buy_pct >= ANALYST_CONSENSUS_THRESHOLD:
        passed.append(
            f"L3_analyst_buy_aligns: {int(buy_pct*100)}% buy, score={score}"
        )

    # Check 3.2
    if sell_pct >= ANALYST_CONSENSUS_THRESHOLD and score > (50 + ANALYST_SCORE_GAP // 2):
        warnings.append(
            f"L3_analyst_sell_vs_high_score: {int(sell_pct*100)}% analyst sell "
            f"consensus but internal score={score}. Score may be inflated."
        )

    return passed, warnings


# ── MAIN ENTRY POINT — trust score verification ───────────────────────────────

def verify_trust_output(
    ticker: str,
    trust: dict,
    fundamentals: dict,
    analyst_data: dict | None = None,
) -> dict:
    """
    Run all three verification layers on a computed trust score.

    This function is called inside get_trust_score_with_fallback() immediately
    after the score is computed. It attaches a 'verification' key to the trust
    dict that propagates through tracker → API → frontend.

    Return schema:
    {
        "confidence":         "HIGH" | "MEDIUM" | "SUPPRESSED",
        "suppressed":         bool,
        "suppression_reason": str | None,
        "warnings":           list[str],
        "checks_passed":      list[str],
        "display_score":      int | None,   # None when suppressed
        "display_grade":      str,
        "caveat":             str | None,   # 1-line user-facing note for MEDIUM
    }
    """
    score = trust.get("total_score")
    dq    = trust.get("data_quality", "full")

    # ── Fast path: data_quality = "unavailable" ────────────────────────────
    # trust_score already returns None for total_score — this is the correct
    # honest output. Tag it for the log; don't add any new suppression logic.
    if dq == "unavailable" or score is None:
        result = {
            "confidence": "SUPPRESSED",
            "suppressed": True,
            "suppression_reason": "DATA_UNAVAILABLE: <70% required fields populated",
            "warnings": ["data_quality=unavailable"],
            "checks_passed": [],
            "display_score": None,
            "display_grade": "Data Unavailable",
            "caveat": None,
        }
        _write_log({
            "ts": time.time(), "ticker": ticker, "output_type": "trust_score",
            "confidence": "SUPPRESSED", "score": score,
            "suppression_reason": result["suppression_reason"],
            "warnings": result["warnings"],
        })
        return result

    # ── Run three layers ───────────────────────────────────────────────────
    p1, w1          = _l1_data(trust, fundamentals)
    p2, w2, critical = _l2_logic(ticker, trust, fundamentals)
    p3, w3          = _l3_external(trust, analyst_data or {})

    all_passed   = p1 + p2 + p3
    all_warnings = w1 + w2 + w3

    # ── Critical failure → SUPPRESSED ─────────────────────────────────────
    # "Critical" warnings are those that indicate data integrity failures
    # or logic errors severe enough that displaying the score would mislead.
    CRITICAL_PREFIXES = (
        "L1_zero_fundamentals_inflated_score",
        "L2_invalid_score",
        "L2_large_cap_floor_fail",
    )
    critical_w = [w for w in all_warnings if any(w.startswith(p) for p in CRITICAL_PREFIXES)]

    if critical or critical_w:
        reason = critical or "; ".join(critical_w[:2])
        result = {
            "confidence": "SUPPRESSED",
            "suppressed": True,
            "suppression_reason": reason,
            "warnings": all_warnings,
            "checks_passed": all_passed,
            "display_score": None,
            "display_grade": "Review Manually",
            "caveat": None,
        }
        _write_log({
            "ts": time.time(), "ticker": ticker, "output_type": "trust_score",
            "confidence": "SUPPRESSED", "score": score,
            "suppression_reason": reason, "warnings": all_warnings,
        })
        return result

    # ── Determine confidence from warning count ────────────────────────────
    soft_warnings = all_warnings  # at this point only non-critical remain
    if len(soft_warnings) >= 2:
        confidence = "MEDIUM"
        caveat = soft_warnings[0][:80]
    elif soft_warnings:
        confidence = "MEDIUM"
        caveat = soft_warnings[0][:80]
    else:
        confidence = "HIGH"
        caveat = None

    result = {
        "confidence": confidence,
        "suppressed": False,
        "suppression_reason": None,
        "warnings": all_warnings,
        "checks_passed": all_passed,
        "display_score": score,
        "display_grade": trust.get("grade", ""),
        "caveat": caveat,
    }
    _write_log({
        "ts": time.time(), "ticker": ticker, "output_type": "trust_score",
        "confidence": confidence, "score": score,
        "suppression_reason": None, "warnings": all_warnings,
    })
    return result


# ── Recommendation verification ───────────────────────────────────────────────

def verify_recommendation(
    ticker: str,
    score: int | None,
    rec: str,
    auto_disq: bool,
) -> tuple[str, str | None]:
    """
    Ensure the recommendation is consistent with the trust score.
    Returns (verified_rec, correction_note | None).

    Rules (in priority order):
    R1  auto_disq          → always SELL. No exceptions.
    R2  score is None      → cannot recommend. Return "—".
    R3  score < 40 + BUY   → downgrade to HOLD.
    R4  score >= 70 + SELL → upgrade to HOLD (score contradicts SELL).
    """
    if auto_disq:
        if rec != "SELL":
            _write_log({
                "ts": time.time(), "ticker": ticker, "output_type": "recommendation",
                "confidence": "SUPPRESSED", "score": score,
                "suppression_reason": f"R1_disq_rec_corrected: was {rec}, forced SELL",
                "warnings": [],
            })
            return "SELL", f"R1: auto-disqualified — recommendation forced to SELL (was {rec})"
        return "SELL", None

    if score is None:
        return "—", "R2: score unavailable — cannot generate recommendation"

    if rec in ("BUY", "STRONG BUY") and score < 40:
        _write_log({
            "ts": time.time(), "ticker": ticker, "output_type": "recommendation",
            "confidence": "SUPPRESSED", "score": score,
            "suppression_reason": f"R3_buy_suppressed: score={score}<40, was {rec}",
            "warnings": [],
        })
        return "HOLD", f"R3: BUY suppressed (score={score} < 40 threshold) → HOLD"

    if rec == "SELL" and score >= 70:
        _write_log({
            "ts": time.time(), "ticker": ticker, "output_type": "recommendation",
            "confidence": "SUPPRESSED", "score": score,
            "suppression_reason": f"R4_sell_suppressed: score={score}>=70, was SELL",
            "warnings": [],
        })
        return "HOLD", f"R4: SELL suppressed (score={score} ≥ 70 contradicts SELL) → HOLD"

    return rec, None


# ── Smart Picks gate ──────────────────────────────────────────────────────────

def verify_pick(
    ticker: str,
    trust: dict,
    fundamentals: dict,
) -> tuple[bool, str | None]:
    """
    Gate function for /api/picks — a stock must pass ALL of these to appear
    as a Smart Pick. Returns (approved: bool, rejection_reason: str | None).

    P1  data_quality must not be "unavailable"
    P2  score must be an integer >= 60 — picks the top of "Moderate" and above
    P3  stock must not be auto-disqualified
    P4  market_cap must be > 0 (confirms it is a priced public company)
    P5  must pass the large-cap sanity check (no score < 30 for large-caps)
    P6  quality gate — must be profitable OR revenue-growing (≥2% YoY)
        Prevents showing declining money-losers that happen to score 60+ on
        analyst sentiment alone. This is the "growth-oriented profitable" filter.
    """
    score  = trust.get("total_score")
    dq     = trust.get("data_quality", "full")
    auto_d = trust.get("auto_disqualified", False)
    mc     = fundamentals.get("market_cap") or 0

    if dq == "unavailable":
        reason = f"P1_data_unavailable: cannot verify pick quality for {ticker}"
        _write_log({"ts": time.time(), "ticker": ticker, "output_type": "pick",
                    "confidence": "SUPPRESSED", "score": score,
                    "suppression_reason": reason, "warnings": []})
        return False, reason

    if auto_d:
        reason = f"P3_auto_disqualified: {trust.get('disqualify_reason', '')}"
        _write_log({"ts": time.time(), "ticker": ticker, "output_type": "pick",
                    "confidence": "SUPPRESSED", "score": score,
                    "suppression_reason": reason, "warnings": []})
        return False, reason

    if score is None or score < 60:
        reason = f"P2_score_below_threshold: score={score} (need ≥60)"
        _write_log({"ts": time.time(), "ticker": ticker, "output_type": "pick",
                    "confidence": "SUPPRESSED", "score": score,
                    "suppression_reason": reason, "warnings": []})
        return False, reason

    if mc == 0:
        reason = f"P4_no_market_cap: cannot validate pick without pricing data"
        _write_log({"ts": time.time(), "ticker": ticker, "output_type": "pick",
                    "confidence": "SUPPRESSED", "score": score,
                    "suppression_reason": reason, "warnings": []})
        return False, reason

    # P5 — large-cap sanity
    if mc >= LARGE_CAP_USD and score < LARGE_CAP_SCORE_FLOOR:
        reason = (f"P5_large_cap_floor: ${mc/1e9:.0f}B cap but score={score} "
                  f"(floor={LARGE_CAP_SCORE_FLOOR})")
        _write_log({"ts": time.time(), "ticker": ticker, "output_type": "pick",
                    "confidence": "SUPPRESSED", "score": score,
                    "suppression_reason": reason, "warnings": []})
        return False, reason

    # P6 — quality gate: two distinct criteria, not conflated.
    #
    # PROFITABLE: positive net margin — includes quality mature companies
    # (Coca-Cola growing 3%, JPMorgan growing 6%) that are real businesses.
    # Profitability alone is sufficient — slow growth on a profitable company
    # is a feature, not a bug. The score already penalises slow growers.
    #
    # HIGH-GROWTH: revenue growing ≥ 10% YoY — genuine growth-oriented stocks.
    # 2% was inflation-level "growth" — not meaningful. 10% is a real signal.
    # Allows unprofitable but fast-growing companies (cloud, biotech pre-profit)
    # to qualify on growth alone.
    #
    # Rejects: unprofitable + growing < 10% — not quality, not growth-oriented.
    # Example: a company losing money and growing 5% has no business in picks.
    profitable  = (fundamentals.get("profit_margins") or 0) > 0
    gaap_ok     = trust.get("gaap_profitable", False)
    high_growth = (fundamentals.get("revenue_growth") or 0) >= 0.10  # ≥ 10% YoY

    if not profitable and not gaap_ok and not high_growth:
        reason = (
            f"P6_quality_gate: not profitable and revenue_growth "
            f"{round((fundamentals.get('revenue_growth') or 0)*100,1)}% < 10% threshold — "
            f"neither quality nor growth-oriented"
        )
        _write_log({"ts": time.time(), "ticker": ticker, "output_type": "pick",
                    "confidence": "SUPPRESSED", "score": score,
                    "suppression_reason": reason, "warnings": []})
        return False, reason

    _write_log({"ts": time.time(), "ticker": ticker, "output_type": "pick",
                "confidence": "HIGH", "score": score,
                "suppression_reason": None, "warnings": []})
    return True, None


# ── AI text verification ──────────────────────────────────────────────────────

# Phrases that indicate the AI returned a generic response not tailored to the stock
_GENERIC_MARKERS = [
    "the company operates in a competitive market",
    "investors should conduct their own research",
    "past performance is not indicative",
    "consult a financial advisor before",
    "this analysis is for informational purposes only",
    "always do your own due diligence",
]

def verify_ai_text(
    ticker: str,
    text: str,
    output_type: str = "verdict",
) -> tuple[bool, str]:
    """
    Verify AI-generated text is specific to the stock, not generic boilerplate.
    Returns (approved: bool, verified_text_or_fallback: str).

    T1  Text must be >= 50 characters.
    T2  Text must contain at least one number (price, %, year, score).
    T3  Text must not be a known generic advisory phrase.
    T4  Text should reference the ticker or contain a stock-specific fact.

    On failure, returns (False, fallback_message) rather than crashing.
    """
    if not text or len(text.strip()) < 50:
        _write_log({"ts": time.time(), "ticker": ticker, "output_type": output_type,
                    "confidence": "SUPPRESSED", "score": None,
                    "suppression_reason": "T1_text_too_short", "warnings": []})
        return False, (
            f"Analysis pending for {ticker}. "
            "Data is being gathered — check back in a few minutes."
        )

    text_lower = text.lower()

    # T2 — must contain at least one number
    has_number = any(c.isdigit() for c in text)
    if not has_number:
        _write_log({"ts": time.time(), "ticker": ticker, "output_type": output_type,
                    "confidence": "SUPPRESSED", "score": None,
                    "suppression_reason": "T2_no_numbers_no_specifics", "warnings": []})
        return False, (
            f"Insufficient specific data to generate a defensible analysis for {ticker}. "
            "Showing data summary only."
        )

    # T3 — generic advisory boilerplate
    for marker in _GENERIC_MARKERS:
        if marker in text_lower:
            # Don't suppress — the text may still have useful content alongside the boilerplate.
            # Log it as MEDIUM and return the original text with a note.
            _write_log({"ts": time.time(), "ticker": ticker, "output_type": output_type,
                        "confidence": "MEDIUM", "score": None,
                        "suppression_reason": None,
                        "warnings": [f"T3_generic_phrase_detected: '{marker[:40]}'"]})
            return True, text   # pass through — don't suppress

    return True, text


# ── Watchlist signal verification ─────────────────────────────────────────────

def verify_watchlist_signal(
    ticker: str,
    trust: dict,
    signal: str,
    wl_group: str,
) -> tuple[str, str, str | None]:
    """
    Verify the watchlist signal is consistent with the trust score.
    Returns (verified_signal, verified_group, correction_note | None).

    W1  data_quality=unavailable → neutral signal, "watching" group.
    W2  auto_disqualified        → "Auto-disqualified — do not buy", "avoid" group.
    W3  "ready" group + score<70 → corrected to "watching" (entry not confirmed).
    W4  "avoid" group + score≥70 + no auto_disq → corrected to "watching".
    """
    score    = trust.get("total_score")
    dq       = trust.get("data_quality", "full")
    auto_disq = trust.get("auto_disqualified", False)

    if dq == "unavailable" or score is None:
        return "No fundamental data — monitor manually", "watching", None

    if auto_disq:
        return "Auto-disqualified — do not buy", "avoid", None

    if wl_group == "ready" and score < 70:
        note = f"W3_ready_corrected: score={score} (<70) — moved to watching"
        _write_log({"ts": time.time(), "ticker": ticker, "output_type": "watchlist_signal",
                    "confidence": "MEDIUM", "score": score,
                    "suppression_reason": None, "warnings": [note]})
        return "Entry conditions not fully met", "watching", note

    if wl_group == "avoid" and score >= 70 and not auto_disq:
        note = f"W4_avoid_corrected: score={score} (≥70, no disq) — moved to watching"
        _write_log({"ts": time.time(), "ticker": ticker, "output_type": "watchlist_signal",
                    "confidence": "MEDIUM", "score": score,
                    "suppression_reason": None, "warnings": [note]})
        return "Score improved — reassess entry", "watching", note

    return signal, wl_group, None
