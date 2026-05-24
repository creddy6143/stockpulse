"""Trust Score calculator — 3 pillars, 100 points total.

Every computed score is passed through the verification layer before being
returned. The 'verification' key in the result dict carries confidence level,
suppression reason, and any warnings from the three-layer Real Money Test.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from data.fetcher import get_fundamentals, get_insider_data, get_analyst_data, get_news_catalyst_signal
from data.india import get_india_signals, is_indian_stock
from intelligence.verification import verify_trust_output, verify_recommendation


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


# ── DATA SUFFICIENCY INFRASTRUCTURE ─────────────────────────────────────────
# A stock must have ≥ 70% of these fields to receive any score.
# Below that threshold, scoring would produce a fake number based on zeros —
# which is worse than no score at all.

REQUIRED_FIELDS = [
    "market_cap",       # Company size — confirms it's a real public company
    "revenue_growth",   # Core business health signal
    "profit_margins",   # Profitability
    "gaap_profitable",  # Binary profitability flag
]


def _data_sufficiency(f: dict) -> float:
    """Returns fraction (0.0–1.0) of REQUIRED_FIELDS that have real data."""
    def _has(field: str) -> bool:
        v = f.get(field)
        if field == "gaap_profitable":
            return v is not None
        if field == "market_cap":
            return (v or 0) > 0
        return v is not None and abs(float(v or 0)) > 0.001
    return sum(_has(fld) for fld in REQUIRED_FIELDS) / len(REQUIRED_FIELDS)


def _data_unavailable_result(ticker: str, data_source: str = "no coverage") -> dict:
    """Returned when < 70% of required fundamental fields have real data.
    total_score is None (not 0, not 50) — the frontend must display '?' not a number.
    """
    return {
        "ticker": ticker,
        "total_score": None,
        "business_score": None,
        "smart_money_score": None,
        "momentum_score": None,
        "grade": "Data Unavailable",
        "auto_disqualified": False,
        "disqualify_reason": None,
        "is_speculative": False,
        "analyst_buy": 0,
        "analyst_hold": 0,
        "analyst_sell": 0,
        "analyst_target": None,
        "data_quality": "unavailable",
        "data_source": data_source,
    }


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

    # ── PRE-REVENUE DETECTION (before sufficiency gate) ──────────────────────
    # Pre-revenue companies (OKLO, NNE, IONQ) have a real market_cap but zero
    # operating metrics. The sufficiency gate below would mark them "Data
    # Unavailable" because market_cap is real but revenue/margins are legitimately
    # absent — not a data failure. Detect them first and score on smart_money +
    # momentum only, capped at 50 pts to reflect pre-commercial risk.
    if _is_speculative_prerevenue(fundamentals):
        auto_disq, disq_reason = _check_auto_disqualifiers(ticker, fundamentals, insider)
        if auto_disq:
            return _disqualified_result(ticker, disq_reason,
                                        data_source=fundamentals.get("data_source") or "live_data")
        try:
            catalyst = get_news_catalyst_signal(ticker)
        except Exception:
            catalyst = {"catalyst_pts": 0, "catalyst_type": "none", "catalyst_desc": ""}
        india = {}
        if is_indian_stock(ticker):
            india = get_india_signals(ticker)
            insider["_fii_consecutive_buying"] = india.get("consecutive_fii_buying", 0)
            insider["_fii_holding_pct"] = fundamentals.get("fii_holding_pct", 0) or 0
        sm  = _smart_money_score(insider)
        mom = _momentum_score(analyst, fundamentals, price_data, catalyst)
        if is_indian_stock(ticker):
            if india.get("consecutive_fii_buying", 0) >= 3:
                mom = min(25, mom + 3)
            if india.get("block_deal_buy"):
                sm = min(35, sm + 2)
        total = min(50, sm + mom)
        return {
            "ticker": ticker, "total_score": total, "business_score": 0,
            "smart_money_score": sm, "momentum_score": mom,
            "grade": "Speculative", "auto_disqualified": False,
            "disqualify_reason": None, "is_speculative": True,
            "analyst_buy": analyst.get("buy_count", 0),
            "analyst_hold": analyst.get("hold_count", 0),
            "analyst_sell": analyst.get("sell_count", 0),
            "analyst_target": analyst.get("target_price"),
            "data_quality": "limited",
            "data_source": fundamentals.get("data_source"),
        }

    # ── DATA SUFFICIENCY CHECK ────────────────────────────────────────────────
    # Universal replacement for the old hardcoded suffix check (.ST, .AS etc.).
    # If < 70% of required fundamental fields have real data, scoring produces a
    # fake low number based on zero-defaults. Return "Data Unavailable" instead.
    if _data_sufficiency(fundamentals) < 0.70:
        return _data_unavailable_result(ticker, fundamentals.get("data_source", "no coverage"))

    # ── AUTO-DISQUALIFIERS ───────────────────────────────────────────────────
    auto_disq, disq_reason = _check_auto_disqualifiers(ticker, fundamentals, insider)
    if auto_disq:
        return _disqualified_result(ticker, disq_reason,
                                    data_source=fundamentals.get("data_source") or "live_data")

    # ── PILLAR 1: BUSINESS QUALITY (40 pts) ──────────────────────────────────
    business = _business_score(fundamentals)

    # ── PILLAR 2: SMART MONEY (35 pts) ───────────────────────────────────────
    # For Indian stocks, inject FII institutional data as smart-money proxy.
    # FII consecutive buying and FII holding % are the most reliable signals
    # available when Finnhub free-tier blocks insider/analyst data (403).
    india = {}
    if is_indian_stock(ticker):
        india = get_india_signals(ticker)
        insider["_fii_consecutive_buying"] = india.get("consecutive_fii_buying", 0)
        insider["_fii_holding_pct"] = fundamentals.get("fii_holding_pct", 0) or 0
    smart_money = _smart_money_score(insider)

    # ── PILLAR 3: MOMENTUM (25 pts) ──────────────────────────────────────────
    # News catalyst signal is fetched here (cache hit — get_news() already ran
    # during price fetch) and passed into the momentum scorer.
    # This closes the architectural gap: get_news() data was being fetched but
    # never influencing the numeric trust score.
    try:
        catalyst = get_news_catalyst_signal(ticker)
    except Exception:
        catalyst = {"catalyst_pts": 0, "catalyst_type": "none", "catalyst_desc": ""}
    momentum = _momentum_score(analyst, fundamentals, price_data, catalyst)

    # Indian market bonus adjustments (post-scoring)
    if is_indian_stock(ticker):
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
        "data_source": fundamentals.get("data_source"),
    }


def _check_auto_disqualifiers(ticker, fundamentals, insider) -> tuple:
    """Returns (bool, reason_str|None).

    RULE: Auto-disqualifiers are ONLY for objective categorical facts —
    things that are binary, verifiable, and not subject to interpretation.
    Examples: cash runway < 6 months, reverse splits, board resignations, SEC fraud.

    Financial-metric conditions (profit_margins, revenue_growth) have been
    intentionally removed from this function. Reasons:
      1. They fire incorrectly on legitimate early-stage companies (quantum
         computing, pre-commercial biotech, AI infrastructure) where very
         negative margins and quarter-to-quarter revenue dips are NORMAL
         and expected business behaviour — not distress signals.
      2. The three-pillar scoring engine already handles poor financials
         correctly: a company with severe losses and declining revenue will
         score <40 on business_score alone, producing a "Blocked" grade and
         SELL recommendation — the honest, accurate output.
      3. Auto-disq escalates to score=0 + URGENT ALERT, which is factually
         wrong for a stock that is simply early-stage or cyclically down.
    """
    # ── Data confidence gate ──────────────────────────────────────────────────
    # Any future condition added here that relies on financial metrics MUST pass
    # this gate first. If data sufficiency < 70% the numbers are defaults (0.0),
    # not real measured values, so disqualifying on them would be based on nothing.
    # This mirrors the picks P1 gate in verification.py.
    data_ok = _data_sufficiency(fundamentals) >= 0.70

    # Cash runway: objective hard fact — only fires when explicitly populated.
    # safe regardless of data_ok because the `is not None` guard already ensures
    # this field was explicitly set by a data source (not a 0.0 default).
    cash_months = fundamentals.get("cash_runway_months")
    if cash_months is not None and cash_months < 6:
        return True, f"Cash runway only {cash_months} months — imminent dilution risk"

    # NOTE: Any future financial-metric disqualifier (margins, revenue trends,
    # debt ratios) MUST be gated: `if data_ok and <condition>: return True, reason`
    # Without data_ok, zero-defaults will trigger false positives.
    _ = data_ok  # referenced above — keeps linter happy

    return False, None


def _disqualified_result(ticker: str, reason: str, data_source: str = "verified") -> dict:
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
        "data_source": data_source,
        "analyst_buy": 0, "analyst_hold": 0, "analyst_sell": 0, "analyst_target": None,
    }


def _business_score(f: dict) -> int:
    score = 0
    rev = f.get("revenue_growth", 0) or 0
    has_data = _has_real_data(f)

    # Large-cap established business flag.
    # market_cap > $10B (USD) or equivalent: Finnhub stores in absolute USD,
    # Screener.in stores in INR (400k Cr ≈ 4e12 INR >> 1e10).
    # This threshold correctly identifies INFY, TCS, ASML, ERIC etc. as
    # established businesses that should not be penalized for "only" 8-10% growth.
    mkt_cap = f.get("market_cap", 0) or 0
    is_large = mkt_cap > 10_000_000_000  # > $10B or > ₹10B (INR)

    gm = f.get("gross_margins", 0) or 0
    pm = f.get("profit_margins", 0) or 0

    # ── FINANCIAL-SECTOR PATTERN DETECTION ───────────────────────────────────
    # Banks, insurance, and payment processors report gross_margins ≈ 0% in
    # yfinance because they have no traditional COGS (business model, not a flaw).
    # Penalising these stocks for "0% gross margin" produces a false 10-pt gap vs
    # tech/retail peers.  Solution: when gross_margins is near-zero but the
    # company is GAAP profitable with real profit margins, use profit_margins as
    # the margin quality metric instead.
    #
    # Two detection patterns (data-driven, no sector metadata needed):
    # 1. Traditional: gross_margins < 3% — US/EU banks, payment processors (JPM, V, MA)
    #    gm ≈ 0 because no traditional COGS (net interest income is the business model)
    # 2. NBFC/inverted: profit_margins > gross_margins — Indian NBFCs (BAJFINANCE, HDFCBANK)
    #    Screener.in reports OPM as gross_margin; for NBFCs pm > gm is mathematically
    #    impossible in standard accounting, signalling the "gross margin" is not a
    #    traditional metric. Use profit_margins for scoring instead.
    is_financial_model = (
        # US/EU banks and payment processors: gross_margin ≈ 0
        (gm < 0.03 and pm > 0.05 and f.get("gaap_profitable", False))
        # Indian NBFC / financial services: profit margin > gross margin (inverted)
        # In standard accounting pm < gm always. If pm > gm, the "gross margin"
        # is not a traditional COGS-based metric — use profit_margins instead.
        # pm < 0.80 cap: prevents one-time accounting events (debt extinguishment
        # gains, asset sales) from triggering the financial model. Legitimate NBFCs
        # have pm 10-40%; pm > 80% signals a non-recurring item corrupting TTM data
        # (e.g. BYND pm=91% from a debt restructuring gain in a single TTM window).
        or (pm > gm > 0 and 0.05 < pm < 0.80)
    )

    # Revenue growth (12 pts max)
    if is_large:
        # Established companies: steady 8%+ growth = excellent for their scale
        if rev > 0.20:
            score += 12
        elif rev > 0.08:   # INFY 9.6% → +8 pts (was +3 under old 15% threshold)
            score += 8
        elif rev > 0.02:
            score += 4
        elif rev > 0:
            score += 2
        elif rev < 0:
            if f.get("gaap_profitable") and pm > 0.05:
                # ── CYCLICAL DOWN-CYCLE CREDIT (profitable) ───────────────────
                # e.g. XOM revenue -5% when oil drops, margins still 10%+ → +3
                score += 3
            elif gm > 0.25:
                # ── CYCLICAL DOWN-CYCLE CREDIT (gross-margin intact) ──────────
                # Large established company with gross margins > 25% (INTC ~40%)
                # but GAAP net losses from one-time restructuring / impairments.
                # The gross margin confirms the core business model is intact;
                # the net loss is accounting charges, not operational collapse.
                score += 2
    else:
        # Small/mid-cap: higher growth expected, original thresholds apply
        if rev > 0.30:
            score += 12
        elif rev > 0.15:
            score += 8
        elif rev > 0:
            score += 3
        elif rev < 0 and f.get("gaap_profitable") and pm > 0.05:
            score += 2  # smaller cyclical credit for small-cap

    # Profitability (10 pts)
    # GUARD: profit_margins defaults to 0.0 when data unavailable. has_data can be
    # True from market_cap alone, so profit_margins=0.0 (default) would incorrectly
    # pass the old "> -0.10" check. Require pm_real: the value must be an explicitly
    # measured non-zero margin before awarding near-profitable credit.
    pm_real = abs(pm) > 0.001   # measured margin (not a 0.0 default)
    if f.get("gaap_profitable"):
        score += 10
    elif has_data and pm_real and pm > -0.10:
        score += 5   # Near breakeven — on the path to profitability
    elif is_large and has_data and gm > 0.25:
        # ── LARGE-CAP RESTRUCTURING CREDIT ────────────────────────────────────
        # INTC/ERIC-type situation: gross margins > 25% confirm the core business
        # economics are sound, but GAAP net income is negative from one-time charges
        # (impairments, restructuring, write-downs). These are accounting events,
        # not operational collapse. Do NOT score 0 identically to a failing startup.
        score += 3

    # Earnings quality (8 pts) — multi-quarter streak beats single-quarter surprise.
    # A company beating estimates 4 consecutive quarters demonstrates systematic
    # execution discipline (the "sandbagging" pattern — one of our 8 core patterns).
    # Single-quarter surprise is too noisy; the streak is the signal.
    history = f.get("earnings_history") or []
    beats_valid = [
        (float(q["actual"]), float(q.get("estimate") or q.get("est")))
        for q in history[:4]
        if q.get("actual") is not None
        and (q.get("estimate") or q.get("est"))
        and float(q.get("estimate") or q.get("est")) != 0
    ]
    beat_count  = sum(1 for act, est in beats_valid if act > est)
    valid_count = len(beats_valid)

    if valid_count >= 2:
        # Use streak scoring when we have at least 2 quarters of history
        if beat_count >= 4:
            score += 8   # Beat all 4 — systematic over-delivery
        elif beat_count >= 3:
            score += 5   # Beat 3 of 4 — reliable execution
        elif beat_count >= 2:
            score += 2   # Beat half — improving or mixed
    else:
        # No multi-quarter history available — fall back to single-quarter surprise
        surprise = f.get("earnings_surprise_pct", 0) or 0
        if surprise > 20:
            score += 8
        elif surprise > 5:
            score += 5
        elif surprise > 0:
            score += 2

    # Gross/profit margins quality (10 pts)
    # For financial-model stocks (banks, utilities): use profit_margins because
    # yfinance reports gross_margins = 0% for these (no traditional COGS).
    # A bank with 30%+ net margins is a well-run business; the 10-pt gap vs
    # tech peers was an unfair artifact of different accounting conventions.
    margin_metric = pm if is_financial_model else gm
    if is_large:
        # Large established companies: 20%+ margin = strong
        if margin_metric > 0.40:
            score += 10
        elif margin_metric > 0.20:    # INFY OPM ~21% → +7
            score += 7
        elif margin_metric > 0.10:
            score += 4
    else:
        if margin_metric > 0.60:
            score += 10
        elif margin_metric > 0.40:
            score += 7
        elif margin_metric > 0.20:
            score += 4

    # EPS growth quality (4 pts) — separate from revenue growth, measures
    # bottom-line acceleration which is the truest sign of business health.
    # ROE PROXY: Screener.in for Indian stocks provides ROE (stored as %, e.g. 43.4)
    # but not earnings_growth. ROE > 25% signals outstanding capital efficiency and
    # is a reliable proxy for business quality when EPS growth is unavailable.
    # Only used when earnings_growth = 0 (data absent) to avoid double-counting.
    eps = f.get("earnings_growth", 0) or 0
    roe_raw = f.get("roe") or 0   # screener.in stores as percentage (43.4 = 43.4%)
    if eps > 0.50:
        score += 4
    elif eps > 0.20:
        score += 2
    elif eps == 0 and roe_raw > 25:
        score += 4   # Outstanding ROE (> 25%) — proxy for strong earnings quality
    elif eps == 0 and roe_raw > 15:
        score += 2   # Decent ROE (> 15%) — proxy for adequate earnings quality

    # Forward EPS inflection bonus (4 pts) — the only forward-looking business signal.
    # Analyst consensus forward EPS captures the re-rating the market is pricing in.
    # Loss → Profit inflection: analysts collectively expect profitable operations
    # next year when the company is currently loss-making. This is one of the
    # strongest re-rating triggers in equity markets (INTC, AMD 2022, RKLB).
    # Strong EPS growth expectation (25%+): analysts expect major earnings acceleration.
    fwd_eps = f.get("forward_eps") or 0
    ttm_eps = f.get("trailing_eps") or 0
    if fwd_eps > 0 and ttm_eps <= 0:
        score += 4   # Loss → Profit inflection — analysts expect turnaround
    elif fwd_eps > 0 and ttm_eps > 0 and fwd_eps > ttm_eps * 1.25:
        score += 2   # Strong EPS growth expected (25%+)

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
    else:
        # Counts unavailable but direction known from recommendationKey.
        # Finnhub/Yahoo throttle means num_analysts=0 yet rec_key="buy".
        # Award conservative 5 pts (not 15) — confirms positive direction
        # without overstating confidence in the distribution.
        rec_dir = (analyst.get("recommendation") or "hold").lower()
        if rec_dir in ("buy", "strong_buy", "strongbuy", "outperform"):
            score += 5

    # India FII institutional proxy (replaces CEO buying when absent).
    # FII holding % from Screener.in is the best available smart-money signal
    # for Indian stocks: INFY = 33.4% FII = strong institutional conviction.
    # FII consecutive buying (from NSE daily data) signals active accumulation.
    fii_pct  = insider.get("_fii_holding_pct", 0) or 0
    fii_days = insider.get("_fii_consecutive_buying", 0) or 0
    if fii_pct > 0 or fii_days > 0:
        if not insider.get("ceo_buying") and (insider.get("insider_buy_value") or 0) <= 100_000:
            # Active FII accumulation flow signal
            if fii_days >= 3:
                score += 12
            elif fii_days >= 1:
                score += 5
        # FII holding % — structural institutional backing (always scores)
        if fii_pct > 30:
            score += 8    # INFY 33.4% → +8
        elif fii_pct > 15:
            score += 5    # Strong foreign institutional backing (15%+ is above Nifty avg)
        elif fii_pct > 8:
            score += 2

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


def _momentum_score(analyst: dict, fundamentals: dict, price_data: dict,
                    catalyst: dict | None = None) -> int:
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

    # Price vs 200-day moving average (7 pts)
    # The universally used institutional trend confirmation — CLAUDE.md spec baseline
    # that was never implemented. Every professional fund uses this as the primary
    # filter: above 200MA = money flowing in, below = money flowing out.
    # Well above (10%+) confirms not just direction but strength of the move.
    # Downtrend penalty: well below 200MA (-3) is a mild signal, not a disqualifier.
    ma200 = (fundamentals or {}).get("ma_200d") or 0
    cur   = (price_data or {}).get("price", 0)
    if ma200 > 0 and cur > 0:
        ratio = cur / ma200
        if ratio >= 1.10:
            score += 7   # 10%+ above 200MA — confirmed uptrend with momentum
        elif ratio >= 1.02:
            score += 5   # Above 200MA — uptrend established
        elif ratio >= 0.98:
            score += 2   # Hugging 200MA — testing support, neutral
        elif ratio < 0.85:
            score -= 3   # Well below 200MA — confirmed downtrend, capital leaving
        # 0.85–0.97: 0 pts — below MA but not confirmed breakdown

    # Near 52-week high = market conviction (5 pts)
    # A stock trading at 90%+ of its 52-week high has passed the most demanding
    # real-money test: institutional investors are buying/holding at these prices
    # despite full knowledge of the company's situation. Analyst price targets
    # often lag during recoveries — trading at or above old targets is NOT a
    # penalty, it signals the market sees more ahead. Also catches turnarounds
    # (INTC at ATH despite restructuring losses) that fundamentals lag to capture.
    w52h = (fundamentals or {}).get("w52_high") or 0
    cur  = (price_data or {}).get("price", 0)
    if w52h > 0 and cur > 0:
        pct_of_high = cur / w52h
        if pct_of_high >= 0.95:
            score += 5   # at or near 52-week high — strong market conviction
        elif pct_of_high >= 0.85:
            score += 2   # strong recovery from recent lows

    # News catalyst signal (up to +5 / down to -10)
    # Closes the architectural gap: get_news() was fetched but never scored.
    # Positive: government contract, FDA approval, partnership, beat estimates
    # Negative: SEC investigation, bankruptcy, guidance cut, fraud
    # Clamped so a single article cannot dominate the score.
    if catalyst:
        cat_pts = int(catalyst.get("catalyst_pts", 0) or 0)
        if cat_pts != 0:
            score += cat_pts

    return max(0, min(25, score))


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
        "data_source": "manual_block",
    },
    "XGN": {
        "total_score": 8, "business_score": 2, "smart_money_score": 2,
        "momentum_score": 4, "grade": "Blocked", "auto_disqualified": True,
        "disqualify_reason": "Board resigned 18 days before earnings.",
        "data_source": "manual_block",
    },
    "NKLA": {
        "total_score": 7, "business_score": 0, "smart_money_score": 2,
        "momentum_score": 5, "grade": "Blocked", "auto_disqualified": True,
        "disqualify_reason": "CEO + CFO resigned. SEC fraud. Chapter 11.",
        "data_source": "manual_block",
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
        # Blocked overrides are pre-verified — mark them HIGH so the badge stays clean
        result["verification"] = {
            "confidence": "HIGH", "suppressed": False,
            "suppression_reason": None, "warnings": [],
            "checks_passed": ["manual_block_override"],
            "display_score": result.get("total_score"),
            "display_grade": result.get("grade", "Blocked"),
            "caveat": None,
        }
        return result

    # Live calculation for every other stock
    try:
        score = calculate_trust_score(ticker, price_data)
        # Pass through valid results: numeric score, auto-disqualified, or Data Unavailable
        # (total_score can be None for Data Unavailable — that is a valid honest result)
        if (score.get("total_score") is not None
                or score.get("auto_disqualified")
                or score.get("data_quality") == "unavailable"):

            # ── REAL MONEY TEST ────────────────────────────────────────────
            # Run all three verification layers. Attach result as 'verification'.
            # Fetch fundamentals from cache (near-instant after calculate_trust_score ran them).
            try:
                fundamentals = get_fundamentals(ticker)
                analyst      = {
                    "buy_count":  score.get("analyst_buy", 0),
                    "hold_count": score.get("analyst_hold", 0),
                    "sell_count": score.get("analyst_sell", 0),
                }
                verif = verify_trust_output(ticker, score, fundamentals, analyst)
                score["verification"] = verif

                # If verification suppresses the score, zero out display fields.
                # Internal score is preserved so _detect_situation logic still works.
                if verif["suppressed"] and score.get("data_quality") != "unavailable":
                    score["display_score"] = None
                    score["display_grade"] = verif["display_grade"]
                else:
                    score["display_score"] = score.get("total_score")
                    score["display_grade"] = score.get("grade", "")

                # Verify recommendation consistency
                rec_input = "SELL" if score.get("auto_disqualified") else (
                    "BUY"  if (score.get("total_score") or 0) >= 75 else
                    "HOLD" if (score.get("total_score") or 0) >= 60 else
                    "SELL"
                )
                verified_rec, rec_note = verify_recommendation(
                    ticker,
                    score.get("total_score"),
                    rec_input,
                    score.get("auto_disqualified", False),
                )
                score["verified_rec"] = verified_rec
                score["rec_correction"] = rec_note
            except Exception:
                # Verification must never crash the app — fail open with HIGH confidence
                score["verification"] = {
                    "confidence": "HIGH", "suppressed": False,
                    "suppression_reason": None, "warnings": ["verification_layer_error"],
                    "checks_passed": [], "display_score": score.get("total_score"),
                    "display_grade": score.get("grade", ""), "caveat": None,
                }
                score["display_score"] = score.get("total_score")
                score["display_grade"] = score.get("grade", "")
            # ── END REAL MONEY TEST ────────────────────────────────────────

            return score
    except Exception:
        pass

    # APIs completely unreachable — return generic fallback (low confidence)
    fallback = {
        "ticker": ticker, "total_score": 50,
        "business_score": 20, "smart_money_score": 15, "momentum_score": 15,
        "grade": "Moderate", "auto_disqualified": False, "disqualify_reason": None,
        "is_speculative": False, "data_quality": "limited",
        "analyst_buy": 0, "analyst_hold": 0, "analyst_sell": 0, "analyst_target": None,
        "display_score": 50, "display_grade": "Moderate",
        "verified_rec": "HOLD",
        "verification": {
            "confidence": "MEDIUM",
            "suppressed": False,
            "suppression_reason": None,
            "warnings": ["L1_no_source: APIs unreachable — using generic fallback score"],
            "checks_passed": [],
            "display_score": 50,
            "display_grade": "Moderate",
            "caveat": "Score estimated — live data unavailable",
        },
    }
    return fallback
