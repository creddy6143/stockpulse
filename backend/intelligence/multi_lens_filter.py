"""
Smart Picks Multi-Lens Conviction Scorer
==========================================
35 filters across 3 lenses + safety overlays.
Produces a Conviction Score (0-100) from weighted lens subscores.

ARCHITECTURE
────────────
This module post-processes data already fetched by the scan pipeline.
No additional API calls required — it uses the trust dict, fundamentals
dict, stock history, and patterns that _score_one_ticker() already has.

LENSES
──────
Fundamental   (12 filters, weight 40%)  — business quality gates
Technical     (12 filters, weight 30%)  — price/trend/momentum gates
Analyst       (11 filters, weight 30%)  — smart money & coverage gates
Safety Gates  (3  gates,   hard block)  — instant disqualification

CONVICTION SCORE
────────────────
conviction = fundamental×0.40 + technical×0.30 + analyst×0.30

TIERS
─────
≥ 80   STRONG BUY
≥ 70   BUY
≥ 60   HOLD  (appears in picks)
< 60   drops out of picks entirely

DOWNGRADE RULE
──────────────
If any single lens scores < 50, downgrade to HOLD with 'Mixed signals' tag,
regardless of the composite score.
"""
from __future__ import annotations
from typing import Optional

# ── Sector P/E medians (consistent with dip_filter) ──────────────────────────
SECTOR_PE_MEDIANS: dict[str, float] = {
    "Information Technology": 32.0,
    "Health Care": 22.0,
    "Financials": 14.0,
    "Consumer Discretionary": 25.0,
    "Consumer Staples": 22.0,
    "Industrials": 24.0,
    "Energy": 15.0,
    "Materials": 18.0,
    "Utilities": 20.0,
    "Real Estate": 40.0,
    "Communication Services": 22.0,
    "Diversified": 22.0,
}

BAD_PATTERNS = {"dead_cat", "falling_knife"}


def _f(fid: int, name: str, lens: str, status: str, value=None, threshold: str = "", note: str = "") -> dict:
    return {
        "id": fid,
        "name": name,
        "lens": lens,
        "status": status,           # PASS | FAIL | UNKNOWN
        "value": str(value) if value is not None else None,
        "threshold": threshold,
        "note": note,
    }


