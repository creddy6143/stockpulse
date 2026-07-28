"""Pulse — Sector Rotation detection.

Reads the ``theme_daily_history`` log and infers whether capital is persistently
rotating OUT of one correlated group of themes and INTO another. We display the
OBSERVED inverse pattern — we NEVER claim to trace actual fund flows.

Guard rails (see rotation_pulse_methodology.md):
  • PERSISTENCE — a regime needs the inverse pattern for ≥2 consecutive sessions.
  • BREADTH     — the OUT side needs ≥60% of members red, the IN side ≥60% green.
  • NOISE FLOOR — both sides must move ≥0.8% (abs) that session.
  • RISK-OFF    — if ≥70% of all themes are red, we SUPPRESS any pair; broad
                  correlated selling is not rotation.

Grouping of correlated themes ("Hardware", "Software"…) is DERIVED from same-sign
correlated moves in the log — not a hard-coded pair list. The family map below is
used only to give a derived cluster a readable NAME.
"""
import statistics
from datetime import datetime, date as _date

# ── thresholds ────────────────────────────────────────────────────────────────
MIN_MEMBERS_PRESENT = 3       # need ≥3 members priced to judge a theme at all
MOVE_MIN            = 0.8     # noise floor, abs % — one-day flips below this are noise
BREADTH_RED         = 0.40    # ≤40% green  ⟺  ≥60% red
BREADTH_GREEN       = 0.60    # ≥60% green
RISK_OFF_FRAC       = 0.70    # ≥70% of themes red this session → risk-off override
CORR_MIN            = 0.50    # themes correlated ≥ this move together → one cluster
MIN_CONSEC          = 2       # consecutive sessions required for a regime

# Session recency ranking — the freshest reading wins per (theme, date).
_SESSION_RANK = {"pre": 1, "regular": 2, "post": 3, "close": 4}

# Display-only family labels (naming, NOT grouping). If every theme in a derived
# cluster shares a family, we use it; otherwise we name the cluster by its themes.
_FAMILY = {
    "storage_memory": "Hardware", "semiconductors": "Hardware",
    "ai_infrastructure": "Hardware", "robotics_automation": "Hardware",
    "ai_software": "Software", "cybersecurity": "Software",
    "cloud_hyperscalers": "Software", "fintech_payments": "Software",
    "gaming": "Software",
    "solar_renewables": "Clean Energy", "hydrogen": "Clean Energy",
    "ev_battery": "Clean Energy", "lithium_rare_earths": "Clean Energy",
    "nuclear_smr": "Clean Energy", "grid_electrification": "Clean Energy",
    "defense_rearmament": "Defence", "defense_tech_drones": "Defence",
    "european_defence": "Defence", "swedish_defence": "Defence",
    "indian_defence": "Defence", "space_satellites": "Defence",
    "glp1_obesity": "Healthcare", "gene_editing_crispr": "Healthcare",
}


def _members(theme: dict) -> list:
    members = list(theme.get("candidates") or [])
    winner = theme.get("early_winner")
    if winner and winner not in members:
        members = [winner] + members
    return members


# ── session log (per-theme snapshot for one session) ──────────────────────────
def compute_session_log(ticker_pct: dict, membership: dict) -> list:
    """Per-theme {avg_pct, breadth, member_count, members[]} for one session.

    ``ticker_pct`` maps TICKER → % move (premarket or regular, caller's choice).
    """
    out = []
    for key, theme in membership.items():
        present = [(t, ticker_pct[t]) for t in _members(theme)
                   if ticker_pct.get(t) is not None]
        if len(present) < MIN_MEMBERS_PRESENT:
            continue
        pcts = [p for _, p in present]
        avg = sum(pcts) / len(pcts)
        breadth = sum(1 for p in pcts if p > 0) / len(pcts)
        out.append({
            "theme": key,
            "name": theme.get("name", key),
            "avg_pct": round(avg, 3),
            "breadth": round(breadth, 3),
            "member_count": len(present),
            "members": sorted(
                [{"ticker": t, "pct": round(p, 2)} for t, p in present],
                key=lambda x: x["pct"]),
        })
    out.sort(key=lambda r: r["avg_pct"], reverse=True)
    return out


