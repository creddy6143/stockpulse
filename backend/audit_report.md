# StockPulse Trust Score Audit Report
**Date:** 2026-05-18  
**Auditor:** Claude Code — full pipeline trace

## Executive Summary

| Ticker | Score | Grade | Status | Root Cause |
|--------|-------|-------|--------|------------|
| TNXP | 18 | Blocked | CORRECT — Manual block | 8 reverse splits, chronic dilution |
| XGN | 8 | Blocked | CORRECT — Manual block | Board resigned before earnings |
| ASTS | 29 | Blocked | MISLEADING — Score defensible, label misleading | -482% margins, $282M insider selling vs $2.5k buying |
| NNE | 36 | Blocked | BROKEN — Pre-revenue scoring failure | Zero fundamentals score 36 but 78% analyst buy consensus |
| OKLO | 35 | Blocked | BROKEN — Pre-revenue scoring failure | Zero fundamentals score 35 but 75% analyst buy consensus |
| MILDEF.ST | 7 | Blocked | BROKEN — Data coverage failure | Finnhub has no Swedish stock data |
| LUG.ST | 7 | Blocked | BROKEN — Data coverage failure | Finnhub has no Swedish stock data |

---

## TNXP
- Manual block via BLOCKED_OVERRIDES. Score 18 hardcoded.
- Reason: "8 reverse splits. Chronic dilution."
- TODAY +11.8%: Irrelevant. A single green day does not change 8 reverse splits.
- VERDICT: TRUSTWORTHY — Block is correct. Keep it.

## XGN
- Manual block via BLOCKED_OVERRIDES. Score 8 hardcoded.
- Reason: "Board resigned 18 days before earnings."
- VERDICT: TRUSTWORTHY — Block is correct. Keep it.

---

## ASTS (AST SpaceMobile) — Score 29

### Raw Data (Live — 2026-05-18)
- Price: $83.69, Change: +0.82%
- Revenue Growth TTM YoY: +1505% (ARTIFACT — near-zero base)
- Profit Margins: -482%
- GAAP Profitable: False
- Earnings Surprise: -188.5%
- Analyst: 9 Buy / 7 Hold / 2 Sell (50% buy)
- Insider Buy (90d): $2,564
- Insider Sell (90d): $282,840,174 — MASSIVE NET SELLING
- Auto-Disqualified: False

### Pillar Trace
Business (max 40):
  revenue_growth 15.05 (1505/100) > 0.30 -> +12 pts
  gaap not profitable, margins -4.82 < -0.10 -> +0 pts
  earnings_surprise -188.5% -> +0 pts
  gross_margins positive -> ~+7 pts
  eps negative -> +0 pts
  BUSINESS TOTAL: ~19 pts

Smart Money (max 35):
  ceo_buying False, buy_value $2564 < $100k -> +0 pts
  analyst buy_pct 50% -> >0.40 -> +5 pts
  short_interest unknown -> +0 pts
  SMART MONEY TOTAL: 5 pts

Momentum (max 25):
  rec "hold" -> +2 pts
  no target_price, earn < 0 -> +0 pts
  rev+earn: earn < 0 -> +0 pts
  surprise negative -> +0 pts
  MOMENTUM TOTAL: ~5 pts

CALCULATED TOTAL: 29/100

### Issues Found
1. Revenue growth 1505% is an artifact (ASTS had near-zero prior year revenue).
   This inflates business score by 12 pts.
2. $282M insider selling is unpenalized (insider sell penalty was removed).
   This magnitude (net $282M sold) is not a scheduled 10b5-1 plan — it signals conviction selling.

### Cross-Reference
Our score: 29 — Blocked
Analyst consensus (Finnhub): HOLD (50% buy)
Yahoo Finance: Moderate Buy

### VERDICT: MISLEADING
Score is mathematically consistent with the formula. But ASTS is a legitimate satellite company. Score 29 puts it alongside NKLA bankruptcy. The label "Blocked" is misleading.

---

## NNE (Nano Nuclear Energy) — Score 36

### Raw Data (Live)
- Price: $24.93, Change: -9.48%
- Revenue Growth: 0.0 (PRE-REVENUE — no data)
- Profit Margins: 0.0 (DEFAULT — no data)
- GAAP Profitable: False
- Earnings Surprise: +34.7%
- Analyst: 7 Buy / 2 Hold / 0 Sell (78% buy)
- Analyst Recommendation: buy
- Auto-Disqualified: False

### THE BUG — "Near Profitability" False Award
Code in trust_score.py _business_score():
  elif f.get("profit_margins", 0) > -0.10:
      score += 5

profit_margins defaults to 0.0 when no data exists.
0.0 > -0.10 is TRUE -> awards 5 pts for "near profitability."
NNE has NO REVENUE. It's pre-revenue. 0.0 is a missing-data default, not a metric.
This is a data artifact giving 5 pts to every stock with no coverage.