def _compute_rsi(closes: list, period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    for i in range(period, len(closes) - 1):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return round(100 - 100 / (1 + rs), 1)


def compute_conviction_score(
    ticker: str,
    trust: dict,
    fundamentals: dict,
    hist: dict,
    price: float,
    patterns: list,
    sector: str = "Diversified",
) -> dict:
    """
    Compute the 35-filter Conviction Score for a Smart Pick candidate.

    All 3 lenses contribute to the final score.
    Hard FAIL on safety gates returns immediately with conviction_score=0.

    Returns a dict with conviction_score, recommendation, lens scores,
    filter_results list, and mixed_signals flag.
    """
    filters: list[dict] = []

    # ── Pull out values ───────────────────────────────────────────────────────
    ts        = int(trust.get("total_score") or 0)
    biz       = int(trust.get("business_score") or 0)
    sm        = int(trust.get("smart_money_score") or 0)
    mom       = int(trust.get("momentum_score") or 0)
    auto_disq = bool(trust.get("auto_disqualified", False))
    dq        = trust.get("data_quality", "")
    an_buy    = int(trust.get("analyst_buy") or 0)
    an_hold   = int(trust.get("analyst_hold") or 0)
    an_sell   = int(trust.get("analyst_sell") or 0)
    an_total  = an_buy + an_hold + an_sell

    mc         = int(fundamentals.get("market_cap") or 0)
    rev_gr     = float(fundamentals.get("revenue_growth") or 0)
    pm         = float(fundamentals.get("profit_margins") or 0)
    d2e        = float(fundamentals.get("debt_to_equity") or 0)
    fcf        = int(fundamentals.get("free_cashflow") or 0)
    roe        = float(fundamentals.get("return_on_equity") or 0)
    pe         = fundamentals.get("pe_ratio") or fundamentals.get("forward_pe")
    ma200      = float(fundamentals.get("ma_200d") or 0)
    ma50       = float(fundamentals.get("ma_50d") or 0)
    w52h       = float(fundamentals.get("w52_high") or 0)
    w52l       = float(fundamentals.get("w52_low") or 0)

    prices_raw = hist.get("prices", [])
    closes     = [float(p["price"]) for p in prices_raw if p.get("price")]
    h1m        = float(hist.get("1M") or 0)
    h3m        = float(hist.get("3M") or 0)
    h6m        = float(hist.get("6M") or 0)
    h1y        = float(hist.get("1Y") or 0)
    rsi        = _compute_rsi(closes) if len(closes) >= 16 else None

    pat_names  = {(p.get("pattern") or "").lower() for p in (patterns or [])}
    pe_median  = SECTOR_PE_MEDIANS.get(sector, 22.0)

    # ── SAFETY GATES (instant block — no contribution to score) ──────────────

    # SG1: No auto-disqualifiers
    if auto_disq:
        filters.append(_f(0, "Safety: No auto-disqualifiers", "safety", "FAIL",
                          trust.get("disqualify_reason", "auto-disq"), "clean",
                          "Hard gate — auto-disqualified stocks never appear in Smart Picks"))
        return _zero_result(ticker, filters, "Safety gate: auto-disqualified")

    # SG2: Data quality valid
    if dq == "unavailable":
        filters.append(_f(0, "Safety: Data quality", "safety", "FAIL",
                          dq, "not unavailable"))
        return _zero_result(ticker, filters, "Safety gate: data unavailable")

    # SG3: Trust score ≥ 60 (minimum bar to appear at all)
    if ts < 60:
        filters.append(_f(0, "Safety: Trust ≥ 60", "safety", "FAIL",
                          f"{ts}/100", "≥ 60"))
        return _zero_result(ticker, filters, "Safety gate: trust too low")

    # ── FUNDAMENTAL LENS (F1-F12) ─────────────────────────────────────────────
    fund_pass = 0
    fund_total = 0

    def fund(fid, name, status, value=None, threshold="", note=""):
        nonlocal fund_pass, fund_total
        filters.append(_f(fid, name, "fundamental", status, value, threshold, note))
        fund_total += 1
        if status == "PASS":
            fund_pass += 1

    # F1: Revenue growth ≥ 15% YoY
    if rev_gr == 0.0 and fundamentals.get("revenue_growth") is None:
        fund(1, "Revenue growth ≥ 15% YoY", "UNKNOWN", "—", "≥ 15%", "No revenue data")
        fund_total -= 1  # don't count UNKNOWN in total
    elif rev_gr >= 0.15:
        fund(1, "Revenue growth ≥ 15% YoY", "PASS", f"+{rev_gr*100:.0f}%", "≥ 15%")
    else:
        fund(1, "Revenue growth ≥ 15% YoY", "FAIL", f"{rev_gr*100:.1f}%", "≥ 15%")

    # F2: Business quality score ≥ 28/40 (top 70%)
    if biz >= 28:
        fund(2, "Business quality ≥ 28/40", "PASS", f"{biz}/40", "≥ 28")
    else:
        fund(2, "Business quality ≥ 28/40", "FAIL", f"{biz}/40", "≥ 28")

    # F3: Market cap ≥ $2B (institutional quality threshold)
    if mc == 0:
        fund(3, "Market cap ≥ $2B", "UNKNOWN", "—", "≥ $2B")
        fund_total -= 1
    elif mc >= 2_000_000_000:
        fund(3, "Market cap ≥ $2B", "PASS", f"${mc/1e9:.1f}B", "≥ $2B")
    else:
        fund(3, "Market cap ≥ $2B", "FAIL", f"${mc/1e6:.0f}M", "≥ $2B")

    # F4: Free Cash Flow positive
    if fcf == 0 and fundamentals.get("free_cashflow") is None:
        fund(4, "Free cash flow positive", "UNKNOWN", "—", "> 0")
        fund_total -= 1
    elif fcf > 0:
        fund(4, "Free cash flow positive", "PASS", f"${fcf/1e6:.0f}M", "> 0")
    else:
        fund(4, "Free cash flow positive", "FAIL", f"${fcf/1e6:.0f}M", "> 0",
             "Negative FCF — cash burn without return")

    # F5: Debt-to-equity < 2.0
    if d2e == 0 and fundamentals.get("debt_to_equity") is None:
        fund(5, "Debt/equity < 2.0", "UNKNOWN", "—", "< 2.0")
        fund_total -= 1
    elif d2e < 2.0:
        fund(5, "Debt/equity < 2.0", "PASS", f"{d2e:.1f}x", "< 2.0")
    else:
        fund(5, "Debt/equity < 2.0", "FAIL", f"{d2e:.1f}x", "< 2.0")

    # F6: Return on equity ≥ 10%
    if roe == 0.0 and fundamentals.get("return_on_equity") is None:
        fund(6, "Return on equity ≥ 10%", "UNKNOWN", "—", "≥ 10%")
        fund_total -= 1
    elif roe >= 0.10:
        fund(6, "Return on equity ≥ 10%", "PASS", f"{roe*100:.0f}%", "≥ 10%")
    else:
        fund(6, "Return on equity ≥ 10%", "FAIL", f"{roe*100:.1f}%", "≥ 10%")

    # F7: Profit margin ≥ 5%
    if pm == 0.0 and fundamentals.get("profit_margins") is None:
        fund(7, "Profit margin ≥ 5%", "UNKNOWN", "—", "≥ 5%")
        fund_total -= 1
    elif pm >= 0.05:
        fund(7, "Profit margin ≥ 5%", "PASS", f"{pm*100:.1f}%", "≥ 5%")
    else:
        fund(7, "Profit margin ≥ 5%", "FAIL", f"{pm*100:.1f}%", "≥ 5%",
             "Below profitability threshold")

    # F8: P/E ≤ 2x sector median (reasonable valuation)
    if pe is None:
        fund(8, "Valuation: P/E ≤ 2× sector median", "UNKNOWN", "—",
             f"≤ {pe_median*2:.0f}x")
        fund_total -= 1
    else:
        pe_f = float(pe)
        limit = pe_median * 2.0
        if 0 < pe_f <= limit:
            fund(8, "Valuation: P/E ≤ 2× sector median", "PASS",
                 f"{pe_f:.0f}x", f"≤ {limit:.0f}x")
        elif pe_f <= 0:
            fund(8, "Valuation: P/E ≤ 2× sector median", "UNKNOWN",
                 f"{pe_f:.0f}x", f"≤ {limit:.0f}x", "Negative or zero P/E")
            fund_total -= 1
        else:
            fund(8, "Valuation: P/E ≤ 2× sector median", "FAIL",
                 f"{pe_f:.0f}x", f"≤ {limit:.0f}x")

    # F9: Revenue growth accelerating or strong (≥ 20% = accelerating)
    if rev_gr >= 0.20:
        fund(9, "Revenue acceleration ≥ 20%", "PASS", f"+{rev_gr*100:.0f}%", "≥ 20%",
             "High-growth trajectory")
    elif rev_gr >= 0.10:
        fund(9, "Revenue acceleration ≥ 20%", "FAIL", f"+{rev_gr*100:.0f}%", "≥ 20%",
             "Growing but not accelerating")
    elif fundamentals.get("revenue_growth") is None:
        fund(9, "Revenue acceleration ≥ 20%", "UNKNOWN", "—", "≥ 20%")
        fund_total -= 1
    else:
        fund(9, "Revenue acceleration ≥ 20%", "FAIL", f"{rev_gr*100:.1f}%", "≥ 20%")

    # F10: Earnings quality — business score ≥ 25 (beat-rate proxy)
    if biz >= 25:
        fund(10, "Earnings beat-rate (proxy ≥ 25/40)", "PASS", f"{biz}/40", "≥ 25")
    else:
        fund(10, "Earnings beat-rate (proxy ≥ 25/40)", "FAIL", f"{biz}/40", "≥ 25",
             "Low business quality suggests missed estimates")

    # F11: No going concern / no guidance cut (auto_disq reason check)
    disq_rsn = (trust.get("disqualify_reason") or "").lower()
    if "guidance cut" in disq_rsn or "going concern" in disq_rsn:
        fund(11, "No guidance cuts / going concern", "FAIL",
             disq_rsn[:40], "clean")
    else:
        fund(11, "No guidance cuts / going concern", "PASS", "clean", "clean")

    # F12: Total score ≥ 70 (minimum fundamental quality bar)
    if ts >= 75:
        fund(12, "Overall trust ≥ 75 (quality bar)", "PASS", f"{ts}/100", "≥ 75")
    elif ts >= 70:
        fund(12, "Overall trust ≥ 75 (quality bar)", "FAIL", f"{ts}/100", "≥ 75",
             "Meets minimum but not optimal")
    else:
        fund(12, "Overall trust ≥ 75 (quality bar)", "FAIL", f"{ts}/100", "≥ 75")

    # ── TECHNICAL LENS (F13-F24) ──────────────────────────────────────────────
    tech_pass = 0
    tech_total = 0

    def tech(fid, name, status, value=None, threshold="", note=""):
        nonlocal tech_pass, tech_total
        filters.append(_f(fid, name, "technical", status, value, threshold, note))
        tech_total += 1
        if status == "PASS":
            tech_pass += 1

    # F13: Price above MA200 (long-term trend intact)
    if ma200 > 0 and price > 0:
        if price >= ma200:
            tech(13, "Price above 200-day MA", "PASS",
                 f"${price:.2f} > ${ma200:.2f}", "price > MA200")
        else:
            tech(13, "Price above 200-day MA", "FAIL",
                 f"${price:.2f} < ${ma200:.2f}", "price > MA200",
                 "Below long-term trend — bearish signal")
    else:
        tech(13, "Price above 200-day MA", "UNKNOWN", "—", "price > MA200")
        tech_total -= 1

    # F14: MA50 above MA200 (golden cross / uptrend)
    if ma50 > 0 and ma200 > 0:
        if ma50 >= ma200:
            tech(14, "MA50 above MA200 (uptrend)", "PASS",
                 f"MA50 ${ma50:.0f} > MA200 ${ma200:.0f}", "MA50 > MA200")
        else:
            tech(14, "MA50 above MA200 (uptrend)", "FAIL",
                 f"MA50 ${ma50:.0f} < MA200 ${ma200:.0f}", "MA50 > MA200",
                 "Death cross — downtrend signal")
    else:
        tech(14, "MA50 above MA200 (uptrend)", "UNKNOWN", "—", "MA50 > MA200")
        tech_total -= 1

    # F15: Price within 25% of MA50 (not too extended)
    if ma50 > 0 and price > 0:
        pct_from_ma50 = abs(price - ma50) / ma50 * 100
        if pct_from_ma50 <= 25:
            tech(15, "Price within 25% of MA50", "PASS",
                 f"{pct_from_ma50:.1f}% from MA50", "≤ 25%")
        else:
            tech(15, "Price within 25% of MA50", "FAIL",
                 f"{pct_from_ma50:.1f}% from MA50", "≤ 25%",
                 "Too extended from near-term average")
    else:
        tech(15, "Price within 25% of MA50", "UNKNOWN", "—", "≤ 25%")
        tech_total -= 1

    # F16: Not >30% below 52-week high (avoids falling knives)
    if w52h > 0 and price > 0:
        pct_from_high = (w52h - price) / w52h * 100
        if pct_from_high <= 30:
            tech(16, "Within 30% of 52-week high", "PASS",
                 f"{pct_from_high:.0f}% below 52wk high", "≤ 30%")
        else:
            tech(16, "Within 30% of 52-week high", "FAIL",
                 f"{pct_from_high:.0f}% below 52wk high", "≤ 30%",
                 "Fallen too far from highs — possible structural decline")
    else:
        tech(16, "Within 30% of 52-week high", "UNKNOWN", "—", "≤ 30%")
        tech_total -= 1

    # F17: 6-month return ≥ 0%
    if h6m != 0 or hist.get("6M") is not None:
        if h6m >= 0:
            tech(17, "6-month return ≥ 0%", "PASS", f"{h6m:+.1f}%", "≥ 0%")
        else:
            tech(17, "6-month return ≥ 0%", "FAIL", f"{h6m:.1f}%", "≥ 0%",
                 "Negative 6M return — medium-term downtrend")
    else:
        tech(17, "6-month return ≥ 0%", "UNKNOWN", "—", "≥ 0%")
        tech_total -= 1

    # F18: 3-month return ≥ -5% (allows normal volatility)
    if h3m != 0 or hist.get("3M") is not None:
        if h3m >= -5:
            tech(18, "3-month return ≥ -5%", "PASS", f"{h3m:+.1f}%", "≥ -5%")
        else:
            tech(18, "3-month return ≥ -5%", "FAIL", f"{h3m:.1f}%", "≥ -5%",
                 "Significant 3M decline")
    else:
        tech(18, "3-month return ≥ -5%", "UNKNOWN", "—", "≥ -5%")
        tech_total -= 1

    # F19: RSI 40-70 (not overbought, not oversold for a strong pick)
    if rsi is not None:
        if 40 <= rsi <= 70:
            tech(19, "RSI 40-70 (healthy range)", "PASS", f"{rsi:.0f}", "40-70")
        elif rsi > 70:
            tech(19, "RSI 40-70 (healthy range)", "FAIL", f"{rsi:.0f}", "40-70",
                 "Overbought — risk of near-term pullback")
        else:
            tech(19, "RSI 40-70 (healthy range)", "FAIL", f"{rsi:.0f}", "40-70",
                 "Oversold — momentum broken")
    else:
        tech(19, "RSI 40-70 (healthy range)", "UNKNOWN", "—", "40-70")
        tech_total -= 1

    # F20: Momentum score ≥ 15/25
    if mom >= 15:
        tech(20, "Momentum score ≥ 15/25", "PASS", f"{mom}/25", "≥ 15")
    else:
        tech(20, "Momentum score ≥ 15/25", "FAIL", f"{mom}/25", "≥ 15",
             "Weak technical momentum")

    # F21: No dead_cat or falling_knife patterns detected
    bad = pat_names & BAD_PATTERNS
    if bad:
        tech(21, "No bearish reversal patterns", "FAIL",
             ", ".join(bad), "none",
             "Bearish pattern detected — avoid buying dips here")
    else:
        tech(21, "No bearish reversal patterns", "PASS", "clean", "none")

    # F22: Not >40% above MA200 (not dangerously extended)
    if ma200 > 0 and price > 0:
        pct_above = (price - ma200) / ma200 * 100
        if pct_above <= 40:
            tech(22, "Not >40% above MA200", "PASS",
                 f"+{pct_above:.0f}% above MA200", "≤ 40%")
        else:
            tech(22, "Not >40% above MA200", "FAIL",
                 f"+{pct_above:.0f}% above MA200", "≤ 40%",
                 "Too far above long-term average — mean reversion risk")
    else:
        tech(22, "Not >40% above MA200", "UNKNOWN", "—", "≤ 40%")
        tech_total -= 1

    # F23: 1-year return ≥ 5% (long-term winner)
    if h1y != 0 or hist.get("1Y") is not None:
        if h1y >= 5:
            tech(23, "1-year return ≥ 5%", "PASS", f"{h1y:+.1f}%", "≥ 5%")
        else:
            tech(23, "1-year return ≥ 5%", "FAIL", f"{h1y:.1f}%", "≥ 5%",
                 "Negative or flat 1Y — not a compounding story yet")
    else:
        tech(23, "1-year return ≥ 5%", "UNKNOWN", "—", "≥ 5%")
        tech_total -= 1

    # F24: Smart money score ≥ 18/35 (institutional interest)
    if sm >= 18:
        tech(24, "Smart money signal ≥ 18/35", "PASS", f"{sm}/35", "≥ 18",
             "Institutions are interested")
    else:
        tech(24, "Smart money signal ≥ 18/35", "FAIL", f"{sm}/35", "≥ 18",
             "Weak institutional support")

    # ── ANALYST LENS (F25-F35) ────────────────────────────────────────────────
    ana_pass = 0
    ana_total = 0

    def ana(fid, name, status, value=None, threshold="", note=""):
        nonlocal ana_pass, ana_total
        filters.append(_f(fid, name, "analyst", status, value, threshold, note))
        ana_total += 1
        if status == "PASS":
            ana_pass += 1

    # F25: ≥ 60% analyst buy ratings
    if an_total >= 3:
        buy_pct = an_buy / an_total * 100
        if buy_pct >= 60:
            ana(25, "Analyst buy consensus ≥ 60%", "PASS",
                f"{buy_pct:.0f}% buy ({an_buy}/{an_total})", "≥ 60%")
        else:
            ana(25, "Analyst buy consensus ≥ 60%", "FAIL",
                f"{buy_pct:.0f}% buy ({an_buy}/{an_total})", "≥ 60%",
                "Analysts not convinced enough")
    else:
        ana(25, "Analyst buy consensus ≥ 60%", "UNKNOWN",
            f"{an_total} analysts", "≥ 3 analysts first")
        ana_total -= 1

    # F26: Smart money score ≥ 20/35 (institutional conviction)
    if sm >= 20:
        ana(26, "Institutional conviction ≥ 20/35", "PASS", f"{sm}/35", "≥ 20")
    else:
        ana(26, "Institutional conviction ≥ 20/35", "FAIL", f"{sm}/35", "≥ 20",
            "Insufficient institutional backing")

    # F27: Analyst coverage ≥ 5
    if an_total >= 5:
        ana(27, "Analyst coverage ≥ 5 analysts", "PASS", f"{an_total}", "≥ 5",
            "Well-covered by the street")
    elif an_total == 0:
        ana(27, "Analyst coverage ≥ 5 analysts", "UNKNOWN", "0", "≥ 5",
            "No analyst data available")
        ana_total -= 1
    else:
        ana(27, "Analyst coverage ≥ 5 analysts", "FAIL", f"{an_total}", "≥ 5",
            "Under-covered — higher information risk")

    # F28: More buy ratings than sell ratings
    if an_total >= 3:
        if an_buy > an_sell:
            ana(28, "Buys outnumber sells", "PASS",
                f"{an_buy} buy > {an_sell} sell", "buy > sell")
        else:
            ana(28, "Buys outnumber sells", "FAIL",
                f"{an_buy} buy ≤ {an_sell} sell", "buy > sell",
                "Sell ratings dominate — bearish consensus")
    else:
        ana(28, "Buys outnumber sells", "UNKNOWN", "—", "need data")
        ana_total -= 1

    # F29: No hold-heavy consensus (buys > holds)
    if an_total >= 5:
        if an_buy >= an_hold:
            ana(29, "Buys ≥ holds (not 'hold and hope')", "PASS",
                f"{an_buy} buy ≥ {an_hold} hold", "buy ≥ hold")
        else:
            ana(29, "Buys ≥ holds (not 'hold and hope')", "FAIL",
                f"{an_buy} buy < {an_hold} hold", "buy ≥ hold",
                "Majority 'hold' — cautious street view")
    else:
        ana(29, "Buys ≥ holds (not 'hold and hope')", "UNKNOWN", "—", "need data")
        ana_total -= 1

    # F30: Smart money score ≥ 15/35 (minimum institutional interest)
    if sm >= 15:
        ana(30, "Minimum institutional interest ≥ 15/35", "PASS", f"{sm}/35", "≥ 15")
    else:
        ana(30, "Minimum institutional interest ≥ 15/35", "FAIL", f"{sm}/35", "≥ 15")

    # F31: Business score ≥ 20/40 (analyst favourite requires real fundamentals)
    if biz >= 20:
        ana(31, "Business score ≥ 20/40 (analyst credibility)", "PASS",
            f"{biz}/40", "≥ 20")
    else:
        ana(31, "Business score ≥ 20/40 (analyst credibility)", "FAIL",
            f"{biz}/40", "≥ 20",
            "Weak fundamentals undermine analyst buy ratings")

    # F32: No heavy insider selling (smart money score proxy — low score signals selling)
    if sm >= 10:
        ana(32, "No heavy insider selling signal", "PASS", f"SM={sm}/35", "SM ≥ 10")
    else:
        ana(32, "No heavy insider selling signal", "FAIL", f"SM={sm}/35", "SM ≥ 10",
            "Smart money score very low — possible insider distribution")

    # F33: Momentum not broken (momentum score ≥ 10)
    if mom >= 10:
        ana(33, "Momentum not broken ≥ 10/25", "PASS", f"{mom}/25", "≥ 10")
    else:
        ana(33, "Momentum not broken ≥ 10/25", "FAIL", f"{mom}/25", "≥ 10",
            "Momentum collapsed — analysts may be behind the curve")

    # F34: 1-year return ≥ market (≥ 5% as proxy for outperformance)
    if h1y != 0 or hist.get("1Y") is not None:
        if h1y >= 5:
            ana(34, "1Y return ≥ 5% (market outperformer)", "PASS",
                f"{h1y:+.1f}%", "≥ 5%")
        else:
            ana(34, "1Y return ≥ 5% (market outperformer)", "FAIL",
                f"{h1y:.1f}%", "≥ 5%",
                "Underperforming — analyst thesis not playing out")
    else:
        ana(34, "1Y return ≥ 5% (market outperformer)", "UNKNOWN", "—", "≥ 5%")
        ana_total -= 1

    # F35: Total trust ≥ 75 (analysts' favourite stocks have strong fundamentals)
    if ts >= 75:
        ana(35, "Trust ≥ 75 (analyst-quality floor)", "PASS", f"{ts}/100", "≥ 75")
    else:
        ana(35, "Trust ≥ 75 (analyst-quality floor)", "FAIL", f"{ts}/100", "≥ 75",
            "Below threshold analysts expect for strong-buy")

    # ── LENS SCORES (0-100) ────────────────────────────────────────────────────
    fundamental_score = round(fund_pass / max(fund_total, 1) * 100)
    technical_score   = round(tech_pass / max(tech_total, 1) * 100)
    analyst_score     = round(ana_pass  / max(ana_total,  1) * 100)

    conviction_raw = (
        fundamental_score * 0.40 +
        technical_score   * 0.30 +
        analyst_score     * 0.30
    )
    conviction_score = round(conviction_raw)

    # Downgrade rule: any single lens < 50 → cap at 69 (HOLD)
    mixed_signals = any(s < 50 for s in [fundamental_score, technical_score, analyst_score])
    if mixed_signals and conviction_score >= 70:
        conviction_score = 69

    # Cap: if trust < 75, cap at BUY (don't give STRONG BUY to moderate-trust stocks)
    if ts < 75 and conviction_score >= 80:
        conviction_score = 79

    # Recommendation tier
    if conviction_score >= 80:
        recommendation = "STRONG BUY"
    elif conviction_score >= 70:
        recommendation = "BUY"
    elif conviction_score >= 60:
        recommendation = "HOLD"
    else:
        recommendation = "BELOW THRESHOLD"

    total_pass = fund_pass + tech_pass + ana_pass
    total_fail = sum(1 for f2 in filters if f2["status"] == "FAIL")
    total_unk  = sum(1 for f2 in filters if f2["status"] == "UNKNOWN")

    return {
        "conviction_score":   conviction_score,
        "recommendation":     recommendation,
        "fundamental_score":  fundamental_score,
        "technical_score":    technical_score,
        "analyst_score":      analyst_score,
        "mixed_signals":      mixed_signals,
        "filter_results":     filters,
        "filters_passed":     total_pass,
        "filters_failed":     total_fail,
        "filters_unknown":    total_unk,
        "fund_pass":          fund_pass,
        "fund_total":         fund_total,
        "tech_pass":          tech_pass,
        "tech_total":         tech_total,
        "ana_pass":           ana_pass,
        "ana_total":          ana_total,
    }


def _zero_result(ticker: str, filters: list, reason: str) -> dict:
    """Returns a zero-score result for safety-gate failures."""
    return {
        "conviction_score":   0,
        "recommendation":     "BLOCKED",
        "fundamental_score":  0,
        "technical_score":    0,
        "analyst_score":      0,
        "mixed_signals":      False,
        "filter_results":     filters,
        "filters_passed":     0,
        "filters_failed":     len(filters),
        "filters_unknown":    0,
        "fund_pass": 0, "fund_total": 0,
        "tech_pass": 0, "tech_total": 0,
        "ana_pass":  0, "ana_total":  0,
    }
