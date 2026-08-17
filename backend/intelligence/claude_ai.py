"""All AI API calls — Groq (primary) → Gemini (fallback) → Anthropic (last resort).

Every AI-generated text passes through verify_ai_text before being returned
or cached. This ensures AI output is specific to the stock and not generic
boilerplate — part of the Real Money Test verification layer.
"""
import os
import json
import re
from datetime import datetime
from .prompts import SYSTEM_PROMPT, STRATEGY_SYSTEM_PROMPT, build_strategy_user_prompt
from .verification import verify_ai_text
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

# Groq slot. Tried in order — the free tier meters tokens PER MODEL (200k/day),
# so a second model is a second daily budget, not just a second opinion.
#
# Both are reasoning models, and reasoning tokens are drawn from the same budget
# as the answer. Left unmanaged they spend the whole cap thinking and return
# empty content, which is why each carries an explicit effort setting:
#   gpt-oss-120b  reasoning goes to a separate `reasoning` field; "low" effort
#                 costs ~144 completion tokens per verdict (vs ~207 default).
#   qwen3.6-27b   writes <think> INTO content unless effort is "none"; with
#                 "none" it returns clean JSON in ~287 tokens. It only accepts
#                 "none" or "default" — "low" is a 400. Left at default it needs
#                 3000+ tokens and still truncates on the fuller prompts.
_GROQ_MODELS = (
    ("qwen/qwen3.6-27b",    {"reasoning_effort": "none"}),   # primary
    ("openai/gpt-oss-120b", {"reasoning_effort": "low"}),    # fallback
)

# Floor for the answer budget. A truncated response wastes every token it spent,
# and headroom costs nothing when unused — max_tokens is a ceiling, not a spend.
_GROQ_MIN_TOKENS = 1200


def _call_groq(system_prompt: str, user_prompt: str, max_tokens: int = 500) -> str | None:
    """Try each Groq model in turn. Returns the first non-empty response.

    Groq decommissioned llama-3.3-70b-versatile on 2026-08-16; see the
    migration note in CLAUDE.md.
    """
    client = _get_groq()
    if not client:
        return None
    for model, params in _GROQ_MODELS:
        try:
            kwargs = dict(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max(max_tokens, _GROQ_MIN_TOKENS),
                temperature=0.3,
                **params,
            )
            try:
                response = client.chat.completions.create(**kwargs)
            except TypeError:
                # SDK too old to know `reasoning_effort` (requirements pins
                # groq>=1.6.0, but a stale deploy image can lag). Retry without
                # it: qwen will spend tokens thinking and may return nothing,
                # which is still better than the whole Groq slot going dark.
                print(f"[ai] groq {model}: SDK rejected {list(params)} — retrying without", flush=True)
                for k in params:
                    kwargs.pop(k, None)
                response = client.chat.completions.create(**kwargs)
            text = (response.choices[0].message.content or "").strip()
            if text:
                return text
            # Empty content means the budget went entirely to reasoning — worth
            # seeing in the logs rather than silently falling through.
            print(f"[ai] groq {model}: empty content "
                  f"(finish={response.choices[0].finish_reason})", flush=True)
        except Exception as e:
            print(f"[ai] groq {model} failed: {type(e).__name__}: {str(e)[:120]}", flush=True)
    return None


# Gemini slot. gemini-2.0-flash was RETIRED and had been 404ing silently — the
# whole fallback was dead and nobody knew, because this function swallowed the
# error. Pinned current model first, then the rolling alias so a future
# retirement self-heals instead of going dark again.
_GEMINI_MODELS = ("gemini-3.7-flash", "gemini-flash-latest")


