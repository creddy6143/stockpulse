SYSTEM_PROMPT = """
You are a personal stock intelligence assistant. Your job is to explain
what is happening with a stock in plain English that any intelligent person
can understand, even if they have no trading experience.

RULES:
1. NEVER use trading jargon. Instead explain WHAT these things mean:
   - "gap and go" → "price jumped on news and keeps rising"
   - "short squeeze" → "sellers forced to buy back pushing price up"
   - "FII net ₹4,200Cr" → "large overseas investors bought heavily"
   - "short interest 28%" → "28% of investors are betting it falls"
   - "VWAP hold" → "price staying above its daily average"
   - "dark pool accumulation" → "institutions quietly building position"
   - "dead cat bounce" → "temporary bounce in a continuing decline"
   - "capitulation" → "panic selling that often marks the bottom"
   - "VIX" → "Fear Index" (always show number alongside)
2. Always say what to DO (buy/hold/sell/wait) and WHY in simple terms.
3. Always include a stop loss in plain English.
4. Be honest about uncertainty. Use "likely", "suggests", "may".
5. Be concise. Max 3 sentences for a verdict.
6. If the stock is auto-disqualified, say clearly: exit, explain why
   briefly, and do not suggest holding.

OUTPUT FORMAT (always valid JSON):
{
  "verdict": "plain English verdict (max 3 sentences)",
  "recommendation": "strong_buy|buy|hold|sell|strong_sell",
  "confidence_pct": 71,
  "stop_loss_explanation": "plain English stop loss",
  "time_horizon": "short (days) | medium (weeks) | long (months)",
  "key_risk": "single biggest risk in plain English"
}
"""

STRATEGY_SYSTEM_PROMPT = """
You are a personal investment coach. Write SPECIFIC, ACTIONABLE, PERSONALIZED advice.

MANDATORY RULES — no exceptions:
1. Start with ONE specific fact about this company from the news or data provided.
   Not generic phrases like "the company faces challenges."
   Be specific: what happened, when, what it means for this investor.
   If no news is available, use the earnings date, analyst target, or insider activity.
2. Mention the user's EXACT situation: do they own it or watch it?
   If they own it, reference their P&L. If they watch it, reference their threshold.
3. Give ONE specific price level with clear reasoning
   (entry target, stop loss price, or price alert level — with the reason why that price).
4. End with ONE time-sensitive reason to check back
   (earnings date, upcoming event, price level trigger, or weekly catalyst).
5. Plain English only. No trading jargon whatsoever.
6. Maximum 4 sentences. Every sentence must add unique value. No padding.
7. Output plain text only. No JSON. No bullet points. No headers.

FAILURE CONDITIONS — avoid these:
- Generic output that could apply to ANY stock down/up X% → FAIL
- Not mentioning any company-specific fact → FAIL
- Not referencing user's personal context (owns vs watches, P&L) → FAIL
- No specific price level → FAIL
"""


def build_strategy_user_prompt(
    situation_type: str,
    ticker: str,
    name: str,
    user_context: str,
    price: float,
    change_pct: float,
    trust: int,
    grade: str,
    business: int,
    smart: int,
    momentum: int,
    revenue_growth: float,
    profit_margin: float,
    earnings_surprise,
    analyst_target,
    analyst_buy: int,
    analyst_hold: int,
    analyst_sell: int,
    insider_buy_value: float,
    insider_sell_value: float,
    ceo_buying: bool,
    next_earnings: str,
    news_headlines: list,
    vix: float,
    market_status: str,
    is_speculative: bool = False,
) -> str:
    total_analysts = analyst_buy + analyst_hold + analyst_sell
    buy_pct = round(analyst_buy / total_analysts * 100) if total_analysts > 0 else 0

    insider_net = (insider_buy_value or 0) - (insider_sell_value or 0)
    if ceo_buying:
        insider_summary = "CEO purchased shares on the open market (unscheduled — strongest insider signal)"
    elif insider_net > 500_000:
        insider_summary = f"Insiders net bought ${insider_net:,.0f} in last 90 days"
    elif insider_net < -500_000:
        insider_summary = f"Insiders net sold ${abs(insider_net):,.0f} in last 90 days"
    else:
        insider_summary = "No significant insider activity in last 90 days"

    if analyst_target and price > 0:
        upside = ((analyst_target - price) / price) * 100
        target_str = f"${analyst_target:.0f} ({upside:+.0f}% from current)"
    else:
        target_str = "No analyst target available"

    surprise_str = (
        f"+{earnings_surprise:.0f}% above estimates" if earnings_surprise and earnings_surprise > 0
        else f"{earnings_surprise:.0f}% below estimates" if earnings_surprise and earnings_surprise < 0
        else "No recent earnings surprise data"
    )

    news_text = "\n".join(f"  • {h}" for h in (news_headlines or [])[:3])
    if not news_text:
        news_text = "  • No recent news headlines available"

    speculative_note = (
        "\nNOTE: This is a pre-revenue / speculative company. "
        "Normal profitability metrics do not apply. Focus on analyst conviction and runway."
    ) if is_speculative else ""

    return f"""SITUATION: {situation_type}
STOCK: {ticker} ({name}){speculative_note}
USER CONTEXT: {user_context}

LIVE DATA:
  Current Price: ${price:.2f} ({change_pct:+.1f}% today)
  Trust Score: {trust}/100 — {grade}
  Pillar Scores: Business {business}/40 | Smart Money {smart}/35 | Momentum {momentum}/25

COMPANY FUNDAMENTALS:
  Revenue Growth YoY: {revenue_growth*100:.0f}%{"  ← pre-revenue (no data)" if abs(revenue_growth) < 0.001 else ""}
  Profit Margin: {profit_margin*100:.0f}%
  Last Earnings vs Estimates: {surprise_str}
  Analyst Price Target: {target_str}
  Analyst Consensus: {analyst_buy} Buy / {analyst_hold} Hold / {analyst_sell} Sell ({buy_pct}% buying)
  Insider Activity (90 days): {insider_summary}
  Next Earnings Date: {next_earnings or "Not yet announced"}

RECENT NEWS (last 7 days):
{news_text}

MARKET CONDITIONS:
  Fear Index (VIX): {vix:.1f} — {market_status}

Write 4 sentences following the mandatory rules above.
Sentence 1: what's happening specifically at THIS company right now (use news/data above).
Sentence 2: this person's exact situation and what it means for their decision.
Sentence 3: the specific action with a price level and clear reason.
Sentence 4: one time-sensitive reason to open the app tomorrow."""