### Pillar Trace
Business: 0 (revenue) + 5 (BUG) + 8 (earnings beat) + 0 + 0 = 13 pts
Smart Money: 0 (no CEO buy) + 10 (78% analyst buy) + 0 = 10 pts
Momentum: 8 (analyst rec "buy") + 0 + 0 + 5 (earnings beat) = 13 pts
TOTAL: 36 — below 40 threshold -> Grade "Blocked"

### Cross-Reference
Our score: 36 — Blocked
Analyst consensus: 78% BUY (7/9 analysts)
Yahoo Finance: Strong Buy

### VERDICT: BROKEN
Scores 36 due to data artifact. Real quality unknown. Fix the near-profitability bug first.

---

## OKLO — Score 35

### Raw Data (Live)
- Price: $62.27, Change: -7.35%
- Revenue Growth: 0.0 (PRE-REVENUE)
- Profit Margins: 0.0 (DEFAULT)
- Earnings Surprise: +3.4%
- Analyst: 21 Buy / 6 Hold / 1 Sell (75% buy consensus)
- Insider Buy (90d): $38,200,000
- Insider Sell (90d): $97,200,000
- Auto-Disqualified: False

### Pillar Trace
Business: 0 + 5 (BUG) + 2 (earnings beat) + 0 + 0 = 7 pts
Smart Money: 8 ($38M insider buys > $100k) + 10 (75% buy) + 0 = 18 pts
Momentum: 8 (rec "buy") + 0 + 0 + 2 (surprise > 0) = 10 pts
TOTAL: 35 — Grade "Blocked"

### Cross-Reference
Our score: 35 — Blocked
Analyst consensus: 75% BUY (21/28)
Yahoo Finance: Strong Buy

### VERDICT: BROKEN
OKLO has 21/28 analyst buy ratings and $38M insider buying. Score 35 puts it with NKLA.
The pre-revenue bug is responsible. Fix Bug 1 (near profitability false award).

---

## MILDEF.ST — Score 7

### Root Cause
Finnhub free tier has no coverage for Stockholm Exchange (.ST) stocks.
get_fundamentals("MILDEF") returns all metric values as empty dict.
All fields default to 0.

Pillar Trace:
Business: 0 + 5 (BUG on 0.0 margins) + 0 + 0 + 0 = 5 pts
Smart Money: 0 + 0 + 0 = 0 pts
Momentum: 2 (default "hold") + 0 + 0 + 0 = 2 pts
TOTAL: 7

MILDEF is a profitable Swedish defence company on Nasdaq Stockholm.
Score 7 is entirely a data coverage artifact.

### Cross-Reference
Our score: 7 — Blocked
Reality: Profitable, growing (European rearmament theme), actively listed

### VERDICT: BROKEN — Data coverage failure. Score meaningless.

---

## LUG.ST — Score 7

Same root cause as MILDEF.ST.
Lagercrantz Group is a profitable Swedish industrial conglomerate.
Score 7 is entirely a data coverage artifact.

### VERDICT: BROKEN — Data coverage failure. Score meaningless.

---

## Three Bugs Found and Fix Required

### BUG 1 — False "Near Profitability" Award
Location: intelligence/trust_score.py, _business_score()
Code: `elif f.get("profit_margins", 0) > -0.10: score += 5`
Problem: profit_margins defaults to 0.0 when no data. 0.0 > -0.10 = True.
Fix: Only award this if we actually received financial data (e.g., market_cap > 0).
Affected: NNE, OKLO, MILDEF.ST, LUG.ST

### BUG 2 — No Data Coverage Fallback for Non-US Stocks
Location: data/fetcher.py, get_fundamentals()
Problem: When Finnhub returns empty data for .ST/.CO/.HE/.OL stocks,
  scoring engine cannot distinguish "truly zero metrics" vs "no data available."
Fix: If all key fundamental fields are 0/None and market is non-US,
  return 50-point fallback with data_quality="limited" flag.
Affected: All Scandinavian and some European stocks

### BUG 3 — Watchlist "Upside" Is Mislabeled Trust Score
Location: frontend/src/App.jsx, CompactWatchRow + PivotSection
Problem: Column header says "Upside" but renders s.trust (trust score 0-100).
  User sees "35" under "Upside" and reads it as "35% upside."
  entry and potential are both hardcoded "—" — never calculated.
Fix: Rename column to "Score" OR calculate real upside from analyst target price.
Affected: Entire watchlist view

---

## Do Not Trade Until
1. Bug 1 fixed (pre-revenue false award)
2. Bug 2 fixed (coverage fallback for non-US)
3. Bug 3 fixed (mislabeled column or real upside calculated)
4. ASTS reviewed — score 29 is defensible but misleading for a legitimate company
