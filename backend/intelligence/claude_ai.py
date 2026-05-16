"""All Claude API calls."""
import os
import json
import anthropic
from .prompts import SYSTEM_PROMPT, STRATEGY_SYSTEM_PROMPT

_client = None

DEMO_VERDICTS = {
    "TNXP": {"verdict": "8 reverse splits. Auto-disqualified. Exit on any pre-market pop this morning.", "recommendation": "strong_sell", "confidence_pct": 95, "stop_loss_explanation": "Exit immediately — do not hold through earnings today.", "time_horizon": "short (days)", "key_risk": "Further dilution from the authorized 9th reverse split."},
    "XGN":  {"verdict": "Board resigned 18 days before earnings — a severe warning sign. Pre-market pop is your exit window. Exit at open.", "recommendation": "strong_sell", "confidence_pct": 92, "stop_loss_explanation": "Exit at market open. Do not wait for results.", "time_horizon": "short (days)", "key_risk": "91% of stocks with board resignations before earnings declined further within 30 days."},
    "GRRR": {"verdict": "AI contracts executing but macro conditions dragged the price down, not the business. Hold through June 17 earnings — that is when the thesis gets confirmed or denied.", "recommendation": "hold", "confidence_pct": 65, "stop_loss_explanation": "Exit if it falls below $8.50 from current levels.", "time_horizon": "medium (weeks)", "key_risk": "June 17 earnings miss on contract pipeline commentary."},
    "INSM": {"verdict": "Biotech with significant Phase 3 pipeline. Small 10-share position means low stress. Watch BofA Healthcare Conference May 12 for a narrative catalyst.", "recommendation": "hold", "confidence_pct": 58, "stop_loss_explanation": "Exit if it falls 25% from your entry of $115.", "time_horizon": "medium (weeks)", "key_risk": "Phase 3 trial data miss — binary event risk."},
    "NVDA": {"verdict": "AI supercycle is real and accelerating. Revenue up 122% year over year. Hold with a trailing stop — but note you now hold 31% of your portfolio in one stock.", "recommendation": "hold", "confidence_pct": 85, "stop_loss_explanation": "Sell if it falls 20% from its recent peak. Also consider trimming to reduce concentration.", "time_horizon": "long (months)", "key_risk": "Concentration risk — one bad earnings report moves your entire portfolio."},
    "AXON": {"verdict": "All three quality signals aligned. CEO bought $1.2M of his own stock in the open market — the strongest insider signal. Entry zone $285-310 is active now.", "recommendation": "strong_buy", "confidence_pct": 87, "stop_loss_explanation": "Exit if it falls below $260 from entry.", "time_horizon": "long (months)", "key_risk": "Government contract budget cuts in a tough fiscal year."},
    "PLTR": {"verdict": "Government AI platform gaining traction fast. Commercial revenue up 55% year over year. Good entry below $25.", "recommendation": "buy", "confidence_pct": 76, "stop_loss_explanation": "Exit if it falls 20% from your entry price.", "time_horizon": "long (months)", "key_risk": "Valuation remains high — any revenue growth slowdown will hurt the price."},
    "MSFT": {"verdict": "Azure cloud growth re-accelerating with AI. World-class business generating $68B in free cash annually. Hold with confidence.", "recommendation": "hold", "confidence_pct": 80, "stop_loss_explanation": "Exit if it falls 15% from current levels.", "time_horizon": "long (months)", "key_risk": "OpenAI partnership costs rising while Copilot monetisation remains early-stage."},
    "ASML": {"verdict": "Monopoly supplier of the machines needed to make every advanced chip. AI demand drives a long equipment order cycle. Hold for July 16 results.", "recommendation": "buy", "confidence_pct": 82, "stop_loss_explanation": "Exit if it falls 18% from current price.", "time_horizon": "long (months)", "key_risk": "China export restrictions tightening could cut order backlog."},
    "CVNA": {"verdict": "Turnaround confirmed and now GAAP profitable. Revenue growing 20% year over year. Monitor the 2026 debt maturity closely.", "recommendation": "hold", "confidence_pct": 62, "stop_loss_explanation": "Exit if it falls below $150 as debt concerns would resurface.", "time_horizon": "long (months)", "key_risk": "2026 debt maturity wall — refinancing in a high-rate environment."},
    "RELIANCE": {"verdict": "India's largest company with Jio and Retail both growing. Large overseas investors buying for 3 consecutive days — a clear vote of confidence.", "recommendation": "buy", "confidence_pct": 74, "stop_loss_explanation": "Exit if it falls below ₹2,550.", "time_horizon": "long (months)", "key_risk": "Regulatory changes in Indian telecom or retail markets."},
    "HDFCBANK": {"verdict": "India's most trusted private bank. Both domestic and overseas institutions accumulating. Long-term compounder at fair value.", "recommendation": "buy", "confidence_pct": 70, "stop_loss_explanation": "Exit if it falls below ₹1,450.", "time_horizon": "long (months)", "key_risk": "Indian credit cycle turning — rising bad loans could pressure margins."},
}


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if api_key:
            _client = anthropic.Anthropic(api_key=api_key)
    return _client


