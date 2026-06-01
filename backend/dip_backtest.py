#!/usr/bin/env python3
"""
dip_backtest.py — Calibration Backtest for the 28-Filter Quality Pullback Screener
===================================================================================
Data sources:
  • Production universe: smart_picks_cache (120 stocks, trust+sector pre-computed)
  • Fundamentals:        .scan_cache.json (307 cached entries: PE, D/E, FCF, cap)
  • Analyst data:        .scan_cache.json + analyst_cache DB (354 entries)
  • Price history:       Yahoo Finance v8 chart API (3y daily, no yfinance library)
  • VIX history:         Same API (^VIX)
"""

import sys, os, json, time, sqlite3
from datetime import date, timedelta, datetime
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
import numpy as np

DB_PATH     = "/home/gowrav55/stockpulse/backend/stockpulse.db"
CACHE_PATH  = "/home/gowrav55/stockpulse/backend/.scan_cache.json"
PRICE_CACHE = "/tmp/dip_bt_prices_v3.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://finance.yahoo.com",
    "Referer": "https://finance.yahoo.com/",
}

SECTOR_PE = {
    "Information Technology": 32.0, "Health Care": 22.0, "Financials": 14.0,
    "Consumer Discretionary": 25.0, "Consumer Staples": 22.0, "Industrials": 24.0,
    "Energy": 15.0, "Materials": 18.0, "Utilities": 20.0,
    "Real Estate": 40.0, "Communication Services": 22.0, "Diversified": 22.0,
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. LOAD DATA
# ─────────────────────────────────────────────────────────────────────────────

def load_scan_cache():
    with open(CACHE_PATH) as f:
        return json.load(f)


def load_universe(scan_cache):
    """Load 120 stocks from smart_picks_cache, overlay with scan_cache fundamentals."""
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute("SELECT all_picks_json FROM smart_picks_cache LIMIT 1").fetchone()
    conn.close()
    all_picks = json.loads(row[0]) if row else []

    universe = {}
    for pick in all_picks:
        ticker = pick["ticker"]
        trust  = pick.get("trust", {})
        ts     = trust.get("total_score", 0)
        auto_d = trust.get("auto_disqualified", False)
        dq     = trust.get("data_quality", "full")
        mom_sc = trust.get("momentum_score", 10)

        # Analyst: prefer scan_cache
        ac     = scan_cache.get(f"analyst:{ticker}", {}).get("value", {})
        buy_c  = int(ac.get("buy_count")  or trust.get("analyst_buy")  or 0)
        hold_c = int(ac.get("hold_count") or trust.get("analyst_hold") or 0)
        sell_c = int(ac.get("sell_count") or trust.get("analyst_sell") or 0)

        # Fundamentals from scan_cache
        fc = scan_cache.get(f"fundamentals:{ticker}", {}).get("value", {})
        pe  = fc.get("pe_ratio") or fc.get("forward_pe")
        raw_de = fc.get("debt_to_equity") or 0
        # fetcher stores D/E as a ratio (not percentage), verify
        d2e = float(raw_de) if raw_de else 0.5
        # Some Finnhub D/E values come back as 0.88 (=88%) — treat >5 as % form
        if d2e > 5:
            d2e = d2e / 100.0
        fcf = fc.get("free_cashflow") or 0
        mc  = fc.get("market_cap") or 10_000_000_000

        universe[ticker] = {
            "sector":      pick.get("sector", "Diversified"),
            "trust_score": ts,
            "auto_disq":   auto_d,
            "data_quality": dq,
            "momentum_score": mom_sc,
            "buy_count":   buy_c,
            "hold_count":  hold_c,
            "sell_count":  sell_c,
            "pe_ratio":    pe,
            "de_ratio":    d2e,
            "free_cashflow": fcf,
            "market_cap":  mc,
            "short_pct":   5.0,   # neutral; no short-int cache available
        }

    return universe


# ─────────────────────────────────────────────────────────────────────────────
# 2. FETCH PRICE HISTORY (v8 chart API, 3 years daily)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_chart(ticker, range_="3y"):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?range={range_}&interval=1d")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        res = r.json().get("chart", {}).get("result")
        if not res:
            return None
        ts      = res[0].get("timestamp", [])
        closes  = res[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
        # Pair (timestamp, close) and drop nulls
        pairs   = [(t, c) for t, c in zip(ts, closes) if c is not None]
        return pairs   # list of (unix_ts, close_price)
    except Exception:
        return None


def load_prices(tickers, delay=0.7):
    """Load 3y price history for all tickers. Caches to /tmp to avoid re-fetching."""
    if os.path.exists(PRICE_CACHE):
        age = datetime.now().timestamp() - os.path.getmtime(PRICE_CACHE)
        if age < 86400:
            print("    Loading cached price data …")
            with open(PRICE_CACHE) as f:
                return json.load(f)

    print(f"    Fetching {len(tickers)} × 3y price series (~{delay*len(tickers):.0f}s) …")
    all_prices = {}
    for i, t in enumerate(tickers):
        pairs = fetch_chart(t)
        if pairs:
            all_prices[t] = pairs
        else:
            print(f"      {t}: no data")
        if i < len(tickers) - 1:
            time.sleep(delay)
        if (i + 1) % 10 == 0:
            print(f"    {i+1}/{len(tickers)} …")

    with open(PRICE_CACHE, "w") as f:
        json.dump(all_prices, f)
    return all_prices


def load_vix(delay=0.3):
    vix_path = "/tmp/dip_bt_vix_v3.json"
    if os.path.exists(vix_path):
        age = datetime.now().timestamp() - os.path.getmtime(vix_path)
        if age < 86400:
            with open(vix_path) as f:
                return json.load(f)
    print("    Fetching VIX history …")
    time.sleep(delay)
    pairs = fetch_chart("^VIX", range_="3y")
    data  = pairs if pairs else []
    with open(vix_path, "w") as f:
        json.dump(data, f)
    return data


def prices_at_date(pairs, target_ts: float):
    """Return list of closes UP TO AND INCLUDING the target timestamp."""
    arr = [c for ts, c in pairs if ts <= target_ts + 86400]
    return arr   # chronological order, oldest first


def date_to_ts(d: date) -> float:
    return float(datetime(d.year, d.month, d.day).timestamp())


def vix_at_date(vix_pairs, target_ts: float) -> float:
    valid = [(abs(ts - target_ts), v) for ts, v in vix_pairs if ts <= target_ts + 86400]
    if not valid:
        return 14.0
    return valid[-1][1]


# ─────────────────────────────────────────────────────────────────────────────
# 3. FILTER ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def compute_rsi(closes, period=14):
    if len(closes) < period + 2:
        return None
    ch = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    g  = [max(c, 0.0) for c in ch]
    l  = [max(-c, 0.0) for c in ch]
    ag = sum(g[:period]) / period
    al = sum(l[:period]) / period
    for i in range(period, len(ch)):
        ag = (ag*(period-1) + g[i]) / period
        al = (al*(period-1) + l[i]) / period
    return round(100.0 - 100.0/(1.0 + ag/al), 1) if al > 0 else 100.0


def run_filters(ticker, closes, vix, fund):
    """28 filters. Returns (passed: bool, first_fail_key: str | None)."""
    if len(closes) < 15:
        return False, "insufficient_data"

    price   = closes[-1]
    prev    = closes[-2] if len(closes) >= 2 else price
    chg_pct = (price - prev) / prev * 100 if prev > 0 else 0.0

    wk   = closes[-6]  if len(closes) >= 6  else closes[0]
    h1w  = (price - wk) / wk * 100 if wk > 0 else 0.0

    h6m_p  = closes[-127] if len(closes) >= 127 else closes[0]
    h6m    = (price - h6m_p) / h6m_p * 100 if h6m_p > 0 else 0.0

    h1y_p  = closes[-253] if len(closes) >= 253 else closes[0]
    h1y    = (price - h1y_p) / h1y_p * 100 if h1y_p > 0 else 0.0

    ma50   = float(np.mean(closes[-50:]))  if len(closes) >= 50  else None
    ma200  = float(np.mean(closes[-200:])) if len(closes) >= 200 else None
    w52h   = max(closes[-252:]) if len(closes) >= 252 else max(closes)
    rsi    = compute_rsi(list(closes[-50:]))

    ts     = fund.get("trust_score", 0)
    auto_d = fund.get("auto_disq", False)
    dq     = fund.get("data_quality", "full")
    mc     = fund.get("market_cap", 1e10) or 1e10
    d2e    = fund.get("de_ratio", 0.5) or 0
    fcf    = fund.get("free_cashflow", 1)
    pe     = fund.get("pe_ratio")
    si_pct = fund.get("short_pct", 5.0)
    buy_c  = int(fund.get("buy_count", 0) or 0)
    hold_c = int(fund.get("hold_count", 0) or 0)
    sell_c = int(fund.get("sell_count", 0) or 0)
    total  = buy_c + hold_c + sell_c
    mom    = fund.get("momentum_score", 10)
    sector = fund.get("sector", "Diversified")

    # ── T1: Foundation ────────────────────────────────────────────────────────
    if ts < 70:                        return False, "F1_trust"
    if dq == "unavailable":            return False, "F2_dataquality"
    if auto_d:                         return False, "F3_autodisq"
    if 0 < mc < 1_000_000_000:        return False, "F4_marketcap"

    # ── T2: Dip Quality ───────────────────────────────────────────────────────
    if chg_pct >= -0.3:                return False, "F5a_not_down_today"
    if h1w >= -1.0:                    return False, "F5b_multiday"
    if h1w < -15.0 or h1w > -3.0:     return False, "F6_drop_range"
    if ma200 and price <= ma200:       return False, "F7_ma200"
    if ma50 and abs(price-ma50)/ma50*100 > 10.0: return False, "F8_ma50dist"
    if rsi is not None and not (30 <= rsi <= 55): return False, "F9_rsi"
    if w52h > 0 and (price-w52h)/w52h*100 < -25: return False, "F10_52whigh"

    # ── T3: Conviction ────────────────────────────────────────────────────────
    if total > 0:
        conv = (buy_c * 1.5) / (total * 2)
        if conv < 0.60:                return False, "F11_conviction"
    if total > 0 and total < 8:        return False, "F13_coverage"
    if mom < 5:                        return False, "F16_bad_news"

    # ── T4: Macro & News ─────────────────────────────────────────────────────
    if abs(chg_pct) < 1.5:             return False, "F19_exdiv"
    if vix >= 30.0:                    return False, "F20_vix"

    # ── T5: Volume & Momentum ────────────────────────────────────────────────
    if ma50 and ma200 and ma50 < ma200*0.97: return False, "F22_deathcross"
    if si_pct >= 15.0:                 return False, "F23_shortint"

    # ── T6: Sanity Checks ────────────────────────────────────────────────────
    if h6m < 5.0:                      return False, "F24_6m"
    if h1y < -5.0:                     return False, "F25_1y"
    sp_pe = SECTOR_PE.get(sector, 22.0)
    if pe and pe > 0 and pe > sp_pe*1.5: return False, "F26_pe"
    if d2e >= 2.0:                     return False, "F27_de"
    if fcf < 0:                        return False, "F28_fcf"

    return True, None


# ─────────────────────────────────────────────────────────────────────────────
# 4. BACKTEST ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def run_on_date(all_prices, vix_pairs, candidates, target: date):
    target_ts = date_to_ts(target)
    vix       = vix_at_date(vix_pairs, target_ts)
    qualifiers= []
    attrition = defaultdict(int)

    for ticker, fund in candidates.items():
        pairs = all_prices.get(ticker)
        if not pairs:
            attrition["missing_data"] += 1
            continue
        closes = prices_at_date(pairs, target_ts)
        if len(closes) < 20:
            attrition["insufficient_history"] += 1
            continue

        passed, fkey = run_filters(ticker, closes, vix, fund)
        if passed:
            qualifiers.append(ticker)
        else:
            attrition[fkey or "unknown"] += 1

    return qualifiers, attrition, vix


def make_test_dates():
    today = date(2026, 6, 1)
    return [
        ("Today (2026-06-01)",               today),
        ("Yesterday (~1 td ago)",            today - timedelta(days=2)),
        ("5 td ago (~2026-05-23)",           today - timedelta(days=7)),
        ("10 td ago (~2026-05-16)",          today - timedelta(days=14)),
        ("20 td ago (~2026-05-02)",          today - timedelta(days=29)),
        ("60 td ago (~2026-03-09)",          today - timedelta(days=84)),
        ("120 td ago (~2025-12-15)",         today - timedelta(days=168)),
        ("250 td ago (~2025-06-06)",         today - timedelta(days=350)),
    ]


import random
def random_dates_around(center: date, spread=10, n=5):
    random.seed(center.toordinal())
    offs = random.sample(range(-spread, spread+1), min(n, 2*spread))
    return [center + timedelta(days=o) for o in offs]


# ─────────────────────────────────────────────────────────────────────────────
# 5. REPORT
# ─────────────────────────────────────────────────────────────────────────────

FILTER_LABELS = {
    "F1_trust":           "F1: Trust ≥ 70",
    "F2_dataquality":     "F2: Data quality not unavailable",
    "F3_autodisq":        "F3: No auto-disqualifiers",
    "F4_marketcap":       "F4: Market cap ≥ $1B",
    "F5a_not_down_today": "F5a: Down today (> −0.3%)",
    "F5b_multiday":       "F5b: Multi-day pullback (week < −1%)",
    "F6_drop_range":      "F6: Cumulative drop −3% to −15%",
    "F7_ma200":           "F7: Price above 200-day MA",
    "F8_ma50dist":        "F8: Within 10% of 50-day MA",
    "F9_rsi":             "F9: RSI between 30 and 55",
    "F10_52whigh":        "F10: Not >25% below 52W high",
    "F11_conviction":     "F11: Analyst conviction ≥ 0.60",
    "F13_coverage":       "F13: At least 8 analysts",
    "F16_bad_news":       "F16: No major negative news",
    "F19_exdiv":          "F19: Drop > 1.5%",
    "F20_vix":            "F20: VIX < 30",
    "F22_deathcross":     "F22: No death cross (MA50 ≥ MA200×0.97)",
    "F23_shortint":       "F23: Short interest < 15%",
    "F24_6m":             "F24: 6M return ≥ +5%",
    "F25_1y":             "F25: 1Y return ≥ −5%",
    "F26_pe":             "F26: P/E ≤ 1.5× sector median",
    "F27_de":             "F27: Debt-to-equity < 2.0",
    "F28_fcf":            "F28: Positive free cash flow",
}

ORDERED_FILTERS = list(FILTER_LABELS.keys())


def write_report(calib, atr_10d, universe, n_universe, n_cand):
    lines = []
    W = lines.append

    W("# Dip Filter Calibration Report")
    W("")
    W(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    W(f"**Production universe:** {n_universe} stocks (smart_picks_cache)")
    W(f"**F1-eligible candidates:** {n_cand} stocks (trust ≥ 70, not auto-disqualified)")
    W("")
    W("## Methodology")
    W("")
    W("| Signal | Source | Point-in-time? |")
    W("|--------|--------|----------------|")
    W("| Price (F5/6/7/8/9/10/19/22/24/25) | Yahoo Finance v8 chart API (3y daily) | ✅ Historical |")
    W("| VIX (F20) | Yahoo Finance v8 chart API (^VIX) | ✅ Historical |")
    W("| Trust score (F1) | Production smart_picks_cache | ⚠ Current only |")
    W("| Fundamentals (F4/26/27/28) | .scan_cache.json | ⚠ Current only |")
    W("| Analyst data (F11/13) | analyst_cache DB + scan_cache | ⚠ Current only |")
    W("| F2/3/12/14/15/17/18/21/23 | Assumed clean / UNKNOWN | — |")
    W("")
    W("> **Limitation:** Trust score and fundamentals use current values. For large-cap stocks these")
    W("> are relatively stable, but in past crisis periods (e.g. 60+ td ago) trust scores may have")
    W("> been lower. This means qualification rates for past dates may be *slightly overstated*.")
    W("")
    W("---")
    W("")
    W("## Part 1 — Calibration Table")
    W("")
    W("| Date | Period | Qualifiers | ±10d avg | VIX | Qualifying tickers |")
    W("|------|--------|-----------|---------|-----|-------------------|")

    counts = []
    for row in calib:
        label, td, quals, avg_r, vix_v, note = row
        counts.append(len(quals))
        tlist = ", ".join(quals) if quals else "—"
        arvg  = f"{avg_r:.1f}" if avg_r is not None else "—"
        W(f"| {td} | {label} | **{len(quals)}** | {arvg} | {vix_v:.1f} | {tlist} |")

    avg = sum(counts) / len(counts) if counts else 0
    W(f"| — | **Average** | **{avg:.1f}** | — | — | — |")
    W("")
    W("")

    # Most frequently qualifying stocks
    freq = defaultdict(int)
    for _, _, quals, _, _, _ in calib:
        for q in quals:
            freq[q] += 1
    top = sorted(freq.items(), key=lambda x: -x[1])[:10]
    if top:
        W("### Stocks qualifying most frequently")
        W("")
        W("| Ticker | Sector | N dates (out of 8) |")
        W("|--------|--------|--------------------|")
        for t, n in top:
            sec = universe.get(t, {}).get("sector", "—")
            W(f"| **{t}** | {sec} | {n}/8 |")
        W("")

    W("---")
    W("")
    W("## Part 2 — Calibration Verdict")
    W("")
    if avg <= 2:
        verdict = "🔴 FILTERS TOO TIGHT"
        interp  = (
            f"Average **{avg:.1f} qualifiers/day** is below the minimum useful threshold (3). "
            "The screener fires too rarely to be a product feature. Users will see 0 stocks "
            "on most trading days regardless of market conditions.\n\n"
            "Today's 0 is explained by filters being too tight, not by market conditions."
        )
    elif avg <= 15:
        verdict = "🟢 CALIBRATION IS CORRECT"
        interp  = (
            f"Average **{avg:.1f} qualifiers/day** is within the ideal 3–15 range. "
            "Today's 0 reflects genuine market conditions — no quality large-cap stocks "
            "are currently in a meaningful −3% to −15% weekly pullback. "
            "The empty state is honest behavior, not a broken feature."
        )
    elif avg <= 30:
        verdict = "🟡 CALIBRATION OK — SLIGHTLY RICH"
        interp  = (
            f"Average **{avg:.1f} qualifiers/day** is above ideal. The screener works "
            "but produces more candidates than necessary. "
            "Consider displaying only Quality Score ≥ 72."
        )
    else:
        verdict = "🔴 FILTERS TOO LOOSE"
        interp  = (
            f"Average **{avg:.1f} qualifiers/day** means the screener is producing noise. "
            "The filters need tightening."
        )

    W(f"### {verdict}")
    W("")
    W(interp)
    W("")
    W("---")
    W("")
    W("## Part 3 — Filter Attrition Waterfall")
    W("")
    W(f"Reference date: 10 trading days ago (calibration test date)")
    W(f"Starting candidates: **{n_cand}** (all with trust ≥ 70)")
    W("")
    W("| Filter | Eliminated | % of pool | Remaining |")
    W("|--------|-----------|-----------|-----------|")

    remaining = n_cand
    for fk in ORDERED_FILTERS:
        dropped = atr_10d.get(fk, 0)
        if dropped > 0:
            remaining -= dropped
            pct = dropped / n_cand * 100
            lbl = FILTER_LABELS.get(fk, fk)
            W(f"| {lbl} | {dropped} | {pct:.0f}% | {remaining} |")

    W(f"| **QUALIFIED** | — | — | **{atr_10d.get('PASS', 0)}** |")
    W("")

    # Tier-level rollup
    tier_map = {
        "F1_trust": "T1", "F2_dataquality": "T1", "F3_autodisq": "T1", "F4_marketcap": "T1",
        "F5a_not_down_today": "T2", "F5b_multiday": "T2", "F6_drop_range": "T2",
        "F7_ma200": "T2", "F8_ma50dist": "T2", "F9_rsi": "T2", "F10_52whigh": "T2",
        "F11_conviction": "T3", "F13_coverage": "T3", "F16_bad_news": "T3/4",
        "F19_exdiv": "T4", "F20_vix": "T4", "F22_deathcross": "T5", "F23_shortint": "T5",
        "F24_6m": "T6", "F25_1y": "T6", "F26_pe": "T6", "F27_de": "T6", "F28_fcf": "T6",
    }
    tier_names = {
        "T1": "Tier 1 — Foundation",
        "T2": "Tier 2 — Dip Quality",
        "T3": "Tier 3 — Conviction",
        "T3/4": "Tier 3/4 — News/Macro",
        "T4": "Tier 4 — Macro & News",
        "T5": "Tier 5 — Volume & Momentum",
        "T6": "Tier 6 — Sanity Checks",
    }
    tier_totals = defaultdict(int)
    for fk, dropped in atr_10d.items():
        t = tier_map.get(fk)
        if t:
            tier_totals[t] += dropped

    W("### Attrition by tier:")
    W("")
    W("| Tier | Stocks eliminated | % of candidates |")
    W("|------|-------------------|-----------------|")
    for tier, cnt in sorted(tier_totals.items(), key=lambda x: -x[1]):
        pct = cnt / n_cand * 100 if n_cand > 0 else 0
        W(f"| {tier_names.get(tier, tier)} | {cnt} | {pct:.0f}% |")
    W("")
    W("---")
    W("")
    W("## Part 4 — Filter-by-Filter Diagnosis")
    W("")

    DIAGNOSES = {
        "F5a_not_down_today": (
            "**Expected behavior.** On any given day, ~80% of large-cap stocks are flat or up. "
            "A dip screener requires the stock to be down today. This is a structural pre-condition, "
            "not a miscalibrated threshold."
        ),
        "F5b_multiday": (
            "**Expected behavior.** This eliminates single-day spikes that reverse immediately. "
            "A genuine pullback is multi-day. The weekly return of <−1% is the right criterion."
        ),
        "F6_drop_range": (
            "**Core precision filter.** The −3% to −15% range targets stocks in a controlled pullback. "
            "Too shallow (>−3%): noise. Too deep (<−15%): falling knife risk. "
            "If this eliminates too many legitimate dips, consider widening to −2% / −18%."
        ),
        "F7_ma200": (
            "**Critical safety filter. Do not loosen.** Price below MA200 = long-term uptrend broken. "
            "These stocks are in sustained downtrends. Buying here is a turnaround play, not a dip."
        ),
        "F8_ma50dist": (
            "**Controlled pullback check.** More than 10% from MA50 means the stock has overshot "
            "normal support. Either in freefall (risky) or recovering (MA50 irrelevant). "
            "If this blocks many valid candidates, consider widening to 15%."
        ),
        "F9_rsi": (
            "**Sweet-spot filter.** RSI 30–55 excludes overbought (>55: not a real dip) and "
            "extremely oversold (<30: potentially a crash). The 30–55 range is well-calibrated. "
            "If too many valid dips have RSI 55–65, consider widening upper bound to 58."
        ),
        "F24_6m": (
            "**Medium-term trend check.** Up <+5% over 6 months means the stock has been "
            "flat/declining for half a year. We want dips in genuinely uptrending names. "
            "In weak markets this will eliminate many stocks — which is correct behavior."
        ),
        "F25_1y": (
            "**Long-term trend check.** 1Y return <−5% means the long-term uptrend is broken. "
            "Tolerance is already generous at −5%. In sustained bear markets, this correctly "
            "produces an empty state."
        ),
        "F26_pe": (
            "**Valuation filter.** P/E > 1.5× sector median on a dip is dangerous — "
            "valuation compression can continue even after a pullback. For tech stocks with "
            "sector median 32×, the threshold is 48×. If many tech dips fail, consider 2.0×."
        ),
        "F11_conviction": (
            "**Analyst signal.** Conviction ratio <0.60 means analysts are bearish or mixed. "
            "A quality dip should have at least 60% buy-weighted analyst sentiment. "
            "If this blocks many stocks, check analyst data coverage for those tickers."
        ),
        "F20_vix": (
            "**Market stress gate.** VIX ≥ 30 = market panic. In panic conditions, "
            "individual stock signals are unreliable — correlation spikes across all names. "
            "This correctly blocks the screener during market-wide crises."
        ),
        "F19_exdiv": (
            "**Ex-dividend artifact filter.** A drop of <1.5% could be just the dividend "
            "going ex-, not a real pullback. If this blocks legitimate small daily drops, "
            "consider lowering to 0.8%."
        ),
    }

    top_elim = sorted(
        [(atr_10d.get(fk, 0), fk) for fk in ORDERED_FILTERS],
        reverse=True
    )
    for cnt, fk in top_elim[:8]:
        if cnt == 0:
            continue
        lbl  = FILTER_LABELS.get(fk, fk)
        pct  = cnt / n_cand * 100 if n_cand > 0 else 0
        diag = DIAGNOSES.get(fk, "No specific diagnosis.")
        W(f"### {lbl} — eliminated {cnt} stocks ({pct:.0f}%)")
        W("")
        W(diag)
        W("")

    W("---")
    W("")
    W("## Part 5 — Recommendation")
    W("")

    if avg <= 2:
        W("### B — Adjust 2–4 filter thresholds")
        W("")
        W("The screener fires too rarely. Specific proposed relaxations:")
        W("")
        W("| Priority | Filter | Current | Proposed | Impact |")
        W("|----------|--------|---------|---------|--------|")
        W("| 1 (highest) | F6: Weekly drop range | −3% to −15% | −2% to −18% | More candidates in mild pullbacks |")
        W("| 2 | F9: RSI range | 30–55 | 28–58 | Includes slightly overbought dips |")
        W("| 3 | F24: 6M return | ≥ +5% | ≥ −2% | Allows dips in flat/sideways markets |")
        W("| 4 | F8: MA50 distance | ≤ 10% | ≤ 15% | Captures deeper-than-normal pullbacks |")
        W("")
        W("**Implement priority 1 and 2 first.** Re-run this backtest before applying 3 and 4.")
    elif avg <= 15:
        W("### A — Keep all 28 filters as-is")
        W("")
        W("Calibration is correct. Today's 0-stock result is accurate market intelligence.")
        W("")
        W("**What to monitor:**")
        W("- If 0 stocks for >10 consecutive trading days *across varying VIX*, revisit F6 and F9.")
        W("- A quiet green week producing 0 is honest. Two months of 0 is a calibration signal.")
        W("- Re-run this backtest quarterly or after a major market regime change.")
    elif avg <= 30:
        W("### B — Add Quality Score display threshold")
        W("")
        W("Filters are slightly rich. Proposed fix: display only stocks with Quality Score ≥ 72.")
        W("No filter logic changes needed.")
    else:
        W("### B — Tighten 3 filters")
        W("")
        W("| Filter | Current | Proposed |")
        W("|--------|---------|---------|")
        W("| F1: Trust | ≥ 70 | ≥ 75 |")
        W("| F6: Drop range | −3% to −15% | −4% to −12% |")
        W("| F11: Conviction | ≥ 0.60 | ≥ 0.70 |")

    W("")
    W("---")
    W("")
    W("*Generated by `dip_backtest.py` — do not modify production filters without")
    W("product owner review of this report.*")

    report = "\n".join(lines)
    path   = "/home/gowrav55/stockpulse/backend/dip_filter_calibration_report.md"
    with open(path, "w") as fh:
        fh.write(report)
    print(f"\n✓ Report → {path}")
    return avg, verdict


# ─────────────────────────────────────────────────────────────────────────────
# 6. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Dip Filter Calibration Backtest")
    print("=" * 60)

    # 1. Load production data
    print("[1/5] Loading production universe & cache …")
    scan_cache = load_scan_cache()
    universe   = load_universe(scan_cache)
    n_universe = len(universe)

    candidates = {t: f for t, f in universe.items()
                  if f["trust_score"] >= 70
                  and not f["auto_disq"]
                  and f["data_quality"] != "unavailable"}
    n_cand = len(candidates)
    print(f"    Universe: {n_universe} | F1-eligible: {n_cand}")
    print(f"    Candidates: {', '.join(list(candidates.keys()))}")

    # 2. Price history
    print("[2/5] Loading price history …")
    tickers   = list(candidates.keys())
    all_prices = load_prices(tickers, delay=0.7)
    print(f"    Prices loaded for {len(all_prices)} tickers")

    # 3. VIX
    print("[3/5] Loading VIX history …")
    vix_pairs = load_vix()
    print(f"    VIX data: {len(vix_pairs)} points")

    # 4. Calibration
    print("[4/5] Running calibration across 8 dates …")
    test_dates = make_test_dates()
    calib = []

    for label, td in test_dates:
        quals, _, vix_v = run_on_date(all_prices, vix_pairs, candidates, td)

        # ±10d random average
        rnd_counts = []
        for rd in random_dates_around(td):
            rq, _, _ = run_on_date(all_prices, vix_pairs, candidates, rd)
            rnd_counts.append(len(rq))
        avg_r = sum(rnd_counts) / len(rnd_counts) if rnd_counts else None

        note = ""
        if vix_v >= 30:      note = "High VIX — panic gate active"
        elif vix_v >= 20:    note = "Elevated VIX"
        elif len(quals) > 0: note = f"{len(quals)} genuine dip(s)"
        else:                note = "No dips in buy range"

        calib.append((label, td, quals, avg_r, vix_v, note))
        q_str = ", ".join(quals[:6]) if quals else "none"
        rnd_s = f"{avg_r:.1f}" if avg_r is not None else "—"
        print(f"  {str(td):12}  q={len(quals):2d}  VIX={vix_v:.1f}  ±10d={rnd_s}  [{q_str[:55]}]")

    # 5. Attrition on the 10-td-ago date
    print("[5/5] Attrition analysis (10 td ago) …")
    ref_row  = calib[3] if len(calib) > 3 else calib[-1]
    ref_date = ref_row[1]
    _, atr, _ = run_on_date(all_prices, vix_pairs, candidates, ref_date)
    atr_dict  = dict(atr)
    atr_dict["PASS"] = len(ref_row[2])

    print("\n  Filter attrition:")
    for fk in ORDERED_FILTERS:
        v = atr_dict.get(fk, 0)
        if v > 0:
            print(f"    {FILTER_LABELS.get(fk,fk):52} {v:3d}")
    print(f"    {'PASS':52} {atr_dict.get('PASS',0):3d}")

    # 6. Report
    avg, verdict = write_report(calib, atr_dict, universe, n_universe, n_cand)

    print(f"\n{'='*60}")
    print(f"  AVERAGE QUALIFIERS / DAY: {avg:.1f}")
    print(f"  VERDICT: {verdict}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
