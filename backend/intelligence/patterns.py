"""8 core pattern detectors."""
import yfinance as yf
from data.fetcher import get_fundamentals, get_insider_data
from data.cache import cache_get, cache_set


def _get_price_history(ticker: str, period: str = "3mo") -> list:
    key = f"hist:{ticker}:{period}"
    cached = cache_get(key)
    if cached:
        return cached
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)
        result = [
            {"date": str(idx.date()), "close": float(row["Close"]),
             "volume": int(row["Volume"]), "open": float(row["Open"])}
            for idx, row in hist.iterrows()
        ]
        cache_set(key, result)
        return result
    except Exception:
        return []


def _avg_volume(history: list, days: int = 30) -> float:
    vols = [h["volume"] for h in history[-days:] if h["volume"] > 0]
    return sum(vols) / len(vols) if vols else 1


def detect_all_patterns(ticker: str, trust_score: int, price_data: dict,
                         fundamentals: dict = None, insider: dict = None) -> list:
    """Returns list of detected patterns with confidence and plain_english."""
    if fundamentals is None:
        fundamentals = get_fundamentals(ticker)
    if insider is None:
        insider = get_insider_data(ticker)

    history = _get_price_history(ticker)
    if not history:
        return []

    detected = []
    price = price_data.get("price", 0)
    change_pct = price_data.get("change_pct", 0)
    volume = price_data.get("volume", 0)
    avg_vol = _avg_volume(history)

    # ── 1. SHORT SQUEEZE ─────────────────────────────────────────────────────
    short_pct = insider.get("short_interest_pct", 0)
    surprise = fundamentals.get("earnings_surprise_pct", 0) or 0
    if short_pct > 20 and surprise > 50 and volume > 3 * avg_vol:
        detected.append({
            "pattern": "squeeze",
            "name": "Short Squeeze",
            "confidence": 0.71,
            "stop_loss_pct": 0.25,
            "time_horizon_days": 5,
            "recommendation": "buy",
            "plain_english": "Investors who bet against this stock are being forced to buy back — pushing the price up fast.",
        })

    # ── 2. GAP AND GO ─────────────────────────────────────────────────────────
    if change_pct > 8 and volume > 2 * avg_vol:
        detected.append({
            "pattern": "gap_and_go",
            "name": "Strong Momentum",
            "confidence": 0.68,
            "stop_loss_pct": 0.20,
            "time_horizon_days": 7,
            "recommendation": "buy",
            "plain_english": "Price jumped on real news and is continuing to rise with strong interest.",
        })

    # ── 3. DEAD CAT ──────────────────────────────────────────────────────────
    if len(history) >= 30:
        lo_30 = min(h["close"] for h in history[-30:])
        hi_3 = max(h["close"] for h in history[-3:])
        drop_30d = (lo_30 - history[-30]["close"]) / history[-30]["close"] if history[-30]["close"] else 0
        bounce = (hi_3 - lo_30) / lo_30 if lo_30 else 0
        rev_growth = fundamentals.get("revenue_growth", 0) or 0
        if trust_score < 40 and drop_30d < -0.30 and bounce > 0.10 and rev_growth < 0:
            detected.append({
                "pattern": "dead_cat",
                "name": "False Recovery",
                "confidence": 0.76,
                "stop_loss_pct": 0.15,
                "time_horizon_days": 14,
                "recommendation": "sell",
                "plain_english": "This looks like a recovery but the underlying problems have not been fixed. Likely to keep falling.",
            })

    # ── 4. KITCHEN SINK ──────────────────────────────────────────────────────
    profit = fundamentals.get("profit_margins", 0) or 0
    surprise_neg = surprise < -30
    if surprise_neg and profit > -0.30 and not insider.get("ceo_leaving", False):
        detected.append({
            "pattern": "kitchen_sink",
            "name": "Deliberate Reset",
            "confidence": 0.69,
            "stop_loss_pct": 0.20,
            "time_horizon_days": 90,
            "recommendation": "hold",
            "plain_english": "Management may have deliberately reported a bad quarter to reset expectations. Recovery often follows.",
        })

    # ── 5. ATH LAUNCHPAD ─────────────────────────────────────────────────────
    if len(history) >= 252:
        ath = max(h["close"] for h in history)
        if price >= ath * 0.99 and trust_score > 70 and volume > 1.5 * avg_vol:
            detected.append({
                "pattern": "ath_launchpad",
                "name": "All-Time High Breakout",
                "confidence": 0.67,
                "stop_loss_pct": 0.15,
                "time_horizon_days": 30,
                "recommendation": "buy",
                "plain_english": "Stock hit an all-time high with strong backing. Quality stocks often keep rising from here.",
            })

    # ── 6. FALLING KNIFE ────────────────────────────────────────────────────
    if len(history) >= 5:
        drop_5d = (price - history[-5]["close"]) / history[-5]["close"] if history[-5]["close"] else 0
        down_days = sum(1 for h in history[-5:] if h["close"] < h["open"])
        if drop_5d < -0.15 and down_days >= 3 and trust_score < 50:
            detected.append({
                "pattern": "falling_knife",
                "name": "Avoid — Still Falling",
                "confidence": 0.73,
                "stop_loss_pct": 0.10,
                "time_horizon_days": 14,
                "recommendation": "sell",
                "plain_english": "Stock is in a strong downtrend. Buying now is like catching a falling knife — likely to keep dropping.",
            })

    # ── 7. SANDBAGGING ──────────────────────────────────────────────────────
    history_eps = fundamentals.get("earnings_history", [])
    if len(history_eps) >= 4:
        beats = sum(1 for e in history_eps if (e.get("actual") or 0) > (e.get("estimate") or 0))
        avg_beat = 0
        beat_mags = []
        for e in history_eps:
            est = e.get("estimate") or 0
            act = e.get("actual") or 0
            if est and est != 0:
                beat_mags.append((act - est) / abs(est))
        if beat_mags:
            avg_beat = sum(beat_mags) / len(beat_mags)
        if beats >= 6 and avg_beat > 0.08:
            detected.append({
                "pattern": "sandbagging",
                "name": "Consistent Beater",
                "confidence": 0.71,
                "stop_loss_pct": 0.15,
                "time_horizon_days": 30,
                "recommendation": "buy",
                "plain_english": "This company consistently beats its own expectations. Upcoming results likely better than forecast.",
            })

    # ── 8. CAPITULATION ─────────────────────────────────────────────────────
    if len(history) >= 30:
        drop_30 = (price - history[-30]["close"]) / history[-30]["close"] if history[-30]["close"] else 0
        if drop_30 < -0.30 and volume > 3 * avg_vol and trust_score > 60:
            detected.append({
                "pattern": "capitulation",
                "name": "Potential Bottom",
                "confidence": 0.68,
                "stop_loss_pct": 0.15,
                "time_horizon_days": 60,
                "recommendation": "buy",
                "plain_english": "Panic selling may be overdone on a quality stock. Historically these moments have been good entry points.",
            })

    return detected
