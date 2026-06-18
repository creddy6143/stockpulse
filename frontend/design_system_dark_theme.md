# StockPulse — Dark Theme Design Tokens (My Stocks)

Applies to: `CompactRow` component and the `PivotSection` container when `dark={true}`.
All other screens and tabs remain on the existing light theme.

---

## Colour Tokens

| Token         | Value       | Usage                                          |
|---------------|-------------|------------------------------------------------|
| `DK_BG`       | `#141821`   | Stock row background (normal)                 |
| `DK_HOVER`    | `#1a2030`   | Stock row background (expanded / hovered)     |
| `DK_EXP`      | `#0f1520`   | Expanded panel background                     |
| `DK_HDR`      | `#0f1420`   | PivotSection header strip background          |
| `DK_SURFACE`  | `#0a0e14`   | PivotSection outer container background       |
| `DK_T1`       | `#f5f7fa`   | Primary text (company name, large numbers)    |
| `DK_T2`       | `#a8b2c0`   | Secondary text (sub-labels, entry price)      |
| `DK_T3`       | `#7a8290`   | Muted text (column labels, timestamp, chevron)|
| `DK_DIV`      | `rgba(255,255,255,.07)` | Row dividers, section borders       |
| `DK_POS`      | `#4da3ff`   | Positive values — daily gain, total return    |
| `DK_NEG`      | `#ff5c5c`   | Negative values — daily loss, total loss      |

---

## Semantic Colours (Intelligence Layer)

These colours appear on the bottom intelligence line of each row.

| State         | Colour      | Usage                                          |
|---------------|-------------|------------------------------------------------|
| Urgent        | `#ff5c5c`   | Urgency dot + label — auto-disqualified/SELL   |
| Monitor       | `#f5a623`   | Urgency dot + label — watch closely            |
| Stable        | `#4ade80`   | Urgency dot + label — holding well             |
| Trust 75+     | `#6b8cff`   | Trust score text — Strong                     |
| Trust 60–74   | `#f5a623`   | Trust score text — Moderate                   |
| Trust 40–59   | `#f59e0b`   | Trust score text — Weak                       |
| Trust <40     | `#ff5c5c`   | Trust score text — Blocked                    |
| REC: BUY      | `#4ade80`   | Recommendation badge text                     |
| REC: HOLD     | `#f5a623`   | Recommendation badge text                     |
| REC: SELL     | `#ff5c5c`   | Recommendation badge text                     |
| REC: Review   | `#7a8290`   | Suppressed score — no directional call        |

---

## Row Layout — Avanza Style

Each portfolio stock row has three visual zones:

### 1. Header line (padding: 14px 16px 8px)
```
🇺🇸  NVIDIA Corporation  NVDA                15:42  ›
```
- Flag: 16px
- Company name: DM Sans 600 15px DK_T1
- Ticker: IBM Plex Mono 11px DK_T3
- Timestamp: IBM Plex Mono 11px DK_T3
- Chevron: `›` 20px DK_T3

### 2. 4-column data grid (grid: 1fr 1fr 1fr 1fr, padding: 0 16px 10px)

| Col | Label     | Primary (15px mono)  | Secondary (12px mono)    |
|-----|-----------|----------------------|--------------------------|
| 1   | Idag      | daily % (DK_POS/NEG) | daily absolute (opacity .72) |
| 2   | Kurs/Inköp| current price (DK_T1)| buy price (DK_T2)        |
| 3   | Sedan köp | total return % (DK_POS/NEG) | total SEK P&L (opacity .72) |
| 4   | Innehav   | total value kr (DK_T1)| share count (DK_T2)     |

Column labels: IBM Plex Mono 10px DK_T3, letter-spacing 0.5px.

### 3. Intelligence line (padding: 7px 16px 13px, border-top: DK_DIV)
```
Trust 87 · S.BUY · Stable                            ●
```
- Trust score: mono 12px, colour by grade, tap opens score breakdown
- Separator dots: DK_DIV coloured
- REC badge: mono 12px bold, colour by recommendation
- Category label: DM Sans 12px, urgency colour
- Right dot: 8×8px circle with glow, urgency colour

---

## PivotSection Container (dark=true)

| Property          | Value                          |
|-------------------|--------------------------------|
| Background        | `#0a0e14`                      |
| Border            | `1px solid rgba(255,255,255,.07)` |
| Shadow            | `0 4px 24px rgba(0,0,0,.4)`    |
| Header background | `#0f1420`                      |
| Header text       | `#a8b2c0` (DK_T2)              |
| Pill active bg    | `{sliceColor}18`               |
| Pill inactive bg  | `rgba(255,255,255,.05)`        |

Watchlist column headers still rendered (unchanged light style).
Portfolio column headers removed — each row carries its own inline labels.

---

## What Was NOT Changed

- All data shown (Trust score, REC, daily change, P&L, holdings, etc.)
- Recommendation engine and scoring logic
- Watchlist rows (`CompactWatchRow`) — still light theme
- Smart Picks, Strategy, Home tabs — unchanged
- Filter pills, search bar, header, navigation
- Expanded panel data (verdict, lots, earnings, FX rate, action buttons)
