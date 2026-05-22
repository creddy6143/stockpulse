# StockPulse — Smart Picks Scan Report

**Generated:** 2026-05-22 17:00  
**Universe:** 410 tickers · 11 GICS sectors  
**Fetched successfully:** 397/410 (97%)  
**Fetch failures:** 13  
**Final picks:** 13 main + 0 dip  

---

## Data Fetch Results

| | Count | % of Universe |
|---|---:|:---:|
| Tickers scanned | 410 | 100% |
| Price fetched successfully | 397 | 97% |
| Fetch failures (rate-limited / delisted) | 13 | 3% |

**Failed tickers (sample):** ANSS, JNPR, LTIM.NS, MMC, DFS, TATAMOTORS.NS, K, DANO.PA, HES, MRO, BASF.DE, IPG, ATVI

---

## Filter Gate Pass Rates

| Gate | Passed | % of Universe |
|------|-------:|:-------------:|
| Universe scanned              |  410 | 100%  |
| 1 · Price data returned       |  397 |  96%  |
| 2 · Not auto-disqualified     |  382 |  93%  |
| 3 · Trust score ≥ 75          |   13 |   3%  |
| 4 · verify_pick() P1–P5 passed|   13 |   3%  |
| **Final top-15 picks**        | **13**  | —     |
| Buy-the-dip picks (≥65, –4%+) |    0 | —     |

---

## Final Top 15 Picks (main · sorted by trust score)

| # | Ticker | Name | Sector | Score | Grade | Price | Chg% |
|---|--------|------|--------|------:|-------|------:|-----:|
|  1 | **APH** | APH | Information Technology | 86 | Strong | $124.86 | +1.5% |
|  2 | **STX** | STX | Information Technology | 83 | Strong | $810.46 | +7.9% |
|  3 | **LLY** | LLY | Health Care | 80 | Strong | $1041.65 | +2.2% |
|  4 | **MU** | MU | Information Technology | 80 | Strong | $762.10 | +4.1% |
|  5 | **IRM** | IRM | Real Estate | 78 | Strong | $127.33 | +1.2% |
|  6 | **WDC** | WDC | Information Technology | 77 | Strong | $486.46 | +5.8% |
|  7 | **WELL** | WELL | Real Estate | 77 | Strong | $216.01 | -1.2% |
|  8 | **DDOG** | DDOG | Information Technology | 76 | Strong | $218.04 | +2.7% |
|  9 | **PODD** | PODD | Health Care | 76 | Strong | $156.89 | +0.2% |
| 10 | **AMD** | AMD | Information Technology | 75 | Strong | $449.59 | +0.5% |
| 11 | **NVDA** | NVDA | Information Technology | 75 | Strong | $219.51 | -1.8% |
| 12 | **PLTR** | PLTR | Information Technology | 75 | Strong | $137.41 | +0.2% |
| 13 | **ROKU** | ROKU | Communication Services | 75 | Strong | $125.08 | +0.7% |

---

## Buy-the-Dip Picks (trust ≥ 65, down ≥ 4% today)

_No dip picks today — no qualifying stocks down ≥ 4%._

---

## Sector Distribution of Picks

| Sector | Count |
|--------|------:|
| Information Technology | 8 |
| Health Care | 2 |
| Real Estate | 2 |
| Communication Services | 1 |

---

## Auto-Disqualified (blocked from picks)

Stocks that failed at Gate 2 — auto-disqualified regardless of score.

| Ticker | Score | Reason |
|--------|------:|--------|
| MRNA | 0 | Severe losses with declining revenue — going concern risk |

---

## Verification Notes

Every pick passed the following gates before inclusion:

- **P1 — Data quality**: `data_quality` not `unavailable`
- **P2 — Score threshold**: `total_score ≥ 75`
- **P3 — No auto-disqualification**: `auto_disqualified = False`
- **P4 — Market cap present**: `market_cap > 0`
- **P5 — Large-cap sanity floor**: score ≥ 90 requires market cap > $1 B

Dip picks (trust ≥ 65, down ≥ 4%) bypass P2 threshold but must still pass P1/P3.

## Rate Limiting Strategy

- Finnhub: token bucket 50 calls/min (free tier limit = 60)
- yfinance Python lib: serialised lock + 0.8s gap between calls
- Yahoo Finance REST: semaphore(3) concurrent + exponential backoff on 429
- Scan: batches of 50 tickers, 2 workers, 20s pause between batches
- Disk cache: fundamentals + insider data persisted 24h to .scan_cache.json

_Report generated 2026-05-22 17:00_
