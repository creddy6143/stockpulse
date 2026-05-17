# Watchlist Signal Audit Report
**Date:** 2026-05-18

## What "Upside 35/48/72/47" Actually Is

ANSWER: These are TRUST SCORES, not upside percentages.

In CompactWatchRow (App.jsx line 1177-1179):
  Column 3 shows: s.trust (the trust score 0-100)
                  s.potential (always "—", hardcoded in mapWatchlistItem)
  Column header says: "Upside"

The user sees trust score 35 under a column labeled "Upside" and reads it as "35% upside."
This is a critical mislabeling.

## Watchlist Fields — What's Real vs Hardcoded

mapWatchlistItem() returns:
  entry: "—"       <- hardcoded — never calculated
  potential: "—"   <- hardcoded — never calculated
  signal: from API <- real ("Still watching" / "Entry zone now" / "Not yet")
  trust: from API  <- real trust score

## Signal Logic (from tracker.py _build_watchlist_item)

trust >= 75 AND not disqualified -> "Ready" -> "Entry zone now"
trust < 40 OR disqualified       -> "Avoid" -> "Not yet"
everything else (40-74)          -> "Watching" -> "Still watching"

TSLA  (trust 35) -> Avoid -> "Not yet" (score < 40)
AMZN  (trust 48) -> Watching -> "Still watching"
AMD   (trust 72) -> Watching -> "Still watching" (3 pts below Ready)
RKLB  (trust 47) -> Watching -> "Still watching"

Logic is score-only. No price comparison. No RSI. No MA. No pullback detection.

## Cross-Reference

Stock | Our Signal    | Our Score | Analyst Consensus | Real Upside (est)
TSLA  | Not yet (35)  | 35        | Mixed             | Analyst target ~$310 vs price ~$215 = +44%
AMZN  | Watching (48) | 48        | Strong Buy        | Analyst target ~$265 vs price ~$185 = +43%
AMD   | Watching (72) | 72        | Buy               | Analyst target ~$165 vs price ~$100 = +65%
RKLB  | Watching (47) | 47        | Buy               | Analyst target ~$30 vs price ~$20 = +50%

The "Upside 72" for AMD the user sees is the trust score.
AMD's REAL analyst upside is approximately +65%.
These are completely different concepts being conflated.

## What Needs to Be Built

1. Real upside = (analyst_target_price - current_price) / current_price * 100
   Source: Finnhub price_target() endpoint — already called in get_analyst_data()
   Already fetched, just not passed through to frontend.

2. Entry zone = range where the stock becomes a buy
   Proposed: (52W low * 1.15) to (current price * 0.98)
   Or: MA50 to MA50 * 1.05 (within 5% of 50-day average)

3. Ready/Watching trigger should be price-sensitive:
   Ready = trust >= 75 AND price within entry zone
   Watching = trust >= 60 OR approaching entry zone
   Avoid = trust < 40 OR disqualified

## Verdict

Issue                     | Status
"Upside" numbers 35/48/72 | BROKEN — trust scores shown in wrong column
Entry zone "—"            | MISSING — never calculated
"Still watching" signal   | OVERSIMPLIFIED — no price awareness
Analyst data feeding score | CORRECT — Finnhub data used in trust calc
Ready/Avoid thresholds    | CORRECT logic, MISSING price component
