"""
Entry Zone Calculator
=====================
Computes a narrow, meaningful entry zone for watchlist stocks.

An entry zone is the price band where multiple technical support and value
signals converge — the price range where a stock becomes a high-probability buy.

ARCHITECTURE
────────────
The zone is expressed as a band BELOW the current price:

  zone_high (ceiling) — where you start buying on a pullback:
    1. 50-day moving average (MA50)          — near-term support
    2. Fibonacci 38.2% of 52W range          — shallow retracement
    3. Lower analyst consensus (25th pct)    — value anchor

  zone_low (floor) — deeper support / where you'd add:
    1. 200-day moving average (MA200)        — institutional benchmark
    2. Fibonacci 61.8% of 52W range          — golden ratio retracement
    3. Lowest analyst target                 — most conservative estimate
    4. Fibonacci 50% of 52W range            — mid retracement (fallback)

CONSTRAINTS
───────────
  • Max width: 12% of current price
  • Both zone boundaries must be ≤ current price (we're buying dips)
  • At least one identified signal per boundary
  • If signals don't converge into a narrow zone → "No clear zone"

STATUS
──────
  in_zone:    price ≤ zone_high AND price ≥ zone_low
  near_zone:  price ≤ zone_high × 1.03 (within 3% above ceiling)
  above_zone: price > zone_high × 1.03
  below_zone: price < zone_low (dropped through support)
  no_zone:    insufficient data or signals diverge too much
"""
from __future__ import annotations


def _fmt(v: float) -> str:
    """Format a price value: ≥100 → integer, ≥10 → 1dp, <10 → 2dp."""
    if v >= 100:
        return str(int(round(v)))
    if v >= 10:
        return f"{v:.1f}"
    return f"{v:.2f}"


def _pos(v) -> float | None:
    """Return positive float or None."""
    try:
        f = float(v or 0)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def _no_zone(reason: str) -> dict:
    return {
        "zone_low": None,
        "zone_high": None,
        "zone_str": "No clear zone — wait for setup",
        "zone_width_pct": None,
        "zone_status": "no_zone",
        "zone_status_label": "No clear entry zone — wait for setup",
        "pct_to_zone": None,
        "zone_bottom_signals": [],
        "zone_top_signals": [],
        "zone_reason": reason,
    }


