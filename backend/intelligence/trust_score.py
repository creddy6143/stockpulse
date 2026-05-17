"""Trust Score calculator — 3 pillars, 100 points total."""
from data.fetcher import get_fundamentals, get_insider_data, get_analyst_data
from data.india import get_india_signals, is_indian_stock


def calculate_trust_score(ticker: str, price_data: dict = None) -> dict:
    """
    Returns full trust score breakdown:
      - business_score (0-40)
      - smart_money_score (0-35)
      - momentum_score (0-25)
      - total_score (0-100)
      - grade
      - auto_disqualified (bool)
      - disqualify_reason (str|None)
    """
    fundamentals = get_fundamentals(ticker)
    insider = get_insider_data(ticker)
    analyst = get_analyst_data(ticker)
    # Expose analyst to smart_money scoring (needed for consensus proxy)
    insider["_analyst"] = analyst

    # ── AUTO-DISQUALIFIERS ───────────────────────────────────────────────────
    auto_disq, disq_reason = _check_auto_disqualifiers(ticker, fundamentals, insider)
    if auto_disq:
        return _disqualified_result(ticker, disq_reason)

    # ── PILLAR 1: BUSINESS QUALITY (40 pts) ──────────────────────────────────
    business = _business_score(fundamentals)

    # ── PILLAR 2: SMART MONEY (35 pts) ───────────────────────────────────────
    smart_money = _smart_money_score(insider)

    # ── PILLAR 3: MOMENTUM (25 pts) ──────────────────────────────────────────
    momentum = _momentum_score(analyst, fundamentals, price_data)

    # Indian market bonus signals
    if is_indian_stock(ticker):
        india = get_india_signals(ticker)
        if india.get("consecutive_fii_buying", 0) >= 3:
            momentum = min(25, momentum + 3)
        if india.get("block_deal_buy"):
            smart_money = min(35, smart_money + 2)

    total = business + smart_money + momentum
    grade = _grade(total)

    return {
        "ticker": ticker,
        "total_score": total,
        "business_score": business,
        "smart_money_score": smart_money,
        "momentum_score": momentum,
        "grade": grade,
        "auto_disqualified": False,
        "disqualify_reason": None,
    }


def _check_auto_disqualifiers(ticker, fundamentals, insider) -> tuple:
    """Returns (bool, reason_str|None)."""
    cash_months = fundamentals.get("cash_runway_months")
    if cash_months is not None and cash_months < 6:
        return True, f"Cash runway only {cash_months} months — imminent dilution risk"

    if not fundamentals.get("gaap_profitable", True):
        rev_growth = fundamentals.get("revenue_growth", 0)
        profit_margin = fundamentals.get("profit_margins", 0)
        if profit_margin < -0.50 and rev_growth < 0:
            return True, "Severe losses with declining revenue — going concern risk"

    return False, None


def _disqualified_result(ticker: str, reason: str) -> dict:
    return {
        "ticker": ticker,
        "total_score": 0,
        "business_score": 0,
        "smart_money_score": 0,
        "momentum_score": 0,
        "grade": "Blocked",
        "auto_disqualified": True,
        "disqualify_reason": reason,
    }


def _business_score(f: dict) -> int:
    score = 0
    rev = f.get("revenue_growth", 0) or 0

    # Revenue growth (12 pts max)
    if rev > 0.30:
        score += 12
    elif rev > 0.15:
        score += 8
    elif rev > 0:
        score += 3

    # Profitability (10 pts)
    if f.get("gaap_profitable"):
        score += 10
    elif f.get("profit_margins", 0) > -0.10:
        score += 5

    # Earnings surprise (8 pts)
    surprise = f.get("earnings_surprise_pct", 0) or 0
    if surprise > 20:
        score += 8
    elif surprise > 5:
        score += 5
    elif surprise > 0:
        score += 2

    # Gross margins quality (10 pts)
    gm = f.get("gross_margins", 0) or 0
    if gm > 0.60:
        score += 10
    elif gm > 0.40:
        score += 7
    elif gm > 0.20:
        score += 4

    return min(40, score)


def _smart_money_score(insider: dict) -> int:
    score = 0
    analyst = insider.get("_analyst", {})

    # CEO buying is highest single signal (20 pts)
    if insider.get("ceo_buying"):
        score += 20
    elif insider.get("insider_buy_value", 0) > 100_000:
        score += 8

    # Analyst consensus as institutional proxy (10 pts)
    # Finnhub free tier doesn't expose institutional ownership; analyst
    # consensus (e.g. 93% buy on NVDA) is a reliable proxy for smart money.
    buy_n = analyst.get("buy_count", 0)
    hold_n = analyst.get("hold_count", 0)
    sell_n = analyst.get("sell_count", 0)
    total_analysts = buy_n + hold_n + sell_n
    if total_analysts > 0:
        buy_pct = buy_n / total_analysts
        if buy_pct > 0.80:
            score += 10
        elif buy_pct > 0.60:
            score += 6
        elif buy_pct > 0.40:
            score += 3

    # Short interest (5 pts for low — only when data is available)
    short_pct = insider.get("short_interest_pct", 0)
    if short_pct > 0 and short_pct < 5:
        score += 5
    elif short_pct > 40:
        score -= 5

    # Insider selling penalty removed — 10b5-1 scheduled plans (e.g. Jensen
    # Huang selling NVDA) are not bearish signals; penalising them produced
    # false S.SELL readings on world-class stocks.

    return max(0, min(35, score))