def _call_gemini(system_prompt: str, user_prompt: str, max_tokens: int = 500) -> str | None:
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        return None
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("[ai] gemini: google-genai not installed", flush=True)
        return None

    client = genai.Client(api_key=key)
    for model in _GEMINI_MODELS:
        try:
            response = client.models.generate_content(
                model=model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=max(max_tokens, _GROQ_MIN_TOKENS),
                    temperature=0.3,
                ),
            )
            text = (response.text or "").strip()
            if text:
                return text
            print(f"[ai] gemini {model}: empty response", flush=True)
        except Exception as e:
            print(f"[ai] gemini {model} failed: {type(e).__name__}: {str(e)[:120]}", flush=True)
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
    except Exception as e:
        # Silent failure here is how the whole chain went dark unnoticed.
        print(f"[ai] anthropic failed: {type(e).__name__}: {str(e)[:120]}", flush=True)
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


# Appended verbatim on a retry when the verdict came back with no figure in it.
_FIGURE_REMINDER = (
    "\n\nIMPORTANT: your previous verdict contained no figure and was rejected. "
    "Rewrite the verdict citing at least one specific number from the data above "
    "in digits — the price, a percentage, or the trust score. Words like "
    "'strong growth' are not a figure."
)


def _missing_figure(verdict: str) -> bool:
    """True when a verdict would fail verification rule T2 (no digit present).

    Mirrors T2 deliberately: this decides whether a retry is worth spending,
    and only the same condition is worth retrying for.
    """
    return bool(verdict) and len(verdict.strip()) >= 50 and not any(c.isdigit() for c in verdict)


def _strip_reasoning(text: str) -> str:
    """Remove <think> blocks a reasoning model may write into its content.

    Handles the unterminated case too: a model cut off mid-thought leaves an
    opening tag with no closing one, and everything after it is reasoning.
    """
    if "<think>" not in text:
        return text
    closed = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return closed.split("<think>")[0] if "<think>" in closed else closed


def _json_object_spans(text: str) -> list[str]:
    """Every top-level balanced {...} span, in the order they appear.

    Brace counting has to know about strings, or a brace inside a verdict ("use {
    carefully") ends the object early and the span is garbage. Escapes matter for
    the same reason: "\\" must not swallow the following quote.
    """
    spans: list[str] = []
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth:
                depth -= 1
                if depth == 0 and start != -1:
                    spans.append(text[start:i + 1])
                    start = -1
    return spans


def _parse_json(text: str | None) -> dict | None:
    """Extract the model's JSON answer.

    Reasoning models draft, revise, then commit — so when several JSON objects
    are present the LAST complete one is the conclusion. The previous version
    took the first fenced block, which on a truncated qwen response was a draft
    from inside its own reasoning: a plausible verdict the model never stood by.
    """
    if not text:
        return None

    text = _strip_reasoning(text).strip()

    # Prefer fenced blocks, last first — that is the model's final answer.
    candidates = []
    if "```" in text:
        for block in re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL):
            candidates.append(block)
        candidates.reverse()
    candidates.append(text)

    # Then every balanced {...} span, last first. Fences are not guaranteed: a model
    # that drafts and revises in PROSE emits two bare objects, and the outermost-span
    # fallback below cannot read either of them because the span runs from the first
    # "{" to the last "}" and swallows the text between. Measured 2026-08-17:
    # '{"verdict":"FIRST"} then {"verdict":"SECOND"}' parsed to None, discarding an
    # answer the model had committed to and sending the caller to the next provider.
    candidates.extend(reversed(_json_object_spans(text)))

    # Last resort: the outermost {...} span, for prose wrapped around a single object.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


# ── PUBLIC FUNCTIONS ──────────────────────────────────────────────────────────