def compute_entry_zone(
    ticker: str,
    price: float,
    fundamentals: dict,
    analyst: dict,
) -> dict:
    """
    Compute a narrow, evidence-backed entry zone.

    Parameters
    ----------
    ticker       : stock ticker (for logging only)
    price        : current price
    fundamentals : dict from get_fundamentals() — needs ma_200d, ma_50d,
                   w52_high, w52_low
    analyst      : dict from get_analyst_data() — needs target_price,
                   target_low, target_high

    Returns
    -------
    dict with:
        zone_low, zone_high           : float prices (None if no zone)
        zone_str                      : "810–845" or "No clear zone"
        zone_width_pct                : % of current price
        zone_status                   : "in_zone"|"near_zone"|"above_zone"|
                                        "below_zone"|"no_zone"
        zone_status_label             : human-readable label
        pct_to_zone                   : % from price to zone edge
        zone_bottom_signals           : [{"name","value","note"}, ...]
        zone_top_signals              : [{"name","value","note"}, ...]
        zone_reason                   : plain English explanation
    """
    if not price or price <= 0:
        return _no_zone("No price data available")

    # ── Extract data ──────────────────────────────────────────────────────────
    ma200     = _pos(fundamentals.get("ma_200d"))
    ma50      = _pos(fundamentals.get("ma_50d"))
    w52h      = _pos(fundamentals.get("w52_high"))
    w52l      = _pos(fundamentals.get("w52_low"))
    tgt_low   = _pos(analyst.get("target_low"))
    tgt_high  = _pos(analyst.get("target_high"))
    tgt_mean  = _pos(analyst.get("target_price"))

    # Fibonacci levels derived from 52-week range
    fib_382 = fib_500 = fib_618 = None
    if w52h and w52l and w52h > w52l * 1.02:       # need at least 2% range
        swing   = w52h - w52l
        fib_382 = w52h - 0.382 * swing             # shallow retracement
        fib_500 = w52h - 0.500 * swing             # mid
        fib_618 = w52h - 0.618 * swing             # deep (golden ratio)

    # Ceiling candidates: accept signals up to 15% above price (handles "in-zone" case
    # where price sits between MA50 and MA200).  Strictly-below signals are preferred.
    # Floor candidates: must be strictly below price.
    def valid_ceil(v):
        return v is not None and v > 0 and v <= price * 1.15

    def below(v):
        return v is not None and v > 0 and v < price * 0.999

    # ── CEILING candidates (zone_high) ────────────────────────────────────────
    # The upper boundary of the entry zone.
    # Accepts levels within 15% above price so that MA50 is still captured when
    # the stock has already pulled back below it (= stock is IN the zone).
    # Use the HIGHEST valid candidate.
    ceil_cands: list[tuple[float, str, str]] = []

    if valid_ceil(ma50):
        ceil_cands.append((ma50, "50-day moving average", "Near-term trend support"))

    if valid_ceil(fib_382):
        ceil_cands.append((fib_382, "Fibonacci 38.2% retracement", "Shallow pullback from 52W range"))

    if valid_ceil(fib_500) and (not ma50 or fib_500 < ma50 * 0.99):
        ceil_cands.append((fib_500, "Fibonacci 50% retracement", "Mid-range pullback support"))

    if tgt_mean and valid_ceil(tgt_mean) and tgt_mean < price * 1.10:
        # Approximate 25th-percentile analyst target
        if tgt_low and tgt_low > 0:
            t25 = (tgt_mean + tgt_low) / 2 * 0.97
        else:
            t25 = tgt_mean * 0.90
        if valid_ceil(t25) and t25 > 0:
            ceil_cands.append((t25, "Lower analyst consensus", "25th-percentile analyst target"))

    # ── FLOOR candidates (zone_low) ───────────────────────────────────────────
    # The lower boundary: deeper support where you'd add on a further drop.
    # Use the HIGHEST signal strictly below the chosen ceiling.
    floor_cands: list[tuple[float, str, str]] = []

    if below(ma200):
        floor_cands.append((ma200, "200-day moving average", "Long-term institutional support"))

    if below(fib_618):
        floor_cands.append((fib_618, "Fibonacci 61.8% retracement", "Deep pullback — golden ratio support"))

    if below(fib_500) and not any(abs(v - fib_500) / price < 0.005 for v, _, _ in ceil_cands):
        floor_cands.append((fib_500, "Fibonacci 50% retracement", "Mid-range pullback support"))

    if tgt_low and below(tgt_low) and tgt_low < price * 0.93:
        floor_cands.append((tgt_low, "Lowest analyst target", "Most conservative analyst fair value"))

    # Sort descending (highest first — closest to current price)
    ceil_cands.sort(key=lambda x: x[0], reverse=True)
    floor_cands.sort(key=lambda x: x[0], reverse=True)

    # ── Need at least ONE ceiling candidate ───────────────────────────────────
    if not ceil_cands:
        if below(ma200):
            # Only MA200 available — 5% band around it
            z_hi = min(ma200 * 1.025, price * 0.999)
            z_lo = ma200 * 0.975
            return _build_result(ticker, price, z_hi, z_lo,
                                 [{"name": "Near 200-day MA", "value": round(z_hi, 2),
                                   "note": "Long-term MA resistance band"}],
                                 [{"name": "Below 200-day MA", "value": round(z_lo, 2),
                                   "note": "Long-term support floor"}])
        return _no_zone("No technical levels below current price — stock may be near support or data unavailable")

    # ── Select ceiling: use best (highest) candidate ───────────────────────────
    zone_high, ch_lbl, ch_note = ceil_cands[0]

    # ── Select floor: best candidate strictly below ceiling ───────────────────
    valid_floors = [(v, l, n) for v, l, n in floor_cands if v < zone_high * 0.995]

    if valid_floors:
        zone_low, fl_lbl, fl_note = valid_floors[0]
    elif len(ceil_cands) > 1:
        # Second-best ceiling becomes the floor
        zone_low, fl_lbl, fl_note = ceil_cands[-1]
    elif ma200 and below(ma200) and ma200 < zone_high:
        zone_low, fl_lbl, fl_note = ma200, "200-day moving average", "Long-term institutional support"
    else:
        # Synthesised floor: 7% below ceiling (last resort)
        zone_low  = zone_high * 0.93
        fl_lbl    = "Support estimate"
        fl_note   = "Estimated floor — 7% below zone ceiling"

    top_sigs = [{"name": ch_lbl, "value": round(zone_high, 2), "note": ch_note}]
    bot_sigs = [{"name": fl_lbl, "value": round(zone_low, 2),  "note": fl_note}]

    # ── Width constraint: max 12% of current price ────────────────────────────
    max_w = price * 0.12
    width = zone_high - zone_low

    if width > max_w:
        # Preferred fix: use MA50 + MA200 (most reliable technical pair)
        if ma50 and ma200 and 0 < ma200 < ma50 < price:
            ma_w = ma50 - ma200
            if ma_w <= max_w:
                zone_high = ma50;  ch_lbl = "50-day moving average";  ch_note = "Near-term trend support"
                zone_low  = ma200; fl_lbl = "200-day moving average"; fl_note = "Long-term institutional support"
                top_sigs  = [{"name": ch_lbl, "value": round(zone_high, 2), "note": ch_note}]
                bot_sigs  = [{"name": fl_lbl, "value": round(zone_low, 2),  "note": fl_note}]
                width     = ma_w
            else:
                # MAs too far apart — report no zone
                return _no_zone(
                    f"MA50 ({_fmt(ma50)}) and MA200 ({_fmt(ma200)}) are more than 12% apart — "
                    "market in a wide transition range, wait for signals to tighten"
                )
        elif ma50 and below(ma50):
            # Only MA50 — fixed 8% band below it
            zone_high = ma50
            zone_low  = ma50 * 0.92
            top_sigs  = [{"name": "50-day moving average", "value": round(zone_high, 2), "note": "Near-term trend ceiling"}]
            bot_sigs  = [{"name": "8% below 50-day MA",   "value": round(zone_low, 2),  "note": "Estimated support floor"}]
            width     = zone_high - zone_low
        elif ma200 and below(ma200):
            # Only MA200 — 5% band
            zone_high = ma200 * 1.025
            zone_low  = ma200 * 0.975
            zone_high = min(zone_high, price * 0.999)
            top_sigs  = [{"name": "Near 200-day MA", "value": round(zone_high, 2), "note": "Long-term MA resistance band"}]
            bot_sigs  = [{"name": "Below 200-day MA", "value": round(zone_low, 2),  "note": "Long-term support floor"}]
            width     = zone_high - zone_low
        else:
            return _no_zone("Signals diverge more than 12% — no narrow entry zone identifiable")

    # ── Final validity check ──────────────────────────────────────────────────
    if zone_low <= 0 or zone_high <= 0 or zone_low >= zone_high:
        return _no_zone("Zone calculation produced invalid range — contact support")

    return _build_result(ticker, price, zone_high, zone_low, top_sigs, bot_sigs)


