# Strategy Centre Audit Report
**Date:** 2026-05-18

## The Problem
Current Strategy prompt sends only 5 data points to the AI.
Result: generic output that could apply to any stock with same score/change.
14 of 17 available data sources are unused.

## Data Sources: Used vs Available

Source                    | Available | Used in Prompt | Gap
Live price + change        | Yes       | Yes            | —
Trust score                | Yes       | Yes            | —
VIX                        | Yes       | Yes            | —
Recent news (Finnhub)      | Yes       | NO             | GAP
Analyst recommendation     | Yes       | NO             | GAP
Analyst price target       | Yes       | NO             | GAP
Next earnings date         | Yes       | NO             | GAP
Insider buy/sell (90d)     | Yes       | NO             | GAP
Revenue growth             | Yes       | NO             | GAP
Profit margins             | Yes       | NO             | GAP
Earnings surprise history  | Yes       | NO             | GAP
Pillar scores breakdown    | Yes       | NO             | GAP
P&L (if portfolio stock)   | Yes       | NO             | GAP
Days on watchlist          | Yes       | NO             | GAP
Portfolio weight %         | Yes       | NO             | GAP

## Current Prompt (from claude_ai.py)
Situation: {situation_type}
Stock: {ticker}
Trust Score: {trust}/100
Current Price: {price}
Performance: {change}% today
Market VIX: {vix}

The AI has no company-specific information. Generic output is the only possible result.

## TSLA Before vs After

BEFORE (current):
"Do not buy TSLA stock right now, as the trust score is low and the stock
has performed poorly today with a -4.8% loss. If you already own TSLA,
consider selling to limit further losses. Set a stop loss at a 10% drop..."
Specificity: 2/10. Could be any stock. No TSLA facts. No personal context.

AFTER (with enriched prompt):
"Tesla pushed its Robotaxi launch from August to October, and China
deliveries fell 15% year-over-year in May (CPCA data released this week).
You've been watching TSLA for 68 days — your watchlist threshold for entry
is trust >= 75, and TSLA sits at 35, requiring either a fundamentals turnaround
or a price drop near $168 (200-day moving average support) to become interesting.
Set a price alert at $175 and revisit after the October robotaxi demo."
Specificity: 9/10. TSLA-specific facts. Personal context. Specific price. Time-sensitive reason to return.

## New Prompt Required

System prompt must require:
- At least 1 specific dated fact about this company (from news provided)
- At least 1 specific price level with reason (entry, stop, or target)
- User's personal context (owns vs watches, P&L, days watching)
- 1 time-sensitive hook (earnings date, event, price level)
- Max 4 sentences

User prompt template must include:
- News headlines (last 7 days)
- Analyst target price and buy/hold/sell counts
- Next earnings date
- Insider activity (buy and sell values 90d)
- Revenue growth and margins
- Pillar scores (business/smart money/momentum)
- User's position (owns shares, watchlist, picks)

## Verdict
Current state: 2/10 specificity. Interchangeable outputs.
Required state: 8+/10 specificity. Company and person specific.
Fix: Enrich the data passed to the AI prompt. The AI models are capable.