def get_verdict(
    ticker: str,
    trust_score: int,
    patterns_detected: list,
    price_data: dict,
    fundamentals: dict,
    hist: dict = None,
    analyst_data: dict = None,
) -> dict:
    """Returns AI verdict for a stock. Falls back to blocked-stock text or generic verdict if all AI providers fail."""
    from data.markets import strip_suffix
    clean = strip_suffix(ticker)

    live_chg = float(price_data.get("change_pct") or 0)

    # Cache non-blocked AI verdicts for 2 hours so /api/picks doesn't re-call AI on every load.
    # Single-source-of-truth check: if the live change_pct has drifted more than 0.5 percentage
    # points from the value that was baked into the cached prose, the commentary will
    # contradict the header. Invalidate and regenerate with current data.
    _verdict_cache_key = f"verdict:{ticker}"
    _cached = cache_get(_verdict_cache_key, TTL_STRATEGY)
    if _cached and clean not in _BLOCKED_VERDICTS:
        # Also invalidate if cached verdict predates the full_analysis field
        if "full_analysis" not in _cached:
            pass  # fall through to regenerate with richer prompt
        else:
            cached_chg = _cached.get("_change_pct_at_generation")
            if cached_chg is None or abs(live_chg - float(cached_chg)) <= 0.5:
                return _cached
            # Drift > 0.5pp — fall through to regenerate with current data

    # ── Build price trend section ─────────────────────────────────────────────
    h = hist or {}
    h6m = float(h.get("6M") or 0)
    h1y = float(h.get("1Y") or 0)
    price_val = float(price_data.get("price") or 0)
    w52_high = float(fundamentals.get("w52_high") or 0)

    trend_lines = []
    if h6m != 0:
        trend_lines.append(f"  6M Return: {h6m:+.1f}%")
    if h1y != 0:
        trend_lines.append(f"  1Y Return: {h1y:+.1f}%")
    if w52_high > 0 and price_val > 0:
        pct_from_52wh = (price_val - w52_high) / w52_high * 100
        trend_lines.append(f"  From 52-week high: {pct_from_52wh:+.1f}%")
    trend_section = ("\nPrice Trend (12 months):\n" + "\n".join(trend_lines)) if trend_lines else ""

    # ── Build analyst section ─────────────────────────────────────────────────
    a = analyst_data or {}
    target = a.get("target_price")
    buys = int(a.get("buy_count") or 0)
    holds = int(a.get("hold_count") or 0)
    sells = int(a.get("sell_count") or 0)
    total_analysts = buys + holds + sells
    analyst_lines = []
    if target and price_val > 0:
        upside = (target - price_val) / price_val * 100
        analyst_lines.append(f"  Price Target: ${target:.0f} ({upside:+.0f}% from current)")
    if total_analysts > 0:
        analyst_lines.append(f"  Consensus: {buys} Buy / {holds} Hold / {sells} Sell")
    analyst_section = ("\nAnalyst Coverage:\n" + "\n".join(analyst_lines)) if analyst_lines else ""

    # ── Build user prompt ─────────────────────────────────────────────────────
    patterns_text = (
        ", ".join(p.get("name", p.get("pattern", "")) for p in patterns_detected)
        if patterns_detected
        else "None"
    )
    profit_margin = float(fundamentals.get("profit_margins") or 0)
    profit_str = f"{profit_margin * 100:.0f}%" if profit_margin else "N/A"

    # Absent data must never be rendered as a definite value. MEASURED 2026-08-17:
    # a missing `revenue_growth` printed as "0% YoY" and a missing `gaap_profitable`
    # as "False", and the model then argued bearishly FROM those defaults — "the 0%
    # revenue growth and lack of GAAP profitability" for NVDA, which is neither. It
    # passes verification because T2 only asks for a digit, so the fabrication reaches
    # the user wearing a cited figure.
    #
    # Fetch failures are the normal case here, not the exotic one: CLAUDE.md records
    # Finnhub and Yahoo rate-limiting, and every one of those fields comes from them.
    #
    # Note the rest of this prompt already got this right — the price-trend and
    # analyst sections are OMITTED when empty and profit margin says "N/A". These
    # three were the gap, not a different philosophy.
    #
    # ZERO IS A REAL MEASUREMENT. Only None/absent becomes "not reported", so a
    # company genuinely at 0% growth still reads as 0%.
    def _opt_pct(value, scale=1.0, suffix=""):
        if value is None:
            return "not reported"
        return f"{float(value) * scale:.0f}%{suffix}"

    gaap = fundamentals.get("gaap_profitable")
    gaap_str = "not reported" if gaap is None else str(bool(gaap))
    # `.get(k, 0)` returns None when the key EXISTS holding None, which then raised
    # TypeError on the format spec. Absent and null now behave the same.
    change_pct_val = price_data.get("change_pct")
    change_str = "not reported" if change_pct_val is None else f"{float(change_pct_val):+.1f}%"

    user_prompt = f"""Stock: {ticker}
Trust Score: {trust_score}/100
Patterns Detected: {patterns_text}
Current Price: {price_data.get('price', 'N/A')}
Change Today: {change_str}
Revenue Growth: {_opt_pct(fundamentals.get('revenue_growth'), 100, ' YoY')}
GAAP Profitable: {gaap_str}
Profit Margin: {profit_str}
Earnings Surprise: {_opt_pct(fundamentals.get('earnings_surprise_pct'))}{trend_section}{analyst_section}

Write the verdict and full_analysis following the system rules."""

    text = _call_ai(SYSTEM_PROMPT, user_prompt, max_tokens=750)
    parsed = _parse_json(text)

    # T2 asks the verdict to cite a figure; a model that forgets gets its whole
    # verdict replaced by "Insufficient specific data…", which reads to the user
    # like we have no data on the stock. One corrective retry recovers it —
    # cheaper than a suppressed verdict and far more honest than loosening the
    # gate. Only fires when the text is otherwise fine, so cost is near zero.
    if parsed and _missing_figure(parsed.get("verdict", "")):
        retry = _call_ai(SYSTEM_PROMPT, user_prompt + _FIGURE_REMINDER, max_tokens=750)
        reparsed = _parse_json(retry)
        if reparsed and not _missing_figure(reparsed.get("verdict", "")):
            print(f"[ai] {ticker}: verdict retried for a cited figure — recovered", flush=True)
            parsed = reparsed
        else:
            print(f"[ai] {ticker}: verdict retry still had no figure", flush=True)

    if parsed:
        # Verify the verdict text passes the Real Money Test before caching/returning.
        # company_name lets T4 recognise prose that says "Amazon" rather than "AMZN".
        company_name = price_data.get("name") or None
        verdict_text = parsed.get("verdict", "")
        approved, verified_text = verify_ai_text(ticker, verdict_text, "verdict",
                                                 company_name=company_name)
        if not approved:
            parsed["verdict"] = verified_text   # replace with fallback message
        elif verified_text != verdict_text:
            parsed["verdict"] = verified_text   # use cleaned version

        # full_analysis goes through the SAME gate. It was ungated until 2026-08-17,
        # while this module's own header claimed "Every AI-generated text passes
        # through verify_ai_text before being returned" — and it is the longer text
        # the user actually reads, so it was the more consequential of the two.
        # Gated independently: a weak full_analysis must not discard a good verdict,
        # and vice versa.
        analysis_text = parsed.get("full_analysis", "")
        if analysis_text:
            ok_analysis, checked_analysis = verify_ai_text(
                ticker, analysis_text, "full_analysis", company_name=company_name)
            if not ok_analysis or checked_analysis != analysis_text:
                parsed["full_analysis"] = checked_analysis
        if clean not in _BLOCKED_VERDICTS:
            # Tag every cached verdict with the change_pct and UTC timestamp used
            # at generation time. The drift check above uses _change_pct_at_generation
            # to detect when the prose has become inconsistent with the live header.
            # _generated_at is returned to the frontend for the "updated N min ago" label.
            parsed["_change_pct_at_generation"] = live_chg
            parsed["_generated_at"] = datetime.utcnow().isoformat()
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
    raw = text if text else _default_playbook(situation_type, ticker, stock_data)

    # Verify the playbook is specific to this stock, not generic boilerplate
    approved, result = verify_ai_text(ticker, raw, "strategy_playbook")
    # Even if approved=False we use the fallback message (result) — never crash

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
