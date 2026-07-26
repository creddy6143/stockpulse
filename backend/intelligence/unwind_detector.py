"""Correlated-selloff (Unwind) detector — Tier 4b of the dip-buy stack.

THE DISTINCTION
---------------
A *dip* is one stock pulling back while its world is fine.
A *correlated selloff* is the world falling — the whole theme dropping together
on a shared macro driver.  Individual dip quality CANNOT be assessed during a
correlated selloff, so every dip-buy flag inside an unwinding theme is suspended.

During an unwind the most valuable output is NOT a buy signal — it is a
measurable, honest answer to "how close is this theme to being safe to assess
again."  That answer is the stabilization tracker.

DETECTION (per theme, using the TIGHTEST theme from theme_membership.json)
--------------------------------------------------------------------------
Suppress all dip-buy flags in a theme when ANY of:
  • 3+ theme members down > 5% within the same 1-5 day window, OR
  • theme average down > 8% over 5 days.

While suppressed the affected stocks are NOT removed — they group under one
Unwind banner, their recommendation is forced to WATCH, and their scores are
FROZEN at pre-unwind values (not recomputed during the unwind).

HONESTY
-------
Every number here traces to real change data (today %, 3-day %, 5-day %) or real
price levels (MA50/MA200, recent high).  Nothing is fabricated.  Where a criterion
needs data we do not have (e.g. per-theme volume), it is reported as pending, not
guessed.  Recovery-resilience uses the shared module, which returns
"Insufficient history" when < ~6 months of data exists.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime

# ── Tier 4b thresholds ────────────────────────────────────────────────────────
MEMBER_DROP_PCT  = -5.0    # a member counts as "down >5%" in the window
MIN_MEMBERS_DOWN = 3       # 3+ such members → correlated
THEME_AVG_DROP   = -8.0    # theme 5-day average this bad → correlated
MIN_THEME_SIZE   = 3       # need ≥3 members present to judge correlation at all
GROUP_DROP_PCT   = -2.0    # members down at least this much are grouped as affected

_DATA_DIR      = os.path.join(os.path.dirname(__file__), "..", "data")
_STATE_FILE    = os.path.join(_DATA_DIR, "theme_unwind_state.json")
_HISTORY_FILE  = os.path.join(_DATA_DIR, "theme_unwind_history.json")
_MEMBERSHIP    = os.path.join(_DATA_DIR, "theme_membership.json")


# ── membership ─────────────────────────────────────────────────────────────────
def _load_membership() -> dict:
    try:
        with open(_MEMBERSHIP) as f:
            return json.load(f)
    except Exception:
        return {}


def _theme_members(theme: dict) -> list[str]:
    members = list(theme.get("candidates") or [])
    winner = theme.get("early_winner")
    if winner and winner not in members:
        members = [winner] + members
    return members


# ── small persistence helpers (defensive — never raise) ────────────────────────
def _read_json(path: str, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: str, data) -> None:
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


# ── metrics ────────────────────────────────────────────────────────────────────
def _window_drop(td: dict) -> float:
    """Worst of today's % and the 5-day % — used only for grouping/sorting depth."""
    return min(float(td.get("change_pct") or 0), float(td.get("week_change") or 0))


def _in_selloff(td: dict) -> bool:
    """True only for GENUINE multi-day weakness — the mark of a correlated selloff.

    A red day inside an uptrend is a dip, not an unwind. So a member counts only
    when it is down >5% over the 5-day window, OR down >5% today while the week is
    also negative (a fresh leg down). This prevents flagging a theme that is up
    strongly on the week just because a few members pulled back today
    (e.g. Storage/Memory +16.5% on the week with a red Friday).
    """
    today = float(td.get("change_pct") or 0)
    week  = float(td.get("week_change") or 0)
    return week <= MEMBER_DROP_PCT or (today <= MEMBER_DROP_PCT and week < 0)


def _avg(vals: list[float]) -> float:
    return round(sum(vals) / len(vals), 1) if vals else 0.0


