"""Structural Analog Score engine.

Finds stocks that share the structural setup of an early-winner
within a given theme/sector, BEFORE they have moved.

Analog Score: 5 dimensions (30 / 15 / 25 / 15 / 15)
  1. Sector/Theme Match  (30%)
  2. Size/Stage Match    (15%)
  3. Fundamental Profile (25%)
  4. Sentiment/Coverage  (15%)
  5. Technical Setup     (15%)

"Already Moved" adjustment: if candidate has already captured most of
the reference's 6M gain, it is excluded from results.
"""
from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import logging
logger = logging.getLogger(__name__)

# ── Theme membership data ─────────────────────────────────────────────────────

_THEME_PATH = Path(__file__).parent.parent / "data" / "theme_membership.json"


def _load_themes() -> dict:
    with open(_THEME_PATH, encoding="utf-8") as f:
        return json.load(f)


# ── Country / flag helper ─────────────────────────────────────────────────────

def _flag(ticker: str) -> str:
    t = ticker or ""
    if t.endswith(".NS") or t.endswith(".BO"):
        return "🇮🇳"
    if any(t.endswith(sfx) for sfx in (".AS", ".DE", ".PA", ".ST", ".L", ".F", ".MI", ".SW")):
        return "🇪🇺"
    return "🇺🇸"


# ── Analog Score ──────────────────────────────────────────────────────────────

