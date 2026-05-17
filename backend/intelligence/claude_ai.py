"""All AI API calls — Groq (primary) → Gemini (fallback) → Anthropic (last resort)."""
import os
import json
from .prompts import SYSTEM_PROMPT, STRATEGY_SYSTEM_PROMPT, build_strategy_user_prompt
from data.cache import cache_get, cache_set, TTL_STRATEGY

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

    # For manually-blocked stocks: return the base verdict but if there's a
    # significant price move today, surface it as the EXIT WINDOW (not a reason to hold).
    blocked = _BLOCKED_VERDICTS.get(clean)
    if blocked:
        change_pct = float(price_data.get("change_pct", 0) or 0)
        if change_pct >= 5:
            # Big up day — use it as context: exit at a better price
            result = dict(blocked)
            result["verdict"] = (
                f"Up {change_pct:.0f}% today — this pop is your exit window. "
                f"{blocked['verdict']}"
            )
            result["stop_loss_explanation"] = (
                f"Exit now while price is elevated {change_pct:+.0f}%. "
                f"Do not wait for it to reverse — the underlying problems have not changed."
            )
            return result
        elif change_pct <= -5:
            # Big down day — reinforce urgency
            result = dict(blocked)
            result["verdict"] = (
                f"Down {abs(change_pct):.0f}% today — confirms the exit signal. "
                f"{blocked['verdict']}"
            )
            return result
        return blocked

    return _default_verdict(ticker, trust_score)


def generate_strategy_playbook(
    situation_type: str,
    ticker: str,
    stock_data: dict,
    market_data: dict,
    fundamentals: dict = None,
    analyst: dict = None,
    insider: dict = None,
    news: list = None,
    user_context: str = "",
) -> str:
    """Returns a specific, personalized plain English strategy playbook.

    Enriched with all available data: news, analyst targets, insider activity,
    earnings dates, fundamentals. Cached per-stock for 2 hours to prevent
    repeated AI calls on refresh.
    """
    cache_key = f"strategy_playbook:{ticker}:{situation_type}"
    cached = cache_get(cache_key, TTL_STRATEGY)
    if cached:
        return cached

    f = fundamentals or {}
    a = analyst or {}
    ins = insider or {}
    vix_data = market_data.get("vix", {})
    vix = vix_data.get("price", 15) if isinstance(vix_data, dict) else 15
    market_status = market_data.get("status", {}).get("label", "Market Calm")

    trust = stock_data.get("trust_score", 50)
    grade = stock_data.get("grade", "Moderate")

    prompt = build_strategy_user_prompt(
        situation_type=situation_type,
        ticker=ticker,
        name=stock_data.get("name", ticker),
        user_context=user_context or _build_user_context(situation_type, stock_data),
        price=stock_data.get("current_price") or stock_data.get("price", 0),
        change_pct=stock_data.get("change_pct", 0),
        trust=trust,
        grade=grade,
        business=stock_data.get("business_score", 0),
        smart=stock_data.get("smart_money_score", 0),
        momentum=stock_data.get("momentum_score", 0),
        revenue_growth=f.get("revenue_growth", 0) or 0,
        profit_margin=f.get("profit_margins", 0) or 0,
        earnings_surprise=f.get("earnings_surprise_pct"),
        analyst_target=a.get("target_price"),
        analyst_buy=a.get("buy_count", 0),
        analyst_hold=a.get("hold_count", 0),
        analyst_sell=a.get("sell_count", 0),
        insider_buy_value=ins.get("insider_buy_value", 0),
        insider_sell_value=ins.get("insider_sell_value", 0),
        ceo_buying=ins.get("ceo_buying", False),
        next_earnings=f.get("next_earnings_date"),
        news_headlines=[n.get("headline", "") for n in (news or [])[:3]],
        vix=vix,
        market_status=market_status,
        is_speculative=stock_data.get("is_speculative", False),
    )

    text = _call_ai(STRATEGY_SYSTEM_PROMPT, prompt, max_tokens=350)
    result = text if text else _default_playbook(situation_type, ticker, stock_data)

    cache_set(cache_key, result)
    return result


def _build_user_context(situation_type: str, stock_data: dict) -> str:
    """Build a plain English user context string from stock data."""
    ticker = stock_data.get("ticker", "")
    pnl_pct = stock_data.get("pnl_pct")
    pnl_sek = stock_data.get("pnl_sek")
    shares = stock_data.get("shares")
    buy_price = stock_data.get("buy_price")
    trust = stock_data.get("trust_score", 50)

    if shares and buy_price:
        # Portfolio stock — user owns it
        pnl_str = ""
        if pnl_pct is not None:
            pnl_str = f", currently {pnl_pct:+.1f}% P&L"
            if pnl_sek is not None:
                pnl_str += f" ({pnl_sek:+,.0f} SEK)"
        return (
            f"You own {shares} shares of {ticker} bought at ${buy_price:.2f}{pnl_str}. "
            f"Trust score is {trust}/100."
        )
    else:
        # Watchlist — user is watching
        return (
            f"You are watching {ticker} on your watchlist (not yet owned). "
            f"Trust score {trust}/100 — threshold for entry is ≥75."
        )


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
