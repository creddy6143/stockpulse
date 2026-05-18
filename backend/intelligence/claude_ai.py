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
        "verdict": "Flagged: 8 reverse splits on record — a pattern historically associated with ongoing shareholder dilution. This is one of the risk signals our system tracks closely. Not financial advice — review your own situation carefully.",
        "recommendation": "strong_sell", "confidence_pct": 95,
        "stop_loss_explanation": "Historically, holders of stocks with this many reverse splits have seen continued value erosion. Consider what your personal exit criteria are.",
        "time_horizon": "short (days)",
        "key_risk": "Repeated reverse splits have historically diluted existing shareholders significantly each time.",
    },
    "XGN": {
        "verdict": "Flagged: entire board resigned within 30 days of an earnings report — historically one of the strongest negative signals in corporate governance. This pattern warrants careful review of your position.",
        "recommendation": "strong_sell", "confidence_pct": 92,
        "stop_loss_explanation": "Board resignations before earnings have historically preceded significant negative results. Review your position with your own risk tolerance in mind.",
        "time_horizon": "short (days)",
        "key_risk": "Unexpected board resignations before earnings have historically signalled serious undisclosed problems.",
    },
    "NKLA": {
        "verdict": "Flagged: SEC fraud conviction, executive departures, and Chapter 11 bankruptcy filing — all three of the most serious corporate distress signals simultaneously. This is for informational purposes only.",
        "recommendation": "strong_sell", "confidence_pct": 99,
        "stop_loss_explanation": "In Chapter 11 bankruptcy, equity holders are typically last in the recovery priority queue. Review your situation with that in mind.",
        "time_horizon": "short (days)",
        "key_risk": "In bankruptcy proceedings, equity typically has little or no recovery value once creditors are paid.",
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

    # Cache non-blocked AI verdicts for 1 hour so /api/picks doesn't re-call AI on every load
    _verdict_cache_key = f"verdict:{ticker}"
    _cached = cache_get(_verdict_cache_key, TTL_STRATEGY)
    if _cached and clean not in _BLOCKED_VERDICTS:
        return _cached

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
        if clean not in _BLOCKED_VERDICTS:
            cache_set(_verdict_cache_key, parsed)
        return parsed

    # For manually-blocked stocks: show today's price move as context alongside the signal.
    blocked = _BLOCKED_VERDICTS.get(clean)
    if blocked:
        change_pct = float(price_data.get("change_pct", 0) or 0)
        if change_pct >= 5:
            # Big up day — note the move but keep signal-based framing
            result = dict(blocked)
            result["verdict"] = (
                f"Up {change_pct:.0f}% today — a short-term catalyst is driving this move. "
                f"{blocked['verdict']}"
            )
            result["stop_loss_explanation"] = (
                f"Price is elevated {change_pct:+.0f}% today. "
                f"The underlying risk signals have not changed — weigh this carefully against your own situation."
            )
            return result
        elif change_pct <= -5:
            result = dict(blocked)
            result["verdict"] = (
                f"Down {abs(change_pct):.0f}% today. "
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
            "verdict": "Multiple risk signals detected — the data does not support a bullish case at this score. Review the fundamentals carefully before making any decision.",
            "recommendation": "sell",
            "confidence_pct": 60,
            "stop_loss_explanation": "Historically, stocks at this score level that fall a further 10% have rarely recovered quickly. Consider what your personal risk threshold is.",
            "time_horizon": "short (days)",
            "key_risk": "Fundamental deterioration across multiple metrics.",
        }
    return {
        "verdict": "Quality signals are mixed — the data suggests monitoring rather than adding. Watch next earnings for clearer direction.",
        "recommendation": "hold",
        "confidence_pct": 55,
        "stop_loss_explanation": "A 20% decline from current price would represent a significant move against this position — consider at what point you'd want to reassess.",
        "time_horizon": "medium (weeks)",
        "key_risk": "A market-wide correction could affect this stock regardless of its own fundamentals.",
    }


def _default_playbook(situation_type: str, ticker: str, stock_data: dict) -> str:
    defaults = {
        "crash_decision": (
            f"The fall in {ticker} may be market-driven rather than company-specific. "
            f"Checking whether the business fundamentals remain intact is worth doing before making any decision. "
            f"If the core business is still executing well, many investors in this situation set a personal review level around 20% below current price."
        ),
        "exit_now": (
            f"{ticker} has multiple serious risk signals flagged. Historically, these warning signs have preceded further declines in similar situations. "
            f"This is for informational purposes — review your own position and risk tolerance carefully."
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