def _estimate_day_count(theme_today_avg: float, theme_5d_avg: float) -> int:
    """Estimate how many days the unwind has been running.

    We only have today's move and the 5-day move, so this is an ESTIMATE:
    if most of the 5-day drop happened today the unwind is ~1 day old; if the
    drop is spread across the week it is multi-day.  Labelled as an estimate in
    the UI copy — never presented as an exact figure.
    """
    if theme_5d_avg >= -0.5:
        return 1
    ratio = theme_today_avg / theme_5d_avg if theme_5d_avg else 1.0   # share of week's drop that is today
    if ratio >= 0.6:
        return 1
    return min(5, max(2, round(1.0 / max(ratio, 0.2))))


def _reclaim_level(price: float, td: dict) -> dict:
    """Nearest meaningful overhead resistance above current price.

    Candidates: recent high (proxy), MA50, MA200.  Pick the CLOSEST one above
    price.  Status is a point-in-time read; full confirmation (2 closes held on
    above-average volume) requires multi-day tracking and is stated as pending.
    """
    cands = []
    for key in ("recent_high", "ma50", "ma200"):
        v = td.get(key)
        try:
            v = float(v or 0)
        except (TypeError, ValueError):
            v = 0
        if v > 0:
            cands.append((key, v))

    above = [(k, v) for k, v in cands if v > price]
    if not above:
        # Price is above every reference level — nothing overhead to reclaim.
        return {
            "level": None, "source": None, "pct_below": None,
            "status": "above", "status_label": "Above resistance — no overhead level",
        }
    source, level = min(above, key=lambda kv: kv[1])   # closest above
    pct_below = round((price - level) / level * 100, 1)

    if price >= level * 1.005:
        status, label = "reclaimed_day1", "Reclaimed — needs 1 more close + volume confirmation"
    elif price >= level * 0.995:
        status, label = "testing", "Testing reclaim"
    else:
        status, label = "below", "Bounce, not confirmed"

    return {
        "level": round(level, 2), "source": source, "pct_below": pct_below,
        "status": status, "status_label": label,
    }


def _stabilization_tracker(present: list[str], ticker_data: dict) -> dict:
    """4 criteria measuring how close the theme is to being safe to assess again.

    Each is computed from real theme-aggregate change data.  Criterion 2 (volume)
    is reported as pending when per-theme volume is unavailable — never guessed.
    """
    today = [float(ticker_data[t].get("change_pct") or 0) for t in present]
    d3    = [float(ticker_data[t]["d3"]) for t in present if ticker_data[t].get("d3") is not None]
    d5    = [float(ticker_data[t].get("week_change") or 0) for t in present]
    theme_today = _avg(today)
    theme_5d    = _avg(d5)
    have_d3     = len(d3) > 0
    theme_3d    = _avg(d3) if have_d3 else None

    vols = [ticker_data[t].get("vol_ratio") for t in present
            if ticker_data[t].get("vol_ratio") is not None]
    if vols:
        vol_met = (sum(vols) / len(vols)) < 1.5
        vol_note = f"theme volume {sum(vols)/len(vols):.1f}× average"
    else:
        vol_met = False
        vol_note = "volume data pending"

    criteria = [
        {"label": "No new theme-wide low today", "met": theme_today > -1.5,
         "detail": f"theme avg today {theme_today:+.1f}%"},
        {"label": "Theme volume < 1.5× average", "met": vol_met, "detail": vol_note},
        {"label": "3 days without a lower low",
         "met": (theme_3d is not None and theme_3d > -1.0),
         "detail": (f"theme 3-day {theme_3d:+.1f}%" if have_d3 else "3-day data pending")},
        {"label": "Theme flat-or-up over 5 days", "met": theme_5d >= 0.0,
         "detail": f"theme 5-day {theme_5d:+.1f}%"},
    ]
    met = sum(1 for c in criteria if c["met"])
    return {"criteria": criteria, "met_count": met, "total": 4, "stabilized": met == 4}