# ── history shaping ───────────────────────────────────────────────────────────
def _collapse_by_date(rows: list):
    """(date)→{theme:(avg,breadth)} using the freshest session per (theme,date)."""
    best = {}   # (date,theme) → (rank, avg, breadth)
    for r in rows:
        if r.get("avg_pct") is None:
            continue
        k = (r["date"], r["theme"])
        rk = _SESSION_RANK.get(r.get("session_type"), 2)
        if k not in best or rk > best[k][0]:
            best[k] = (rk, r["avg_pct"], r.get("breadth"))
    dates = sorted({d for d, _ in best})
    by_date = {d: {} for d in dates}
    for (d, th), (_rk, avg, br) in best.items():
        by_date[d][th] = (avg, br if br is not None else 0.5)
    return dates, by_date


def _corr(a: list, b: list):
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    try:
        return statistics.correlation([p[0] for p in pairs], [p[1] for p in pairs])
    except Exception:
        return None   # zero variance etc.


def _cluster(themes: list, series: dict) -> list:
    """Union-find clustering: themes correlated ≥ CORR_MIN share a cluster."""
    parent = {t: t for t in themes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(len(themes)):
        for j in range(i + 1, len(themes)):
            c = _corr(series[themes[i]], series[themes[j]])
            if c is not None and c >= CORR_MIN:
                parent[find(themes[i])] = find(themes[j])
    groups = {}
    for t in themes:
        groups.setdefault(find(t), []).append(t)
    return list(groups.values())


def _cluster_avg(cluster: list, date_map: dict):
    vals = [date_map[th][0] for th in cluster if th in date_map]
    brs = [date_map[th][1] for th in cluster if th in date_map]
    if not vals:
        return None, None
    return sum(vals) / len(vals), sum(brs) / len(brs)


def _name_cluster(cluster: list, membership: dict) -> str:
    fams = {_FAMILY.get(t) for t in cluster}
    fams.discard(None)
    if len(fams) == 1:
        return fams.pop()
    names = [membership.get(t, {}).get("name", t) for t in cluster]
    return " + ".join(names[:2]) + ("…" if len(names) > 2 else "")


def _side_detail(cluster: list, date_map: dict, membership: dict) -> dict:
    themes = []
    for th in cluster:
        if th in date_map:
            themes.append({"theme": th,
                           "name": membership.get(th, {}).get("name", th),
                           "avg_pct": round(date_map[th][0], 2),
                           "breadth": round(date_map[th][1], 3)})
    themes.sort(key=lambda x: x["avg_pct"])
    avg, br = _cluster_avg(cluster, date_map)
    return {"label": _name_cluster(cluster, membership),
            "avg_pct": round(avg, 2) if avg is not None else None,
            "breadth": round(br, 3) if br is not None else None,
            "themes": themes}


def _segment_runs(dates: list, out_series: list, in_series: list) -> list:
    """Maximal runs where OUT<0 and IN>0 (the inverse pattern), each with
    {start, end, days, max_div, cum_div}."""
    runs, cur = [], None
    for i, d in enumerate(dates):
        oa, ia = out_series[i], in_series[i]
        hit = (oa is not None and ia is not None and oa < 0 and ia > 0)
        if hit:
            div = ia - oa
            if cur is None:
                cur = {"start": d, "end": d, "days": 1,
                       "max_div": div, "cum_div": div}
            else:
                cur["end"] = d
                cur["days"] += 1
                cur["cum_div"] += div
                cur["max_div"] = max(cur["max_div"], div)
        else:
            if cur:
                runs.append(cur)
                cur = None
    if cur:
        runs.append(cur)
    return runs


# ── main detector ─────────────────────────────────────────────────────────────
def detect_rotation(history_rows: list, membership: dict) -> dict:
    """Classify the latest session into one of three states.

    Returns ``{state: "active"|"none"|"risk_off"|"insufficient", ...}``.
    """
    dates, by_date = _collapse_by_date(history_rows)
    if len(dates) < MIN_CONSEC:
        return {"state": "insufficient", "sessions": len(dates),
                "reason": "Need ≥2 sessions of history to detect a regime."}

    latest = dates[-1]
    latest_map = by_date[latest]

    # 1 — RISK-OFF OVERRIDE (a seesaw reading during a market-wide selloff is
    #      false and dangerous — suppress the pair entirely).
    present = list(latest_map.values())
    total = len(present)
    red = sum(1 for a, _ in present if a is not None and a < 0)
    if total and red / total >= RISK_OFF_FRAC:
        return {"state": "risk_off", "red": red, "total": total,
                "latest_date": latest}

    # 2 — DERIVE correlated clusters from the log.
    themes = sorted({th for d in dates for th in by_date[d]})
    series = {th: [by_date[d].get(th, (None, None))[0] for d in dates] for th in themes}
    clusters = _cluster(themes, series)

    def cluster_series(cluster):
        return [_cluster_avg(cluster, by_date[d])[0] for d in dates]

    # 3 — Candidate OUT (most negative, ≥60% red) / IN (most positive, ≥60% green)
    #      clusters on the latest session.
    scored = []
    for cl in clusters:
        avg, br = _cluster_avg(cl, latest_map)
        if avg is not None:
            scored.append((avg, br, cl))
    downs = [(a, b, cl) for a, b, cl in scored if a <= -MOVE_MIN and b <= BREADTH_RED]
    ups = [(a, b, cl) for a, b, cl in scored if a >= MOVE_MIN and b >= BREADTH_GREEN]

    if not downs or not ups:
        return {"state": "none", "latest_date": latest,
                "reason": "No divergent OUT/IN clusters that clear the breadth "
                          "and noise thresholds this session."}

    out_cl = min(downs, key=lambda x: x[0])[2]
    in_cl = max(ups, key=lambda x: x[0])[2]
    out_series = cluster_series(out_cl)
    in_series = cluster_series(in_cl)

    # 4 — PERSISTENCE: consecutive sessions (latest → back) with the inverse pattern.
    consec, cum = 0, 0.0
    for i in range(len(dates) - 1, -1, -1):
        oa, ia = out_series[i], in_series[i]
        if oa is not None and ia is not None and oa < 0 and ia > 0:
            consec += 1
            cum += (ia - oa)
        else:
            break
    if consec < MIN_CONSEC:
        return {"state": "none", "latest_date": latest, "consec": consec,
                "reason": "Divergence present today but not yet persistent "
                          f"({consec} session — needs ≥{MIN_CONSEC})."}

    start_date = dates[len(dates) - consec]
    ended = [r for r in _segment_runs(dates, out_series, in_series)
             if r["end"] != latest][-5:]

    return {
        "state": "active",
        "latest_date": latest,
        "start_date": start_date,
        "day_count": consec,
        "divergence_cum": round(cum, 2),
        "out": _side_detail(out_cl, latest_map, membership),
        "in": _side_detail(in_cl, latest_map, membership),
        "ended_regimes": [
            {"start": r["start"], "end": r["end"], "days": r["days"],
             "max_div": round(r["max_div"], 2)} for r in reversed(ended)],
    }


# ── Phase C — quality watch list gating (IN / receiving side) ─────────────────
WATCH_TRUST_MIN = 70
EARNINGS_WINDOW_DAYS = 7
EXTENDED_MULT = 1.20          # price >20% above 50-day MA → "extended" flag

_WDAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MON = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
        "Oct", "Nov", "Dec"]


