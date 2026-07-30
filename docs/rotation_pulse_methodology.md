# Pulse — Sector Rotation methodology

Pulse is a sub-tab in the **Strategy Centre** (`My Stocks · Watchlist · Smart Picks ·
Dip Buys · Analogs · Frameworks · **Pulse**`). It infers whether capital is
persistently rotating **out of** one correlated group of themes and **into** another,
and — when it is — surfaces a research watch list for the receiving side.

**It displays an OBSERVED inverse pattern. It never claims to trace actual fund flows.**
It is additive: it reuses `theme_membership.json` and existing Trust/verification data,
and touches none of the recommendation, Picks, Dip Buys, or Tier-4b unwind logic.

---

## Code paths

| Piece | Location |
|---|---|
| Theme universe | `backend/data/theme_membership.json` (33 themes, reused) |
| History store | SQLite table `theme_daily_history` (`database/models.py`, CRUD in `database/db.py`) — persists via the Railway `/data` volume |
| Rotation computation | `backend/intelligence/rotation.py` (colocated with `unwind_detector.py`) |
| Scan + endpoint | `backend/main.py` → `_refresh_rotation_scan()`, `GET /api/rotation`, warm-trigger on `/api/strategy`, authless probe on `/api/dip-status` |
| UI | `frontend/src/App.jsx` → `PulseTab` (rendered as Strategy sub-tab 6); `client.js` → `getRotation()` |

`theme_daily_history` schema: `(theme, date, session_type, avg_pct, breadth,
member_count)`, primary key `(theme, date, session_type)`. One row per theme per date
per session; re-running a session overwrites its row.

---

## Data & sessions

- **Premarket / regular / after-hours** per-ticker moves come from Yahoo's
  `quoteSummary` **`price`** module (`marketState`, `preMarketChangePercent`,
  `regularMarketChangePercent`, `postMarketChangePercent`), routed through the
  Cloudflare worker so it reaches Railway. Coverage is ~70–100% of the universe
  premarket.
- **Session type** is read from `marketState` of a liquid probe (`SPY`): `PRE → pre`,
  `REGULAR → regular`, `POST → post`, else `close`. Per-ticker value is chosen to match
  (premarket during PRE, etc.) with a per-ticker fallback to the regular change.
- **Fallback rule (honesty):** if premarket coverage of the universe is `< 40%`, the
  session is relabelled **CLOSE** and the UI shows *"Premarket data unavailable or thin
  — showing the most recent regular-session close."* Stale data is never presented as
  live.
- **Backfill:** on first run against an empty store, ~10 real regular sessions are
  seeded from Yahoo v8 **daily bars** (`range=1mo&interval=1d`, reachable directly from
  Railway), computing each past session's theme `avg_pct` + `breadth`. Only real
  observed moves — nothing synthesised. Premarket is never backfilled (only today's live
  session can be premarket-labelled).
- **Refresh:** `_refresh_rotation_scan()` runs in the background with a **5-minute TTL**,
  full universe, off the request path (lazily triggered when Strategy / Pulse /
  dip-status are hit).

---

## Per-theme session log

For each theme with **≥3 members priced** that session (`compute_session_log`):

- `avg_pct` = mean member % move
- `breadth` = fraction of members green (`pct > 0`)
- `member_count` = members priced