def _safe(val, default=0.0) -> float:
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def compute_analog_score(
    candidate_ticker: str,
    theme_key: str,
    theme_data: dict,
    cand_fund: dict,
    ref_fund: dict,
    cand_insider: dict,
    cand_history: dict,
    ref_history: dict,
) -> Optional[dict]:
    """Compute an analog score for a candidate against the theme reference.

    Returns None if the candidate should be excluded entirely.
    """

    # ── "Already Moved" gate ─────────────────────────────────────────────────
    ref_6m = _safe(ref_history.get("6M"))
    cand_6m = _safe(cand_history.get("6M"))

    already_moved = False
    if ref_6m > 10 and cand_6m > ref_6m:
        # Candidate already outpaced the reference — exclude entirely
        return None

    if ref_6m > 10 and cand_6m > ref_6m * 0.8:
        already_moved = True   # penalise but don't exclude

    # ── Dimension 1 — Sector / Theme Match (30%) ─────────────────────────────
    # All candidates in the JSON are pre-curated for the theme → 100 base.
    # Penalise if the yfinance sector string is clearly unrelated.
    cand_sector = (cand_fund.get("sector") or "").lower()
    ref_sector  = (ref_fund.get("sector")  or "").lower()
    theme_name  = theme_data.get("name", "").lower()

    # Broad sector family groups — partial overlap is fine
    TECH_WORDS     = {"technology", "software", "semiconductor", "hardware", "communication", "internet", "cloud"}
    HEALTH_WORDS   = {"healthcare", "health", "biotech", "pharmaceutical", "medical"}
    ENERGY_WORDS   = {"energy", "utilities", "oil", "gas", "nuclear", "power", "renewable"}
    FINANCE_WORDS  = {"financial", "finance", "bank", "insurance", "real estate", "reit"}
    DEFENSE_WORDS  = {"defense", "defence", "aerospace", "industrial", "conglomerate"}
    MATERIAL_WORDS = {"materials", "mining", "chemical", "metal", "lithium"}
    CONSUMER_WORDS = {"consumer", "media", "entertainment", "gaming", "retail", "luxury"}
    INDIA_WORDS    = {"india", "emerging"}

    def _family(s: str) -> str:
        for w in TECH_WORDS:
            if w in s: return "tech"
        for w in HEALTH_WORDS:
            if w in s: return "health"
        for w in ENERGY_WORDS:
            if w in s: return "energy"
        for w in FINANCE_WORDS:
            if w in s: return "finance"
        for w in DEFENSE_WORDS:
            if w in s: return "defense"
        for w in MATERIAL_WORDS:
            if w in s: return "material"
        for w in CONSUMER_WORDS:
            if w in s: return "consumer"
        return "other"

    cand_fam = _family(cand_sector)
    ref_fam  = _family(ref_sector)

    if cand_fam == ref_fam and cand_fam != "other":
        dim_theme = 100
    elif cand_fam != "other" and ref_fam != "other":
        dim_theme = 65   # related but different family
    else:
        dim_theme = 80   # unknown sector — give benefit of doubt (pre-curated list)

    # ── Dimension 2 — Size / Stage Match (15%) ───────────────────────────────
    cand_mc = _safe(cand_fund.get("market_cap"))
    ref_mc  = _safe(ref_fund.get("market_cap"))

    if ref_mc > 0 and cand_mc > 0:
        ratio = cand_mc / ref_mc
        if 0.5 <= ratio <= 3.0:
            dim_size = 100
        elif 0.25 <= ratio <= 5.0:
            dim_size = 75
        elif 0.1 <= ratio <= 10.0:
            dim_size = 50
        else:
            dim_size = 25
    else:
        dim_size = 50   # no data

    # Bonus for small/mid-cap laggard (more upside potential)
    if cand_mc > 0 and cand_mc < 10e9:
        dim_size = min(100, dim_size + 10)

    # ── Dimension 3 — Fundamental Profile Match (25%) ────────────────────────
    ref_rev_growth = _safe(ref_fund.get("revenue_growth"))
    ref_profit_mgn = _safe(ref_fund.get("profit_margins"))
    ref_gross_mgn  = _safe(ref_fund.get("gross_margins"))
    ref_de         = _safe(ref_fund.get("debt_to_equity"), default=1.0)

    cand_rev_growth = _safe(cand_fund.get("revenue_growth"))
    cand_profit_mgn = _safe(cand_fund.get("profit_margins"))
    cand_gross_mgn  = _safe(cand_fund.get("gross_margins"))
    cand_de         = _safe(cand_fund.get("debt_to_equity"), default=1.0)

    # Count how many reference fields are valid
    ref_fields = [ref_rev_growth, ref_profit_mgn, ref_gross_mgn]
    valid_ref  = sum(1 for v in ref_fields if v != 0.0)

    if valid_ref < 2:
        # Pre-revenue / sparse reference — skip this dimension
        dim_fundamentals = None
    else:
        # Normalise each metric to 0-100 range then compute RMS distance
        def _norm(v: float, lo: float, hi: float) -> float:
            if hi == lo:
                return 50.0
            return max(0.0, min(100.0, (v - lo) / (hi - lo) * 100))

        # Revenue growth: -50% to +100%
        nr_c = _norm(cand_rev_growth, -50, 100)
        nr_r = _norm(ref_rev_growth,  -50, 100)
        # Profit margin: -100% to +50%
        npm_c = _norm(cand_profit_mgn, -100, 50)
        npm_r = _norm(ref_profit_mgn,  -100, 50)
        # Gross margin: 0% to 100%
        ngm_c = _norm(cand_gross_mgn, 0, 100)
        ngm_r = _norm(ref_gross_mgn,  0, 100)
        # D/E: 0 to 5
        nde_c = _norm(cand_de, 0, 5)
        nde_r = _norm(ref_de,  0, 5)

        rms = math.sqrt(
            ((nr_c - nr_r) ** 2 + (npm_c - npm_r) ** 2 +
             (ngm_c - ngm_r) ** 2 + (nde_c - nde_r) ** 2) / 4
        )
        # RMS distance 0→100: invert so 0 distance = 100 score
        dim_fundamentals = max(0, round(100 - rms))

    # ── Dimension 4 — Sentiment / Coverage Match (15%) ───────────────────────
    analyst_count = _safe(cand_fund.get("analyst_count") or cand_fund.get("number_of_analyst_opinions"))
    inst_buying   = cand_fund.get("institutional_buying") or \
                    (_safe(cand_insider.get("institutional_ownership_pct", 0)) > 20)
    short_pct     = _safe(cand_insider.get("short_interest_pct") or
                           cand_insider.get("short_percent_of_float", 0))
    if short_pct <= 1.0:
        short_pct = short_pct * 100   # fraction → %

    # Under-coverage bonus (more upside when fewer analysts track it)
    if analyst_count == 0:
        cov_score = 80   # no coverage data
    elif analyst_count < 5:
        cov_score = 95   # very under-covered
    elif analyst_count < 15:
        cov_score = 80
    else:
        cov_score = 55   # well-followed → less room for re-rating surprise

    inst_score  = 25 if inst_buying else 0
    short_score = 25 if short_pct < 8 else (15 if short_pct < 15 else 5)

    dim_sentiment = min(100, cov_score // 2 + inst_score + short_score)

    # ── Dimension 5 — Technical Setup Match (15%) ────────────────────────────
    cand_ma200  = _safe(cand_fund.get("ma_200d") or cand_fund.get("ma200"))
    ref_ma200   = _safe(ref_fund.get("ma_200d")  or ref_fund.get("ma200"))
    cand_price  = _safe(cand_fund.get("current_price") or cand_fund.get("price"))
    ref_price   = _safe(ref_fund.get("current_price")  or ref_fund.get("price"))
    cand_rsi    = _safe(cand_fund.get("rsi"))
    ref_rsi     = _safe(ref_fund.get("rsi"))
    cand_w52h   = _safe(cand_fund.get("w52_high") or cand_fund.get("fifty_two_week_high"))
    ref_w52h    = _safe(ref_fund.get("w52_high")  or ref_fund.get("fifty_two_week_high"))
    cand_week   = _safe(cand_history.get("1W"))
    ref_week    = _safe(ref_history.get("1W"))

    tech_pts = 0

    # MA200 position — same side = match
    cand_above_ma = cand_ma200 > 0 and cand_price > cand_ma200
    ref_above_ma  = ref_ma200 > 0 and ref_price > ref_ma200
    if cand_above_ma == ref_above_ma:
        tech_pts += 30

    # RSI similarity
    if cand_rsi > 0 and ref_rsi > 0:
        rsi_diff = abs(cand_rsi - ref_rsi)
        tech_pts += 25 if rsi_diff < 10 else (15 if rsi_diff < 20 else 5)
    else:
        tech_pts += 12   # neutral if no RSI data

    # Distance from 52W high
    cand_off_ath = (cand_price / cand_w52h - 1) * 100 if cand_w52h > 0 and cand_price > 0 else None
    ref_off_ath  = (ref_price  / ref_w52h  - 1) * 100 if ref_w52h > 0 and ref_price > 0 else None

    if cand_off_ath is not None and ref_off_ath is not None:
        # Both < 20% off ATH → match; both well below → match; else mixed
        both_near = cand_off_ath > -20 and ref_off_ath > -20
        both_far  = cand_off_ath < -30 and ref_off_ath < -30
        if both_near or both_far:
            tech_pts += 30
        else:
            tech_pts += 10
    else:
        tech_pts += 15   # neutral

    # Week direction
    same_direction = (cand_week >= 0) == (ref_week >= 0)
    tech_pts += 15 if same_direction else 5

    dim_technical = min(100, tech_pts)

    # ── Weighted total ────────────────────────────────────────────────────────
    if dim_fundamentals is None:
        # Redistribute 25% equally across remaining 4 dims
        # 30+25/4=36.25 / 15+25/4=21.25 / 15+25/4=21.25 / 15+25/4=21.25
        total = (
            dim_theme     * 0.3625 +
            dim_size      * 0.2125 +
            dim_sentiment * 0.2125 +
            dim_technical * 0.2125
        )
        prerevenue_ref = True
        dim_fundamentals_display = None
    else:
        total = (
            dim_theme        * 0.30 +
            dim_size         * 0.15 +
            dim_fundamentals * 0.25 +
            dim_sentiment    * 0.15 +
            dim_technical    * 0.15
        )
        prerevenue_ref = False
        dim_fundamentals_display = dim_fundamentals

    analog_score = round(total)

    # Apply already_moved penalty
    if already_moved:
        analog_score = max(0, analog_score - 15)

    # ── Plain English rationale ───────────────────────────────────────────────
    highlights = []
    if dim_theme >= 90:
        highlights.append("direct sector match")
    elif dim_theme >= 70:
        highlights.append("adjacent sector")
    if dim_size >= 90:
        highlights.append("similar size company")
    elif dim_size >= 60:
        highlights.append("comparable scale")
    if dim_fundamentals_display is not None and dim_fundamentals_display >= 80:
        highlights.append("similar business fundamentals")
    if dim_sentiment >= 80:
        highlights.append("under-covered with institutional backing")
    if dim_technical >= 80:
        highlights.append("matching technical setup")
    if already_moved:
        highlights.append("has already started moving")

    why_matches = (
        f"{', '.join(highlights[:3]).capitalize()}." if highlights else
        f"Curated analog in {theme_data.get('name','this theme')} theme."
    )

    return {
        "analog_score":       analog_score,
        "dim_theme":          dim_theme,
        "dim_size":           dim_size,
        "dim_fundamentals":   dim_fundamentals_display,
        "dim_sentiment":      dim_sentiment,
        "dim_technical":      dim_technical,
        "already_moved":      already_moved,
        "prerevenue_ref":     prerevenue_ref,
        "why_matches":        why_matches,
        "move_ref_6m":        round(ref_6m, 1),
        "move_cand_6m":       round(cand_6m, 1),
        "excluded":           False,
    }


# ── Main entry point ──────────────────────────────────────────────────────────

def build_analogs_response() -> dict:
    """Build the full analogs payload for the /api/analogs endpoint.

    Fetches market data for each theme's early winner and candidates,
    computes analog scores, and packages results.
    """
    # Import here to avoid circular imports at module level
    from data.fetcher import (
        get_fundamentals, get_insider_data, get_stock_history, get_stock_price
    )
    from intelligence.recovery_resilience import compute_recovery_resilience
    from intelligence.trust_score import get_trust_score_with_fallback

    themes_raw = _load_themes()
    result_themes = []
    total_candidates = 0

    for theme_key, theme_data in themes_raw.items():
        ref_ticker  = theme_data.get("early_winner", "")
        candidates  = theme_data.get("candidates", [])

        # ── Fetch reference data ──────────────────────────────────────────────
        try:
            ref_fund    = get_fundamentals(ref_ticker)
            ref_history = get_stock_history(ref_ticker)
        except Exception as exc:
            logger.warning(f"[ANALOGS] ref {ref_ticker} fetch error: {exc}")
            ref_fund    = {}
            ref_history = {"1W": 0, "1M": 0, "3M": 0, "6M": 0, "1Y": 0, "prices": []}

        ref_6m = float(ref_history.get("6M") or 0)

        analogs = []
        for cand in candidates:
            total_candidates += 1
            try:
                cand_fund    = get_fundamentals(cand)
                cand_history = get_stock_history(cand)
                cand_insider = get_insider_data(cand)
                cand_price_d = get_stock_price(cand)
            except Exception as exc:
                logger.warning(f"[ANALOGS] candidate {cand} fetch error: {exc}")
                continue

            score_result = compute_analog_score(
                candidate_ticker=cand,
                theme_key=theme_key,
                theme_data=theme_data,
                cand_fund=cand_fund,
                ref_fund=ref_fund,
                cand_insider=cand_insider,
                cand_history=cand_history,
                ref_history=ref_history,
            )

            if score_result is None:
                # "Already moved" — excluded entirely
                continue

            if score_result["analog_score"] < 35:
                # Too weak a match — skip
                continue

            # Resilience
            try:
                resilience = compute_recovery_resilience(
                    ticker=cand,
                    price_history_obj=cand_history,
                    fundamentals=cand_fund,
                    insider=cand_insider,
                )
            except Exception as exc:
                logger.warning(f"[ANALOGS] resilience {cand}: {exc}")
                resilience = {"score": None, "label": "Insufficient history", "components": {}, "translation": ""}

            # Trust score (best-effort — tolerate errors)
            try:
                trust_result = get_trust_score_with_fallback(cand)
                trust_score  = trust_result.get("total_score") or trust_result.get("score")
                grade        = trust_result.get("grade", "")
            except Exception:
                trust_score = None
                grade       = ""

            # Current price + change
            price     = float(cand_price_d.get("price") or cand_fund.get("current_price") or 0)
            change    = float(cand_price_d.get("change_pct") or 0)
            name      = cand_fund.get("name") or cand_fund.get("company_name") or cand

            analogs.append({
                "ticker":       cand,
                "name":         name,
                "flag":         _flag(cand),
                "price":        round(price, 2),
                "change_pct":   round(change, 2),
                "analog_score": score_result["analog_score"],
                "already_moved": score_result["already_moved"],
                "prerevenue_ref": score_result.get("prerevenue_ref", False),
                "dim_theme":      score_result["dim_theme"],
                "dim_size":       score_result["dim_size"],
                "dim_fundamentals": score_result["dim_fundamentals"],
                "dim_sentiment":  score_result["dim_sentiment"],
                "dim_technical":  score_result["dim_technical"],
                "why_matches":    score_result["why_matches"],
                "move_ref_6m":    score_result["move_ref_6m"],
                "move_cand_6m":   score_result["move_cand_6m"],
                "resilience":     resilience,
                "trust_score":    trust_score,
                "grade":          grade,
            })

        # Sort by analog_score descending
        analogs.sort(key=lambda x: x["analog_score"], reverse=True)

        empty_reason = None
        if not analogs:
            empty_reason = (
                f"No candidates match the structural setup of {ref_ticker} closely enough yet."
            )

        result_themes.append({
            "key":                    theme_key,
            "name":                   theme_data.get("name", theme_key),
            "icon":                   theme_data.get("icon", "📊"),
            "force":                  theme_data.get("force", ""),
            "early_winner":           ref_ticker,
            "early_winner_return_6m": round(ref_6m, 1),
            "filter_pill":            theme_data.get("filter_pill", "All Themes"),
            "risk_level":             theme_data.get("risk_level", "moderate"),
            "analogs":                analogs,
            "empty_reason":           empty_reason,
        })

    return {
        "themes":            result_themes,
        "scanned_at":        datetime.now(timezone.utc).isoformat(),
        "total_candidates":  total_candidates,
    }
