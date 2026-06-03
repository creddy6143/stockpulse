"""Portfolio P&L and positions management — all values in native currency + SEK."""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from database import db as _db
from database.db import get_portfolio, get_watchlist
from data.fetcher import get_stock_price, get_exchange_rates, get_historical_sek_rate, get_analyst_data, get_fundamentals, get_fmp_profile
from intelligence.trust_score import get_trust_score_with_fallback
from intelligence.verification import verify_watchlist_signal
from portfolio.entry_zone import compute_entry_zone
from portfolio.classification import classify_with_hysteresis


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


def _build_position(pos: dict, rates: dict, user_id: str = "OWNER") -> dict:
    """Fetch live data + trust for a single position. Runs in thread pool."""
    ticker = pos["ticker"]
    price_data = get_stock_price(ticker)
    trust = get_trust_score_with_fallback(ticker, price_data)

    price = price_data.get("price") or pos["buy_price"]

    # Currency priority: live price API (always accurate) > ticker suffix > DB stored value.
    # The DB value can be stale or wrong from old code paths — never trust it over live data.
    _known = {"USD", "EUR", "GBP", "INR", "SEK"}
    _price_ccy = (price_data.get("currency") or "").upper()
    if _price_ccy in _known:
        currency = _price_ccy
    else:
        _detected = _detect_currency(ticker)
        currency = _detected if _detected != "USD" else (pos.get("currency") or "USD")

    rate = _sek_rate(currency, rates)

    shares    = pos["shares"]
    buy_price = pos["buy_price"]
    buy_date  = pos.get("buy_date")

    # Native-currency P&L (stock performance, currency-neutral)
    pnl     = (price - buy_price) * shares
    pnl_pct = ((price - buy_price) / buy_price * 100) if buy_price else 0

    # SEK P&L — use historical rate on buy date when available.
    # If no buy_date (or fetch fails), fall back to current rate on both sides
    # (old behaviour, shows stock gain only, hides currency drift).
    value_sek = price * shares * rate
    hist_rate = get_historical_sek_rate(buy_date, currency) if buy_date else None
    if hist_rate:
        invested_sek = buy_price * shares * hist_rate
        buy_rate_sek = hist_rate          # historical rate — shows depreciation
    else:
        invested_sek = buy_price * shares * rate
        buy_rate_sek = rate               # no buy_date → treat as bought at today's rate
    pnl_sek = value_sek - invested_sek

    group = classify_with_hysteresis(ticker, user_id, trust)

    return {
        "id": pos["id"],
        "ticker": ticker,
        "name": pos.get("name") or price_data.get("name", ticker),
        "shares": shares,
        "buy_price": buy_price,
        "buy_date": pos.get("buy_date"),
        "current_price": round(float(price), 4),
        "change_pct": round(float(price_data.get("change_pct", 0)), 2),
        "pnl": round(float(pnl), 2),
        "pnl_pct": round(float(pnl_pct), 2),
        "value_sek": round(value_sek, 0),
        "invested_sek": round(invested_sek, 0),
        "pnl_sek": round(pnl_sek, 0),
        "sek_rate": rate,
        "buy_rate_sek": buy_rate_sek,   # historical rate on buy date (None if no date)
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


def _build_position_group(lots: list, rates: dict, user_id: str = "OWNER") -> dict:
    """Accept all DB rows for one ticker; return a single aggregated position dict.
    For a single lot it is identical to _build_position but adds a `lots` key.
    For multiple lots it recalculates all financial fields using per-lot historical rates.
    """
    # Fetch price + trust once (same ticker for all lots)
    base = _build_position(lots[0], rates, user_id=user_id)

    if len(lots) == 1:
        base["lots"] = [{
            "id":           lots[0]["id"],
            "shares":       lots[0]["shares"],
            "buy_price":    lots[0]["buy_price"],
            "buy_date":     lots[0].get("buy_date"),
            "buy_rate_sek": base.get("buy_rate_sek"),
            "invested_sek": base.get("invested_sek", 0),
            "value_sek":    base.get("value_sek", 0),
            "pnl_sek":      base.get("pnl_sek", 0),
        }]
        return base

    # Multi-lot: recalculate aggregated financials
    currency = base["currency"]
    rate     = base["sek_rate"]   # today's SEK rate (already in base)
    price    = base["current_price"]

    total_shares       = 0.0
    total_value_sek    = 0.0
    total_invested_sek = 0.0
    total_pnl_native   = 0.0
    weighted_buy_numer = 0.0
    lot_details        = []

    for lot in lots:
        sh = lot["shares"]
        bp = lot["buy_price"]
        bd = lot.get("buy_date")
        hist = get_historical_sek_rate(bd, currency) if bd else None
        lot_rate = hist if hist else rate

        lot_val      = price * sh * rate
        lot_invested = bp * sh * lot_rate
        lot_pnl_sek  = lot_val - lot_invested

        total_shares       += sh
        total_value_sek    += lot_val
        total_invested_sek += lot_invested
        total_pnl_native   += (price - bp) * sh
        weighted_buy_numer += bp * sh

        lot_details.append({
            "id":           lot["id"],
            "shares":       sh,
            "buy_price":    bp,
            "buy_date":     bd,
            "buy_rate_sek": round(lot_rate, 6),
            "invested_sek": round(lot_invested, 0),
            "value_sek":    round(lot_val, 0),
            "pnl_sek":      round(lot_pnl_sek, 0),
        })

    wavg_buy  = weighted_buy_numer / total_shares if total_shares else 0
    pnl_pct   = ((price - wavg_buy) / wavg_buy * 100) if wavg_buy else 0
    total_pnl_sek = total_value_sek - total_invested_sek
    wavg_rate = (total_invested_sek / (wavg_buy * total_shares)
                 if wavg_buy * total_shares > 0 else rate)

    # Re-classify using the hysteresis-aware classifier (same trust dict as base)
    trust_dict = {
        "total_score":       base["trust_score"],
        "display_score":     base["display_score"],
        "auto_disqualified": base["auto_disqualified"],
        "grade":             base["grade"],
        "business_score":    base.get("business_score"),
        "smart_money_score": base.get("smart_money_score"),
        "data_quality":      base.get("data_quality", "full"),
    }
    ticker = lots[0]["ticker"]
    base["group"] = classify_with_hysteresis(ticker, user_id, trust_dict)

    base.update({
        "shares":       total_shares,
        "buy_price":    round(wavg_buy, 4),
        "pnl":          round(total_pnl_native, 2),
        "pnl_pct":      round(pnl_pct, 2),
        "value_sek":    round(total_value_sek, 0),
        "invested_sek": round(total_invested_sek, 0),
        "pnl_sek":      round(total_pnl_sek, 0),
        "buy_rate_sek": round(wavg_rate, 6),
        "lots":         lot_details,
    })
    return base


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


def get_portfolio_with_pnl(user_id=None) -> dict:
    """All positions with live P&L — prices + trust fetched in parallel."""
    positions = get_portfolio(user_id)
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

    # Group DB rows by ticker so multi-lot positions are aggregated
    ticker_lots: dict = defaultdict(list)
    for pos in positions:
        ticker_lots[pos["ticker"]].append(pos)

    grouped = list(ticker_lots.values())
    workers = min(20, len(grouped))
    result = []
    _uid = user_id or "OWNER"
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_build_position_group, lots, rates, _uid): lots
                   for lots in grouped}
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

    # ── Entry zone: narrow, evidence-backed band from multiple signals ─────────
    # Uses MA50/MA200, Fibonacci from 52W range, analyst target_low/high.
    # Max width 12% of current price. Returns status label for signal badge.
    zone = compute_entry_zone(ticker, price, fundamentals, analyst)
    entry_str      = zone["zone_str"]
    zone_status    = zone["zone_status"]
    zone_status_lbl = zone["zone_status_label"]
    pct_to_zone    = zone["pct_to_zone"]
    zone_bot_sigs  = zone["zone_bottom_signals"]
    zone_top_sigs  = zone["zone_top_signals"]
    zone_reason    = zone["zone_reason"]

    # ── Signal and wl_group ──────────────────────────────────────────────────
    # signal is the zone status label (tells user EXACTLY where price stands vs zone)
    # wl_group drives Ready / Waiting / Avoid categories:
    #   ready   — price IS in the entry zone + trust ≥ 75 (Strong grade) + not blocked
    #   avoid   — auto-disqualified OR trust < 30 (distressed)
    #   watching — everything else (above zone, near zone, no zone, trust 30-74)
    # Threshold ≥ 75 matches _detect_wl_situation UI text and verify_watchlist_signal
    # backstop — all three must agree to prevent contradictory labels.
    score = trust["total_score"]
    signal = zone_status_lbl

    if trust["auto_disqualified"] or (score is not None and score < 30):
        wl_group = "avoid"
        # Override signal to make urgency clear
        if trust["auto_disqualified"]:
            signal = "Not suitable — " + (trust.get("disqualify_reason") or "disqualified")[:40]
        else:
            signal = "Weak fundamentals — not yet"
    elif zone_status == "in_zone" and score is not None and score >= 75:
        wl_group = "ready"
        # Signal already set to "✓ In entry zone now" from zone calculation
    else:
        wl_group = "watching"
        # Signal already set from zone calculation (e.g. "Above zone — wait for X%")

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
        # Zone diagnostic — enables evidence display in expanded watchlist row
        "zone_status": zone_status,
        "zone_pct_to_entry": pct_to_zone,
        "zone_bottom_signals": zone_bot_sigs,
        "zone_top_signals": zone_top_sigs,
        "zone_reason": zone_reason,
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


def get_watchlist_with_signals(user_id=None) -> list:
    """Watchlist items with trust scores — fetched in parallel."""
    items = get_watchlist(user_id)
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