def _parse_earnings(next_earnings_date, today: _date):
    """→ (days:int|None, label:str|None, unverified:bool).

    Honest: an unparseable / missing date is UNVERIFIED (never a fabricated
    exclusion date). "Today" → 0 days.
    """
    if not next_earnings_date:
        return None, None, True
    s = str(next_earnings_date).strip()
    if s.lower() == "today":
        return 0, "reports today", False
    iso = s.replace("/", "-")[:10]
    try:
        d = datetime.strptime(iso, "%Y-%m-%d").date()
    except Exception:
        return None, None, True
    days = (d - today).days
    label = f"reports {_WDAY[d.weekday()]} {_MON[d.month]} {d.day}"
    return days, label, False


def watch_gate(trust: dict, next_earnings_date, price, ma_50d,
               today: _date = None) -> dict:
    """Classify one IN-theme member for the watch list — PURE (caller fetches).

    Reuses EXISTING trust/verification data only; invents no new score.
    Returns ``{status, ...}`` where status is:
      • "main"          — clears every gate → main watch list
      • "earnings_soon" — clears quality gates but reports within 7 days
      • "excluded"      — fails a quality gate (never shown)
    """
    today = today or _date.today()
    score = trust.get("total_score") or 0
    auto_disq = bool(trust.get("auto_disqualified"))
    # Matches recommendation._is_suppressed: verification flag, or display_score
    # explicitly nulled (present AND None). An ABSENT key is not a suppression.
    suppressed = bool(trust.get("suppressed")) or \
        ("display_score" in trust and trust.get("display_score") is None)

    if auto_disq:
        return {"status": "excluded", "reason": "auto-disqualified"}
    if suppressed:
        return {"status": "excluded", "reason": "score under review (unverified)"}
    if score < WATCH_TRUST_MIN:
        return {"status": "excluded", "reason": f"trust {score} < {WATCH_TRUST_MIN}"}

    days, label, unverified = _parse_earnings(next_earnings_date, today)
    if days is not None and 0 <= days <= EARNINGS_WINDOW_DAYS:
        return {"status": "earnings_soon", "trust": score,
                "earnings_days": days, "earnings_label": label}

    extended = bool(ma_50d and price and price > EXTENDED_MULT * ma_50d)
    return {"status": "main", "trust": score, "extended": extended,
            "earnings_unverified": unverified,
            "earnings_days": days, "earnings_label": label}


