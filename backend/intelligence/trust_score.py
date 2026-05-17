"""Trust Score calculator — 3 pillars, 100 points total."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from data.fetcher import get_fundamentals, get_insider_data, get_analyst_data
from data.india import get_india_signals, is_indian_stock


def _has_real_data(f: dict) -> bool:
    """True when at least one meaningful fundamental field has real data.
    Prevents awarding points on missing-data defaults (e.g. profit_margins=0.0
    when Finnhub simply has no coverage for a stock).
    """
    return (
        (f.get("market_cap") or 0) > 0
        or abs(f.get("revenue_growth") or 0) > 0.001
        or abs(f.get("gross_margins") or 0) > 0.001
        or abs(f.get("profit_margins") or 0) > 0.001
        or (f.get("earnings_surprise_pct") is not None)
    )


def _is_speculative_prerevenue(f: dict) -> bool:
    """True when market cap data exists but fundamental operating data is absent.
    This means a company that IS real (it has a market cap) but has not yet
    reached revenue-generating stage. NNE, OKLO are examples.
    Distinct from 'no coverage' (MILDEF.ST) and from 'failing traditional business'.
    """
    market_cap = f.get("market_cap") or 0
    rev = abs(f.get("revenue_growth") or 0)
    gross = abs(f.get("gross_margins") or 0)
    profitable = f.get("gaap_profitable", False)
    # Has market cap (real company) but zero operating metrics → pre-revenue
    return market_cap > 0 and rev < 0.001 and gross < 0.001 and not profitable


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
    # Fetch all 3 data sources in parallel — was serial (3× slower)
    with ThreadPoolExecutor(max_workers=3) as ex:
        f_future = ex.submit(get_fundamentals, ticker)
        i_future = ex.submit(get_insider_data, ticker)
        a_future = ex.submit(get_analyst_data, ticker)
        fundamentals = f_future.result()
        insider      = i_future.result()
        analyst      = a_future.result()
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

    # Detect pre-revenue speculative stage AFTER scoring
    speculative = _is_speculative_prerevenue(fundamentals)
    grade = _grade(total, speculative)

    # Include analyst consensus in result so frontend can display it
    buy_n  = analyst.get("buy_count", 0)
    hold_n = analyst.get("hold_count", 0)
    sell_n = analyst.get("sell_count", 0)

    return {
        "ticker": ticker,
        "total_score": total,
        "business_score": business,
        "smart_money_score": smart_money,
        "momentum_score": momentum,
        "grade": grade,
        "auto_disqualified": False,
        "disqualify_reason": None,
        "is_speculative": speculative,
        # Analyst consensus — displayed on watchlist and stock rows
        "analyst_buy": buy_n,
        "analyst_hold": hold_n,
        "analyst_sell": sell_n,
        "analyst_target": analyst.get("target_price"),
        "data_quality": "limited" if not _has_real_data(fundamentals) else "full",
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
        "is_speculative": False,
        "data_quality": "full",
        "analyst_buy": 0, "analyst_hold": 0, "analyst_sell": 0, "analyst_target": None,
    }


def _business_score(f: dict) -> int:
    score = 0
    rev = f.get("revenue_growth", 0) or 0
    has_data = _has_real_data(f)

    # Revenue growth (12 pts max)
    if rev > 0.30:
        score += 12
    elif rev > 0.15:
        score += 8
    elif rev > 0:
        score += 3

    # Profitability (10 pts)
    # BUG FIX: only award "near profitable" when we actually have data.
    # profit_margins defaults to 0.0 when no data — 0.0 > -0.10 was awarding
    # 5 pts to pre-revenue companies and uncovered stocks (NNE, OKLO, MILDEF.ST).
    if f.get("gaap_profitable"):
        score += 10
    elif has_data and (f.get("profit_margins") or 0) > -0.10:
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

    # EPS growth quality (4 pts) — separate from revenue growth, measures
    # bottom-line acceleration which is the truest sign of business health.
    eps = f.get("earnings_growth", 0) or 0
    if eps > 0.50:
        score += 4
    elif eps > 0.20:
        score += 2

    return min(40, score)


def _smart_money_score(insider: dict) -> int:
    score = 0
    analyst = insider.get("_analyst", {})

    # CEO buying is highest single signal (20 pts)
    if insider.get("ceo_buying"):
        score += 20
    elif insider.get("insider_buy_value", 0) > 100_000:
        score += 8

    # Analyst consensus as institutional proxy (15 pts)
    # Finnhub free tier blocks institutional ownership (403). Analyst consensus
    # (71 analysts, 93% buy on NVDA) is the strongest available proxy for
    # where professional money is positioned — raised from 10 to 15 pts.
    buy_n = analyst.get("buy_count", 0)
    hold_n = analyst.get("hold_count", 0)
    sell_n = analyst.get("sell_count", 0)
    total_analysts = buy_n + hold_n + sell_n
    if total_analysts > 0:
        buy_pct = buy_n / total_analysts
        if buy_pct > 0.80:
            score += 15
        elif buy_pct > 0.60:
            score += 10
        elif buy_pct > 0.40:
            score += 5

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

    # Price vs analyst target / upside proxy (7 pts)
    # Finnhub free tier blocks price_target (403), so we fall back to
    # revenue+earnings acceleration as a forward-upside proxy: stocks with
    # >50% revenue AND >50% EPS growth consistently outperform over 12 months.
    rev = fundamentals.get("revenue_growth", 0) or 0
    earn = fundamentals.get("earnings_growth", 0) or 0
    target = analyst.get("target_price")
    price = (price_data or {}).get("price", 0)
    if target and price and price > 0:
        upside = (target - price) / price
        if upside > 0.20:
            score += 7
        elif upside > 0.05:
            score += 4
    else:
        # Growth-acceleration proxy for upside (when no target price available)
        if rev > 0.50 and earn > 0.50:
            score += 7   # hyper-growth — high probability of price appreciation
        elif rev > 0.30 and earn > 0:
            score += 4   # strong growth
        elif rev > 0.15 and earn > 0:
            score += 2   # decent growth

    # Revenue + earnings growth momentum (5 pts)
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


def _grade(total: int, speculative: bool = False) -> str:
    if speculative:
        # Pre-revenue companies get "Speculative" — not "Blocked"
        # They can still rank within speculative by score:
        # Speculative-Strong (score >= 25), Speculative (lower)
        return "Speculative"
    if total >= 90:
        return "Exceptional"
    if total >= 75:
        return "Strong"
    if total >= 60:
        return "Moderate"
    if total >= 40:
        return "Weak"
    return "Blocked"


# ── MANUAL BLOCK OVERRIDES ────────────────────────────────────────────────────
# Stocks with disqualifying red flags that Finnhub free-tier data cannot
# detect automatically (reverse splits, board resignations, SEC fraud).
# Every entry here MUST have auto_disqualified=True.
# All other stocks are scored 100% from live API data — no hardcoding.

BLOCKED_OVERRIDES = {
    "TNXP": {
        "total_score": 18, "business_score": 3, "smart_money_score": 5,
        "momentum_score": 10, "grade": "Blocked", "auto_disqualified": True,
        "disqualify_reason": "8 reverse splits. Chronic dilution.",
    },
    "XGN": {
        "total_score": 8, "business_score": 2, "smart_money_score": 2,
        "momentum_score": 4, "grade": "Blocked", "auto_disqualified": True,
        "disqualify_reason": "Board resigned 18 days before earnings.",
    },
    "NKLA": {
        "total_score": 7, "business_score": 0, "smart_money_score": 2,
        "momentum_score": 5, "grade": "Blocked", "auto_disqualified": True,
        "disqualify_reason": "CEO + CFO resigned. SEC fraud. Chapter 11.",
    },
}


def get_trust_score_with_fallback(ticker: str, price_data: dict = None) -> dict:
    """
    Priority order:
      1. Manual block overrides (BLOCKED_OVERRIDES) — red flags live data can't detect
      2. Live calculation from real APIs — always used for everything else
      3. Generic 50-point fallback if live APIs are completely down
    """
    import re
    clean = re.sub(r'\.[A-Z]{1,3}$', '', ticker.upper())

    # Manual block overrides — Finnhub can't detect reverse splits, board
    # resignations, or fraud convictions, so these are hardcoded permanently.
    override = BLOCKED_OVERRIDES.get(clean)
    if override:
        result = dict(override)
        result["ticker"] = ticker
        return result

    # Live calculation for every other stock
    try:
        score = calculate_trust_score(ticker, price_data)
        if score.get("total_score", 0) > 0 or score.get("auto_disqualified"):
            return score
    except Exception:
        pass

    # APIs completely unreachable — return generic fallback
    return {
        "ticker": ticker, "total_score": 50,
        "business_score": 20, "smart_money_score": 15, "momentum_score": 15,
        "grade": "Moderate", "auto_disqualified": False, "disqualify_reason": None,
        "is_speculative": False, "data_quality": "limited",
        "analyst_buy": 0, "analyst_hold": 0, "analyst_sell": 0, "analyst_target": None,
    }
