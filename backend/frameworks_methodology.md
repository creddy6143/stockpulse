# Investment Frameworks — Methodology

> `intelligence/frameworks/` · four independent analysis **lenses**.

## The contract

Frameworks **inform** the user; they **never** change any verdict, score, or badge.
They do not feed the recommendation engine, classification, Smart Picks, or Dip Buys.
Each answers ONE question:

| Framework | Question |
|---|---|
| GARP | Is this growth already paid for? |
| Piotroski F-Score | Is the business getting healthier? |
| Rule of 40 | Is this SaaS balancing growth and profit? |
| Altman Z-Score | Is there balance-sheet survival risk? |

Every `compute(ctx)` returns:
```
{status: "ok" | "na" | "insufficient", value, label, verdict, color,
 inputs_used: [{label, value, period}], applicability, caveats: [...], checks?: [...]}
```
- **ok** — computed, has a value + verdict.
- **na** — framework genuinely doesn't apply (a feature, not a failure).
- **insufficient** — data missing. **Never fabricated.**

## Data source

Multi-year statements come from Yahoo's **`fundamentals-timeseries`** endpoint,
routed through the Cloudflare worker (`/yahoo-ts/`) because it's IP-blocked from
Railway. `fetcher.get_financial_statements()` returns period-aligned annual series
(oldest → newest, `None`-padded) so index `-1` = latest FY and `-2` = prior FY for
every metric. Cached 24h (statement data moves slowly).

## The four formulas

### GARP — PEG = P/E ÷ EPS-growth-%
- P/E: forward if available, else trailing.
- Growth: forward EPS growth **only when on a consistent scale** with reported EPS
  (forward_eps can be split-adjusted vs raw statement shares); otherwise the
  self-consistent **trailing EPS CAGR** from the statements.
- Growth capped at 50% for the math. Growth ≤ 0 or no positive earnings → **N/A**.
- Bands: PEG ≤ 1.0 STRONG · ≤ 1.5 OK · ≤ 2.0 STRETCHED · > 2.0 EXPENSIVE.
- **Cyclical flag** (non-removable) for Storage/Memory, Semiconductors, Materials,
  Energy themes: "⚠️ PEG unreliable at cycle extremes."

### Piotroski F-Score (0–9) — latest FY vs prior
Profitability: (1) ROA>0 (2) OCF>0 (3) ROA improved (4) OCF>net income.
Leverage/liquidity: (5) LT-debt/assets down (6) current ratio up (7) no dilution (>2%).
Efficiency: (8) gross margin up (9) asset turnover up.
- Needs 2 full fiscal years, else **insufficient history**.
- < 5 evaluable checks → insufficient. Unknown checks counted as not-passed (noted).
- The 9-check breakdown IS the value (shown on tap). Financials get an "interpret
  with care" caveat.
- Bands: 8–9 STRONG · 6–7 SOLID · 4–5 MIXED · 0–3 WEAK.

### Rule of 40 — revenue growth % + FCF margin %
- FCF margin, else operating margin (labeled). Bands: ≥ 40 PASSES · 30–40 NEAR · < 30 BELOW.
- **Applies only to SaaS/software themes** (AI Software, Cloud/Hyperscalers,
  Cybersecurity, Fintech, Gaming). All others → **N/A — SaaS metric**.

### Altman Z = 1.2·(WC/TA) + 1.4·(RE/TA) + 3.3·(EBIT/TA) + 0.6·(MktCap/TL) + 1.0·(Rev/TA)
- Bands: > 2.99 SAFE · 1.81–2.99 GREY · < 1.81 DISTRESS.
- **N/A for financials** (banks/insurers) — not computed.
- Pre-revenue: computed with "early-stage skews harsh" caveat.
- DISTRESS surfaces as an **informational** risk flag (`distress_flag`) — it does
  **not** change the recommendation.

## Applicability (from `theme_membership.json`, not hardcoded tickers)
- `CYCLICAL_THEMES` → GARP cyclical warning.
- `SAAS_THEMES` → Rule of 40 applies.
- Financials (GICS sector, `indian_banks` theme, or name contains bank/insurance) →
  Altman N/A + F-Score caveat.

## Cross-framework rules
- **Never** blended into one composite number — they answer different questions.
  A summary line shows counts only: "2 ✅ · 1 N/A · 1 ?".
- Every value exposes its inputs on tap (numbers, period, fallbacks).

## Adding a 5th framework (the extension pattern)
1. Add `frameworks/<name>.py` with `compute_<name>(ctx) -> {...}` returning the
   standard shape. `ctx = {ticker, statements, fundamentals, price, meta}`.
2. Register it in `FRAMEWORKS` in `frameworks/__init__.py`.
That's it — the orchestrator, endpoints, and both display surfaces pick it up.

## Surfaces
- `GET /api/frameworks/{ticker}` → all four for one stock (stock-detail section).
- `GET /api/frameworks` → ranked lists across the top-40 picks universe (6h scan):
  GARP by PEG asc · F-Score by score desc · Rule of 40 by score desc · Altman = a
  separate DISTRESS risk list.