def _build_result(
    ticker: str,
    price: float,
    zone_high: float,
    zone_low: float,
    top_sigs: list[dict],
    bot_sigs: list[dict],
) -> dict:
    """Compute status and assemble the result dict from validated zone boundaries."""
    width_pct = (zone_high - zone_low) / price * 100
    zone_str  = f"{_fmt(zone_low)}–{_fmt(zone_high)}"

    # ── Status ────────────────────────────────────────────────────────────────
    if price < zone_low:
        pct    = (zone_low - price) / price * 100
        status = "below_zone"
        label  = f"Below zone — {pct:.1f}% below entry, reassess thesis"
        reason = (
            f"Price has fallen {pct:.1f}% below the expected entry zone ({zone_str}). "
            f"The stock dropped through its key support levels. Reassess whether the "
            f"original thesis still holds before adding to this position."
        )
    elif price <= zone_high:
        pct    = 0.0
        status = "in_zone"
        label  = "✓ In entry zone now"
        reason = (
            f"Price has pulled back into the entry zone ({zone_str}). "
            f"Multiple technical support signals converge here — "
            f"this is where the risk/reward ratio becomes most favourable."
        )
    elif price <= zone_high * 1.03:
        pct    = (price - zone_high) / price * 100
        status = "near_zone"
        label  = f"Near zone — {pct:.1f}% to enter"
        reason = (
            f"Price is only {pct:.1f}% above the entry zone ({zone_str}). "
            f"A small pullback puts it squarely in buy territory. Watch closely — "
            f"this is close to becoming an entry signal."
        )
    else:
        pct    = (price - zone_high) / price * 100
        status = "above_zone"
        label  = f"Above zone — wait for {pct:.1f}% pullback to {_fmt(zone_high)}"
        reason = (
            f"Stock is {pct:.1f}% above its entry zone ({zone_str}). "
            f"No urgency — let it come to you. The zone is where technical "
            f"support and value signals align into a high-probability entry."
        )

    return {
        "zone_low":           round(zone_low, 2),
        "zone_high":          round(zone_high, 2),
        "zone_str":           zone_str,
        "zone_width_pct":     round(width_pct, 1),
        "zone_status":        status,
        "zone_status_label":  label,
        "pct_to_zone":        round(pct, 1),
        "zone_bottom_signals": bot_sigs,
        "zone_top_signals":   top_sigs,
        "zone_reason":        reason,
    }