def _enrich_levels(ticker: str) -> dict:
    """Fetch real price levels (MA50/MA200, 52-week high, recent high) for the
    reclaim-level and drawdown computations. Cached fetches in normal operation.
    Returns {} on any failure — the caller degrades gracefully.
    """
    try:
        from data.fetcher import get_fundamentals, get_stock_history
        f = get_fundamentals(ticker) or {}
        hist = get_stock_history(ticker) or {}
        prices = [p["price"] for p in hist.get("prices", []) if p.get("price") is not None]
        recent_high = max(prices[-6:]) if len(prices) >= 2 else None
        return {
            "ma50": f.get("ma_50d"),
            "ma200": f.get("ma_200d"),
            "w52_high": f.get("w52_high"),
            "recent_high": recent_high,
        }
    except Exception:
        return {}


def _recovery_for(ticker: str) -> dict:
    """Recovery-resilience from REAL history only; honest when insufficient."""
    try:
        from data.fetcher import get_stock_history, get_fundamentals, get_insider_data
        from intelligence.recovery_resilience import compute_recovery_resilience
        rr = compute_recovery_resilience(
            ticker, get_stock_history(ticker), get_fundamentals(ticker), get_insider_data(ticker)
        )
        return {"score": rr.get("score"), "label": rr.get("label"),
                "median_recovery_days": rr.get("components", {}).get("median_recovery_days")}
    except Exception:
        return {"score": None, "label": "Insufficient history", "median_recovery_days": None}


# ── main detection ──────────────────────────────────────────────────────────────
def detect_unwinds(ticker_data: dict, frozen: dict | None = None,
                   membership: dict | None = None, deep: bool = False) -> list[dict]:
    """Detect themes in a correlated selloff.

    Parameters
    ----------
    ticker_data : {ticker: {change_pct, week_change, d3, price, ma50, ma200,
                            recent_high, vol_ratio, next_earnings, w52_high}}
    frozen      : {ticker: {rec, score}} — pre-unwind values to freeze at.
    deep        : when True, compute per-stock recovery-resilience (extra fetches).

    Returns a list of unwind-theme dicts (tightest theme wins grouping).
    """
    membership = membership or _load_membership()
    frozen = frozen or {}
    unwinds: list[dict] = []
    claimed: set[str] = set()   # a ticker belongs to its tightest triggering theme only

    # Sort themes smallest-first so the TIGHTEST theme claims a ticker before any
    # broader one (e.g. Storage/Memory before a wider tech grouping).
    themed = sorted(membership.items(), key=lambda kv: len(_theme_members(kv[1])))

    for key, theme in themed:
        present = [t for t in _theme_members(theme)
                   if t in ticker_data and t not in claimed]
        if len(present) < MIN_THEME_SIZE:
            continue

        down_members = [t for t in present if _in_selloff(ticker_data[t])]
        theme_5d_avg    = _avg([float(ticker_data[t].get("week_change") or 0) for t in present])
        theme_today_avg = _avg([float(ticker_data[t].get("change_pct") or 0) for t in present])

        triggered = len(down_members) >= MIN_MEMBERS_DOWN or theme_5d_avg <= THEME_AVG_DROP
        if not triggered:
            continue

        # Group members with genuine weekly weakness — never a member that is up
        # on the week (that is a dip within the theme's rally, not part of a selloff).
        affected = sorted(
            {t for t in present
             if _in_selloff(ticker_data[t])
             or float(ticker_data[t].get("week_change") or 0) <= GROUP_DROP_PCT},
            key=lambda t: _window_drop(ticker_data[t]),
        )
        if len(affected) < MIN_THEME_SIZE:
            continue
        claimed.update(affected)

        day_count = _estimate_day_count(theme_today_avg, theme_5d_avg)
        max_depth = round(min(_window_drop(ticker_data[t]) for t in affected), 1)

        cards = []
        for t in affected:
            td = dict(ticker_data[t])
            # In deep mode fill real price levels (MA50/MA200, 52w high, recent
            # high) so reclaim + drawdown come from real data, not placeholders.
            if deep and not td.get("ma50"):
                td.update({k: v for k, v in _enrich_levels(t).items() if v})
            price = float(td.get("price") or 0)
            fz = frozen.get(t, {})
            w52 = float(td.get("w52_high") or 0)
            dd = round((price - w52) / w52 * 100, 1) if w52 > 0 and price > 0 else None
            chg = float(td.get("change_pct") or 0)
            card = {
                "ticker": t,
                "price": round(price, 2),
                "change_pct": round(chg, 1),
                "week_change": round(float(td.get("week_change") or 0), 1),
                # FROZEN pre-unwind values — not recomputed during the unwind
                "frozen_rec": fz.get("rec", "WATCH"),
                "frozen_score": fz.get("score"),
                "scores_frozen": True,
                "drawdown_from_52w_high_pct": dd,
                "days_into_unwind": day_count,
                "next_earnings": td.get("next_earnings"),
                "reclaim": _reclaim_level(price, td),
                "recovery_resilience": _recovery_for(t) if deep else None,
                "safety_override": (
                    f"Down {chg:.1f}% today — sharp single-day drop." if chg <= -8.0 else None
                ),
                # No BUY-class badge is ever emitted in unwind state.
                "rec": "WATCH",
            }
            cards.append(card)

        driver = theme.get("force") or "shared macro driver"
        unwinds.append({
            "theme_key": key,
            "name": theme.get("name", key),
            "icon": theme.get("icon", "⚠️"),
            "affected_count": len(affected),
            "affected_tickers": affected,
            "day_count": day_count,
            "day_count_estimated": True,
            "theme_5d_avg": theme_5d_avg,
            "theme_today_avg": theme_today_avg,
            "max_depth_pct": max_depth,
            "driver": driver,
            "banner_copy": (
                f"⚠️ Sector-wide unwind: {theme.get('name', key)} — {len(affected)} stocks "
                f"falling together on a shared macro driver. Dip signals suspended until the "
                f"theme stabilizes."
            ),
            "stabilization": _stabilization_tracker(present, ticker_data),
            "stocks": cards,
        })

    _update_history(unwinds)
    return unwinds


