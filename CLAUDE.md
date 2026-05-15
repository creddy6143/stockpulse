# STOCKPULSE — CLAUDE CLI PROJECT MEMORY
## Complete Build Specification
### Read this entire file before writing a single line of code

---

## WHAT THIS IS

StockPulse is a personal AI-powered stock intelligence platform.
It coaches investors through every decision using plain English — no jargon.
Markets: USA 🇺🇸 + Europe 🇪🇺 + India 🇮🇳

Personal use first. Commercial if validated.

**The core promise:** Every number shown must answer "so what?" for the user.
If it can't — it doesn't belong in the UI.

---

## TECH STACK

```
Backend:   FastAPI (Python 3.11+)
Frontend:  React 18 + CSS (no Tailwind — all custom CSS)
Database:  SQLite (file: stockpulse.db)
Data:      yfinance + Finnhub free tier + NSE India free
AI:        Claude API (claude-sonnet-4-5) via Anthropic SDK
Port:      Backend 8000 | Frontend 3000
```

---

## FOLDER STRUCTURE

```
stockpulse/
│
├── CLAUDE.md                    ← This file (project memory)
├── README.md
├── .env                         ← API keys (never commit)
│
├── backend/
│   ├── main.py                  ← FastAPI app entry point
│   ├── requirements.txt
│   │
│   ├── data/
│   │   ├── fetcher.py           ← yfinance + Finnhub fetcher
│   │   ├── india.py             ← NSE/BSE Indian market data
│   │   └── cache.py             ← Simple in-memory cache (15min TTL)
│   │
│   ├── intelligence/
│   │   ├── trust_score.py       ← Trust Score calculator (3 pillars)
│   │   ├── patterns.py          ← 8 core pattern detectors
│   │   ├── signals.py           ← Signal quality gates
│   │   ├── claude_ai.py         ← All Claude API calls
│   │   └── prompts.py           ← All Claude prompt templates
│   │
│   ├── portfolio/
│   │   ├── tracker.py           ← P&L, positions management
│   │   └── averaging.py         ← Averaging down intelligence
│   │
│   └── database/
│       ├── models.py            ← SQLite schema + table creation
│       └── db.py                ← Database operations
│
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── index.js
│   │   ├── App.jsx              ← Root component + routing
│   │   ├── App.css              ← Global styles (design system)
│   │   │
│   │   ├── components/
│   │   │   ├── Header.jsx       ← Logo + market pill + bell
│   │   │   ├── AlertBanner.jsx  ← Sticky urgent alert strip
│   │   │   ├── TabNav.jsx       ← Bottom 3-tab navigation
│   │   │   │
│   │   │   ├── home/
│   │   │   │   ├── PortfolioArc.jsx
│   │   │   │   ├── ActionRequired.jsx
│   │   │   │   ├── SignalsFeed.jsx
│   │   │   │   └── MarketConditions.jsx
│   │   │   │
│   │   │   ├── stocks/
│   │   │   │   ├── StockGroup.jsx    ← Accordion group
│   │   │   │   ├── StockRow.jsx      ← Compact row + expand
│   │   │   │   ├── WatchGroup.jsx    ← Watchlist accordion
│   │   │   │   └── WatchRow.jsx      ← Watchlist row + expand
│   │   │   │
│   │   │   └── picks/
│   │   │       ├── PickRow.jsx       ← Compact pick row + expand
│   │   │       └── DisqList.jsx      ← Disqualified stocks
│   │   │
│   │   ├── screens/
│   │   │   ├── HomeScreen.jsx
│   │   │   ├── StocksScreen.jsx
│   │   │   └── SmartPicksScreen.jsx
│   │   │
│   │   └── api/
│   │       └── client.js        ← All API calls to backend
│   │
│   └── package.json
│
└── docs/
    ├── PATTERN_LIBRARY.md
    ├── EDGE_CASES.md
    └── DEEP_ANALYTICS.md
```

---

## DESIGN SYSTEM — EXACT COLOURS AND FONTS

These must be used exactly. Do not change colours or fonts.

```css
/* Google Fonts — load these */
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@500;600;700;800&family=IBM+Plex+Mono:wght@300;400;500;600&family=DM+Sans:wght@300;400;500;600;700&display=swap');

:root {
  /* Backgrounds */
  --bg: #f0f5ff;
  --white: #fff;
  --card: #fff;
  --card2: #f6f8ff;

  /* Brand colours */
  --indigo: #5b72f8;      /* Primary — interactive elements */
  --sky: #0ea5e9;         /* Secondary — links, accents */
  --emerald: #059669;     /* Bullish / positive / buy */
  --emerald2: #d1fae5;    /* Emerald background */
  --rose: #e11d48;        /* Bearish / urgent / sell */
  --rose2: #fff1f3;       /* Rose background */
  --amber: #d97706;       /* Warning / neutral / watch */
  --amber2: #fef3c7;      /* Amber background */
  --violet: #7c3aed;      /* Smart money pillar */
  --gold: #f59e0b;        /* Indian market accent */
  --gold2: #fffbeb;       /* Gold background */

  /* Text */
  --t1: #0f172a;          /* Primary text */
  --t2: #475569;          /* Secondary text */
  --t3: #94a3b8;          /* Muted text */
  --t4: #e2e8f0;          /* Borders / dividers */

  /* Shadows */
  --shadow: 0 2px 16px rgba(91,114,248,.08);
  --shadowsm: 0 1px 8px rgba(15,23,42,.06);

  /* Border radius */
  --r: 16px;              /* Cards */
  --rm: 12px;             /* Medium elements */
  --rs: 8px;              /* Small elements */

  /* Fonts */
  --mono: 'IBM Plex Mono', monospace;   /* Numbers, codes, labels */
  --syne: 'Syne', sans-serif;           /* Headers, tickers, brand */
  --dm: 'DM Sans', sans-serif;          /* Body text, descriptions */
}

/* App background gradient */
body { background: var(--bg); }
.app {
  max-width: 400px;
  margin: 0 auto;
  background: linear-gradient(180deg, #eaf2ff 0%, #f3f7ff 40%, #f8faff 100%);
}
```

---

## UI LAYOUT — 3 SCREENS

### HEADER (sticky, always visible)

```
┌─────────────────────────────────────────────┐
│ ⚡ StockPulse          🟢 Market Calm   🔔4  │
│    AI Intelligence                           │
│    🇺🇸 🇪🇺 🇮🇳                               │
└─────────────────────────────────────────────┘
```

- Background: `linear-gradient(135deg, #4f68f0, #0ea5e9)`
- Border radius bottom: 24px
- Logo: "⚡" icon in frosted glass box + "StockPulse" (Syne 800 17px white)
- Subtitle: "AI Intelligence" (Mono 8px 60% white uppercase)
- Flags row: 🇺🇸 🇪🇺 🇮🇳 (10px, own row, 4px gap)
- Market pill: pulsing dot + "Market Calm" / "Market Choppy" / "Market Alert"
  - Driven by VIX: <15=Calm 🟢, 15-25=Choppy 🟡, >25=Alert 🔴
- Bell icon with red badge showing unread alert count

**Header NEVER shows portfolio value. Portfolio lives on Home screen only.**

---

### STICKY ALERT BANNER (between header and tabs)

Only shown when there are urgent stocks (auto-disqualified or EXIT signals).

```
● 2 stocks need action today    [View Now]
  TNXP · XGN — earnings this morning
```

- Background: `linear-gradient(135deg, #fff1f3, #ffe4e6)`
- Border: 1.5px solid #fecdd3
- Pulsing red dot (animation)
- Always visible on ALL three screens when active
- Cannot be scrolled past

---

### BOTTOM TAB NAVIGATION

```
┌──────────┬──────────┬──────────┐
│    🏠    │    📊    │    🎯    │
│   Home   │  Stocks  │  Smart   │
│          │          │  Picks   │
└──────────┴──────────┴──────────┘
```

- Active tab: indigo colour + gradient underline bar top
- Inactive: --t3 grey
- Badge (red pill with count) on Home when alerts exist

---

## SCREEN 1 — HOME

### Portfolio Arc (compact — left side)

```
[80px ring]   My Portfolio          View all →
              Invested    $12,450
              Total P&L   -$4,150
              Positions   🇺🇸2  🇪🇺2  🇮🇳2
```

- SVG ring: 80×80px, stroke 8, gradient indigo→sky
- Ring fill % = current value / invested (capped at 100%)
- Centre: "Value" label (Mono 8px) + "$8.3k" (Mono 15px 700)
- Right side: 3 stat rows separated by hairlines
- Positions row: flag + count for each market (NOT "6 stocks")
- "View all →" navigates to Stocks tab

### Action Required Card