def get_verdict(ticker: str, trust_score: int, patterns_detected: list,
                price_data: dict, fundamentals: dict) -> dict:
    """Returns Claude AI verdict for a stock. Falls back to demo data if API unavailable."""
    clean = ticker.replace(".NS", "").replace(".BO", "")
    client = _get_client()

    if not client:
        return DEMO_VERDICTS.get(clean, _default_verdict(ticker, trust_score))

    try:
        patterns_text = ", ".join(p.get("name", p.get("pattern", "")) for p in patterns_detected) if patterns_detected else "None"
        user_prompt = f"""Stock: {ticker}
Trust Score: {trust_score}/100
Patterns Detected: {patterns_text}
Current Price: {price_data.get('price', 'N/A')}
Change Today: {price_data.get('change_pct', 0):.1f}%
Revenue Growth: {(fundamentals.get('revenue_growth', 0) or 0) * 100:.0f}% YoY
GAAP Profitable: {fundamentals.get('gaap_profitable', False)}
Earnings Surprise: {fundamentals.get('earnings_surprise_pct', 0) or 0:.0f}%

Give a plain English verdict following the system rules."""

        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = msg.content[0].text.strip()
        # Extract JSON from response (handle markdown code blocks)
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except json.JSONDecodeError:
        return DEMO_VERDICTS.get(clean, _default_verdict(ticker, trust_score))
    except Exception:
        return DEMO_VERDICTS.get(clean, _default_verdict(ticker, trust_score))


def generate_strategy_playbook(situation_type: str, ticker: str,
                                stock_data: dict, market_data: dict) -> str:
    """Returns a plain English strategy playbook for a situation."""
    client = _get_client()
    if not client:
        return _default_playbook(situation_type, ticker, stock_data)

    try:
        prompt = f"""Situation: {situation_type}
Stock: {ticker}
Trust Score: {stock_data.get('trust_score', 50)}/100
Current Price: {stock_data.get('price', 'N/A')}
Performance: {stock_data.get('change_pct', 0):.1f}% today
Market VIX: {market_data.get('vix', {}).get('price', 15)}

Write a 3-4 sentence plain English playbook for what this investor
should do RIGHT NOW. No jargon. Specific to their situation.
Include a specific stop loss or exit condition."""

        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=STRATEGY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception:
        return _default_playbook(situation_type, ticker, stock_data)


def _default_verdict(ticker: str, trust_score: int) -> dict:
    if trust_score < 40:
        return {
            "verdict": "Trust score too low for a bullish thesis. Review fundamentals before acting.",
            "recommendation": "sell",
            "confidence_pct": 60,
            "stop_loss_explanation": "Exit if it falls 10% further from current price.",
            "time_horizon": "short (days)",
            "key_risk": "Fundamental deterioration.",
        }
    return {
        "verdict": "Quality metrics suggest a hold. Monitor next earnings for confirmation.",
        "recommendation": "hold",
        "confidence_pct": 55,
        "stop_loss_explanation": "Exit if it falls 20% from current price.",
        "time_horizon": "medium (weeks)",
        "key_risk": "Market-wide correction could pressure this stock regardless of fundamentals.",
    }


def _default_playbook(situation_type: str, ticker: str, stock_data: dict) -> str:
    defaults = {
        "crash_decision": f"The fall in {ticker} may be market-driven rather than company-specific. Check if the business fundamentals remain intact before deciding to hold or exit. If the core business is still executing, hold with a stop loss 20% below current price.",
        "exit_now": f"{ticker} has been flagged for immediate exit. Historical data shows these warning signs precede further declines in most cases. Exit at market open to protect remaining capital.",
        "profit_decision": f"{ticker} is showing strong gains. Consider taking partial profits — sell 30-40% to lock in gains while keeping exposure to further upside. Move your stop loss up to protect gains.",
        "default": f"Review your position in {ticker} carefully. Set a clear stop loss and stick to it. Do not let emotions drive your decision.",
    }
    return defaults.get(situation_type, defaults["default"])