def apply_unwind_suppression(dip_results: list[dict], unwinds: list[dict]) -> list[dict]:
    """Force affected dips to WATCH and freeze their scores. Never removes them.

    Returns the dip_results list with affected entries tagged `unwind=True`,
    `dip_rec="WATCH"`, and a `frozen_score` snapshot.
    """
    affected = {t: u for u in unwinds for t in u["affected_tickers"]}
    for d in dip_results:
        u = affected.get(d.get("ticker"))
        if not u:
            continue
        d["unwind"] = True
        d["unwind_theme"] = u["theme_key"]
        d["unwind_theme_name"] = u["name"]
        d["dip_rec"] = "WATCH"
        d["safety_capped"] = True
        d["scores_frozen"] = True
        d["frozen_score"] = d.get("quality_score")
        d["frozen_dip_tier"] = d.get("dip_tier")
        d["safety_note"] = (
            f"Suspended — {u['name']} is in a sector-wide unwind. "
            f"Individual dip quality can't be assessed during a correlated selloff."
        )
    return dip_results


# ── history log (Part 5) ────────────────────────────────────────────────────────
def _update_history(unwinds: list[dict]) -> None:
    """Track open episodes; write completed ones to theme_unwind_history.json.

    State: {theme_key: {start_date, max_depth, members, driver, name}}.
    On each run: open/extend episodes for currently-unwinding themes; any theme
    that WAS unwinding but no longer is → close the episode and append to history.
    """
    today = date.today().isoformat()
    state = _read_json(_STATE_FILE, {})
    active = {u["theme_key"]: u for u in unwinds}

    # Open or extend
    for key, u in active.items():
        s = state.get(key)
        if s is None:
            state[key] = {
                "name": u["name"], "start_date": today,
                "max_depth": u["max_depth_pct"], "driver": u["driver"],
                "members": u["affected_tickers"],
            }
        else:
            s["max_depth"] = min(s.get("max_depth", 0), u["max_depth_pct"])
            s["members"] = sorted(set(s.get("members", [])) | set(u["affected_tickers"]))

    # Close episodes that ended
    history = _read_json(_HISTORY_FILE, [])
    for key in list(state.keys()):
        if key not in active:
            episode = state.pop(key)
            episode.update({"theme": key, "end_date": today})
            history.append(episode)

    _write_json(_STATE_FILE, state)
    _write_json(_HISTORY_FILE, history)