Themes with fewer than 3 priced members are skipped (can't judge correlation).

---

## Regime detection (`detect_rotation`)

Reads the collapsed history (freshest session per theme per date). Three states:

### State 3 — RISK-OFF override (checked first)
If **≥70%** of themes are red in the latest session → `risk_off`. Any rotation pair is
**suppressed**: *"Broad risk-off — N of M themes red. Not a rotation; correlated
selling."* A seesaw reading during a market-wide selloff is false and dangerous, so
suppressing it is a feature.

### State 1 — ACTIVE rotation
1. **Derive clusters** — build each theme's `avg_pct` series across the window and
   cluster themes by pairwise correlation (Pearson, union-find, `corr ≥ 0.50`). Grouping
   is **derived from the log**, not a hard-coded pair list. (A display-only family map —
   Hardware / Software / Clean Energy / Defence / Healthcare — only *names* a derived
   cluster; if a cluster's members span families it is named by its themes.)
2. **Candidate sides (latest session)** — the most-negative cluster with **≥60% of
   members red** is the OUT candidate; the most-positive cluster with **≥60% green** is
   the IN candidate. Both sides must move **≥0.8% absolute** (noise floor).
3. **Persistence** — count consecutive sessions (latest → back) where OUT-cluster avg
   `< 0` **and** IN-cluster avg `> 0`. Requires **≥2**. That count is the **day count**;
   the first date of the run is the **start date**; **cumulative divergence** = Σ(IN
   avg − OUT avg) over the run.

If no divergent pair clears the breadth + noise gates, or the divergence isn't yet
persistent, the state is **`none`** ("No persistent rotation pattern detected").

### Regime end / history
A regime **ends** after 2 consecutive sessions without the inverse pattern.
`ended_regimes()` takes the dominant OUT/IN seesaw over the window, segments it into runs
of the inverse pattern (`_segment_runs`), and returns completed runs (`days ≥ 2`, not
touching the latest session) — the last 5, newest first, each with pair, start–end, days
and max divergence.

### Thresholds (single source in `rotation.py`)
| Constant | Value | Meaning |
|---|---|---|
| `MIN_MEMBERS_PRESENT` | 3 | members priced to score a theme |
| `MOVE_MIN` | 0.8% | per-side noise floor |
| `BREADTH_RED` / `BREADTH_GREEN` | 0.40 / 0.60 | ≥60% red / ≥60% green |
| `RISK_OFF_FRAC` | 0.70 | ≥70% themes red → risk-off |
| `CORR_MIN` | 0.50 | correlation to join a cluster |
| `MIN_CONSEC` | 2 | consecutive sessions for a regime |

---

## Quality watch list — Phase C (`watch_gate`, ACTIVE state only)

Built for the **IN (receiving)** theme(s) from **existing data only** — no new score, no
BUY badges anywhere on the tab.

**Main list (up to 4, ranked by Trust desc):**
- Trust **≥ 70**, verification passes (not suppressed), **no active auto-disqualifiers**
- **Not** reporting earnings within the next 7 days
- Per-stock **`⚠️ extended`** flag if price **> 20% above its 50-day MA** (informational
  — still listed)
- Display: ticker · today/premarket % · Trust. Tap → normal stock detail.

**⏳ Earnings soon (visible exclusions, not a hidden count):**
- Every quality-passing name whose earnings fall within 7 days, each with ticker · Trust
  · exact date (*"reports Thu Jul 30"*), sorted by earnings date ascending, capped at 3
  rows (`+N more`), with *"→ each re-eligible the day after it reports."* After a report
  date passes, the stock automatically returns to the main list on the next refresh if
  the regime is still active and the gates still pass.

**Earnings-date honesty:** a date that can't be confirmed never drives an exclusion — the
stock stays on the **main** list with a *"earnings date unverified"* note.

**Footer (always):** *"Research candidates from existing quality scores — not buy
signals. Rotations reverse without warning."*

---

## The Pulse tab (three states), top → bottom

1. **Header** — "Pulse — Sector Rotation" + session-type timestamp (`PREMARKET` / `LIVE`
   / `CLOSE`) + refresh. A premarket-unavailable notice appears when the fallback fires.
2. **Rotation banner** — ACTIVE (`↔️ OUT → IN`, day count, start, cumulative divergence,
   OUT/IN theme breakdowns) · NONE · RISK-OFF.
3. **Quality watch** (ACTIVE only) — main list + ⏳ earnings-soon + footer.
4. **Full theme heatmap** (all states) — every theme as a row (name, breadth bar, avg %),
   sorted by avg % desc; tap a theme → its member stocks with today's %.
5. **Regime history** (collapsed) — last 5 ended regimes.

Design: Avanza dark tokens (`#000` page, `#111` cards, 14px radius, `#4FA8F7` positive,
`#FF6B9D` negative, tabular-nums).

---

## Copy rules (plain language)

A non-investor should understand the tab without asking. Jargon is replaced everywhere:

| Internal term | Shown as |
|---|---|
| OUT | 🔴 SELLING (money leaving) |
| IN | 🟢 BUYING (money arriving) |
| divergence | "gap of X% between sides" |
| Day 2 | "Going on for: 2 days (since Jul 29)" |
| regime | rotation |
| breadth 63% | "63% of stocks in this theme are up" |
| cum. | "total since it started" |

- **Every % states its timeframe** — "today" or "total since it started". Today's %s come
  from one shared source (the session log); the banner can't contradict the heatmap.
- **"In one sentence"** summary is generated from live **theme names** (never codenames):
  *"For the last N days, investors have been selling [OUT themes] stocks and buying
  [IN themes] stocks instead."* A group label, if shown, lists its member themes.
- **Strength** from the today gap: `<3%` small — could be noise · `3–8%` moderate — worth
  watching · `>8%` big, clear rotation.
- **Section subtitles are always visible** (not hidden behind taps): banner "Where money is
  moving", heatmap "Today's scoreboard by theme", past rotations "Finished rotations, for
  context", quality watch "Quality stocks in the themes money is flowing into — research
  candidates, not buy signals".
- **Past rotations are sentences**: *"Out of AI Infrastructure & AI Software → into Defence ·
  Jul 22–24 · lasted 3 days · widest gap 5.2%."*
- **Reversal warning** is visible in the banner without scrolling: *"This can reverse any
  day. It's a pattern, not a promise."*

### [How to read?] — three worked examples (all labeled "Example · not live data")

1. **When there IS a rotation** — 🔴 SELLING Semiconductors −3.2% / 🟢 BUYING Cybersecurity
   +1.8% / going on 3 days · gap 6.4% moderate. "Money is moving from one group to another…
   what it does NOT mean: that chip stocks are bad or cybersecurity stocks are cheap."
2. **When there is NO rotation** — "No clear pattern today." "Some themes up, some down, but
   no consistent flow… this is normal."
3. **When everything falls (risk-off)** — "Broad sell-off — 24 of 30 themes red." "Not a
   rotation — money is leaving the market. Rotation signals are hidden on days like this."

Also explains the heatmap ("today's scoreboard") and past rotations ("a diary of finished
rotations") in the same panel.

---

## Part 3 — "See it in actual stocks" (opposite pairs)

Placed directly under the banner, above Quality Watch. **Active state only** — hidden in
no-rotation and risk-off. Illustrates the theme rotation with familiar tickers; it is
**not** a trade and never claims one stock causes the other's move.

**Candidate pool** (`_compute_stock_pairs`):
- OUT side = members of the OUT themes that are **red today**; IN side = members of the IN
  themes that are **green today**.
- Both sides gated: **Trust ≥ 60**, verification passing (not suppressed / not
  auto-disqualified), **market cap ≥ $1B** (recognisable, liquid names).

**Pair scoring over the last 10 sessions:**
- `opposite_days` = sessions where one closed up and the other down (primary rank).
- `today_magnitude` = |OUT today %| + |IN today %| (tiebreak).
- **Both tickers need ≥10 real sessions of history** — otherwise the pair is excluded, never
  computed on partial history.
- **Pairs with `opposite_days < 6` are excluded** — below that it's coincidence, not a seesaw.
- Show **top 3**; no ticker appears in more than one pair; distinct theme combinations
  preferred. Empty state: *"No clear stock pairs today…"* — the threshold is never lowered
  to fill the section.

**Display:** `TICKER −X.X% ↔ TICKER +Y.Y%` (pink falling side, cyan rising side), "moved
opposite on N of last 10 days", tap either ticker → stock detail. Footer: *"These pairs tend
to move in opposite directions… Not a rule: on market-wide sell-off days both can fall
together."*

*Worked check (real closes, Jul 2026): MU ↔ HUBS moved opposite on 7 of the last 10 sessions
— the memory-vs-software seesaw.*

---

## Principles

1. Direction is **inferred** from persistent inverse moves — the pattern is displayed,
   never presented as literal fund-flow tracing.
2. One-day flips are noise; a regime requires **persistence *and* breadth**.
3. Broad risk-off is **not** rotation — suppressing the display then is intended.
4. Exclusions are **visible and dated**; unverifiable data never drives an exclusion.
5. The watch list **reuses existing quality scores** — single source of truth, research
   framing, no buy commands.