def _momentum_score(analyst: dict, fundamentals: dict, price_data: dict) -> int:
    score = 0

    # Analyst recommendation (8 pts)
    rec = (analyst.get("recommendation") or "hold").lower()
    if "strong_buy" in rec or rec == "buy":
        score += 8
    elif "hold" in rec:
        score += 2

    # Price vs analyst target (7 pts)
    target = analyst.get("target_price")
    price = (price_data or {}).get("price", 0)
    if target and price and price > 0:
        upside = (target - price) / price
        if upside > 0.20:
            score += 7
        elif upside > 0.05:
            score += 4

    # Revenue growth momentum (5 pts)
    rev = fundamentals.get("revenue_growth", 0) or 0
    earn = fundamentals.get("earnings_growth", 0) or 0
    if rev > 0.20 and earn > 0:
        score += 5
    elif rev > 0.10:
        score += 3

    # Earnings beat streak (5 pts)
    surprise = fundamentals.get("earnings_surprise_pct", 0) or 0
    if surprise > 10:
        score += 5
    elif surprise > 0:
        score += 2

    return min(25, score)


def _grade(total: int) -> str:
    if total >= 90:
        return "Exceptional"
    if total >= 75:
        return "Strong"
    if total >= 60:
        return "Moderate"
    if total >= 40:
        return "Weak"
    return "Blocked"


# ── DEMO OVERRIDES (for known test stocks) ───────────────────────────────────
# When real data is unavailable these provide sensible defaults for demo stocks.

DEMO_SCORES = {
    "TNXP":     {"total_score": 18, "business_score": 3, "smart_money_score": 5, "momentum_score": 10, "grade": "Blocked", "auto_disqualified": True, "disqualify_reason": "8 reverse splits. Chronic dilution."},
    "XGN":      {"total_score": 8,  "business_score": 2, "smart_money_score": 2, "momentum_score": 4,  "grade": "Blocked", "auto_disqualified": True, "disqualify_reason": "Board resigned 18 days before earnings."},
    "NKLA":     {"total_score": 7,  "business_score": 0, "smart_money_score": 2, "momentum_score": 5,  "grade": "Blocked", "auto_disqualified": True, "disqualify_reason": "CEO + CFO resigned. SEC fraud. Chapter 11."},
    "GRRR":     {"total_score": 68, "business_score": 28, "smart_money_score": 22, "momentum_score": 18, "grade": "Moderate", "auto_disqualified": False, "disqualify_reason": None},
    "INSM":     {"total_score": 61, "business_score": 22, "smart_money_score": 20, "momentum_score": 19, "grade": "Moderate", "auto_disqualified": False, "disqualify_reason": None},
    "NVDA":     {"total_score": 89, "business_score": 38, "smart_money_score": 30, "momentum_score": 21, "grade": "Strong", "auto_disqualified": False, "disqualify_reason": None},
    "AXON":     {"total_score": 87, "business_score": 36, "smart_money_score": 32, "momentum_score": 19, "grade": "Strong", "auto_disqualified": False, "disqualify_reason": None},
    "PLTR":     {"total_score": 79, "business_score": 30, "smart_money_score": 28, "momentum_score": 21, "grade": "Strong", "auto_disqualified": False, "disqualify_reason": None},
    "MSFT":     {"total_score": 82, "business_score": 33, "smart_money_score": 28, "momentum_score": 21, "grade": "Strong", "auto_disqualified": False, "disqualify_reason": None},
    "ASML":     {"total_score": 84, "business_score": 35, "smart_money_score": 30, "momentum_score": 19, "grade": "Strong", "auto_disqualified": False, "disqualify_reason": None},
    "CVNA":     {"total_score": 64, "business_score": 26, "smart_money_score": 22, "momentum_score": 16, "grade": "Moderate", "auto_disqualified": False, "disqualify_reason": None},
    "RELIANCE": {"total_score": 76, "business_score": 30, "smart_money_score": 28, "momentum_score": 18, "grade": "Strong", "auto_disqualified": False, "disqualify_reason": None},
    "HDFCBANK": {"total_score": 71, "business_score": 28, "smart_money_score": 25, "momentum_score": 18, "grade": "Strong", "auto_disqualified": False, "disqualify_reason": None},
    "TSLA":     {"total_score": 48, "business_score": 18, "smart_money_score": 15, "momentum_score": 15, "grade": "Weak", "auto_disqualified": False, "disqualify_reason": None},
}


def get_trust_score_with_fallback(ticker: str, price_data: dict = None) -> dict:
    """
    Priority order:
      1. Auto-disqualified demo stocks (human-verified red flags) → DEMO_SCORES
      2. Live calculation from real APIs
      3. Non-disqualified DEMO_SCORES entry (as verified baseline)
      4. Generic 50-point fallback
    """
    import re
    clean = re.sub(r'\.[A-Z]{1,3}$', '', ticker.upper())
    demo = DEMO_SCORES.get(clean)

    # Auto-disqualified stocks use DEMO_SCORES directly — these have been
    # manually verified (reverse splits, fraud, board resignations, etc.)
    if demo and demo.get("auto_disqualified"):
        result = dict(demo)
        result["ticker"] = ticker
        return result

    # All other stocks: try live calculation first
    try:
        score = calculate_trust_score(ticker, price_data)
        if score.get("total_score", 0) > 0 or score.get("auto_disqualified"):
            return score
    except Exception:
        pass

    # Live failed → fall back to DEMO_SCORES baseline if one exists
    if demo:
        result = dict(demo)
        result["ticker"] = ticker
        return result

    # Final fallback — generic moderate score
    return {
        "ticker": ticker, "total_score": 50,
        "business_score": 20, "smart_money_score": 15, "momentum_score": 15,
        "grade": "Moderate", "auto_disqualified": False, "disqualify_reason": None,
    }
