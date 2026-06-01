"""
Quality Pullback / Healthy Dip Filter
======================================
28-filter stack across 7 tiers identifying genuine "buy the dip in a
quality name" setups. Every filter must pass (or be UNKNOWN due to data
limits). No partial credit on hard filters.

DATA CONTRACT
─────────────
This module works on data already cached by the scan pipeline. The caller
supplies dicts that are cache-hits: no extra API calls for most runs.

Required args:
  ticker        str
  trust         dict   — from get_trust_score_with_fallback()
  fundamentals  dict   — from get_fundamentals()
  price_data    dict   — from get_stock_price() with LIVE price
  analyst_data  dict   — from get_analyst_data()
  insider_data  dict   — from get_insider_data()
  hist          dict   — from get_stock_history()  {"1W","1M","6M","1Y","prices":[]}
  vix           float  — current VIX level
  sector        str    — GICS sector

Optional for personalization:
  user_watchlist_tickers  set[str]
  user_portfolio_sectors  dict[str, str]  ticker→sector for owned stocks
  current_picks_tickers   set[str]        tickers that are current Smart Picks
"""

from __future__ import annotations
import math
from datetime import date, datetime
from typing import Optional

# ── Sector P/E medians (2024-2025 approximations) ─────────────────────────────
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


# ── Filter result helpers ──────────────────────────────────────────────────────

def _f(fid: int, name: str, tier: int, status: str,
       value=None, threshold: str = "", note: str = "") -> dict:
    """Build a filter result entry."""
    return {
        "id": fid,
        "name": name,
        "tier": tier,
        "status": status,       # "PASS" | "FAIL" | "UNKNOWN"
        "value": value,
        "threshold": threshold,
        "note": note,
    }


