# Dip Filter Calibration Report

**Generated:** 2026-06-01 20:09:24
**Production universe:** 120 stocks (smart_picks_cache)
**F1-eligible candidates:** 41 stocks (trust ≥ 70, not auto-disqualified)

## Methodology

| Signal | Source | Point-in-time? |
|--------|--------|----------------|
| Price (F5/6/7/8/9/10/19/22/24/25) | Yahoo Finance v8 chart API (3y daily) | ✅ Historical |
| VIX (F20) | Yahoo Finance v8 chart API (^VIX) | ✅ Historical |
| Trust score (F1) | Production smart_picks_cache | ⚠ Current only |
| Fundamentals (F4/26/27/28) | .scan_cache.json | ⚠ Current only |
| Analyst data (F11/13) | analyst_cache DB + scan_cache | ⚠ Current only |
| F2/3/12/14/15/17/18/21/23 | Assumed clean / UNKNOWN | — |

> **Limitation:** Trust score and fundamentals use current values. For large-cap stocks these
> are relatively stable, but in past crisis periods (e.g. 60+ td ago) trust scores may have
> been lower. This means qualification rates for past dates may be *slightly overstated*.

---

## Part 1 — Calibration Table

| Date | Period | Qualifiers | ±10d avg | VIX | Qualifying tickers |
|------|--------|-----------|---------|-----|-------------------|
| 2026-06-01 | Today (2026-06-01) | **0** | 0.0 | 16.0 | — |
| 2026-05-30 | Yesterday (~1 td ago) | **0** | 0.0 | 15.3 | — |
| 2026-05-25 | 5 td ago (~2026-05-23) | **0** | 0.4 | 16.6 | — |
| 2026-05-18 | 10 td ago (~2026-05-16) | **0** | 1.4 | 17.8 | — |
| 2026-05-03 | 20 td ago (~2026-05-02) | **2** | 0.2 | 17.0 | APH, NEM |
| 2026-03-09 | 60 td ago (~2026-03-09) | **0** | 1.0 | 25.5 | — |
| 2025-12-15 | 120 td ago (~2025-12-15) | **0** | 0.4 | 16.5 | — |
| 2025-06-16 | 250 td ago (~2025-06-06) | **0** | 0.2 | 19.1 | — |
| — | **Average** | **0.2** | — | — | — |


### Stocks qualifying most frequently

| Ticker | Sector | N dates (out of 8) |
|--------|--------|--------------------|
| **APH** | Information Technology | 1/8 |
| **NEM** | Materials | 1/8 |

---

## Part 2 — Calibration Verdict

### 🔴 FILTERS TOO TIGHT

Average **0.2 qualifiers/day** is below the minimum useful threshold (3). The screener fires too rarely to be a product feature. Users will see 0 stocks on most trading days regardless of market conditions.

Today's 0 is explained by filters being too tight, not by market conditions.

---

## Part 3 — Filter Attrition Waterfall

Reference date: 10 trading days ago (calibration test date)
Starting candidates: **41** (all with trust ≥ 70)

| Filter | Eliminated | % of pool | Remaining |
|--------|-----------|-----------|-----------|
| F5a: Down today (> −0.3%) | 22 | 54% | 19 |
| F5b: Multi-day pullback (week < −1%) | 3 | 7% | 16 |
| F6: Cumulative drop −2% to −18% | 2 | 5% | 14 |
| F8: Within 15% of 50-day MA | 5 | 12% | 9 |
| F11: Analyst conviction ≥ 0.60 | 4 | 10% | 5 |
| F19: Drop > 1.5% | 3 | 7% | 2 |
| **QUALIFIED** | — | — | **0** |

### Attrition by tier:

| Tier | Stocks eliminated | % of candidates |
|------|-------------------|-----------------|
| Tier 2 — Dip Quality | 32 | 78% |
| Tier 3 — Conviction | 4 | 10% |
| Tier 4 — Macro & News | 3 | 7% |

---

## Part 4 — Filter-by-Filter Diagnosis

### F5a: Down today (> −0.3%) — eliminated 22 stocks (54%)

**Expected behavior.** On any given day, ~80% of large-cap stocks are flat or up. A dip screener requires the stock to be down today. This is a structural pre-condition, not a miscalibrated threshold.

### F8: Within 15% of 50-day MA — eliminated 5 stocks (12%)

**Controlled pullback check.** More than 10% from MA50 means the stock has overshot normal support. Either in freefall (risky) or recovering (MA50 irrelevant). If this blocks many valid candidates, consider widening to 15%.

### F11: Analyst conviction ≥ 0.60 — eliminated 4 stocks (10%)

**Analyst signal.** Conviction ratio <0.60 means analysts are bearish or mixed. A quality dip should have at least 60% buy-weighted analyst sentiment. If this blocks many stocks, check analyst data coverage for those tickers.

### F5b: Multi-day pullback (week < −1%) — eliminated 3 stocks (7%)

**Expected behavior.** This eliminates single-day spikes that reverse immediately. A genuine pullback is multi-day. The weekly return of <−1% is the right criterion.

### F19: Drop > 1.5% — eliminated 3 stocks (7%)

**Ex-dividend artifact filter.** A drop of <1.5% could be just the dividend going ex-, not a real pullback. If this blocks legitimate small daily drops, consider lowering to 0.8%.

### F6: Cumulative drop −2% to −18% — eliminated 2 stocks (5%)

**Core precision filter.** The −3% to −15% range targets stocks in a controlled pullback. Too shallow (>−3%): noise. Too deep (<−15%): falling knife risk. If this eliminates too many legitimate dips, consider widening to −2% / −18%.

---

## Part 5 — Recommendation

### B — Adjust 2–4 filter thresholds

The screener fires too rarely. Specific proposed relaxations:

| Priority | Filter | Current | Proposed | Impact |
|----------|--------|---------|---------|--------|
| 1 (highest) | F6: Weekly drop range | −3% to −15% | −2% to −18% | More candidates in mild pullbacks |
| 2 | F9: RSI range | 30–55 | 28–58 | Includes slightly overbought dips |
| 3 | F24: 6M return | ≥ +5% | ≥ −2% | Allows dips in flat/sideways markets |
| 4 | F8: MA50 distance | ≤ 10% | ≤ 15% | Captures deeper-than-normal pullbacks |

**Implement priority 1 and 2 first.** Re-run this backtest before applying 3 and 4.

---

*Generated by `dip_backtest.py` — do not modify production filters without
product owner review of this report.*