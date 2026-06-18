"""Recovery Resilience scorer.

Measures how well a stock historically recovers from drawdowns.
Uses 1-year price history (~52 weekly datapoints from get_stock_history).

Score: 0-100  Label: RESILIENT / NORMAL / VULNERABLE / FRAGILE
"""
from __future__ import annotations
import math
from typing import Optional


def _find_drawdowns(prices: list[float], threshold: float = 0.10) -> list[dict]:
    """Identify drawdown episodes > threshold in a price series.

    Returns list of {peak_idx, trough_idx, recovery_idx, depth_pct, recovered_to_new_high}.
    recovery_idx is None if the price never recovered by end of series.
    """
    if len(prices) < 5:
        return []

    drawdowns = []
    i = 0
    n = len(prices)

    while i < n - 2:
        peak_idx = i
        peak_val = prices[i]
        # Find local trough after peak
        trough_idx = i
        trough_val = prices[i]
        j = i + 1
        while j < n:
            if prices[j] < trough_val:
                trough_val = prices[j]
                trough_idx = j
            elif prices[j] > trough_val * 1.05:
                # Started recovering — stop looking for lower troughs
                break
            j += 1

        depth = (trough_val - peak_val) / peak_val  # negative number
        if depth < -threshold and trough_idx > peak_idx:
            # Valid drawdown found — find recovery point
            recovery_idx = None
            recovered_to_new_high = False
            new_high_after = peak_val
            for k in range(trough_idx + 1, n):
                if prices[k] >= peak_val:
                    recovery_idx = k
                    # Check if it ever exceeded pre-drop high
                    if prices[k] > new_high_after:
                        recovered_to_new_high = True
                        new_high_after = prices[k]
                    break

            drawdowns.append({
                "peak_idx": peak_idx,
                "trough_idx": trough_idx,
                "recovery_idx": recovery_idx,
                "depth_pct": depth * 100,          # e.g. -25.3
                "recovered_to_new_high": recovered_to_new_high,
            })
            # Skip past the trough so we don't double-count
            i = trough_idx + 1
        else:
            i += 1

    return drawdowns


