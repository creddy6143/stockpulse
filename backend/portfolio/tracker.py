"""Portfolio P&L and positions management — all values in native currency + SEK."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from database import db as _db
from database.db import get_portfolio, get_watchlist
from data.fetcher import get_stock_price, get_exchange_rates, get_analyst_data, get_fundamentals, get_fmp_profile
from intelligence.trust_score import get_trust_score_with_fallback
from intelligence.verification import verify_watchlist_signal


def _detect_currency(ticker: str) -> str:
    """Infer native currency from ticker suffix."""
    if ticker.endswith(".NS") or ticker.endswith(".BO"):
        return "INR"
    if ticker.endswith(".ST"):           # Stockholm — Swedish kronor
        return "SEK"
    if any(ticker.endswith(s) for s in [".AS", ".DE", ".PA", ".F", ".MI", ".MC", ".BR"]):
        return "EUR"
    if ticker.endswith(".L"):
        return "GBP"
    return "USD"


def _sek_rate(currency: str, rates: dict) -> float:
    """How many SEK per 1 unit of the given currency."""
    mapping = {
        "USD": rates.get("USDSEK", 10.4),
        "EUR": rates.get("EURSEK", 11.2),
        "INR": rates.get("INRSEK", 0.124),
        "SEK": 1.0,
        "GBP": rates.get("GBPSEK", 13.2),
    }
    return mapping.get((currency or "USD").upper(), rates.get("USDSEK", 10.4))


def _extract_fmp_profile(fundamentals: dict) -> dict | None:
    """Pull FMP profile fields from a fundamentals dict, or None if not present."""
    if not fundamentals.get("fmp_name"):
        return None
    return {
        "name":        fundamentals.get("fmp_name"),
        "sector":      fundamentals.get("fmp_sector"),
        "industry":    fundamentals.get("fmp_industry"),
        "description": fundamentals.get("fmp_description"),
        "ceo":         fundamentals.get("fmp_ceo"),
        "employees":   fundamentals.get("fmp_employees"),
        "country":     fundamentals.get("fmp_country"),
        "exchange":    fundamentals.get("fmp_exchange"),
        "currency":    fundamentals.get("fmp_currency"),
        "beta":        fundamentals.get("fmp_beta"),
        "isin":        fundamentals.get("fmp_isin"),
        "market_cap":  fundamentals.get("market_cap"),
        "w52_high":    fundamentals.get("w52_high"),
        "w52_low":     fundamentals.get("w52_low"),
    }


def _build_position(pos: dict, rates: dict) -> dict:
    """Fetch live data + trust for a single position. Runs in thread pool."""
    ticker = pos["ticker"]
    price_data = get_stock_price(ticker)
    trust = get_trust_score_with_fallback(ticker, price_data)

    price = price_data.get("price") or pos["buy_price"]
    currency = pos.get("currency") or _detect_currency(ticker)
    rate = _sek_rate(currency, rates)

    shares = pos["shares"]
    buy_price = pos["buy_price"]

    pnl = (price - buy_price) * shares
    pnl_pct = ((price - buy_price) / buy_price * 100) if buy_price else 0
    value_sek = price * shares * rate
    invested_sek = buy_price * shares * rate
    pnl_sek = value_sek - invested_sek

    group = _classify_position(trust, pnl_pct)

    return {
        "id": pos["id"],
        "ticker": ticker,
        "name": pos.get("name") or price_data.get("name", ticker),
        "shares": shares,
        "buy_price": buy_price,
        "current_price": round(float(price), 4),
        "change_pct": round(float(price_data.get("change_pct", 0)), 2),
        "pnl": round(float(pnl), 2),
        "pnl_pct": round(float(pnl_pct), 2),
        "value_sek": round(value_sek, 0),
        "invested_sek": round(invested_sek, 0),
        "pnl_sek": round(pnl_sek, 0),
        "sek_rate": rate,
        "market": pos.get("market", "US"),
        "currency": currency,
        "trust_score": trust["total_score"],
        # display_score is None when verification suppressed the result.
        # Use this for the UI — trust_score is kept for internal logic.
        "display_score": trust.get("display_score", trust["total_score"]),
        "display_grade": trust.get("display_grade", trust["grade"]),
        "grade": trust["grade"],
        "auto_disqualified": trust["auto_disqualified"],
        "disqualify_reason": trust["disqualify_reason"],
        "data_source": trust.get("data_source"),
        "data_quality": trust.get("data_quality", "full"),
        "verified_rec": trust.get("verified_rec"),
        "verification": trust.get("verification"),
        "group": group,
        "is_speculative": trust.get("is_speculative", False),
        "analyst_buy": trust.get("analyst_buy", 0),
        "analyst_hold": trust.get("analyst_hold", 0),
        "analyst_sell": trust.get("analyst_sell", 0),
        "analyst_target": trust.get("analyst_target"),
        "business_score": trust.get("business_score", 0),
        "smart_money_score": trust.get("smart_money_score", 0),
        "momentum_score": trust.get("momentum_score", 0),
        "situation_label": trust.get("situation_label"),
        "situation_note": trust.get("situation_note"),
        # FMP profile enrichment — populated for Data Unavailable stocks
        "fmp_profile": _extract_fmp_profile(get_fundamentals(ticker))
            if trust.get("data_quality") == "unavailable" else None,
    }


def _fire_price_alerts(ticker: str, current_price: float,
                       trust_score, auto_disq: bool) -> None:
    """Check price alerts and generate in-app notifications if triggered.
    Imported lazily to avoid circular imports (main → tracker → main).
    Verification gate: skip alert check if score is suppressed (display_score is None).
    """
    try:
        from main import _check_price_alerts
        _check_price_alerts(ticker, current_price, trust_score, auto_disq)
    except Exception:
        pass


def get_portfolio_with_pnl() -> dict:
    """All positions with live P&L — prices + trust fetched in parallel."""
    positions = get_portfolio()
    if not positions:
        return {
            "positions": [],
            "summary": {
                "total_value_sek": 0, "total_invested_sek": 0,
                "total_pnl_sek": 0, "total_pnl_pct": 0,
                "position_count": 0, "exchange_rates": {},
            },
        }

    rates = get_exchange_rates()

    # Parallel fetch — all stocks at once instead of one-by-one
    workers = min(20, len(positions))
    result = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_build_position, pos, rates): pos for pos in positions}
        for future in as_completed(futures):
            try:
                result.append(future.result())
            except Exception:
                pass  # skip failed positions rather than break the whole response

    # Sort: auto-disqualified first, then worst P&L first
    result.sort(key=lambda x: (not x["auto_disqualified"], x["pnl_pct"]))

    # Fire price alerts + auto-disq in-app notifications (non-blocking, never crashes)
    for pos in result:
        _fire_price_alerts(
            pos["ticker"],
            pos["current_price"],
            pos.get("trust_score"),
            pos.get("auto_disqualified", False),
        )
        # Generate urgent in-app alert ONLY for hard categorical disqualifiers.
        # Hard disqualifiers = objective, binary, verifiable facts:
        #   cash runway, reverse split, board resignation, SEC fraud, etc.
        # Financial-metric conditions (margins, revenue) have been removed from
        # auto-disqualifiers — they were producing false "going concern" alerts on
        # legitimate early-stage companies (quantum computing, biotech).
        # The rule: an alert must only fire when the reason traces to a categorical
        # fact, not a financial inference. We check by scanning the reason text for
        # the keywords that our categorical disqualifiers actually produce.
        _HARD_DISQ_KEYWORDS = (
            "cash runway", "reverse split", "board resign", "ceo", "cfo",
            "sec ", "fraud", "chapter 11", "bankruptcy", "liquidat",
            "going concern",   # only valid if from auditor notes, not our inference
            "promoter pledge", "sebi",
        )
        if pos.get("auto_disqualified") and not _db.recent_alert_exists(pos["ticker"], hours=24):
            reason = pos.get("disqualify_reason") or ""
            reason_lower = reason.lower()
            is_categorical = any(kw in reason_lower for kw in _HARD_DISQ_KEYWORDS)
            # Also fire for manual BLOCKED_OVERRIDES — these have verified reasons
            is_manual_override = pos.get("data_quality") != "limited"
            if is_categorical or is_manual_override:
                _db.create_alert(pos["ticker"], "urgent",
                                 f"{pos['ticker']} — {reason}. Review and consider exiting.")

    total_value_sek    = sum(p["value_sek"]    for p in result)
    total_invested_sek = sum(p["invested_sek"] for p in result)
    total_pnl_sek      = total_value_sek - total_invested_sek
    pnl_pct_sek = (total_pnl_sek / total_invested_sek * 100) if total_invested_sek else 0

    return {
        "positions": result,
        "summary": {
            "total_value_sek":    round(total_value_sek, 0),
            "total_invested_sek": round(total_invested_sek, 0),
            "total_pnl_sek":      round(total_pnl_sek, 0),
            "total_pnl_pct":      round(pnl_pct_sek, 2),
            "position_count":     len(result),
            "exchange_rates":     rates,
        },
    }


def _classify_position(trust: dict, pnl_pct: float) -> str:
    # Suppressed score (display_score is None) and NOT auto-disqualified means we
    # don't have enough data to make a confident call — put in Watch, never Urgent.
    # Saying "Action Required" when data is insufficient is worse than saying nothing.
    if trust.get("display_score") is None and not trust.get("auto_disqualified"):
        return "watch"
    score = trust["total_score"]
    if trust["auto_disqualified"] or (score is not None and score < 40):
        return "urgent"
    if score is None:
        # Data Unavailable — put in watch group (visible but not alarming)
        return "watch"
    if pnl_pct < -20 or score < 60:
        return "watch"
    return "good"


def _build_watchlist_item(item: dict) -> dict:
    """Fetch live data + trust for a single watchlist item. Runs in thread pool."""
    ticker = item["ticker"]
    price_data = get_stock_price(ticker)
    trust = get_trust_score_with_fallback(ticker, price_data)

    # Analyst data is already fetched inside trust score calculation (cached).
    # Re-fetch from cache (near-instant) to get target price for upside calc.
    analyst = get_analyst_data(ticker)
    fundamentals = get_fundamentals(ticker)

    price = price_data.get("price", 0)
    target_price = trust.get("analyst_target") or analyst.get("target_price")

    # Real analyst upside % — (target - price) / price × 100
    if target_price and price > 0:
        upside_pct = round(((target_price - price) / price) * 100, 1)
        upside_str = f"+{upside_pct:.0f}%" if upside_pct >= 0 else f"{upside_pct:.0f}%"
    else:
        upside_pct = None
        upside_str = "—"

    # Entry zone: 52W support +15% → current price -3%
    entry_str = "—"
    w52_low = fundamentals.get("w52_low")
    if w52_low and price > 0:
        entry_low = w52_low * 1.15
        entry_high = price * 0.97
        if entry_low < entry_high:
            entry_str = f"{entry_low:.0f}–{entry_high:.0f}"
        else:
            entry_str = f"{price*0.92:.0f}–{price*0.98:.0f}"

    # Signal group — also considers analyst consensus now
    total_analysts = (trust.get("analyst_buy", 0) + trust.get("analyst_hold", 0)
                      + trust.get("analyst_sell", 0))
    buy_pct = (trust.get("analyst_buy", 0) / total_analysts) if total_analysts > 0 else 0

    score = trust["total_score"]
    if score is not None and score >= 75 and not trust["auto_disqualified"]:
        wl_group = "ready"
        signal = "Entry zone now"
    elif trust["auto_disqualified"] or (score is not None and score < 30):
        # score < 30 = genuinely distressed or blocked — "Avoid"
        # score 30–59 falls through to "watching" below — weak but not a red flag.
        # INTC at 34 (cyclical down-cycle), SOFI at 33 (data gap) belong in
        # "watching", not alongside stocks with SEC investigations or cash crises.
        wl_group = "avoid"
        signal = "Not yet"
    else:
        # score is None (Data Unavailable) or moderate score → watching
        wl_group = "watching"
        # More descriptive signal based on analyst consensus
        if buy_pct >= 0.75:
            signal = "High analyst conviction"
        elif upside_pct is not None and upside_pct > 30:
            signal = f"Analysts see +{upside_pct:.0f}% upside"
        else:
            signal = "Still watching"

    # ── REAL MONEY TEST — watchlist signal verification ────────────────────
    # Catches cases where signal and wl_group are internally inconsistent
    # (e.g. "ready" group with score < 70, or "avoid" with high score).
    signal, wl_group, _correction = verify_watchlist_signal(
        ticker, trust, signal, wl_group
    )

    return {
        "id": item["id"],
        "ticker": ticker,
        "name": item.get("name") or price_data.get("name", ticker),
        "current_price": price,
        "change_pct": price_data.get("change_pct", 0),
        "trust_score": trust["total_score"],
        # display_score is None when verification suppressed the score
        "display_score": trust.get("display_score", trust["total_score"]),
        "display_grade": trust.get("display_grade", trust["grade"]),
        "grade": trust["grade"],
        "is_speculative": trust.get("is_speculative", False),
        "data_quality": trust.get("data_quality", "full"),
        "data_source": trust.get("data_source"),
        "verification": trust.get("verification"),
        "wl_group": wl_group,
        "signal": signal,
        "added_at": item.get("added_at"),
        "market": item.get("market", "US"),
        # Analyst data for display
        "analyst_target": target_price,
        "analyst_upside_pct": upside_pct,
        "analyst_upside_str": upside_str,
        "analyst_entry": entry_str,
        "analyst_buy": trust.get("analyst_buy", 0),
        "analyst_hold": trust.get("analyst_hold", 0),
        "analyst_sell": trust.get("analyst_sell", 0),
        "business_score": trust.get("business_score", 0),
        "smart_money_score": trust.get("smart_money_score", 0),
        "momentum_score": trust.get("momentum_score", 0),
        "situation_label": trust.get("situation_label"),
        "situation_note": trust.get("situation_note"),
        # FMP profile enrichment for Data Unavailable stocks
        "fmp_profile": _extract_fmp_profile(fundamentals)
            if trust.get("data_quality") == "unavailable" else None,
    }


def get_watchlist_with_signals() -> list:
    """Watchlist items with trust scores — fetched in parallel."""
    items = get_watchlist()
    if not items:
        return []

    workers = min(20, len(items))
    result = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_build_watchlist_item, item) for item in items]
        for future in as_completed(futures):
            try:
                result.append(future.result())
            except Exception:
                pass

    return result
