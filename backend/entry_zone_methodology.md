# Entry Zone Methodology

## What is an entry zone?

An entry zone is the price band where multiple technical support and
fundamental value signals converge — the range where a stock becomes a
high-probability buy on a pullback.

It is NOT a 52-week range. It is NOT a static target. It is a narrow
(≤12% of current price) band computed from live data every time the
watchlist loads.

---

## How the zone is computed

### Zone ceiling (zone_high)

The upper boundary of the entry zone — where you start buying on a
pullback. Uses the **highest** valid signal below current price:

| Signal | Source | Notes |
|--------|--------|-------|
| 50-day moving average | yfinance `fiftyDayAverage` | Near-term trend support |
| Fibonacci 38.2% retracement | 52W high − 0.382 × (52W high − 52W low) | Shallow pullback level |
| Fibonacci 50% retracement | 52W high − 0.50 × (52W high − 52W low) | Mid-range pullback |
| Lower analyst consensus | (mean + low) / 2 × 0.97 | 25th-percentile approximation |

### Zone floor (zone_low)

The lower boundary — deeper support where you'd add on a further drop.
Uses the **highest** valid signal strictly below the zone ceiling:

| Signal | Source | Notes |
|--------|--------|-------|
| 200-day moving average | yfinance `twoHundredDayAverage` | Institutional long-term benchmark |
| Fibonacci 61.8% retracement | 52W high − 0.618 × (52W high − 52W low) | Golden-ratio deep support |
| Fibonacci 50% retracement | 52W high − 0.50 × (52W high − 52W low) | Mid-range (if not used as ceiling) |
| Lowest analyst target | Finnhub `targetLow` | Most conservative estimate |

---

## Constraints

1. **Max width: 12% of current price**
   A zone wider than 12% is useless — it tells the user nothing specific.
   If the natural signals produce a wider zone, the algorithm narrows to
   the MA50/MA200 pair. If they too are more than 12% apart, the zone is
   reported as "No clear zone — wait for setup."

2. **Both boundaries must be ≤ current price**
   Entry zones are below the current price — they're where you buy on a
   dip, not at a new high.

3. **Minimum data requirement**
   At least the MA50 or MA200 must be available. Without any technical
   level, no zone is reported.

4. **Fibonacci uses 52-week range**
   Fibonacci retracements are computed from the full 52-week range as a
   proxy for the last meaningful cycle. This is a simplification — a
   proper Fibonacci would use the most recent meaningful swing, but the
   52W range is always available from yfinance without additional calls.

---

## Status labels

The zone status is computed fresh on every page load:

| Status | Condition | Label |
|--------|-----------|-------|
| `in_zone` | current_price ≤ zone_high AND ≥ zone_low | ✓ In entry zone now |
| `near_zone` | price ≤ zone_high × 1.03 (within 3% above ceiling) | Near zone — X% to enter |
| `above_zone` | price > zone_high × 1.03 | Above zone — wait for X% pullback to $Y |
| `below_zone` | price < zone_low | Below zone — X% below entry, reassess thesis |
| `no_zone` | insufficient data or signals diverge | No clear entry zone — wait for setup |

---

## Watchlist group logic

| Group | Condition |
|-------|-----------|
| **Ready** | `zone_status == "in_zone"` AND trust_score ≥ 60 AND not auto-disqualified |
| **Avoid** | `auto_disqualified` OR `trust_score < 30` |
| **Watching** | Everything else (above zone, near zone, no zone, in-zone but low trust) |

The key change from the previous implementation: "Ready" now means the
stock is **actually in its entry zone right now**, not just that the
trust score is ≥ 75.

---

## Example: STX at $879.80

```
MA50  = $845   → zone ceiling
MA200 = $810   → zone floor
Width = $35    → 3.97% of $879.80 ✓ (< 12% constraint)

Zone: $810–$845
Status: above_zone (price $879.80 > $845)
Label: "Above zone — wait for 4.0% pullback to $845"
```

---

## Example: Stock in zone (e.g. price = $820)

```
MA50  = $845  → zone ceiling
MA200 = $810  → zone floor
Zone: $810–$845

Price $820 is between $810 and $845 → in_zone
Label: "✓ In entry zone now"
Group: Ready (if trust ≥ 60)
```

---

## What if the zone shows "No clear zone"?

This happens when:
- MA50 and MA200 are more than 12% apart (market in wide transition)
- Only one boundary signal is available and fallback fails
- Price is above the 52-week high (stock at all-time high)
- Data unavailable (yfinance rate-limited, exchange not covered)

In all these cases, the display shows:
`"No clear entry zone — wait for setup"`

This is honest. A fabricated zone is worse than no zone.

---

## Data sources

| Field | Fetcher function | Source |
|-------|-----------------|--------|
| `ma_200d` | `get_fundamentals()` | yfinance `twoHundredDayAverage` |
| `ma_50d` | `get_fundamentals()` | yfinance `fiftyDayAverage` |
| `w52_high` | `get_fundamentals()` | yfinance `fiftyTwoWeekHigh` |
| `w52_low` | `get_fundamentals()` | yfinance `fiftyTwoWeekLow` |
| `target_low` | `get_analyst_data()` | Finnhub `targetLow` |
| `target_high` | `get_analyst_data()` | Finnhub `targetHigh` |
| `target_price` (mean) | `get_analyst_data()` | Finnhub `targetMean` |

All data is fetched with a 15-minute cache (configurable via `TTL_FUNDAMENTALS`
and `TTL_ANALYST` in `data/cache.py`). The zone is therefore updated at
least every 15 minutes on an active session.