def compute_recovery_resilience(
    ticker: str,
    price_history_obj: dict,
    fundamentals: dict,
    insider: dict,
) -> dict:
    """Compute a recovery resilience score (0-100) for a stock.

    Parameters
    ----------
    ticker : str
    price_history_obj : dict  returned by get_stock_history()
        keys: "prices" (list of {date, price}), "1W", "1M", "3M", "6M", "1Y"
    fundamentals : dict  returned by get_fundamentals()
    insider : dict  returned by get_insider_data()

    Returns
    -------
    dict with keys: score, label, components, translation
    """
    insufficient = {
        "score": None,
        "label": "Insufficient history",
        "components": {},
        "translation": "Not enough price history to assess how this stock handles pullbacks.",
    }

    raw_prices = price_history_obj.get("prices", [])
    prices = [p["price"] for p in raw_prices if p.get("price") is not None]

    if len(prices) < 26:   # < 6 months of weekly data
        return insufficient

    # ── 1. Recovery Speed (30%) ───────────────────────────────────────────────
    drawdowns = _find_drawdowns(prices, threshold=0.10)
    if drawdowns:
        recovery_weeks_list = [
            d["recovery_idx"] - d["trough_idx"]
            for d in drawdowns
            if d["recovery_idx"] is not None
        ]
        if recovery_weeks_list:
            median_weeks = sorted(recovery_weeks_list)[len(recovery_weeks_list) // 2]
        else:
            median_weeks = None   # never recovered from any drawdown
    else:
        median_weeks = None   # no significant drawdowns = very resilient

    if drawdowns and median_weeks is None:
        rs_score = 10   # had drawdowns, never recovered
    elif median_weeks is None:
        rs_score = 90   # no meaningful drawdowns at all
    elif median_weeks < 4:
        rs_score = 90
    elif median_weeks < 12:
        rs_score = 70
    elif median_weeks < 26:
        rs_score = 50
    else:
        rs_score = 30

    # ── 2. Drawdown Depth (15%) ───────────────────────────────────────────────
    if drawdowns:
        worst_dd = min(d["depth_pct"] for d in drawdowns)   # most negative
    else:
        worst_dd = 0.0

    if worst_dd > -15:
        dd_score = 90
    elif worst_dd > -30:
        dd_score = 70
    elif worst_dd > -50:
        dd_score = 50
    else:
        dd_score = 20

    # ── 3. Bounce Pattern Quality (15%) ──────────────────────────────────────
    if drawdowns:
        recovered = [d for d in drawdowns if d["recovery_idx"] is not None]
        recovered_to_new_high = [d for d in recovered if d["recovered_to_new_high"]]
        new_high_pct = (len(recovered_to_new_high) / len(drawdowns)) * 100
    else:
        new_high_pct = None

    if new_high_pct is None:
        bp_score = 60   # neutral: no drawdowns found
    elif new_high_pct >= 80:
        bp_score = 90
    elif new_high_pct >= 60:
        bp_score = 70
    elif new_high_pct >= 40:
        bp_score = 50
    else:
        bp_score = 30

    # ── 4. Trend Resilience (15%) ─────────────────────────────────────────────
    ma_200d = fundamentals.get("ma_200d") or fundamentals.get("ma200")
    if ma_200d and ma_200d > 0:
        above_count = sum(1 for p in prices if p > ma_200d)
        above_pct = above_count / len(prices) * 100
    else:
        # Estimate MA200 from the price series itself (use trailing mean as proxy)
        window = min(len(prices), 20)   # ~20 weeks ≈ 5 months as proxy
        running_above = 0
        for k in range(len(prices)):
            start = max(0, k - window)
            avg = sum(prices[start:k + 1]) / (k - start + 1)
            if prices[k] > avg:
                running_above += 1
        above_pct = running_above / len(prices) * 100
        ma_200d = None

    if above_pct >= 80:
        tr_score = 90
    elif above_pct >= 60:
        tr_score = 70
    elif above_pct >= 40:
        tr_score = 50
    else:
        tr_score = 30

    # ── 5. Structural Support (15%) ──────────────────────────────────────────
    inst_buying = fundamentals.get("institutional_buying") or \
                  (insider.get("institutional_ownership_pct", 0) or 0) > 30
    fcf = fundamentals.get("free_cashflow") or \
          fundamentals.get("operating_cashflow") or 0
    fcf_positive = fcf > 0
    de = fundamentals.get("debt_to_equity") or 999
    low_debt = de < 2.0
    mkt_cap = fundamentals.get("market_cap") or 0
    large_cap = mkt_cap >= 5e9

    ss_score = (
        (25 if inst_buying else 0) +
        (25 if fcf_positive else 0) +
        (25 if low_debt else 0) +
        (25 if large_cap else 0)
    )

    # ── 6. Selling Pressure Risk (10%) ───────────────────────────────────────
    short_pct = insider.get("short_interest_pct") or \
                insider.get("short_percent_of_float") or \
                fundamentals.get("short_interest_pct") or 0
    if isinstance(short_pct, (int, float)):
        short_pct = float(short_pct)
    else:
        short_pct = 0.0

    # short_pct might come as fraction (0.28) or percentage (28) — normalise
    if short_pct > 1.0:
        short_pct = short_pct   # already in %
    else:
        short_pct = short_pct * 100   # convert fraction → %

    if short_pct <= 3:
        sp_score = 90
    elif short_pct <= 8:
        sp_score = 70
    elif short_pct <= 15:
        sp_score = 50
    elif short_pct <= 25:
        sp_score = 30
    else:
        sp_score = 10

    # ── Weighted total ────────────────────────────────────────────────────────
    total = (
        rs_score * 0.30 +
        dd_score * 0.15 +
        bp_score * 0.15 +
        tr_score * 0.15 +
        ss_score * 0.15 +
        sp_score * 0.10
    )
    score = round(total)

    if score >= 85:
        label = "RESILIENT"
    elif score >= 65:
        label = "NORMAL"
    elif score >= 45:
        label = "VULNERABLE"
    else:
        label = "FRAGILE"

    # ── Plain English translation ─────────────────────────────────────────────
    if label == "RESILIENT":
        translation = "Historically bounces back quickly from pullbacks. Strong structural support."
    elif label == "NORMAL":
        translation = "Handles pullbacks reasonably well. Some recovery delays but generally recovers."
    elif label == "VULNERABLE":
        translation = "Takes a while to recover from dips. May need patience after a pullback."
    else:
        translation = "Historically slow to recover from drawdowns. Higher risk in volatile markets."

    return {
        "score": score,
        "label": label,
        "components": {
            "recovery_speed_score": rs_score,
            "drawdown_depth_score": dd_score,
            "bounce_pattern_score": bp_score,
            "trend_resilience_score": tr_score,
            "structural_support_score": ss_score,
            "selling_pressure_score": sp_score,
            "median_recovery_weeks": median_weeks,
            "worst_drawdown_pct": round(worst_dd, 1) if worst_dd else 0.0,
            "drawdowns_recovered_to_new_high_pct": round(new_high_pct, 0) if new_high_pct is not None else None,
            "above_ma200_pct": round(above_pct, 0),
            "institutional_support": bool(inst_buying),
            "fcf_positive": bool(fcf_positive),
            "short_interest_pct": round(short_pct, 1),
        },
        "translation": translation,
    }
