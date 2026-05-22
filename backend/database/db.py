from .models import get_connection
from datetime import datetime


# ── STOCKS ──────────────────────────────────────────────────────────────────

def upsert_stock(ticker, name=None, market=None, exchange=None, currency=None):
    conn = get_connection()
    conn.execute(
        """INSERT INTO stocks (ticker, name, market, exchange, currency)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(ticker) DO UPDATE SET
             name=COALESCE(excluded.name, stocks.name),
             market=COALESCE(excluded.market, stocks.market),
             exchange=COALESCE(excluded.exchange, stocks.exchange),
             currency=COALESCE(excluded.currency, stocks.currency)""",
        (ticker, name, market, exchange, currency),
    )
    conn.commit()
    conn.close()


def get_stock(ticker):
    conn = get_connection()
    row = conn.execute("SELECT * FROM stocks WHERE ticker=?", (ticker,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── PORTFOLIO ────────────────────────────────────────────────────────────────

def get_portfolio():
    conn = get_connection()
    rows = conn.execute(
        """SELECT p.*, s.name, s.market, s.exchange, s.currency
           FROM portfolio p LEFT JOIN stocks s ON p.ticker=s.ticker
           ORDER BY p.id"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_position(ticker, shares, buy_price, buy_date=None, notes=None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO portfolio (ticker, shares, buy_price, buy_date, notes) VALUES (?, ?, ?, ?, ?)",
        (ticker, shares, buy_price, buy_date, notes),
    )
    conn.commit()
    conn.close()


def update_position(pos_id, shares=None, buy_price=None, notes=None):
    conn = get_connection()
    if shares is not None:
        conn.execute("UPDATE portfolio SET shares=? WHERE id=?", (shares, pos_id))
    if buy_price is not None:
        conn.execute("UPDATE portfolio SET buy_price=? WHERE id=?", (buy_price, pos_id))
    if notes is not None:
        conn.execute("UPDATE portfolio SET notes=? WHERE id=?", (notes, pos_id))
    conn.commit()
    conn.close()


def delete_position(pos_id):
    conn = get_connection()
    conn.execute("DELETE FROM portfolio WHERE id=?", (pos_id,))
    conn.commit()
    conn.close()


# ── WATCHLIST ────────────────────────────────────────────────────────────────

def get_watchlist():
    conn = get_connection()
    rows = conn.execute(
        """SELECT w.*, s.name, s.market, s.currency
           FROM watchlist w LEFT JOIN stocks s ON w.ticker=s.ticker
           ORDER BY w.added_at DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_to_watchlist(ticker, notes=None):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO watchlist (ticker, notes) VALUES (?, ?)",
        (ticker, notes),
    )
    conn.commit()
    conn.close()


def remove_from_watchlist(ticker):
    conn = get_connection()
    conn.execute("DELETE FROM watchlist WHERE ticker=?", (ticker,))
    conn.commit()
    conn.close()


# ── TRUST SCORES ─────────────────────────────────────────────────────────────

def save_trust_score(ticker, total, business, smart_money, momentum, grade,
                     auto_disq=False, disq_reason=None):
    conn = get_connection()
    conn.execute(
        """INSERT INTO trust_scores
           (ticker, total_score, business_score, smart_money_score, momentum_score,
            grade, auto_disqualified, disqualify_reason, calculated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(ticker) DO UPDATE SET
             total_score=excluded.total_score,
             business_score=excluded.business_score,
             smart_money_score=excluded.smart_money_score,
             momentum_score=excluded.momentum_score,
             grade=excluded.grade,
             auto_disqualified=excluded.auto_disqualified,
             disqualify_reason=excluded.disqualify_reason,
             calculated_at=excluded.calculated_at""",
        (ticker, total, business, smart_money, momentum, grade,
         auto_disq, disq_reason, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_trust_score(ticker):
    conn = get_connection()
    row = conn.execute("SELECT * FROM trust_scores WHERE ticker=?", (ticker,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── SIGNALS ──────────────────────────────────────────────────────────────────

def save_signal(ticker, pattern, confidence, plain_english, recommendation,
                stop_loss_pct=None, time_horizon_days=None):
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO signals
           (ticker, pattern, confidence, plain_english, recommendation,
            stop_loss_pct, time_horizon_days, outcome)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
        (ticker, pattern, confidence, plain_english, recommendation,
         stop_loss_pct, time_horizon_days),
    )
    sig_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return sig_id


def get_signals(ticker=None):
    conn = get_connection()
    if ticker:
        rows = conn.execute(
            "SELECT * FROM signals WHERE ticker=? ORDER BY fired_at DESC", (ticker,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM signals ORDER BY fired_at DESC LIMIT 50"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_signal_accuracy(days=90):
    conn = get_connection()
    rows = conn.execute(
        """SELECT outcome, COUNT(*) as cnt FROM signals
           WHERE fired_at >= datetime('now', ?)
           AND outcome IN ('correct','incorrect')
           GROUP BY outcome""",
        (f"-{days} days",),
    ).fetchall()
    conn.close()
    data = {r["outcome"]: r["cnt"] for r in rows}
    total = data.get("correct", 0) + data.get("incorrect", 0)
    pct = round(data.get("correct", 0) / total * 100) if total > 0 else 0
    return {"correct": data.get("correct", 0), "incorrect": data.get("incorrect", 0),
            "total": total, "accuracy_pct": pct, "days": days}


# ── ALERTS ───────────────────────────────────────────────────────────────────

def create_alert(ticker, alert_type, message):
    conn = get_connection()
    # Skip if an identical alert (same ticker + message) was created in the last 24 hours.
    # Prevents duplicate rows when signals/portfolio checks fire repeatedly.
    existing = conn.execute(
        """SELECT 1 FROM alerts
           WHERE ticker=? AND message=?
           AND created_at >= datetime('now', '-24 hours')
           LIMIT 1""",
        (ticker, message),
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO alerts (ticker, alert_type, message) VALUES (?, ?, ?)",
            (ticker, alert_type, message),
        )
        conn.commit()
    conn.close()


def get_alerts():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM alerts ORDER BY is_read ASC, created_at DESC LIMIT 100"
    ).fetchall()
    conn.close()
    # Deduplicate in memory by (ticker, message): keep only the most-recent row
    # for each unique pair so legacy duplicate rows don't surface in the UI.
    seen = set()
    deduped = []
    for r in rows:
        d = dict(r)
        key = (d.get("ticker"), d.get("message"))
        if key not in seen:
            seen.add(key)
            deduped.append(d)
    return deduped


def mark_alert_read(alert_id):
    conn = get_connection()
    conn.execute("UPDATE alerts SET is_read=1 WHERE id=?", (alert_id,))
    conn.commit()
    conn.close()


def get_unread_alert_count():
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) as cnt FROM alerts WHERE is_read=0").fetchone()
    conn.close()
    return row["cnt"] if row else 0


# ── PRICE CACHE ───────────────────────────────────────────────────────────────

def save_price(ticker, price, change_pct, volume):
    conn = get_connection()
    conn.execute(
        """INSERT INTO price_cache (ticker, price, change_pct, volume, updated_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(ticker) DO UPDATE SET
             price=excluded.price, change_pct=excluded.change_pct,
             volume=excluded.volume, updated_at=excluded.updated_at""",
        (ticker, price, change_pct, volume, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_cached_price(ticker):
    conn = get_connection()
    row = conn.execute("SELECT * FROM price_cache WHERE ticker=?", (ticker,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── MARKET CACHE ──────────────────────────────────────────────────────────────

def save_market_value(key, value):
    conn = get_connection()
    conn.execute(
        """INSERT INTO market_cache (key, value, updated_at) VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
        (key, value, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_market_value(key):
    conn = get_connection()
    row = conn.execute("SELECT * FROM market_cache WHERE key=?", (key,)).fetchone()
    conn.close()
    return dict(row) if row else None


def clear_all_data():
    conn = get_connection()
    conn.execute("DELETE FROM portfolio")
    conn.execute("DELETE FROM watchlist")
    conn.execute("DELETE FROM signals")
    conn.execute("DELETE FROM alerts")
    conn.commit()
    conn.close()


# ── PICKS UNIVERSE ────────────────────────────────────────────────────────────

def get_picks_universe():
    conn = get_connection()
    rows = conn.execute(
        "SELECT ticker FROM picks_universe ORDER BY added_at DESC"
    ).fetchall()
    conn.close()
    return [r["ticker"] for r in rows]


def add_picks_universe(ticker: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO picks_universe (ticker) VALUES (?)", (ticker,)
    )
    conn.commit()
    conn.close()


def remove_picks_universe(ticker: str):
    conn = get_connection()
    conn.execute("DELETE FROM picks_universe WHERE ticker=?", (ticker,))
    conn.commit()
    conn.close()


def ticker_in_portfolio(ticker: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM portfolio WHERE ticker=? LIMIT 1", (ticker,)
    ).fetchone()
    conn.close()
    return row is not None


def ticker_in_watchlist(ticker: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM watchlist WHERE ticker=? LIMIT 1", (ticker,)
    ).fetchone()
    conn.close()
    return row is not None


# ── PRICE ALERTS ──────────────────────────────────────────────────────────────

def get_price_alerts(ticker=None):
    conn = get_connection()
    if ticker:
        rows = conn.execute(
            "SELECT * FROM price_alerts WHERE ticker=? ORDER BY created_at DESC", (ticker,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM price_alerts ORDER BY created_at DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_price_alert(ticker, alert_type, threshold=None, entry_low=None,
                       entry_high=None, alert_name=None):
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO price_alerts
           (ticker, alert_type, threshold, entry_low, entry_high, alert_name)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (ticker, alert_type, threshold, entry_low, entry_high, alert_name),
    )
    alert_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return alert_id


def delete_price_alert(alert_id):
    conn = get_connection()
    conn.execute("DELETE FROM price_alerts WHERE id=?", (alert_id,))
    conn.commit()
    conn.close()


def toggle_price_alert(alert_id, is_active):
    conn = get_connection()
    conn.execute("UPDATE price_alerts SET is_active=? WHERE id=?", (is_active, alert_id))
    conn.commit()
    conn.close()


def mark_price_alert_triggered(alert_id):
    conn = get_connection()
    conn.execute(
        "UPDATE price_alerts SET triggered_at=?, is_active=0 WHERE id=?",
        (datetime.utcnow().isoformat(), alert_id),
    )
    conn.commit()
    conn.close()


def recent_alert_exists(ticker: str, hours: int = 24) -> bool:
    """True if an alert for this ticker was created within the last N hours."""
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM alerts WHERE ticker=? AND created_at >= datetime('now', ?) LIMIT 1",
        (ticker, f"-{hours} hours"),
    ).fetchone()
    conn.close()
    return row is not None


# ── SMART PICKS CACHE ─────────────────────────────────────────────────────────

def get_picks_cache():
    """Return the latest smart picks cache row, or None if empty."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM smart_picks_cache ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def save_picks_cache(all_picks_json: str, sector_json: str,
                     tickers_scanned: int = 0, tickers_ok: int = 0):
    """Upsert the smart picks result (always a single row — overwrite on each scan)."""
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    existing = conn.execute("SELECT id FROM smart_picks_cache LIMIT 1").fetchone()
    if existing:
        conn.execute(
            """UPDATE smart_picks_cache SET
               all_picks_json=?, sector_json=?,
               scan_status='complete', scan_completed_at=?,
               tickers_scanned=?, tickers_ok=?, updated_at=?
               WHERE id=?""",
            (all_picks_json, sector_json, now, tickers_scanned, tickers_ok, now,
             existing["id"]),
        )
    else:
        conn.execute(
            """INSERT INTO smart_picks_cache
               (all_picks_json, sector_json, scan_status, scan_completed_at,
                tickers_scanned, tickers_ok, updated_at)
               VALUES (?, ?, 'complete', ?, ?, ?, ?)""",
            (all_picks_json, sector_json, now, tickers_scanned, tickers_ok, now),
        )
    conn.commit()
    conn.close()


def set_scan_status(status: str, started_at: str = None):
    """Update (or create) the scan_status field in smart_picks_cache."""
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    existing = conn.execute("SELECT id FROM smart_picks_cache LIMIT 1").fetchone()
    if existing:
        if started_at:
            conn.execute(
                "UPDATE smart_picks_cache SET scan_status=?, scan_started_at=? WHERE id=?",
                (status, started_at, existing["id"]),
            )
        else:
            conn.execute(
                "UPDATE smart_picks_cache SET scan_status=? WHERE id=?",
                (status, existing["id"]),
            )
    else:
        conn.execute(
            """INSERT INTO smart_picks_cache
               (all_picks_json, sector_json, scan_status, scan_started_at, updated_at)
               VALUES ('[]', '{}', ?, ?, ?)""",
            (status, started_at or now, now),
        )
    conn.commit()
    conn.close()


def get_scan_status():
    """Return current scan status metadata."""
    conn = get_connection()
    row = conn.execute(
        """SELECT scan_status, scan_started_at, scan_completed_at,
                  tickers_scanned, tickers_ok, updated_at,
                  progress_current, progress_total
           FROM smart_picks_cache ORDER BY id DESC LIMIT 1"""
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"scan_status": "idle", "scan_started_at": None,
            "scan_completed_at": None, "tickers_scanned": 0,
            "tickers_ok": 0, "updated_at": None,
            "progress_current": 0, "progress_total": 0}


def update_scan_progress(current: int, total: int):
    """Update live progress counters during a running scan."""
    conn = get_connection()
    existing = conn.execute("SELECT id FROM smart_picks_cache LIMIT 1").fetchone()
    if existing:
        conn.execute(
            "UPDATE smart_picks_cache SET progress_current=?, progress_total=? WHERE id=?",
            (current, total, existing["id"]),
        )
    conn.commit()
    conn.close()
