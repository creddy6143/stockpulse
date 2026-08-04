# Contracted-revenue ÷ market-cap screen (RPO/Cap)

A Strategy Centre sub-tab ("Contracted") that screens for companies whose **contracted future
revenue** is large relative to their **market cap** — the idea being the market may be
under-appreciating a company sitting on years of already-won business.

**It is a screening metric, never a return forecast.** No "multibagger" language, no BUY
badges. Trust and recommendation state come from the shared engine, unchanged.

Backend: `intelligence/elite/contracted_revenue.py` + `_refresh_rpo_scan()` in `main.py`
(`/api/contracted-revenue`). Frontend: `ContractedTab` (Strategy sub-tab). Additive — no
existing screen, scoring, or the recommendation engine was modified.

---

## Data audit — what is actually retrievable for free (verified live)

Order book / backlog / RPO / ARR are **not** standard API fields. yfinance and Finnhub expose
**none** of them for any market. The one reliable free structured source is **SEC EDGAR XBRL**.

| Market / model | Source | Retrievable? |
|---|---|---|
| **US companies** | `us-gaap:RevenueRemainingPerformanceObligation` (RPO) via EDGAR | ✅ Yes |
| **Foreign issuers filing a 20-F (ADRs)** | `us-gaap` RPO (native currency) or `ifrs-full:TransactionPriceAllocatedToRemainingPerformanceObligations` | ✅ Yes (SAP, ASML…) |
| **Indian order book** (NCC/NBCC/BHEL) | not in Screener.in/NSE/Moneycontrol structured data; only investor-presentation/exchange PDFs | ❌ No → shown as "not available" |
| **ARR** (subscription) | not a GAAP/IFRS concept — press releases/decks only | ❌ No |
| **EU companies not SEC-listed** | file with local regulators; no free EDGAR-equivalent XBRL | ❌ No |
| **US firms reporting backlog only as narrative** (e.g. Fluor) | no XBRL tag | ❌ No → "not available" |

Verified examples (live): CRM $67.9B, NOW $29.0B, SNOW $9.2B, LMT $230.4B, RTX $289.0B,
GD $118.0B, PWR $33.5B, SAP €90.5B, ASML €46.5B — each with an "as of" date and filing form.

**Key insight:** under ASC 606 / IFRS 15 a *single* disclosure (RPO) is what SaaS calls "RPO",
defence calls "backlog", and engineering calls "order book". We therefore source RPO uniformly
and **label the variant by business model**, always stating the underlying figure is RPO.

---

## Metric variants (label only — the figure is always RPO)

| Variant label | Applies to (from GICS sector/industry) |
|---|---|
| **Backlog** | aerospace / defence |
| **Order book** | construction / engineering / infrastructure / capital goods / machinery / industrials |
| **RPO** | software / SaaS / IT services / internet / communications / media |
| **RPO** (generic) | any other sector that nonetheless files an RPO figure |

Variant is derived from sector/industry data, never from hard-coded tickers.

## Applicability — honest N/A vs not-available

- **RPO present** → ranked, variant labelled by model.
- **No RPO + non-applicable model** (banks/financials, insurance, retail, consumer, most
  pharma/biotech, REITs, utilities, energy, materials/mining, airlines, hotels) →
  **"N/A — this business model has no contracted forward revenue."** No substitute metric.
- **No RPO + Indian** → **"not available"** — Indian order book isn't in free structured filings.
- **No RPO + a model that *could* have it** (e.g. Fluor) → **"not available — reports backlog
  outside structured filings."**

Nothing is estimated. Missing data is "not available", never a guess. Unconvertible currencies
(no FX rate) → ratio omitted rather than approximated.

---

## Ratio, currency, staleness

- **Ratio = contracted revenue ÷ market cap**, both converted to a common currency (USD) via the
  app's existing FX rates. For US-domestic both are USD (no conversion). For ADRs the RPO is in
  native currency (EUR…) and is FX-converted to match.
- Every row shows the **"as of" date** and filing **form** of the RPO figure. RPO is filed
  quarterly/annually and goes stale; **a figure older than 6 months is flagged "STALE".**
- The scan refreshes every ~6 hours (RPO barely moves intraday).

Example ratios (verified): LMT 1.69×, GD 1.13×, RTX 0.98×, PWR 0.32×, CRM 0.43×, NOW 0.24×,
SNOW 0.08× — defence/engineering show the high "contracted work ≫ market cap" signal.

---

## Plain-language framing (shown in the tab)

Contracted future revenue is already-won work that will be recognised as revenue over **several
years — not profit.** A high ratio can also reflect **low margins, execution delays, or client
payment risk** — often exactly why the market values the company low. This is a starting point
for research, not a signal to buy.

## Scan / performance

`_refresh_rpo_scan` is EDGAR-first: it skips Indian tickers outright, probes EDGAR RPO for the
rest (cheap), and only pulls `get_fundamentals` (market cap) for tickers that actually have an
RPO figure. Universe = the curated picks cache. TTL 6h. Trust + shared `get_recommendation_state`
are attached for context only (never a new verdict).