def ended_regimes(history_rows: list, membership: dict, limit: int = 5) -> list:
    """Past ended regimes for the history panel — the dominant OUT/IN seesaw over
    the window, segmented into runs, excluding any run still active at the latest
    session."""
    dates, by_date = _collapse_by_date(history_rows)
    if len(dates) < MIN_CONSEC:
        return []
    themes = sorted({th for d in dates for th in by_date[d]})
    series = {th: [by_date[d].get(th, (None, None))[0] for d in dates] for th in themes}
    clusters = _cluster(themes, series)
    # Dominant seesaw = most-negative avg cluster vs most-positive avg cluster
    # across the whole window.
    def win_avg(cl):
        vs = [v for d in dates for v in [_cluster_avg(cl, by_date[d])[0]] if v is not None]
        return sum(vs) / len(vs) if vs else 0.0
    ranked = sorted(clusters, key=win_avg)
    if len(ranked) < 2:
        return []
    out_cl, in_cl = ranked[0], ranked[-1]
    out_series = [_cluster_avg(out_cl, by_date[d])[0] for d in dates]
    in_series = [_cluster_avg(in_cl, by_date[d])[0] for d in dates]
    latest = dates[-1]
    runs = [r for r in _segment_runs(dates, out_series, in_series)
            if r["end"] != latest and r["days"] >= MIN_CONSEC]
    out_name = _name_cluster(out_cl, membership)
    in_name = _name_cluster(in_cl, membership)
    return [{"pair": f"{out_name} → {in_name}", "start": r["start"], "end": r["end"],
             "days": r["days"], "max_div": round(r["max_div"], 2)}
            for r in list(reversed(runs))[:limit]]