Only shown when disqualified or EXIT-signal stocks exist.

```
┌─ ⚡ Action Required ─────────── 2 stocks ─┐
│ TNXP  Exit on any pre-market pop — today  EXIT → │
│ XGN   Exit at open — board + guidance cut  EXIT → │
└───────────────────────────────────────────────────┘
```

- Background: gradient rose tint
- Border: 1.5px solid #fecdd3
- Each item: ticker (Syne 700 14px rose) + plain English reason + EXIT button

### Today's Signals (compact rows, tap to expand)

```
┌─ Today's Signals ─────────────────── See all → ─┐
│ 💥  INOD   HIGH  Earnings 3× better...   2m ago ▼│
│ 🚀  RKLB  MED-HIGH  Price jumped on...  18m ago ▼│
│ 🇮🇳  RELIANCE.NS  HIGH  Big investors... open   ▼│
└──────────────────────────────────────────────────┘
```

- Compact rows — one line each
- Text truncated with ellipsis
- Tap row → expands with full plain English explanation
- One expanded at a time (accordion)
- Signal text rules: PLAIN ENGLISH ONLY
  - ❌ "Gap and Go confirmed. Volume 4.8×"
  - ✅ "Price jumped on major news and has momentum to continue"
  - ❌ "FII net ₹4,200Cr — 3 consecutive days"
  - ✅ "Large overseas investors buying heavily for 3 days — vote of confidence"

### Market Conditions

```
┌─ Market Conditions ─────────────── Live · yfinance ─┐
│ ┌───────────────────┐ ┌───────────────────────────┐ │
│ │ Fear Index (VIX)  │ │ Markets Today             │ │
│ │ 14.2  🟢 Calm     │ │ 🇺🇸 S&P 500     +0.8%     │ │
│ │ Below 15 reliable │ │ 🇺🇸 Nasdaq      +1.2%     │ │
│ └───────────────────┘ │ 🇪🇺 DAX         +0.4%     │ │
│                       │ 🇮🇳 India (NSE) +1.1%     │ │
│                       └───────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

- VIX fetched from yfinance: `^VIX`
- S&P 500: `^GSPC`, Nasdaq: `^IXIC`, DAX: `^GDAXI`, Nifty: `^NSEI`
- Refreshes every 15 minutes
- "Markets Today" shows ALL four markets — US gets TWO indices (S&P + Nasdaq)

---

## SCREEN 2 — STOCKS

### Filter Pills (horizontal scroll)

```
All  |  My Stocks  |  Watchlist  |  🇺🇸 US  |  🇪🇺 Europe  |  🇮🇳 India
```

- Active: gradient indigo→sky background, white text
- Inactive: white background, --t3 text, --t4 border

### My Stocks / All / Country View — Accordion Groups

**ACCORDION RULE: Only ONE group open at a time.**
Tapping an open group closes it. Tapping another closes current, opens new.

```
🔴 Action Required   2 stocks  ▾   ← default open
🟡 Watch Closely     3 stocks  ▾   ← closed
🟢 Holding Well      6 stocks  ▾   ← closed
```

Each group is a card with coloured left border and tinted background.

### Stock Row (compact, tap to expand)

```
● 🇺🇸 TNXP  Tonix Pharma          $13.50   18/100  SELL  ▼
              ▼71.2%
```

- Coloured dot (rose=sell, amber=hold, emerald=buy) with glow
- Flag + Ticker (Syne 700 13px) + Name (10px --t2)
- Price (Mono 12px) + Change % (coloured)
- Trust score number + grade (coloured by trust level)
- Rec badge (SELL/HOLD/BUY styled pill)
- Chevron ▼/▲

### Expanded Stock Row

```
┌─ P&L ──┐ ┌─ AI Score ─┐ ┌─ Earnings ─┐
│ -$2,794 │ │   68/100   │ │   Jun 17   │
└─────────┘ └────────────┘ └────────────┘

┌─ AI Grade ──────┐ ┌─ Recommendation ──┐
│ Moderate        │ │ Hold              │
└─────────────────┘ └───────────────────┘

AI verdict: Plain English explanation of what to do and why.

