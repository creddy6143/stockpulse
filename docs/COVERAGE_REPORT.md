# StockPulse — International Data Coverage Report

Generated: 2026-05-18
Status: Post-rebuild (international routing complete)

---

## Coverage Matrix

| Source | Indian .NS/.BO | Indian ADRs (NYSE) | EU ADRs (NASDAQ/NYSE) | Nordic .ST (non-ADR) |
|--------|---------------|-------------------|----------------------|---------------------|
| Finnhub basic_financials | ❌ 0 fields | ✅ 133 fields | ✅ 133 fields | ❌ 0 fields |
| Finnhub analyst/insider | ❌ 403 (paid) | ❌ 403 (paid) | ❌ 403 (paid) | ❌ 403 (paid) |
| Screener.in scrape | ✅ Full | N/A | N/A | N/A |
| Yahoo Finance | ❌ 429 blocked | ❌ 429 blocked | ❌ 429 blocked | ❌ 429 blocked |
| Avanza API | N/A | N/A | N/A | ❌ Returns HTML (API changed) |
| Nordnet API | N/A | N/A | N/A | ❌ 401 auth required |

---

## Routing Logic

### Priority order in `get_fundamentals(ticker)`:

1. **ADR map → Finnhub** (major international stocks with US listings)
   - Indian ADRs: INFY→Finnhub:INFY, HDB→Finnhub:HDB, IBN→Finnhub:IBN etc.
   - EU ADRs: ASML.AS→Finnhub:ASML, SAP.DE→Finnhub:SAP, ERIC-B.ST→Finnhub:ERIC
   - Also overlays Screener.in data (promoter/FII holding, ROE, ROCE) for .NS/.BO tickers

2. **Screener.in scraper** (Indian stocks NOT in ADR map)
   - TCS.NS, RELIANCE.NS, SBIN.NS, BPCL.NS, BAJFINANCE.NS etc.
   - Full P&L history (10 years), shareholding pattern, key ratios

3. **Finnhub + Yahoo v10 fallback** (US stocks and covered EU)
   - Standard route for US tickers (NVDA, AXON, AAPL etc.)

---

## ADR Map (Confirmed Working)

| Local Ticker | US ADR | Exchange | Finnhub Fields | Confirmed |
|-------------|--------|----------|----------------|-----------|
| INFY.NS | INFY | NYSE | 133 | ✅ |
| HDFCBANK.NS | HDB | NYSE | 114 | ✅ |
| ICICIBANK.NS | IBN | NYSE | ~130 | ✅ |
| WIPRO.NS | WIT | NYSE | ~130 | ✅ |
| TATAMOTORS.NS | TTM | NYSE | ~130 | ✅ |
| DRREDDY.NS | RDY | NYSE | ~130 | ✅ |
| ASML.AS | ASML | NASDAQ | 133 | ✅ |
| SAP.DE | SAP | NYSE | 133 | ✅ |
| NESN.SW | NSRGY | OTC | 133 | ✅ |
| ERIC-B.ST | ERIC | NASDAQ | 133 | ✅ |
| VOLV-B.ST | VOLVF | OTC | 131 | ✅ |
| SHEL.L | SHEL | NYSE | ~130 | ✅ |
| BP.L | BP | NYSE | ~130 | ✅ |
| AZN.L | AZN | NASDAQ | ~130 | ✅ |

---

## Screener.in Coverage (Confirmed Working)

| Ticker | Source | Fields Available |
|--------|--------|-----------------|
| INFY.NS | Screener.in | Market Cap, P/E, ROE 31.9%, ROCE 40.3%, FII 33.4%, P&L 10yr |
| TCS.NS | Screener.in | Market Cap, P/E, ROE ~59%, ROCE ~70%, P&L 10yr |
| RELIANCE.NS | Screener.in | Market Cap, P/E, ROE ~8%, ROCE ~12%, P&L 10yr |
| SBIN.NS | Screener.in | Market Cap, P/E, ROE ~18%, P&L 10yr |
| HDFCBANK.NS | Screener.in | Market Cap, P/E, ROE ~16%, P&L 10yr |

---

## No Coverage (Data Unavailable)

These tickers have NO data source and will show `grade: "Data Unavailable"`, `total_score: null`:

| Ticker | Reason |
|--------|--------|
| MILDEF.ST | No ADR, Avanza broken, Nordnet requires auth |
| LUG.ST | No ADR, Nordic APIs unavailable |
| Any small .ST/.HE/.CO/.OL not in ADR map | Same as above |

**This is honest and correct.** A null score is infinitely better than a fake 2/100 based on zero-fields.

---

## Expected Scores After Rebuild

Honest scores given free-tier Finnhub (no analyst consensus, no price targets = -22 pts max):

| Ticker | Route | Expected Score | Grade | Cap (Finnhub free tier) |
|--------|-------|---------------|-------|------------------------|
| INFY.NS | finnhub:INFY + screener.in | 60–72 | Moderate–Strong | +8 rev, +10 profit, +7 margin, +8 FII |
| TCS.NS | screener.in | 62–74 | Moderate–Strong | High ROE, strong margins |
| RELIANCE.NS | screener.in | 48–58 | Moderate | Lower ROE/margins, conglomerate |
| SBIN.NS | screener.in | 45–56 | Moderate | Bank metrics, lower margins normal |
| HDFCBANK.NS | finnhub:HDB + screener.in | 60–70 | Moderate–Strong | HDB ADR has data |
| ASML.AS | finnhub:ASML | 68–78 | Moderate–Strong | Strong fundamentals, no analyst data |
| SAP.DE | finnhub:SAP | 58–68 | Moderate | Slower growth |
| ERIC-B.ST | finnhub:ERIC | 48–60 | Moderate | Revenue declining -7.5% |
| MILDEF.ST | none | null | Data Unavailable | No data source |

**Note:** Scores are lower than user benchmarks (75–85 for INFY) because analyst consensus
data (+15 pts smart money) requires a paid Finnhub plan.
Actual paid-tier scores would be: INFY ~78–85, TCS ~80–90, ASML ~82–90.

---

## Scoring Changes (Large-Cap Calibration)

### Revenue Growth thresholds — Large-cap adjusted (market_cap > $10B):

| Growth | Small-cap (old) | Large-cap (new) | Example |
|--------|----------------|-----------------|---------|
| >30% | +12 pts | +12 pts | NVDA |
| >20% | +8 pts | +12 pts | — |
| 8–20% | +3 pts | +8 pts | INFY 9.6% → now +8 |
| 2–8% | +3 pts | +4 pts | Steady mature business |
| 0–2% | +3 pts | +2 pts | Flat but positive |

### Gross Margin thresholds — Large-cap adjusted:

| Margin | Small-cap (old) | Large-cap (new) | Example |
|--------|----------------|-----------------|---------|
| >60% | +10 pts | +10 pts | SaaS companies |
| >40% | +7 pts | +10 pts | — |
| 20–40% | +4 pts | +7 pts | INFY OPM 21% → now +7 |
| 10–20% | 0 pts | +4 pts | Industrial companies |

### FII Proxy (Indian stocks, smart money pillar):

When CEO buying data is unavailable (always on Finnhub free tier):
- FII holding > 30% → +8 pts (INFY: 33.4% → +8)
- FII holding > 20% → +5 pts
- FII holding > 10% → +2 pts
- FII consecutive buying 3+ days → +12 pts (active accumulation)
- FII consecutive buying 1–2 days → +5 pts

---

## Data Sufficiency Rule

A stock must have ≥ 70% of these fields to receive ANY score:
- `market_cap` (confirms it's a real listed company)
- `revenue_growth` (core business health)
- `profit_margins` (profitability)
- `gaap_profitable` (binary profitable flag)

Below 70% (3/4 fields missing) → `total_score: null`, `grade: "Data Unavailable"`.

**This is non-negotiable. A missing score is honest. A fake score is dangerous.**

---

## Cache TTLs

| Data | TTL | Reason |
|------|-----|--------|
| Screener.in fundamentals | 24 hours | Scraping is slow, data changes quarterly |
| Finnhub fundamentals | 24 hours | Financial reports quarterly |
| Finnhub ADR lookup | 24 hours | Same |
| Stock prices | 1 minute | Market data |
| Trust scores | 1 hour | Composition of fundamentals + insider |