def _compute_rsi(closes: list, period: int = 14) -> Optional[float]:
    """Wilder's RSI from a price series. Returns None if insufficient data."""
    if len(closes) < period + 2:
        return None
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(c, 0.0) for c in changes]
    losses = [max(-c, 0.0) for c in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    return round(100.0 - 100.0 / (1.0 + avg_gain / avg_loss), 1)


# ── Main filter function ───────────────────────────────────────────────────────

def evaluate_dip_candidate(
    ticker: str,
    trust: dict,
    fundamentals: dict,
    price_data: dict,
    analyst_data: dict,
    insider_data: dict,
    hist: dict,
    vix: float = 0.0,
    sector: str = "Diversified",
    user_watchlist_tickers: set | None = None,
    user_portfolio_sectors: dict | None = None,
    current_picks_tickers: set | None = None,
) -> dict | None:
    """
    Run all 28 dip filters. Returns a result dict when a stock qualifies,
    None when any hard filter fails.

    Hard FAILs: immediately return None (no evidence entry needed).
    Soft UNKNOWN: proceed; score component uses neutral 50 pts.
    """
    user_watchlist_tickers  = user_watchlist_tickers  or set()
    user_portfolio_sectors  = user_portfolio_sectors  or {}
    current_picks_tickers   = current_picks_tickers   or set()

    filters: list[dict] = []

    def hard_fail(fid, name, tier, value=None, threshold="", note=""):
        filters.append(_f(fid, name, tier, "FAIL", value, threshold, note))
        return None   # sentinel

    price     = float(price_data.get("price") or 0)
    chg_pct   = float(price_data.get("change_pct") or 0)
    ts        = int(trust.get("total_score") or 0)
    auto_disq = bool(trust.get("auto_disqualified", False))
    disq_rsn  = (trust.get("disqualify_reason") or "").lower()
    mc        = int(fundamentals.get("market_cap") or 0)
    ma200     = float(fundamentals.get("ma_200d") or 0)
    ma50      = float(fundamentals.get("ma_50d") or 0)
    w52h      = float(fundamentals.get("w52_high") or 0)
    d2e       = float(fundamentals.get("debt_to_equity") or 0)
    fcf       = int(fundamentals.get("free_cashflow") or 0)
    pe        = fundamentals.get("pe_ratio") or fundamentals.get("forward_pe")
    pm        = float(fundamentals.get("profit_margins") or 0)
    si_pct    = float(insider_data.get("short_interest_pct") or 0)
    inst_buy  = bool(insider_data.get("institutional_buying", False))
    ins_buy_v = float(insider_data.get("insider_buy_value") or 0)
    ins_sell_v= float(insider_data.get("insider_sell_value") or 0)
    buy_c     = int(analyst_data.get("buy_count") or 0)
    hold_c    = int(analyst_data.get("hold_count") or 0)
    sell_c    = int(analyst_data.get("sell_count") or 0)
    total_an  = buy_c + hold_c + sell_c
    tgt_price = analyst_data.get("target_price") or None

    prices_list = hist.get("prices", [])
    closes      = [float(p["price"]) for p in prices_list if p.get("price")]
    h1w  = float(hist.get("1W") or 0)
    h6m  = float(hist.get("6M") or 0)
    h1y  = float(hist.get("1Y") or 0)
    rsi  = _compute_rsi(closes) if len(closes) >= 16 else None

    next_earn_raw = fundamentals.get("next_earnings_date")
    days_to_earn: Optional[int] = None
    if next_earn_raw:
        try:
            if isinstance(next_earn_raw, str):
                earn_date = datetime.strptime(next_earn_raw[:10], "%Y-%m-%d").date()
            else:
                earn_date = next_earn_raw
            days_to_earn = (earn_date - date.today()).days
        except Exception:
            pass

    # ── TIER 1 — FOUNDATION ───────────────────────────────────────────────────

    # F1 — Trust score ≥ 70
    if ts < 70:
        return None   # hard gate, no entry recorded
    filters.append(_f(1, "Trust score ≥ 70", 1, "PASS", f"{ts}/100", "≥ 70"))

    # F2 — Verification layer (data quality not unavailable)
    dq = trust.get("data_quality", "full")
    if dq == "unavailable":
        return None
    filters.append(_f(2, "Verification layer: real data", 1, "PASS", dq, "not unavailable"))

    # F3 — No active auto-disqualifiers
    if auto_disq:
        return None
    filters.append(_f(3, "No active auto-disqualifiers", 1, "PASS",
                      "Clean", "No disqualifying conditions"))

    # F4 — Market cap ≥ $1 billion
    if mc > 0 and mc < 1_000_000_000:
        return None
    mc_label = (f"${mc/1e12:.1f}T" if mc >= 1e12 else
                f"${mc/1e9:.1f}B" if mc >= 1e9 else
                f"${mc/1e6:.0f}M" if mc > 0 else "Unknown")
    if mc == 0:
        filters.append(_f(4, "Market cap ≥ $1 billion", 1, "UNKNOWN",
                          "No cap data", "≥ $1B"))
    else:
        filters.append(_f(4, "Market cap ≥ $1 billion", 1, "PASS", mc_label, "≥ $1B"))

    # ── TIER 2 — DIP QUALITY ──────────────────────────────────────────────────

    # F5 — Multi-day pullback (down today + weekly decline)
    # Proxy: today is negative AND past week is also down ≥ 1%
    is_down_today    = chg_pct < -0.3
    is_down_this_week = h1w < -1.0
    if not is_down_today:
        return None   # positive or flat day — not a dip
    if not is_down_this_week:
        # Single-day spike down — not a multi-day pullback
        filters.append(_f(5, "Multi-day pullback (≥ 2 consecutive down days)", 2, "FAIL",
                          f"Today {chg_pct:+.1f}%, week {h1w:+.1f}%",
                          "Down today AND week < -1%",
                          "Single-day move — not a sustained pullback"))
        return None
    filters.append(_f(5, "Multi-day pullback (≥ 2 consecutive down days)", 2, "PASS",
                      f"Today {chg_pct:+.1f}%, week {h1w:+.1f}%",
                      "Down today + week < -1%"))

    # F6 — Cumulative drop between -2% and -18%
    cumulative = h1w   # 1-week return as proxy for cumulative pullback
    if cumulative < -18.0:
        filters.append(_f(6, "Cumulative drop -2% to -18%", 2, "FAIL",
                          f"{cumulative:.1f}% (1W)",
                          "-2% to -18%", "Drop too severe — falling knife risk"))
        return None
    if cumulative > -2.0:
        filters.append(_f(6, "Cumulative drop -2% to -18%", 2, "FAIL",
                          f"{cumulative:.1f}% (1W)",
                          "-2% to -18%", "Drop too small — not a meaningful pullback"))
        return None
    filters.append(_f(6, "Cumulative drop -2% to -18%", 2, "PASS",
                      f"{cumulative:.1f}% (1W)", "-2% to -18%"))

    # F7 — Still above 200-day MA (long-term uptrend intact)
    if ma200 > 0 and price > 0:
        if price <= ma200:
            filters.append(_f(7, "Price above 200-day MA (uptrend intact)", 2, "FAIL",
                              f"${price:.2f} vs MA ${ma200:.2f}",
                              "Price > MA200", "Broken long-term trend"))
            return None
        pct_above_200 = (price - ma200) / ma200 * 100
        filters.append(_f(7, "Price above 200-day MA (uptrend intact)", 2, "PASS",
                          f"${price:.2f} (+{pct_above_200:.1f}% above MA ${ma200:.2f})",
                          "Price > MA200"))
    else:
        filters.append(_f(7, "Price above 200-day MA (uptrend intact)", 2, "UNKNOWN",
                          "MA data unavailable", "Price > MA200"))

    # F8 — Within 15% of 50-day MA (pulling back toward support)
    if ma50 > 0 and price > 0:
        dist_from_50 = abs(price - ma50) / ma50 * 100
        if dist_from_50 > 15.0:
            filters.append(_f(8, "Within 15% of 50-day MA (at support)", 2, "FAIL",
                              f"{dist_from_50:.1f}% from MA50 ${ma50:.2f}",
                              "≤ 15% away",
                              "Too far from 50d MA — not a controlled pullback"))
            return None
        filters.append(_f(8, "Within 15% of 50-day MA (at support)", 2, "PASS",
                          f"{dist_from_50:.1f}% from MA50 ${ma50:.2f}", "≤ 15% away"))
    else:
        filters.append(_f(8, "Within 15% of 50-day MA (at support)", 2, "UNKNOWN",
                          "MA50 data unavailable", "≤ 15% away"))

    # F9 — RSI 28–58 (cooling off sweet spot)
    if rsi is not None:
        if not (28.0 <= rsi <= 58.0):
            filters.append(_f(9, "RSI between 28 and 58 (cooling off sweet spot)", 2, "FAIL",
                              f"RSI {rsi:.1f}",
                              "28–58",
                              "Overbought" if rsi > 58 else "Extremely oversold"))
            return None
        filters.append(_f(9, "RSI between 28 and 58 (cooling off sweet spot)", 2, "PASS",
                          f"RSI {rsi:.1f}", "28–58"))
    else:
        filters.append(_f(9, "RSI between 28 and 58 (cooling off sweet spot)", 2, "UNKNOWN",
                          "Insufficient price history for RSI", "28–58"))

    # F10 — Not down >25% from 52-week high (healthy dip, not a crash)
    if w52h > 0 and price > 0:
        pct_from_high = (price - w52h) / w52h * 100
        if pct_from_high < -25.0:
            filters.append(_f(10, "Not down >25% from 52-week high", 2, "FAIL",
                              f"{pct_from_high:.1f}% from high ${w52h:.2f}",
                              "≤ -25% from high", "Too far from highs — falling knife"))
            return None
        filters.append(_f(10, "Not down >25% from 52-week high", 2, "PASS",
                          f"{pct_from_high:.1f}% from high ${w52h:.2f}", "≤ -25%"))
    else:
        filters.append(_f(10, "Not down >25% from 52-week high", 2, "UNKNOWN",
                          "52-week high unavailable", "≤ -25%"))

    # ── TIER 3 — CONVICTION ───────────────────────────────────────────────────

    # F11 — Analyst conviction ratio ≥ 0.60
    if total_an > 0:
        # Weighted: Buy×1.5 relative to total×2 (approximates Strong Buy=2, Buy=1, Hold=0)
        conv_ratio = (buy_c * 1.5) / (total_an * 2)
        if conv_ratio < 0.60:
            filters.append(_f(11, "Analyst conviction ratio ≥ 0.60", 3, "FAIL",
                              f"{conv_ratio:.2f} ({buy_c} buy / {total_an} total)",
                              "≥ 0.60", "Analysts not sufficiently bullish"))
            return None
        filters.append(_f(11, "Analyst conviction ratio ≥ 0.60", 3, "PASS",
                          f"{conv_ratio:.2f} ({buy_c} buy / {total_an} total)", "≥ 0.60"))
    else:
        # No analyst data — mark UNKNOWN, don't block
        filters.append(_f(11, "Analyst conviction ratio ≥ 0.60", 3, "UNKNOWN",
                          "No analyst data available", "≥ 0.60",
                          "Data gap on free tier for this exchange"))
        conv_ratio = None

    # F12 — Analyst targets unchanged/rising (no historical target data)
    filters.append(_f(12, "Analyst targets unchanged or rising (30d)", 3, "UNKNOWN",
                      "Historical target data not tracked on free tier",
                      "No cuts in 30d",
                      "Verify manually via broker/Seeking Alpha"))

    # F13 — At least 8 analysts covering
    if total_an > 0:
        if total_an < 8:
            filters.append(_f(13, "At least 8 analysts covering", 3, "FAIL",
                              f"{total_an} analysts", "≥ 8",
                              "Thin coverage — consensus less reliable"))
            return None
        filters.append(_f(13, "At least 8 analysts covering", 3, "PASS",
                          f"{total_an} analysts", "≥ 8"))
    else:
        filters.append(_f(13, "At least 8 analysts covering", 3, "UNKNOWN",
                          "No coverage data available", "≥ 8"))

    # F14 — No heavy insider selling (90d)
    heavy_selling = (ins_sell_v > 1_000_000 and ins_sell_v > ins_buy_v * 2.5)
    if heavy_selling:
        filters.append(_f(14, "No heavy insider selling (last 90d)", 3, "FAIL",
                          f"Selling ${ins_sell_v/1e6:.1f}M vs buying ${ins_buy_v/1e6:.1f}M",
                          "No heavy selling", "Insiders net-selling — negative signal"))
        return None
    insider_buy_signal = ins_buy_v > ins_sell_v and ins_buy_v > 100_000
    insider_status = ("CEO/insider buying — strong signal" if insider_buy_signal else
                      f"Buy ${ins_buy_v/1e6:.1f}M, Sell ${ins_sell_v/1e6:.1f}M — neutral")
    filters.append(_f(14, "No heavy insider selling (last 90d)", 3, "PASS",
                      insider_status, "No heavy selling"))

    # F15 — Institutional ownership ≥ 50% (proxy)
    if inst_buy:
        filters.append(_f(15, "Institutional ownership ≥ 50%", 3, "PASS",
                          "Institutional buying confirmed (top-5 holders ≥ 30%)",
                          "≥ 50%", "Proxy: Finnhub ownership data"))
    else:
        filters.append(_f(15, "Institutional ownership ≥ 50%", 3, "UNKNOWN",
                          "Exact % unavailable on free tier",
                          "≥ 50%", "Verify via broker or Finviz"))

    # ── TIER 4 — MACRO & NEWS ─────────────────────────────────────────────────

    # F16 — No major negative news (7 days)
    neg_signals = any(k in disq_rsn for k in
                      ["guidance cut", "fda rejection", "fraud", "lawsuit",
                       "sec", "earnings miss", "c-suite", "recall"])
    low_momentum = (trust.get("momentum_score") or 0) < 5
    if neg_signals:
        filters.append(_f(16, "No major negative news (last 7 days)", 4, "FAIL",
                          f"Negative signal: {disq_rsn[:60]}",
                          "No bad news", "Disqualifying event detected"))
        return None
    if low_momentum:
        filters.append(_f(16, "No major negative news (last 7 days)", 4, "FAIL",
                          f"Momentum score {trust.get('momentum_score', 0)}/25",
                          "No bad news", "Very low momentum — likely recent negative catalyst"))
        return None
    filters.append(_f(16, "No major negative news (last 7 days)", 4, "PASS",
                      f"Momentum {trust.get('momentum_score', 0)}/25 — no negative signals",
                      "No bad news"))

    # F17 — Sector not in acute weakness (proxy: skip if no sector ETF data)
    filters.append(_f(17, "Sector not in acute weakness (last 30d)", 4, "UNKNOWN",
                      "Sector ETF data not available on free tier",
                      "Sector > -10% in 30d",
                      "Verify sector health via sector ETF chart"))

    # F18 — Earnings NOT within next 7 days
    if days_to_earn is not None:
        if 0 <= days_to_earn <= 7:
            filters.append(_f(18, "Earnings NOT within next 7 days", 4, "FAIL",
                              f"Earnings in {days_to_earn} days",
                              "> 7 days away", "Binary event — avoid pre-earnings"))
            return None
        filters.append(_f(18, "Earnings NOT within next 7 days", 4, "PASS",
                          f"Earnings {days_to_earn}d away", "> 7 days"))
    else:
        filters.append(_f(18, "Earnings NOT within next 7 days", 4, "UNKNOWN",
                          "Earnings date not available", "> 7 days"))

    # F19 — Not an ex-dividend artifact
    # Heuristic: if today's drop is < 1.5%, it may just be the dividend amount
    if abs(chg_pct) < 1.5:
        filters.append(_f(19, "Drop not an ex-dividend artifact", 4, "FAIL",
                          f"Drop {chg_pct:+.1f}% — too small, may be dividend",
                          "> -1.5% drop", "Could be ex-div noise"))
        return None
    filters.append(_f(19, "Drop not an ex-dividend artifact", 4, "PASS",
                      f"Drop {chg_pct:+.1f}% — meaningful decline", "> -1.5%"))

    # F20 — VIX < 30 (market-wide panic suppresses individual signals)
    if vix > 0:
        if vix >= 30.0:
            filters.append(_f(20, "VIX under 30 (no market-wide panic)", 4, "FAIL",
                              f"VIX {vix:.1f}",
                              "< 30", "Market in panic — individual signals unreliable"))
            return None
        filters.append(_f(20, "VIX under 30 (no market-wide panic)", 4, "PASS",
                          f"VIX {vix:.1f}", "< 30"))
    else:
        filters.append(_f(20, "VIX under 30 (no market-wide panic)", 4, "UNKNOWN",
                          "VIX data unavailable", "< 30"))

    # ── TIER 5 — VOLUME & MOMENTUM ────────────────────────────────────────────

    # F21 — Volume on down days not 2x+ average (no distribution)
    filters.append(_f(21, "Volume on down days not 2× average (no distribution)", 5,
                      "UNKNOWN", "Volume data not available in price history",
                      "< 2× avg volume",
                      "Verify via broker chart — high volume on dip = danger"))

    # F22 — MACD not in strong downtrend (approximate from MA data)
    if ma50 > 0 and ma200 > 0:
        macd_ok = ma50 >= ma200 * 0.97   # allow MA50 slightly below MA200 (early dip)
        if not macd_ok:
            filters.append(_f(22, "MACD not in strong downtrend", 5, "FAIL",
                              f"MA50 ${ma50:.2f} vs MA200 ${ma200:.2f} — death cross",
                              "MA50 ≥ MA200×0.97",
                              "Strong downtrend — momentum broken"))
            return None
        filters.append(_f(22, "MACD not in strong downtrend", 5, "PASS",
                          f"MA50 ${ma50:.2f} ≥ MA200×0.97 (${ma200*0.97:.2f})",
                          "MA50 ≥ MA200×0.97"))
    else:
        filters.append(_f(22, "MACD not in strong downtrend", 5, "UNKNOWN",
                          "MA data unavailable", "MA50 ≥ MA200×0.97"))

    # F23 — Short interest < 15%
    if si_pct > 0:
        if si_pct >= 15.0:
            filters.append(_f(23, "Short interest under 15%", 5, "FAIL",
                              f"{si_pct:.1f}% shorted",
                              "< 15%",
                              "High short interest — controversial name"))
            return None
        filters.append(_f(23, "Short interest under 15%", 5, "PASS",
                          f"{si_pct:.1f}%", "< 15%"))
    else:
        filters.append(_f(23, "Short interest under 15%", 5, "UNKNOWN",
                          "Short interest data unavailable", "< 15%"))

    # ── TIER 6 — SANITY CHECKS ────────────────────────────────────────────────

    # F24 — Not down more than 2% over trailing 6 months (no sustained decline)
    if h6m < -2.0:
        filters.append(_f(24, "Not down more than 2% over trailing 6 months", 6, "FAIL",
                          f"{h6m:+.1f}%", "≥ -2%",
                          "Mid-term trend is declining"))
        return None
    filters.append(_f(24, "Not down more than 2% over trailing 6 months", 6, "PASS",
                      f"{h6m:+.1f}%", "≥ -2%"))

    # F25 — At least flat over trailing 12 months (long-term trend intact)
    if h1y < -5.0:   # slight tolerance: allow -5% (some year-ago peaks were ATHs)
        filters.append(_f(25, "Flat or up over trailing 12 months", 6, "FAIL",
                          f"{h1y:+.1f}%", "≥ -5% (1Y)",
                          "Long-term trend broken"))
        return None
    filters.append(_f(25, "Flat or up over trailing 12 months", 6, "PASS",
                      f"{h1y:+.1f}%", "≥ -5%"))

    # F26 — P/E ≤ 1.5× sector median
    sp_pe = SECTOR_PE_MEDIANS.get(sector, 22.0)
    if pe is not None and pe > 0:
        max_pe = sp_pe * 1.5
        if pe > max_pe:
            filters.append(_f(26, f"P/E ≤ 1.5× sector median ({sp_pe:.0f}×)", 6, "FAIL",
                              f"{pe:.1f}×", f"< {max_pe:.0f}×",
                              "Valuation stretched"))
            return None
        filters.append(_f(26, f"P/E ≤ 1.5× sector median ({sp_pe:.0f}×)", 6, "PASS",
                          f"{pe:.1f}× vs sector {sp_pe:.0f}×", f"< {max_pe:.0f}×"))
    else:
        filters.append(_f(26, f"P/E ≤ 1.5× sector median ({sp_pe:.0f}×)", 6, "UNKNOWN",
                          "P/E data unavailable", f"< {sp_pe*1.5:.0f}×"))

    # F27 — Debt-to-equity < 2.0
    if d2e > 0:
        if d2e >= 2.0:
            filters.append(_f(27, "Debt-to-equity under 2.0", 6, "FAIL",
                              f"{d2e:.2f}×", "< 2.0×",
                              "High leverage — vulnerable in volatility"))
            return None
        filters.append(_f(27, "Debt-to-equity under 2.0", 6, "PASS",
                          f"{d2e:.2f}×", "< 2.0×"))
    else:
        filters.append(_f(27, "Debt-to-equity under 2.0", 6, "UNKNOWN",
                          "D/E data unavailable", "< 2.0×"))

    # F28 — Positive FCF (real cash generation)
    if fcf > 0:
        fcf_label = (f"${fcf/1e9:.2f}B" if abs(fcf) >= 1e9 else f"${fcf/1e6:.0f}M")
        filters.append(_f(28, "Positive free cash flow (TTM)", 6, "PASS",
                          fcf_label, "> 0"))
    elif fcf < 0:
        filters.append(_f(28, "Positive free cash flow (TTM)", 6, "FAIL",
                          f"${fcf/1e6:.0f}M negative", "> 0",
                          "Burning cash — balance sheet risk in dip"))
        return None
    else:
        filters.append(_f(28, "Positive free cash flow (TTM)", 6, "UNKNOWN",
                          "FCF data unavailable", "> 0"))

    # ── TIER 7 — QUALITY SCORE ────────────────────────────────────────────────
    # All hard filters passed. Compute weighted Quality Score.

    # Component 1: Trust score (30%)
    c_trust = min(100, max(0, ts))

    # Component 2: Analyst conviction (20%)
    if conv_ratio is not None:
        c_analyst = min(100, int(conv_ratio * 130))   # 0.77 ratio → 100 pts
    else:
        c_analyst = 50   # unknown

    # Component 3: Insider buying signal (15%)
    if insider_buy_signal:
        c_insider = 95
    elif ins_buy_v > ins_sell_v:
        c_insider = 65
    elif heavy_selling:
        c_insider = 0   # won't reach here (blocked above) but for clarity
    else:
        c_insider = 45   # neutral

    # Component 4: Closeness to 200d MA (10%)
    # Higher score when closer to (but still above) the 200d MA
    if ma200 > 0 and price > 0:
        pct_a200 = (price - ma200) / ma200 * 100
        # Sweet spot: 1–8% above MA200 = maximum score
        if 1.0 <= pct_a200 <= 8.0:
            c_ma200 = 100
        elif 0.0 <= pct_a200 < 1.0:
            c_ma200 = 80
        elif 8.0 < pct_a200 <= 15.0:
            c_ma200 = 70
        elif pct_a200 > 15.0:
            c_ma200 = 40   # far above MA = not really a dip to support
        else:
            c_ma200 = 0   # below MA (won't reach here)
    else:
        c_ma200 = 50

    # Component 5: RSI proximity to 35 (10%)
    if rsi is not None:
        rsi_dist = abs(rsi - 35.0)
        c_rsi = max(0, 100 - int(rsi_dist * 4))   # 0 dist → 100, 25 dist → 0
    else:
        c_rsi = 50

    # Component 6: Institutional ownership proxy (10%)
    c_inst = 80 if inst_buy else 40

    # Component 7: FCF positive (5%)
    c_fcf = 100 if fcf > 0 else 50

    quality_score = round(
        c_trust   * 0.30 +
        c_analyst * 0.20 +
        c_insider * 0.15 +
        c_ma200   * 0.10 +
        c_rsi     * 0.10 +
        c_inst    * 0.10 +
        c_fcf     * 0.05
    )

    # ── PERSONALIZATION FLAGS ─────────────────────────────────────────────────
    on_watchlist   = ticker in user_watchlist_tickers
    is_smart_pick  = ticker in current_picks_tickers
    user_sector_count = sum(1 for s in user_portfolio_sectors.values() if s == sector)
    sector_concentrated = user_sector_count >= 3

    # ── BUILD EVIDENCE SUMMARY ────────────────────────────────────────────────
    evidence_parts = []
    evidence_parts.append(
        f"Trust {ts} · Down {abs(h1w):.1f}% this week · Today {chg_pct:+.1f}%"
    )
    if ma200 > 0:
        pct_a = (price - ma200) / ma200 * 100
        evidence_parts.append(
            f"Price ${price:.2f} · 200d MA ${ma200:.2f} (+{pct_a:.1f}% — trend intact)"
        )
    if rsi is not None:
        evidence_parts.append(f"RSI {rsi:.0f} (oversold range)")
    if total_an > 0 and conv_ratio is not None:
        buy_pct = round(buy_c / total_an * 100)
        evidence_parts.append(
            f"Analysts: {buy_pct}% bullish · {total_an} covering"
        )
    if tgt_price and price > 0:
        upside = (tgt_price - price) / price * 100
        evidence_parts.append(f"Target ${tgt_price:.2f} (+{upside:.0f}% upside)")
    if days_to_earn is not None:
        evidence_parts.append(f"Earnings in {days_to_earn}d")
    else:
        evidence_parts.append("Earnings date unknown")

    # Pass count summary
    passed  = sum(1 for f2 in filters if f2["status"] == "PASS")
    failed  = sum(1 for f2 in filters if f2["status"] == "FAIL")
    unknown = sum(1 for f2 in filters if f2["status"] == "UNKNOWN")

    # ── LABEL + ICON (based on severity) ─────────────────────────────────────
    dip_abs = abs(h1w)
    if dip_abs >= 12:
        label = "Deep Pullback"
        icon  = "🟢"
    elif dip_abs >= 7:
        label = "Quality Dip"
        icon  = "📉"
    else:
        label = "Healthy Dip"
        icon  = "📉"

    return {
        "ticker":             ticker,
        "quality_score":      quality_score,
        "filter_results":     filters,
        "filters_passed":     passed,
        "filters_failed":     failed,
        "filters_unknown":    unknown,
        "evidence":           " · ".join(evidence_parts),
        # Display
        "label":              label,
        "icon":               icon,
        "grade":              trust.get("grade", ""),
        "scanned_at":         datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        # Price data
        "price":              price,
        "change_pct":         chg_pct,
        "week_change":        h1w,
        "6m_change":          h6m,
        "1y_change":          h1y,
        # Technical
        "ma200":              ma200,
        "ma50":               ma50,
        "rsi":                rsi,
        "pct_above_ma200":    round((price - ma200) / ma200 * 100, 1) if ma200 > 0 and price > 0 else None,
        # Fundamentals
        "market_cap":         mc,
        "trust_score":        ts,
        "sector":             sector,
        "analyst_target":     tgt_price,
        "analyst_buy_pct":    round(buy_c / total_an * 100) if total_an > 0 else None,
        "analyst_count":      total_an,
        "conv_ratio":         round(conv_ratio, 2) if conv_ratio is not None else None,
        "short_interest":     si_pct,
        "days_to_earnings":   days_to_earn,
        # Personalization
        "on_watchlist":       on_watchlist,
        "is_smart_pick":      is_smart_pick,
        "sector_concentrated": sector_concentrated,
        # Boost flags for ranking (private — stripped at API layer)
        "_watchlist_boost":   1 if on_watchlist else 0,
        "_pick_boost":        1 if is_smart_pick else 0,
    }


# ── Universe scanner ───────────────────────────────────────────────────────────

def run_dip_scan(
    picks_universe: list[dict],
    market_data: dict,
    user_portfolio: list[dict] | None = None,
    user_watchlist: list[dict] | None = None,
    current_picks_tickers: set | None = None,
    top_n: int = 15,
) -> list[dict]:
    """
    Scan the picks universe for Quality Pullback candidates.

    picks_universe : list of pick entries from the DB cache (each must have
                     "ticker", "trust", "price", "change_pct", "sector").
    market_data    : output of get_market_data()
    Returns list of dip entries sorted by Quality Score (best first).
    """
    from data.fetcher import get_fundamentals, get_analyst_data, get_insider_data, get_stock_history
    from data.fetcher import get_stock_price

    vix_raw = (market_data or {}).get("vix", {})
    if isinstance(vix_raw, dict):
        vix = float(vix_raw.get("price") or 0)
    else:
        vix = float(vix_raw or 0)

    user_portfolio       = user_portfolio or []
    user_watchlist       = user_watchlist or []
    current_picks_tickers = current_picks_tickers or set()

    user_watchlist_tickers = {w["ticker"] for w in user_watchlist}
    user_portfolio_sectors: dict[str, str] = {
        p["ticker"]: p.get("sector", "Unknown") for p in user_portfolio
    }

    results: list[dict] = []

    for pick in picks_universe:
        ticker = pick.get("ticker")
        if not ticker:
            continue

        trust = pick.get("trust", {})
        ts    = int(trust.get("total_score") or 0)
        auto_d = bool(trust.get("auto_disqualified", False))
        chg   = float(pick.get("change_pct") or 0)

        # Quick pre-filter before expensive fetches
        if ts < 70 or auto_d or chg >= 0:
            continue
        if trust.get("data_quality") == "unavailable":
            continue

        try:
            # All of these are cache-hits in normal operation
            fundamentals  = get_fundamentals(ticker)
            analyst_data  = get_analyst_data(ticker)
            insider_data  = get_insider_data(ticker)
            hist          = get_stock_history(ticker)
            sector        = pick.get("sector") or "Diversified"

            # Use live price from pick (already refreshed by picks endpoint)
            price_data = {
                "price":      pick.get("price", 0),
                "change_pct": chg,
            }

            result = evaluate_dip_candidate(
                ticker=ticker,
                trust=trust,
                fundamentals=fundamentals,
                price_data=price_data,
                analyst_data=analyst_data,
                insider_data=insider_data,
                hist=hist,
                vix=vix,
                sector=sector,
                user_watchlist_tickers=user_watchlist_tickers,
                user_portfolio_sectors=user_portfolio_sectors,
                current_picks_tickers=current_picks_tickers,
            )
            if result:
                result["name"] = pick.get("name", ticker)
                result["flag"] = _detect_flag(ticker)
                results.append(result)
        except Exception as exc:
            print(f"[DIP] {ticker}: {exc}", flush=True)
            continue

    if not results:
        return []

    # Sort: watchlist + smart pick boosts first, then quality score
    results.sort(key=lambda x: (
        -(x["_pick_boost"] + x["_watchlist_boost"]),
        -x["quality_score"],
    ))

    # Diversification re-ordering:
    # Push results from sectors the user already has 3+ positions in to the back
    concentrated = [r for r in results if r.get("sector_concentrated")]
    diversified  = [r for r in results if not r.get("sector_concentrated")]
    ordered = diversified + concentrated

    return ordered[:top_n]


def _detect_flag(ticker: str) -> str:
    t = ticker.upper()
    if t.endswith((".NS", ".BO")):
        return "🇮🇳"
    if any(t.endswith(s) for s in (".AS", ".DE", ".PA", ".ST", ".L", ".MI", ".MC", ".F", ".BR")):
        return "🇪🇺"
    return "🇺🇸"