[Full Analysis]  [Set Alert]  or  [Exit Position] if SELL
```

### Watchlist Filter — COMPLETELY DIFFERENT UI

When "Watchlist" pill is selected, groups change entirely:

```
🟢 Ready to Buy      ← AI says enter NOW
🟡 Still Watching    ← Good stock, wrong time
🔴 Don't Buy Yet     ← Red flags or overpriced
```

**Watchlist row shows:**
- Flag + Ticker + Signal label ("Entry zone now" / "Wait for pullback" / "Not yet")
- Trust score
- Tap to expand: reason (plain English) + Best Entry + Potential

**Watchlist NEVER shows P&L (user doesn't own these stocks)**

### Trust Score Colours

```
Score 75+  → --indigo  (#5b72f8)  Grade: Strong
Score 60+  → --amber   (#d97706)  Grade: Moderate
Score 40+  → --gold    (#f59e0b)  Grade: Weak
Score <40  → --rose    (#e11d48)  Grade: Blocked
```

---

## SCREEN 3 — SMART PICKS

### Header

```
Smart Picks                    ● 71% accurate · 90d
```

### Pick Rows (compact, tap to expand — scales to 100 stocks)

```
● AXON  STRONG BUY    87/100  Strong  ▼
  Axon Enterprise
```

**Expanded Pick:**
```
[Gradient bar: indigo → sky]

Three Pillars:
┌─ Business ──┐ ┌─ Smart $ ──┐ ┌─ Momentum ─┐
│   36/40     │ │   32/35    │ │   19/25    │ 
│ ████████░   │ │ █████████░ │ │ ███████░░  │
└─────────────┘ └────────────┘ └────────────┘

Why This Stock:
● CEO bought $1.2M own money (open market, unscheduled)
● Vanguard + ARK + Fidelity all freshly added Q1
● Revenue +44% YoY — growth rate accelerating
● Guidance raised 12% above analyst consensus
● Short interest declining 3 consecutive months

┌─ 12M Potential ─┐ ┌─ Entry Zone ──┐
│   +45-70%       │ │  $285-$310    │
└─────────────────┘ └───────────────┘
┌─ Risk Level ────┐ ┌─ Horizon ─────┐
│   LOW-MED       │ │  12 months    │
└─────────────────┘ └───────────────┘
```

### Avoid — Blocked Section

```
🚫 XGN  · 8/100  Board resignation + 2 guidance cuts...
🚫 TNXP · 18/100 8 reverse splits, $99M burn...
🚫 NKLA · 7/100  Fraud conviction, Chapter 11...
```

---

## DATABASE SCHEMA (SQLite)

```sql
-- Stocks being tracked
CREATE TABLE stocks (
  id INTEGER PRIMARY KEY,
  ticker TEXT UNIQUE NOT NULL,
  name TEXT,
  market TEXT,            -- 'US', 'EU', 'IN'
  exchange TEXT,          -- 'NYSE', 'NASDAQ', 'NSE', 'BSE', 'XETRA'
  currency TEXT,          -- 'USD', 'EUR', 'INR'
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User portfolio positions
CREATE TABLE portfolio (
  id INTEGER PRIMARY KEY,
  ticker TEXT NOT NULL,
  shares REAL NOT NULL,
  buy_price REAL NOT NULL,
  buy_date DATE,
  notes TEXT,
  FOREIGN KEY (ticker) REFERENCES stocks(ticker)
);

-- Watchlist (not owned)
CREATE TABLE watchlist (
  id INTEGER PRIMARY KEY,
  ticker TEXT NOT NULL,
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  notes TEXT,
  FOREIGN KEY (ticker) REFERENCES stocks(ticker)
);

-- Trust scores (cached, refreshed daily)
CREATE TABLE trust_scores (
  ticker TEXT PRIMARY KEY,
  total_score INTEGER,
  business_score INTEGER,
  smart_money_score INTEGER,
  momentum_score INTEGER,
  grade TEXT,             -- 'Exceptional','Strong','Moderate','Weak','Blocked'
  auto_disqualified BOOLEAN DEFAULT FALSE,
  disqualify_reason TEXT,
  calculated_at TIMESTAMP,
  FOREIGN KEY (ticker) REFERENCES stocks(ticker)
);

-- Pattern signals
CREATE TABLE signals (
  id INTEGER PRIMARY KEY,
  ticker TEXT NOT NULL,
  pattern TEXT NOT NULL,  -- 'squeeze','gap_go','dead_cat','kitchen_sink' etc
  confidence REAL,        -- 0.0 to 1.0
  plain_english TEXT,     -- Claude-generated explanation
  recommendation TEXT,    -- 'strong_buy','buy','hold','sell','strong_sell'
  stop_loss_pct REAL,
  time_horizon_days INTEGER,
  fired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  resolved_at TIMESTAMP,
  outcome TEXT,           -- 'correct','incorrect','pending'
  FOREIGN KEY (ticker) REFERENCES stocks(ticker)
);

-- Alert log
CREATE TABLE alerts (
  id INTEGER PRIMARY KEY,
  ticker TEXT,
  alert_type TEXT,        -- 'urgent','signal','watchlist_entry','earnings'
  message TEXT,
  is_read BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Price cache
CREATE TABLE price_cache (
  ticker TEXT PRIMARY KEY,
  price REAL,
  change_pct REAL,
  volume REAL,
  updated_at TIMESTAMP
);

-- Market data cache
CREATE TABLE market_cache (
  key TEXT PRIMARY KEY,   -- 'vix','sp500','nasdaq','dax','nifty'
  value REAL,
  updated_at TIMESTAMP
);
```

---

## BACKEND API ENDPOINTS

```
GET  /api/health                     → Health check
GET  /api/market                     → VIX + 4 market indices

GET  /api/portfolio                  → All portfolio positions with P&L
POST /api/portfolio                  → Add position {ticker, shares, buy_price}
PUT  /api/portfolio/{id}             → Update position
DEL  /api/portfolio/{id}             → Remove position

GET  /api/watchlist                  → All watchlist items with signals
POST /api/watchlist                  → Add to watchlist {ticker}
DEL  /api/watchlist/{ticker}         → Remove from watchlist

GET  /api/stock/{ticker}             → Full stock data + trust + signals
GET  /api/stock/{ticker}/trust       → Trust score details
GET  /api/stock/{ticker}/signals     → All signals for stock
GET  /api/stock/{ticker}/verdict     → Claude AI plain English verdict

GET  /api/alerts                     → All alerts (unread first)
PUT  /api/alerts/{id}/read           → Mark alert as read

GET  /api/picks                      → AI-generated smart picks (trust ≥ 75)
GET  /api/picks/disqualified         → Auto-disqualified stocks

GET  /api/accuracy                   → Signal accuracy stats (90-day)
```

---

## DATA FETCHING

### yfinance Tickers

```python
# US Markets
"^VIX"    # Fear Index
"^GSPC"   # S&P 500
"^IXIC"   # Nasdaq Composite
"^GDAXI"  # DAX (Germany/Europe)
"^NSEI"   # Nifty 50 (India NSE)

# Indian stocks — always use .NS suffix for NSE
"RELIANCE.NS"
"HDFCBANK.NS"
"INFY.NS"
"TCS.NS"

# BSE stocks — use .BO suffix
"RELIANCE.BO"

# US stocks — plain ticker
"AAPL", "NVDA", "GRRR"

# EU stocks — use exchange suffix
"ASML.AS"   # Amsterdam
"SAP.DE"    # Frankfurt
```

### NSE India Free Data (from nseindia.com)

```python
# FII/DII daily flow (published every market day)
NSE_FII_URL = "https://www.nseindia.com/api/fiidiiTradeReact"

# Bulk deals
NSE_BULK_URL = "https://www.nseindia.com/api/snapshot-capital-market-largedeal"

# Insider trading disclosures (SEBI)
NSE_INSIDER_URL = "https://www.nseindia.com/api/corporates-pit"
```

### Finnhub (free tier — 60 calls/minute)

```python
# News per ticker
GET https://finnhub.io/api/v1/company-news?symbol={ticker}&from={date}&to={date}&token={key}

# Earnings surprise
GET https://finnhub.io/api/v1/stock/earnings?symbol={ticker}&token={key}

# Insider transactions
GET https://finnhub.io/api/v1/stock/insider-transactions?symbol={ticker}&token={key}
```

---

## TRUST SCORE ALGORITHM

```
Total: 100 points across 3 pillars

PILLAR 1 — BUSINESS QUALITY (40 points max)
  Revenue growth YoY:
    >30% accelerating:     +12
    >15% stable:           +8
    >0% declining:         +3
    Negative:              0

  Earnings quality:
    Beat 4+ quarters:      +8
    Beat 2-3 quarters:     +5
    Mixed:                 +2

  Profitability:
    GAAP profitable:       +10
    Near profitability:    +5
    Pre-revenue:           0

  Guidance:
    Raised guidance:       +10
    Maintained:            +5
    Cut:                   -5

PILLAR 2 — SMART MONEY (35 points max)
  CEO/insider buying (open market):  +20 (highest single signal)
  Institutional adding (13F):        +8
  Short interest declining:           +5
  Dark pool buying:                   +2

  PENALTIES:
    Multiple insiders selling:        -10
    Short interest >40%:              -5

PILLAR 3 — MOMENTUM (25 points max)
  Analyst consensus:
    Strong Buy majority:   +8
    Buy majority:          +5
    Mixed:                 +2

  Price action:
    Above 200-day MA:      +7
    Sector outperforming:  +5

  News sentiment:
    Positive catalyst:     +5
    No major news:         0
    Negative headline:     -5

GRADE THRESHOLDS:
  90+: Exceptional
  75+: Strong
  60+: Moderate
  40+: Weak
  <40: Blocked (show as red, suggest exit)

AUTO-DISQUALIFIERS (override score → show BLOCKED):
  ✗ Active SEC/SEBI investigation
  ✗ Going concern warning in filings
  ✗ Reverse split in last 12 months
  ✗ CEO + CFO both departed simultaneously
  ✗ Cash runway < 6 months
  ✗ Board resignation within 30 days of earnings
  ✗ Guidance cut 3× consecutively
  ✗ [India] Promoter pledge > 50%
  ✗ [India] Promoter holding declining > 5% per quarter
```

---

## 8 CORE PATTERNS TO DETECT

```python
PATTERNS = {
    "squeeze": {
        "name": "Short Squeeze",
        "conditions": [
            "short_interest > 0.20",           # >20% of float shorted
            "earnings_surprise > 0.50",         # >50% beat
            "volume > 3 * avg_volume_30d",      # Volume spike
        ],
        "confidence": 0.71,
        "stop_loss_pct": 0.25,
        "time_horizon_days": 5,
        "plain_english": "Investors who bet against this stock are now being forced to buy back — pushing price up fast."
    },
    "gap_and_go": {
        "name": "Strong Momentum",
        "conditions": [
            "gap_up_pct > 0.08",               # Gapped up >8%
            "volume_at_11am > 2 * avg_volume",  # Sustained volume
            "catalyst_present": True,            # Real news reason
        ],
        "confidence": 0.68,
        "stop_loss_pct": 0.20,
        "time_horizon_days": 7,
        "plain_english": "Price jumped on real news and is continuing to rise with strong interest."
    },
    "dead_cat": {
        "name": "False Recovery",
        "conditions": [
            "trust_score < 40",
            "drop_last_30d > 0.40",            # Fell >40% in 30 days
            "bounce_last_3d > 0.10",            # Bounced 10% recently
            "revenue_declining": True,
        ],
        "confidence": 0.76,
        "action": "BLOCK",
        "plain_english": "This looks like a recovery but the underlying problems haven't been fixed. Likely to keep falling."
    },
    "kitchen_sink": {
        "name": "Deliberate Reset",
        "conditions": [
            "worst_quarter_in_2yr": True,
            "ceo_stayed": True,
            "creditor_support > 0.80",
            "revenue_beating_estimates": True,
        ],
        "confidence": 0.69,
        "plain_english": "Management deliberately reported the worst quarter to reset expectations. Recovery typically follows."
    },
    "ath_launchpad": {
        "name": "All-Time High Breakout",
        "conditions": [
            "price_at_ath": True,
            "trust_score > 70",
            "volume > 1.5 * avg_volume",
        ],
        "confidence": 0.67,
        "plain_english": "Stock hit an all-time high with strong backing. High-quality stocks often keep rising from here."
    },
    "falling_knife": {
        "name": "Avoid — Still Falling",
        "conditions": [
            "drop_last_5d > 0.15",
            "volume_on_down_days > volume_on_up_days",
            "trust_score < 50",
        ],
        "confidence": 0.73,
        "action": "BLOCK",
        "plain_english": "Stock is in a strong downtrend. Buying now is like catching a falling knife — likely to keep dropping."
    },
    "sandbagging": {
        "name": "Consistent Beater",
        "conditions": [
            "beat_count_8q >= 6",              # Beat 6 of last 8 quarters
            "avg_beat_magnitude > 0.08",        # Beat by >8% on average
        ],
        "confidence": 0.71,
        "plain_english": "This company consistently beats its own expectations. Upcoming results likely to be better than forecast."
    },
    "capitulation": {
        "name": "Potential Bottom",
        "conditions": [
            "vix > 25",
            "drop_last_30d > 0.30",
            "volume_spike > 3x",
            "trust_score > 60",                 # Quality stock required
            "sentiment_score < 0.25",           # Very negative sentiment
        ],
        "confidence": 0.68,
        "plain_english": "Panic selling may be overdone on a quality stock. Historically these moments have been good entry points."
    }
}
```

---

## INDIAN MARKET SPECIAL RULES

When a stock has `.NS` or `.BO` suffix, apply these additional checks:

```python
INDIA_RULES = {
    "promoter_holding": {
        "fetch": "screener.in or NSE disclosure",
        "warning": "< 30% or declining > 2% per quarter",
        "block": "declining > 5% per quarter OR pledge > 50%"
    },
    "fii_dii_flow": {
        "fetch": "NSE daily FII/DII data (free)",
        "bullish": "FII net buying 3+ consecutive days",
        "bearish": "FII net selling > ₹3000Cr in one day"
    },
    "circuit_breaker": {
        "upper": "Stock at upper circuit (5/10/20%) = demand signal",
        "lower": "Stock approaching lower circuit = EXIT warning"
    },
    "bulk_block_deals": {
        "fetch": "NSE same-day disclosure (free)",
        "signal": "Large block buy by institution = smart money entry"
    },
    "fiscal_year": "April to March (adjust YoY comparisons)",
    "currency": "Display in INR, convert to USD for portfolio total"
}
```

---

## CLAUDE API INTEGRATION

### System Prompt (used for ALL verdicts)

```python
SYSTEM_PROMPT = """
You are a personal stock intelligence assistant. Your job is to explain
what is happening with a stock in plain English that any intelligent person
can understand, even if they have no trading experience.

RULES:
1. NEVER use trading jargon (no: gap and go, short squeeze mechanics,
   VWAP, dark pool, FII/DII, short interest %). Instead explain WHAT
   these things mean in plain English.
2. Always say what to DO (buy/hold/sell/wait) and WHY in simple terms.
3. Always include a stop loss in plain English ("exit if it falls 20%
   from your entry").
4. Be honest about uncertainty. Use "likely", "suggests", "may".
5. Be concise. Max 3 sentences for a verdict.
6. If the stock is auto-disqualified, say clearly: exit, explain why
   briefly, and do not suggest holding.

OUTPUT FORMAT (always JSON):
{
  "verdict": "plain English verdict (max 3 sentences)",
  "recommendation": "strong_buy|buy|hold|sell|strong_sell",
  "confidence_pct": 71,
  "stop_loss_explanation": "plain English stop loss",
  "time_horizon": "short (days) | medium (weeks) | long (months)",
  "key_risk": "single biggest risk in plain English"
}
"""

def get_verdict(ticker, trust_score, patterns_detected, price_data, fundamentals):
    user_prompt = f"""
Stock: {ticker}
Trust Score: {trust_score}/100
Patterns: {patterns_detected}
Price: {price_data}
Fundamentals: {fundamentals}

Give a plain English verdict following the system rules.
"""
    # Call Claude API
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}]
    )
    return json.loads(response.content[0].text)
```

---

## MARKET CONDITIONS LOGIC

```python
def get_market_status(vix_value):
    if vix_value < 15:
        return {"label": "Market Calm", "dot": "calm", "color": "green"}
    elif vix_value < 25:
        return {"label": "Market Choppy", "dot": "choppy", "color": "amber"}
    else:
        return {"label": "Market Alert", "dot": "alert", "color": "rose"}

# Shown in header pill: plain English only
# Shown in Home cards: VIX number + 4 market indices
```

---

## SMART PICKS LOGIC

```python
def get_smart_picks(all_stocks):
    picks = []
    for stock in all_stocks:
        trust = calculate_trust_score(stock)
        if trust.total >= 75 and not trust.auto_disqualified:
            verdict = get_claude_verdict(stock, trust)
            picks.append({**stock, **trust, **verdict})

    # Sort by trust score descending
    picks.sort(key=lambda x: x['trust_score'], reverse=True)

    # Watchlist grouping
    return {
        "ready_to_buy": [p for p in picks if p['rec'] in ['strong_buy','buy'] and p['in_entry_zone']],
        "still_watching": [p for p in picks if p['rec'] in ['buy','hold'] and not p['in_entry_zone']],
        "dont_buy_yet": [p for p in picks if p['rec'] == 'hold' and p['trust'] < 60]
    }
```

---

## ENVIRONMENT VARIABLES (.env)

```
ANTHROPIC_API_KEY=sk-ant-...
FINNHUB_API_KEY=...
DATABASE_PATH=./stockpulse.db
CACHE_TTL_MINUTES=15
PORT=8000
```

---

## BUILD SEQUENCE — DO THIS IN ORDER

### Step 1: Backend Foundation
```bash
cd stockpulse/backend
pip install fastapi uvicorn yfinance finnhub-python anthropic sqlite3 python-dotenv requests
```
- Create `main.py` with FastAPI app
- Create `database/models.py` — run `CREATE TABLE` statements
- Create `database/db.py` — CRUD operations
- Test: `uvicorn main:app --reload`

### Step 2: Data Fetcher
- Create `data/fetcher.py`
- Implement `get_stock_price(ticker)` using yfinance
- Implement `get_market_data()` — VIX + 4 indices
- Implement `get_fundamentals(ticker)` — revenue, earnings, guidance
- Implement `data/cache.py` — 15-minute TTL cache
- Test: `/api/market` returns real VIX + indices

### Step 3: Trust Score Engine
- Create `intelligence/trust_score.py`
- Implement all 3 pillars
- Implement all auto-disqualifiers
- Test: NKLA returns score <10, AXON returns >75

### Step 4: Pattern Detection
- Create `intelligence/patterns.py`
- Implement all 8 patterns
- Each pattern returns: detected (bool), confidence, plain_english
- Test: each pattern detects on known examples

### Step 5: Claude AI Integration
- Create `intelligence/claude_ai.py`
- Create `intelligence/prompts.py` with SYSTEM_PROMPT
- Test: verdict returns valid JSON, plain English, no jargon

### Step 6: Portfolio + Alert Endpoints
- All CRUD for portfolio
- All CRUD for watchlist
- Alert generation when patterns detected
- Test: add GRRR 100 shares @ $41 → shows -68% P&L

### Step 7: Indian Market Layer
- Create `data/india.py`
- Implement FII/DII fetch (NSE free API)
- Implement promoter holding check
- Add `.NS` / `.BO` suffix detection
- Test: RELIANCE.NS returns Indian-specific signals

### Step 8: React Frontend
- Bootstrap with `create-react-app` or Vite
- Implement design system CSS (exact colours from this file)
- Build components in this order:
  1. Header + AlertBanner + TabNav (shell)
  2. HomeScreen (portfolio arc + signals + market)
  3. StocksScreen (accordion groups + rows)
  4. SmartPicksScreen (compact rows + expand)
- Connect to backend via `api/client.js`
- Test: full app running end to end on localhost

### Step 9: End-to-End Test (Real Portfolio)
```
Add these stocks:
  GRRR  100 shares @ $41    (US, holding at loss)
  INSM  10 shares @ $115    (US, holding at loss)
  TNXP  107 shares @ $46    (US, auto-disqualified — EXIT)
  XGN   50 shares @ $10.50  (US, auto-disqualified — EXIT)

Expected behaviour:
  TNXP → Trust 18, Auto-disqualified, Action Required group
  XGN  → Trust 8, Auto-disqualified, Action Required group
  GRRR → Trust ~65, Watch Closely group
  INSM → Trust ~60, Watch Closely group
  Alert banner → "2 stocks need action today — TNXP · XGN"
```

---

## KEY RULES — NEVER BREAK THESE

```
1. Portfolio value shown in ONE place only: Home screen arc
   Header NEVER shows portfolio value

2. All text must be plain English
   No: "Gap and Go confirmed" "FII net ₹4,200Cr" "Short interest 28%"
   Yes: "Price jumped on real news" "Big investors buying 3 days" "Sellers forced to buy"

3. Every signal must include stop loss in plain English

4. Auto-disqualifiers always run FIRST before any other analysis

5. Trust Score < 40 = no bullish signals fire, ever

6. Market conditions card = market-wide data only
   Stock-specific data lives on stock rows, not market cards

7. Signal accuracy % shown only on Smart Picks screen
   Not on market conditions. Not in header.

8. All three markets treated equally
   Every stock shows its country flag 🇺🇸 🇪🇺 🇮🇳
   No market gets special treatment or its own section
   Indian stocks live in same accordion groups as US stocks

9. Only ONE accordion group open at a time
   In My Stocks: Action Required / Watch Closely / Holding Well
   In Watchlist: Ready to Buy / Still Watching / Don't Buy Yet

10. Claude API calls must output structured JSON
    Validate before showing to user
    If Claude returns invalid JSON → show cached verdict, flag for review
```

---

## REFERENCE UI FILE

The exact UI prototype is saved at:
`/mnt/user-data/outputs/stockpulse_v3.jsx`

This is a complete React component with all CSS, data, and components.
**The built app must match this design exactly.**

Key things to extract from it:
- All CSS variables and values
- Component structure and layout
- Accordion behaviour
- Expand/collapse animations
- Filter pill behaviour
- Watchlist vs My Stocks view switching

---

## ACCURACY TRACKING (from day 1)

Every signal fired → record in `signals` table.
At 30/60/90 days → check if outcome was correct.

```python
def mark_signal_outcome(signal_id, current_price, entry_price, stop_loss_pct):
    stop_loss_price = entry_price * (1 - stop_loss_pct)
    if current_price <= stop_loss_price:
        outcome = "incorrect"  # Stop loss triggered
    elif current_price > entry_price * 1.08:
        outcome = "correct"    # Up >8%
    else:
        outcome = "pending"    # Still running

# Show on Smart Picks: "71% accurate · 90 days"
# This number MUST be real, from the signals table, not hardcoded
```

---

*End of CLAUDE.md*
*Read this file at the start of every session before making any changes.*

---

## ADDITIONS — ALL NEW FEATURES (Added after initial spec)

---

## UPDATED NAVIGATION — 4 TABS (not 3)

```
🏠 Home  |  📊 Stocks  |  🎯 Smart Picks  |  🧭 Strategy
```

Tab 4 is **Strategy** — the most important differentiator.
Badge on Strategy tab shows total active situations count.

```javascript
// Tab grid CSS: 4 columns
.tabs { grid-template-columns: 1fr 1fr 1fr 1fr; }
```

---

## SCREEN 4 — STRATEGY CENTRE

The single most powerful screen in the app.
Shows what to do with EVERY stock — owned, watched, or considering.

### Header
```
Strategy Centre                    11 active
What to do with each stock — right now
```

### Three Sub-Tabs (inside the screen)
```
[My Stocks 5]  [Watchlist 3]  [Smart Picks 3]
```

Each sub-tab shows compact rows — one per stock.
Only ONE row expanded at a time (accordion).

### Strategy Row
```
🚨 🇺🇸 TNXP   Exit Required    Earnings today, exit on pop    EXIT ▼
📉 🇺🇸 GRRR   Crash Decision   Down 68% but business intact   HOLD ▼
👁  🇺🇸 AXON   Pullback Trap    Watched 68 days, up 24%        DECIDE ▼
```

Each row: icon + flag + ticker + situation label + summary + action badge + chevron

### Expanded Strategy Row
```
WHAT TO DO
[Plain English playbook — 3-4 sentences explaining exactly what
 to do and why, using no jargon]

[Action Button — full width, coloured by urgency]
Exit This Position → / View Full Analysis → / Make a Decision →
```

### Action Colour Logic
```
EXIT / WAIT     → Rose (red)    — urgent
HOLD / WATCH    → Amber         — monitor  
TRIM / DECIDE   → Amber         — review needed
BUY / STRONG BUY → Emerald (green) — opportunity
```

### My Stocks Sub-Tab Data Structure
```python
{
  "ticker": "GRRR",
  "flag": "🇺🇸",
  "label": "Crash Decision",   # Situation name
  "icon": "📉",
  "action": "HOLD",            # What to do
  "color": "var(--amber)",     # Label colour
  "summary": "Short 1-line summary shown in compact row",
  "playbook": "Full plain English explanation shown when expanded"
}
```

---

## WATCHLIST INTELLIGENCE — SCREEN 2 UPDATE

When user selects **Watchlist** filter pill on Stocks screen,
the groups change entirely from portfolio groups.

### Portfolio Groups (My Stocks / All / Country filter):
```
🔴 Action Required   (stocks owned needing urgent action)
🟡 Watch Closely     (stocks owned to monitor)
🟢 Holding Well      (stocks owned doing fine)
```

### Watchlist Groups (Watchlist filter selected):
```
🟢 Ready to Buy      (AI says enter NOW — entry conditions met)
🟡 Still Watching    (good stock, wrong time — wait)
🔴 Don't Buy Yet     (red flags or overpriced — avoid)
```

### Watchlist Row (different from portfolio row — no P&L)
```
● 🇺🇸 AXON  Entry zone now    Watched 68 days...  87/100  ▼
```
No P&L shown (user doesn't own these stocks).

### Expanded Watchlist Row
```
[Plain English reason for current status]

Best Entry   $285-$310
Potential    +45-70%

[Action button]
```

---

## 15 UNIVERSAL STRATEGY SITUATIONS

These are the situations every investor faces at least once.
The app detects them automatically and surfaces the playbook.

### Detection Triggers (backend: situation_detector.py)

```python
def detect_situations(portfolio, watchlist, market_data, signals_history):
    situations = []

    for stock in portfolio:
        # 1. Crash Decision
        if stock.change_30d < -0.20:
            situations.append({"type":"crash_decision","ticker":stock.ticker,"priority":2})

        # 2. Profit Decision
        if stock.change_from_entry > 0.30:
            situations.append({"type":"profit_decision","ticker":stock.ticker,"priority":3})

        # 3. Earnings Decision
        if 0 < days_until_earnings(stock) <= 5:
            situations.append({"type":"earnings_decision","ticker":stock.ticker,"priority":1})

        # 4. Concentration Risk
        if stock.portfolio_weight > 0.20:
            situations.append({"type":"concentration","ticker":stock.ticker,"priority":2})

        # 5. Position Sizing (always — on new adds)
        # Shown during add stock flow, not as alert

        # 6. Turnaround Play
        if stock.drop_from_ath > 0.50 and stock.trust_score > 60:
            situations.append({"type":"turnaround","ticker":stock.ticker,"priority":3})

        # 7. Exit Required (auto-disqualified)
        if stock.auto_disqualified:
            situations.append({"type":"exit_now","ticker":stock.ticker,"priority":0})

    for stock in watchlist:
        # 8. Pullback Trap
        if stock.days_on_watchlist > 60 and stock.change_since_added > 0.15:
            situations.append({"type":"pullback_trap","ticker":stock.ticker,"priority":2})

        # 9. Ready to Buy
        if stock.trust_score >= 75 and stock.in_entry_zone:
            situations.append({"type":"ready_to_buy","ticker":stock.ticker,"priority":1})

        # 10. ATH Anxiety
        if market_data.at_ath and stock.days_on_watchlist > 30:
            situations.append({"type":"ath_anxiety","ticker":stock.ticker,"priority":3})

    # Portfolio-level situations
    # 11. Bear Market Survival
    if market_data.vix > 30 and market_data.sp500_drawdown > 0.15:
        situations.append({"type":"bear_market","ticker":None,"priority":0})

    # 12. FOMO Chase (watchlist stocks that ran)
    for stock in watchlist:
        if stock.change_90d > 0.35 and stock.social_sentiment > 0.80:
            situations.append({"type":"fomo_chase","ticker":stock.ticker,"priority":2})

    # 13. Losing Streak
    recent_signals = [s for s in signals_history if s.age_days < 30]
    if len(recent_signals) >= 3:
        wrong = sum(1 for s in recent_signals[-5:] if s.outcome == "incorrect")
        if wrong >= 3:
            situations.append({"type":"losing_streak","ticker":None,"priority":2})

    # 14. Inflation Hedge
    if market_data.cpi > 4.0:
        situations.append({"type":"inflation_hedge","ticker":None,"priority":3})

    # 15. Barbell Strategy (geopolitical)
    if market_data.vix > 25 or market_data.geopolitical_flag:
        situations.append({"type":"barbell","ticker":None,"priority":2})

    return sorted(situations, key=lambda x: x["priority"])
```

### 15 Strategy Playbook Templates

```python
STRATEGY_PLAYBOOKS = {

    "crash_decision": {
        "label": "Crash Decision",
        "icon": "📉",
        "question": "My stock dropped 30%+. Sell, hold or buy more?",
        "check_hold": ["trust_score > 60", "revenue_beating_estimates", "ceo_stayed", "sector_not_declining"],
        "check_exit": ["trust_score < 40", "revenue_missing", "guidance_cut", "insider_selling"],
        "hold_playbook": "Business fundamentals intact. The fall is market-driven not company-driven. Hold. Set stop loss at [X]% below current price.",
        "exit_playbook": "The fundamentals have deteriorated alongside the price. This is not a dip — it is a decline. Exit and protect capital.",
    },

    "profit_decision": {
        "label": "Profit Decision",
        "icon": "💰",
        "question": "I'm up 30%+. Take profits or let it run?",
        "keep_running": ["trust_score > 75", "price_below_analyst_target", "institutional_still_buying"],
        "trim_signals": ["portfolio_weight > 0.20", "approaching_analyst_target", "insider_selling_beginning"],
        "sell_signals": ["trust_score_declining", "fundamentals_weakening", "retail_fomo_phase"],
    },

    "earnings_decision": {
        "label": "Earnings Decision",
        "icon": "📊",
        "question": "Earnings in 5 days. Hold, add or exit?",
        "hold_high_trust": "Hold. Company has strong track record. Risk is managed with existing position.",
        "exit_low_trust": "Exit before earnings. Risk/reward unfavourable. Another miss likely.",
        "sizing_rule": "If you would not add at this price, reduce to half position before earnings.",
    },

    "concentration": {
        "label": "Concentration Risk",
        "icon": "⚠️",
        "question": "One stock is 20%+ of my portfolio.",
        "playbook": "Trim to 15% target. OR add other positions to dilute. OR set hard stop 20% below current price. Never let one stock exceed 25% of portfolio.",
    },

    "exit_now": {
        "label": "Exit Required",
        "icon": "🚨",
        "question": "Auto-disqualified stock. What now?",
        "playbook": "Exit immediately. Auto-disqualifiers exist because historical data shows these patterns precede significant further decline in 90%+ of cases. Do not hold hoping for recovery.",
    },

    "pullback_trap": {
        "label": "Pullback Trap",
        "icon": "👁",
        "question": "Waited 60+ days for a pullback that never came.",
        "options": [
            "Buy 50% now, 50% on any 8-12% dip",
            "Set price alert and walk away",
            "Remove — consciously accept you missed this move"
        ],
        "playbook": "Doing nothing is also a decision. The pullback may not arrive before the next leg higher.",
    },

    "ready_to_buy": {
        "label": "Ready to Buy",
        "icon": "🟢",
        "question": "Entry conditions aligned. When do I buy?",
        "playbook": "Trust Score is strong. Entry zone is active. Smart money is in. The time to act is now. Position sizing: 5-10% depending on conviction.",
    },

    "ath_anxiety": {
        "label": "ATH Anxiety",
        "icon": "🏔️",
        "question": "It's at all-time highs. Is it too late?",
        "playbook": "Quality stocks with improving fundamentals at ATH historically continue higher 71% of the time. ATH is not a sell signal. Deteriorating fundamentals at ATH is a sell signal.",
    },

    "bear_market": {
        "label": "Bear Market",
        "icon": "🐻",
        "question": "Everything is falling. What do I do?",
        "phases": {
            "early": "Trim speculative positions. Raise 20-30% cash. Add defensive stocks.",
            "deep": "Stop selling at the bottom. Watch for capitulation signal. Deploy cash slowly.",
            "recovery": "Rotate from defensive to growth. Best 12-month returns start here.",
        },
    },

    "fomo_chase": {
        "label": "FOMO Chase",
        "icon": "🔥",
        "question": "Ran 80% already. Did I miss it?",
        "genuine_momentum": "Revenue backing the move. Institutional still buying. Still has room. Enter with trailing stop.",
        "fomo_trap": "Only retail buying. No fundamental backing. 78% of these reverse within 60 days.",
    },

    "losing_streak": {
        "label": "Losing Streak",
        "icon": "📉",
        "question": "3+ wrong signals in a row. Am I bad at this?",
        "playbook": "Normal variance. Worst historical 30-day stretch was 35% accuracy. Reduce position sizes 30% for next 3 trades. Do not over-trade to recover.",
    },

    "inflation_hedge": {
        "label": "Inflation Hedge",
        "icon": "📈",
        "question": "Inflation rising. What stocks protect me?",
        "buy": ["Defence", "Commodity producers", "Pricing-power businesses", "Real assets"],
        "avoid": ["High-PE growth", "Utilities", "REITs", "Debt-heavy companies"],
    },

    "barbell": {
        "label": "Barbell Strategy",
        "icon": "🏋️",
        "question": "Geopolitical risk rising. How do I position?",
        "safe_end": ["Defence stocks", "Gold", "Domestic-only businesses", "Energy security"],
        "risky_end": ["AI × Defence", "Cybersecurity", "Critical minerals", "India (China decoupling)"],
        "avoid": "The middle — moderate risk, moderate reward — gets destroyed in volatility.",
    },

    "turnaround": {
        "label": "Turnaround Play",
        "icon": "🔄",
        "question": "Great company now struggling. Comeback or dead?",
        "checklist": [
            "CEO stayed (or credible new CEO)",
            "Core business model still valid",
            "Cash runway > 18 months",
            "70%+ creditor/shareholder support",
            "Revenue declining but beating estimates",
            "Category not structurally shrinking",
            "Insider buying post-crash"
        ],
        "rule": "All 7 YES → Genuine turnaround. Any 2 NO → Dead cat bounce. Avoid.",
    },

    "speculative_bet": {
        "label": "Speculative Bet",
        "icon": "🎲",
        "question": "Small company with 10× upside if one thing goes right.",
        "rules": [
            "Max 2-3% of portfolio per bet",
            "Max 10% of portfolio total in speculative positions",
            "Clear catalyst identified",
            "Downside clearly limited",
            "You can explain it in one sentence"
        ],
    },
}
```

---

## STRATEGY CENTRE — BACKEND ENDPOINT

```python
GET /api/strategy

Response:
{
  "total_situations": 11,
  "my_stocks": [
    {
      "ticker": "TNXP",
      "flag": "🇺🇸",
      "situation_type": "exit_now",
      "label": "Exit Required",
      "icon": "🚨",
      "action": "EXIT",
      "summary": "Auto-disqualified. Earnings today. Exit on any pop.",
      "playbook": "Full Claude-generated plain English playbook...",
      "priority": 0
    }
  ],
  "watchlist": [...],
  "smart_picks": [...]
}
```

Playbook is Claude-generated per situation using:
- Situation type
- Stock specific data (trust score, recent performance, fundamentals)
- Market conditions (VIX, regime)

```python
def generate_playbook(situation_type, stock_data, market_data):
    template = STRATEGY_PLAYBOOKS[situation_type]
    prompt = f"""
    Situation: {situation_type}
    Stock: {stock_data}
    Market: {market_data}

    Write a 3-4 sentence plain English playbook for what this investor
    should do RIGHT NOW. No jargon. Specific to their situation.
    Include a specific stop loss or exit condition.
    """
    return claude_api.complete(prompt)
```

---

## PLAIN ENGLISH RULES — EXTENDED

The following translations are mandatory. Never use the jargon version.

```
JARGON                    → PLAIN ENGLISH
──────────────────────────────────────────────────────────────────
Gap and Go                → Price jumped on news and keeps rising
Short squeeze             → Sellers forced to buy back pushing price up
FII net ₹4,200Cr          → Large overseas investors bought heavily
Short interest 28%        → 28% of investors are betting it falls
VWAP hold                 → Price staying above its daily average
Dark pool accumulation    → Institutions quietly building position
Dead cat bounce           → Temporary bounce in a continuing decline
ATH launchpad             → All-time high — quality stocks often continue
Sandbagging               → Company sets low guidance then beats it
Kitchen sink quarter      → Deliberately bad quarter to reset expectations
Capitulation              → Panic selling — often marks the bottom
Factor exposure           → Type of stocks this tends to be
Information coefficient   → How reliable this signal is historically
Regime                    → Current market conditions
VIX                       → Fear Index (shown with number, not term alone)
Trailing stop             → Sell if it falls X% from its peak
Bull market               → Market Calm (in header pill)
Bear market               → Market Falling (in header pill)
High volatility           → Market Alert (in header pill)
```

---

---

## STOCKS SCREEN — FILTER LOGIC (FINAL)

This is the exact behavior every filter pill must produce.
Do not deviate from this.

### Filter Pills
```
All  |  My Stocks  |  Watchlist  |  🇺🇸 US  |  🇪🇺 Europe  |  🇮🇳 India
```

### Exact Behavior Per Filter

```
ALL
  Shows EVERYTHING — portfolio + watchlist, all countries
  Section 1 — My Stocks label (mono 9px uppercase)
    🔴 Action Required  (portfolio stocks needing urgent action)
    🟡 Watch Closely    (portfolio stocks to monitor)
    🟢 Holding Well     (portfolio stocks doing fine)
  Section 2 — Watchlist label (mono 9px uppercase, marginTop 12px)
    🟢 Ready to Buy     (watchlist stocks — entry conditions met)
    🟡 Still Watching   (watchlist stocks — waiting for right time)
    🔴 Don't Buy Yet    (watchlist stocks — red flags/overpriced)

MY STOCKS
  Shows portfolio groups ONLY (no watchlist)
    🔴 Action Required
    🟡 Watch Closely
    🟢 Holding Well
  No watchlist section shown

WATCHLIST
  Shows watchlist groups ONLY (no portfolio)
    🟢 Ready to Buy
    🟡 Still Watching
    🔴 Don't Buy Yet
  No portfolio section shown

🇺🇸 US / 🇪🇺 Europe / 🇮🇳 India (country filters)
  Shows BOTH portfolio AND watchlist — filtered to that country
  Section 1 — My Stocks label (only if stocks exist)
    🔴 Action Required  (only stocks with matching flag)
    🟡 Watch Closely    (only stocks with matching flag)
    🟢 Holding Well     (only stocks with matching flag)
  Section 2 — Watchlist label (only if watchlist items exist)
    🟢 Ready to Buy     (only items with matching flag)
    🟡 Still Watching   (only items with matching flag)
    🔴 Don't Buy Yet    (only items with matching flag)
  Empty state: if no stocks in that country → show flag + "No X stocks yet"
```

### Country Flag Values
```
US stocks:     flag: "🇺🇸"
EU stocks:     flag: "🇪🇺"
Indian stocks: flag: "🇮🇳"

Filter matching:
  "🇺🇸 US"     → s.flag === "🇺🇸"
  "🇪🇺 Europe" → s.flag === "🇪🇺"
  "🇮🇳 India"  → s.flag === "🇮🇳"
```

### Accordion Rules (STRICT)
```
Portfolio groups: ONE open at a time
  Opening one closes any currently open portfolio group
  Tapping same group again → closes it (all collapsed)
  Default: Action Required open on first load

Watchlist groups: ONE open at a time (separate accordion state)
  Independent from portfolio accordion
  Default: Ready to Buy open on first load

Portfolio accordion and Watchlist accordion are INDEPENDENT
Opening a watchlist group does NOT close a portfolio group
```

### Groups That Are Empty — Hide Them
```
If filteredUrgent.length === 0 → do NOT render Action Required group
If filteredWatch.length === 0  → do NOT render Watch Closely group
If filteredGood.length === 0   → do NOT render Holding Well group
Same applies to watchlist groups
Never show an empty accordion header
```

### React State Required for StocksScreen
```javascript
const [f, setF] = useState("All");           // Active filter pill
const [openGroup, setOpenGroup] = useState("urg");   // Portfolio accordion
const [openWatch, setOpenWatch] = useState("ready"); // Watchlist accordion

const toggle = id => setOpenGroup(g => g === id ? null : id);
const toggleWatch = id => setOpenWatch(g => g === id ? null : id);

const isWatchlist = f === "Watchlist";
const isCountry = ["🇺🇸 US","🇪🇺 Europe","🇮🇳 India"].includes(f);

const byCountry = stocks => {
  if(f === "🇺🇸 US") return stocks.filter(s => s.flag === "🇺🇸");
  if(f === "🇪🇺 Europe") return stocks.filter(s => s.flag === "🇪🇺");
  if(f === "🇮🇳 India") return stocks.filter(s => s.flag === "🇮🇳");
  return stocks;
};

// When filter changes, reset accordion to default open state
// onClick: setF(p); setOpenGroup("urg");
```

### Stock Data Structure (Portfolio)
```javascript
{
  ticker: "GRRR",
  flag: "🇺🇸",           // REQUIRED on every stock — used for filtering
  price: 13.06,
  change: -68.1,          // % change today
  name: "Gorilla Technology",
  buy: 41,                // User's buy price
  shares: 100,            // Number of shares owned
  rec: "HOLD",            // SELL / HOLD / BUY
  rcls: "rr-h",           // CSS class: rr-s / rr-h / rr-b / rr-sb
  trust: 68,              // Trust score 0-100
  verdict: "Plain English explanation of situation",
  earn: "Jun 17"          // Next earnings date
}
```

### Watchlist Data Structure
```javascript
{
  ticker: "AXON",
  flag: "🇺🇸",           // REQUIRED — used for country filtering
  price: 298.4,
  change: +1.8,
  name: "Axon Enterprise",
  trust: 87,
  signal: "Entry zone now",     // Short label shown in row
  reason: "Plain English reason for current status",
  entry: "$285-$310",           // Best entry price
  potential: "+45-70%"          // Upside potential
}
// NOTE: No buy/shares/P&L — user does not own watchlist stocks
```

### Two Different Row Components
```
StockRow    → for portfolio stocks (shows P&L, earnings, verdict, AI grade)
WatchRow    → for watchlist stocks (shows signal, entry, potential — NO P&L)

Never use StockRow for watchlist stocks.
Never use WatchRow for portfolio stocks.
```

---

## LATEST ADDITIONS — FINAL FEATURES

---

### STOCKS SCREEN — PIVOT TABLE DESIGN (Final)

**Completely replaces accordion groups** with a compact data table.

```
PivotSection component:
  - One card per section (My Stocks / Watchlist)
  - Header: thin accent bar + section label + inline pill tabs + total count
  - 3 pill tabs inline (not stacked): tap to switch active category
  - Column headers row (7px mono uppercase)
  - Compact data rows below
```

**My Stocks slice labels:**
```
Urgent  |  Monitor  |  Stable
  2     |     4     |     6
```
NOT: "Exit Now / Watching / Holding" — these caused confusion

**Watchlist slice labels:**
```
Ready  |  Waiting  |  Avoid
  2    |     2     |    1
```

**CompactRow (portfolio stocks):**
```
Grid: 1.9fr 1.5fr .7fr .9fr
Col 1: Flag + Ticker + ▲/▼% + name (9px below)
Col 2: Price · P&L on same line (no stacking)
Col 3: Trust score number only (no "score" label)
Col 4: Rec badge (S.SELL / S.BUY / HOLD etc.)
Row padding: 7px 12px
```

**CompactWatchRow (watchlist stocks):**
```
Grid: 1.4fr 1.8fr .8fr
Col 1: Flag + Ticker + name
Col 2: Signal badge + entry price
Col 3: Trust score + potential upside
```

**Expanded inline panel (tap any row):**
```
Verdict with left border accent
Earnings · Grade · Bought info on one line
[Full Analysis →]  [Exit / Set Alert]
```

**All filters use PivotSection:**
```
All → My Stocks PivotSection + Watchlist PivotSection
My Stocks → My Stocks PivotSection only
Watchlist → Watchlist PivotSection only
🇺🇸 🇪🇺 🇮🇳 → both sections filtered by country flag
```

---

### SMART PICKS SCREEN — Final Design

**Quiet header:**
```
Smart Picks  [71% · 90d]     2 active
```
Title: Syne 700 13px (not 800 16px — no shouting)

**Picks table:**
```
Column headers: Stock | Rec | AI | Upside | (expand)
Row padding: 7px 12px
Ticker: 12px Syne 700
Name: 8px below, muted
Score: 11px mono, colour coded
```

**Expanded pick panel:**
```
2px gradient bar (full width)
3 pillars: single connected bar (3 segments, no floating cards)
3 key signals (bullet list, 10px)
4 stats in ONE row: Upside | Entry | Risk | When
  Each: tiny card, label 6px top, value 8px below
```

**Blocked section:**
```
▌ Blocked — AI signals won't fire on these    3
TICKER  reason truncated...                  score
(no 🚫 emoji, no heavy header, clean inline rows)
```

---

### EARNINGS INTEL FEATURE

**New feature — accessible from Home screen card.**

**Home screen card (always visible):**
```
📅 Earnings Watch                   View all →
XGN  PM +13%  Board resigned Apr 23...
TNXP PM -3%   Auto-disqualified...
```
Pulsing badge when earnings are today.

**EarningsIntel overlay (tap card):**
Slides up from bottom. Shows:
```
TODAY · PENDING
  XGN  Today  PM +13%  Board resigned · results pending →
  TNXP Today  PM -3%   Auto-disqualified · exit now     →

UPCOMING
  GRRR  Jun 17  Watch contract commentary               →
  NVDA  Aug 21  Blackwell ramp commentary               →
  ASML  Jul 16  EUV order backlog update                →
```

**EarningsDetail overlay (tap any earnings card):**
Full detail sliding up:
```
Header: Flag + Ticker + Pre-market % + Price (gradient)
Status banner: "⚡ Pre-market pop — exit window active"
               or "⏳ Results pending"

EPS Estimate | Revenue Estimate
(2 cards side by side)

Earnings History table:
Quarter | Est | Actual | ✅/❌

Your Position:
Shares | Bought at | P&L
(3 columns, if in portfolio)

What to do (coloured left-border card):
  Action label (Exit on pop / Hold / Add)
  Plain English explanation

[Exit Position →]  [Set Price Alert]
```

**EARNINGS DATA STRUCTURE:**
```javascript
{
  ticker: "XGN",
  flag: "🇺🇸",
  name: "Exagen Inc",
  date: "Today",          // "Today" | "Jun 17" | "Aug 21"
  time: "Pre-market",     // "Pre-market" | "After market"
  status: "pending",      // "pending" | "upcoming" | "released"
  inPortfolio: true,
  shares: 50,
  buyPrice: 10.50,
  currentPrice: 3.39,
  preMarketChg: +13.0,    // null if not today
  epsEst: -0.19,
  revEst: 17.0,
  note: "Plain English note about this earnings event",
  history: [
    {q:"Q4 2025", epsEst:-0.20, epsAct:-0.20, beat:false},
    {q:"Q3 2025", epsEst:-0.22, epsAct:-0.21, beat:true}
  ]
}
```

**Action logic (per stock):**
```
Auto-disqualified stocks → EXIT regardless of results
Pre-market pop >8% on disqualified → EXIT ON POP (urgent)
High trust stock → HOLD through earnings
GRRR → HOLD — watch guidance
Default strong trust → HOLD with confidence
```

**Backend endpoint for production:**
```
GET /api/earnings
  → Returns all portfolio + watchlist stocks with upcoming earnings
  → Fetches from Finnhub earnings calendar
  → Checks SEC EDGAR for any same-day press releases
  → Polls every 5 minutes during earnings season

POST /api/earnings/{ticker}/result
  → Called when results are detected
  → Triggers AI analysis of beat/miss/guidance
  → Fires push notification to user
  → Updates recommendation in real time
```

---

### HOME SCREEN — FINAL STATE

No "Action Required" card — removed to avoid duplicate with alert banner.

```
Header (gradient, sticky)
Alert Banner (only when urgent)
Tab Nav (4 tabs)

Scroll content:
  Portfolio Arc (real calculated data)
  📅 Earnings Watch card
  Today's Signals (accordion)
  Market Conditions (VIX + 4 markets)
```

**Portfolio arc — all values calculated from real data:**
```javascript
const all = [...URGENT, ...WATCH, ...GOOD];
const val = all.reduce((s,p) => s + p.price * p.shares, 0);
const invested = all.reduce((s,p) => s + p.buy * p.shares, 0);
const pnl = val - invested;
// Positions: count by flag from portfolio only — NEVER watchlist
```

---

### KEY DESIGN RULES — FINAL

```
1. Labels whisper. Data speaks.
   Font hierarchy: data values large/bold, labels tiny/muted

2. Rows breathe — not too tight, not wasteful
   Pick rows: 7px padding
   Compact table rows: 7-8px padding
   Headers: 4-5px padding

3. No duplicate information
   Action Required appears ONCE (alert banner OR home card — not both)
   Portfolio value in ONE place only (arc on Home)

4. Pre-market indicators pulse
   animation: "pr 1.2s infinite" (keyframe defined in CSS)

5. Everything is plain English
   "Urgent" not "Exit Now"
   "Monitor" not "Watching"
   "Stable" not "Holding"
   Pre-market pop → "Exit window active NOW"

6. Earnings events get dedicated treatment
   Not just a signal row — full overlay with history + position + action

7. Real data, never hardcoded
   Portfolio values calculated from arrays
   Positions count from portfolio arrays only
```

---

### APP COMPONENT — FINAL STATE

```javascript
// 4 state variables
const [tab, setTab] = useState(0);
const [sel, setSel] = useState(null);           // selected stock for StockDetail
const [showEarnings, setShowEarnings] = useState(false);  // EarningsIntel overlay

// 4 screens
const screens = [
  <HomeScreen onEarnings={()=>setShowEarnings(true)}/>,
  <StocksScreen onDetail={setSel}/>,
  <SmartPicksScreen/>,
  <StrategyScreen/>,
];

// 2 overlays rendered on top
{sel && <StockDetail ... onClose={()=>setSel(null)}/>}
{showEarnings && <EarningsIntel onClose={()=>setShowEarnings(false)}/>}
```

---

### FUNCTION ORDER IN FILE (important for Claude CLI)

```
1.  imports (useState, recharts)
2.  CSS string constant
3.  Data arrays (URGENT, WATCH, GOOD, WL_READY, WL_WATCH, WL_AVOID)
4.  SIGNALS, PICKS, DISQ data
5.  STRATEGY data
6.  EARNINGS data
7.  Utility functions (tc, tg, isINR, cu, genChart)
8.  Tip (CustomTooltip) — arrow component
9.  Ring — arrow component
10. StockDetail — function component
11. StockRow — function component
12. Group — function component
13. WatchGroup — function component
14. EarningsCard — function component
15. EarningsDetail — function component
16. EarningsIntel — function component
17. PortfolioArc — function component
18. HomeScreen — function component
19. CompactRow — function component
20. CompactWatchRow — function component
21. PivotSection — function component
22. StocksScreen — function component
23. SmartPicksScreen — function component
24. StrategyScreen — function component
25. App — default export
```

---

### FINAL UI REFERENCE FILE

**`StockPulse_finalised_version.jsx`**

Complete production-ready React prototype.
Zero errors. All div balanced. All features working.

Build the backend to serve this frontend exactly.


---

### EXPANDED STOCK ROW — Design Rules

When a stock row is tapped and expands, show a clean breezy layout. No nested boxes. No form-like grid.

**Structure:**
```
1. Stats strip (single segmented row — no individual boxes)
   P&L | AI Score | Earnings
   All in one clean white card, divided by hairlines

2. Grade + Recommendation as pills (not boxes)
   [Blocked] [Strong Sell]  ← coloured pills, float naturally

3. Verdict as a conversation (left border accent, no background box)
   "8 reverse splits. Exit on any pre-market pop."

4. Action buttons (full width, bolder)
   [Full Analysis →]  [Exit Position]
```

**CSS rules:**
```css
/* Stats strip — segmented single row */
.se-stats { display:flex; background:white; border-radius:10px;
            border:1px solid rgba(15,23,42,.06); overflow:hidden; }
.se-stat  { flex:1; padding:10px 8px; text-align:center;
            border-right:1px solid rgba(15,23,42,.06); }
.se-stat:last-child { border-right:none; }

/* Grade/Rec as pills */
/* Use coloured pill badges, NOT boxes */

/* Verdict — no background box */
.se-verdict { font-size:11px; line-height:1.6;
              padding-left:12px; border-left:3px solid [dot colour]; }
```

**What NOT to do:**
```
❌ Individual boxes for each stat (P&L box, AI Score box, Earnings box)
❌ AI Grade box + Recommendation box (separate cards)
❌ Verdict inside a background box
✅ Everything flows naturally, no heavy borders or backgrounds
```

---

### PORTFOLIO ARC — Data Rules

The portfolio arc on the Home screen must:

```
1. Calculate from REAL data (not hardcoded)
   const all = [...URGENT, ...WATCH, ...GOOD];
   const val = all.reduce((s,p) => s + p.price * p.shares, 0);
   const invested = all.reduce((s,p) => s + p.buy * p.shares, 0);

2. Positions counter = portfolio stocks ONLY
   Count flags from URGENT + WATCH + GOOD arrays
   NEVER count watchlist stocks (WL_READY, WL_WATCH, WL_AVOID)

3. Display:
   Value:     calculated from real prices × shares
   Invested:  calculated from buy prices × shares
   P&L:       val - invested (positive=emerald, negative=rose)
   Positions: 🇺🇸N 🇪🇺N 🇮🇳N — only markets where user OWNS stocks
              Hide any market with count=0
```

---

### FINAL UI REFERENCE FILE

`StockPulse_ready_to_develop.jsx`

Complete React prototype — production ready.
Build the app to match this file exactly.

**All 4 screens:**
- 🏠 Home — Portfolio arc (real data) + alerts + signals + market
- 📊 Stocks — Accordion groups + smart filter pills + watchlist intelligence
- 🎯 Picks — Compact rows + tap to expand with pillars + signals
- 🧭 Strategy — 3 sub-tabs with situation playbooks

**All interactions working:**
- Tap stock row → expands with clean breezy layout
- Full Analysis → StockDetail overlay (chart + 52w range + AI + forecast + metrics)
- Accordion groups — one open at a time
- Filter pills — All/My Stocks/Watchlist/🇺🇸/🇪🇺/🇮🇳 all wired up
- Watchlist groups differ from portfolio groups
- Country filters show both portfolio AND watchlist for that market



