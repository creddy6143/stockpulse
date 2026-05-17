"""All AI API calls — Groq (primary) → Gemini (fallback) → Anthropic (last resort)."""
import os
import json
from .prompts import SYSTEM_PROMPT, STRATEGY_SYSTEM_PROMPT

_groq_client = None
_anthropic_client = None


# Fallback verdicts for manually-blocked stocks only.
# These fire only when ALL three AI providers (Groq + Gemini + Anthropic) fail.
# For manually-blocked stocks the exit message is always the same regardless of
# market conditions, so a static fallback is acceptable.
# All other stocks use _default_verdict() — no stale hardcoded text.
_BLOCKED_VERDICTS = {
    "TNXP": {
        "verdict": "Auto-disqualified: 8 reverse splits. This stock has a history of destroying value through dilution. Exit any position immediately.",
        "recommendation": "strong_sell", "confidence_pct": 95,
        "stop_loss_explanation": "Exit immediately — do not hold.",
        "time_horizon": "short (days)",
        "key_risk": "Continued dilution and reverse splits.",
    },
    "XGN": {
        "verdict": "Auto-disqualified: board resigned before earnings. This is one of the strongest warning signs that exist. Exit any position at the earliest opportunity.",
        "recommendation": "strong_sell", "confidence_pct": 92,
        "stop_loss_explanation": "Exit at market open. Do not wait.",
        "time_horizon": "short (days)",
        "key_risk": "Insider knowledge of bad results is the most likely explanation for a board resignation.",
    },
    "NKLA": {
        "verdict": "Auto-disqualified: SEC fraud conviction, CEO and CFO resigned, Chapter 11 bankruptcy. No recovery path exists.",
        "recommendation": "strong_sell", "confidence_pct": 99,
        "stop_loss_explanation": "Exit immediately. This company is in bankruptcy.",
        "time_horizon": "short (days)",
        "key_risk": "Total loss of capital in bankruptcy proceedings.",
    },
}


# ── CLIENT HELPERS ────────────────────────────────────────────────────────────

def _get_groq():
    global _groq_client
    if _groq_client is None:
        key = os.getenv("GROQ_API_KEY", "")
        if key:
            try:
                from groq import Groq
                _groq_client = Groq(api_key=key)
            except ImportError:
                pass
    return _groq_client


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if key:
            try:
                import anthropic
                _anthropic_client = anthropic.Anthropic(api_key=key)
            except ImportError:
                pass
    return _anthropic_client


# ── PROVIDER CALL FUNCTIONS ───────────────────────────────────────────────────

def _call_groq(system_prompt: str, user_prompt: str, max_tokens: int = 500) -> str | None:
    client = _get_groq()
    if not client:
        return None
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return None


def _call_gemini(system_prompt: str, user_prompt: str, max_tokens: int = 500) -> str | None:
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        return None
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=max_tokens,
                temperature=0.3,
            ),
        )
        return response.text.strip()
    except Exception:
        return None


def _call_anthropic(system_prompt: str, user_prompt: str, max_tokens: int = 500) -> str | None:
    client = _get_anthropic()
    if not client:
        return None
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return msg.content[0].text.strip()
    except Exception:
        return None


def _call_ai(system_prompt: str, user_prompt: str, max_tokens: int = 500) -> str | None:
    """Try Groq → Gemini → Anthropic. Returns first successful response, or None."""
    text = _call_groq(system_prompt, user_prompt, max_tokens)
    if text:
        return text
    text = _call_gemini(system_prompt, user_prompt, max_tokens)
    if text:
        return text
    return _call_anthropic(system_prompt, user_prompt, max_tokens)


def _parse_json(text: str | None) -> dict | None:
    if not text:
        return None
    try:
        # Strip markdown code fences if present
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except (json.JSONDecodeError, IndexError):
        return None


# ── PUBLIC FUNCTIONS ──────────────────────────────────────────────────────────

def get_verdict(
    ticker: str,
    trust_score: int,
    patterns_detected: list,
    price_data: dict,
    fundamentals: dict,
) -> dict:
    """Returns AI verdict for a stock. Falls back to blocked-stock text or generic verdict if all AI providers fail."""
    clean = ticker.replace(".NS", "").replace(".BO", "").replace(".ST", "")

    # Build user prompt
    patterns_text = (
        ", ".join(p.get("name", p.get("pattern", "")) for p in patterns_detected)
        if patterns_detected
        else "None"
    )
    user_prompt = f"""Stock: {ticker}
Trust Score: {trust_score}/100
Patterns Detected: {patterns_text}
Current Price: {price_data.get('price', 'N/A')}
Change Today: {price_data.get('change_pct', 0):.1f}%
Revenue Growth: {(fundamentals.get('revenue_growth', 0) or 0) * 100:.0f}% YoY
GAAP Profitable: {fundamentals.get('gaap_profitable', False)}
Earnings Surprise: {fundamentals.get('earnings_surprise_pct', 0) or 0:.0f}%

Give a plain English verdict following the system rules."""

    text = _call_ai(SYSTEM_PROMPT, user_prompt, max_tokens=500)
    parsed = _parse_json(text)
    if parsed:
        return parsed

    # For manually-blocked stocks, the exit message is always valid regardless of
    # market conditions. For everything else, use the generic trust-score-based verdict.
    return _BLOCKED_VERDICTS.get(clean, _default_verdict(ticker, trust_score))


def generate_strategy_playbook(
    situation_type: str,
    ticker: str,
    stock_data: dict,
    market_data: dict,
) -> str:
    """Returns a plain English strategy playbook for a situation."""
    prompt = f"""Situation: {situation_type}
Stock: {ticker}
Trust Score: {stock_data.get('trust_score', 50)}/100
Current Price: {stock_data.get('price', 'N/A')}
Performance: {stock_data.get('change_pct', 0):.1f}% today
Market VIX: {market_data.get('vix', {}).get('price', 15)}

Write a 3-4 sentence plain English playbook for what this investor
should do RIGHT NOW. No jargon. Specific to their situation.
Include a specific stop loss or exit condition."""

    text = _call_ai(STRATEGY_SYSTEM_PROMPT, prompt, max_tokens=300)
    if text:
        return text
    return _default_playbook(situation_type, ticker, stock_data)


# ── FALLBACK FUNCTIONS ────────────────────────────────────────────────────────

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
        "crash_decision": (
            f"The fall in {ticker} may be market-driven rather than company-specific. "
            f"Check if the business fundamentals remain intact before deciding to hold or exit. "
            f"If the core business is still executing, hold with a stop loss 20% below current price."
        ),
        "exit_now": (
            f"{ticker} has been flagged for immediate exit. Historical data shows these warning signs "
            f"precede further declines in most cases. Exit at market open to protect remaining capital."
        ),
        "profit_decision": (
            f"{ticker} is showing strong gains. Consider taking partial profits — sell 30-40% to lock "
            f"in gains while keeping exposure to further upside. Move your stop loss up to protect gains."
        ),
        "default": (
            f"Review your position in {ticker} carefully. Set a clear stop loss and stick to it. "
            f"Do not let emotions drive your decision."
        ),
    }
    return defaults.get(situation_type, defaults["default"])
