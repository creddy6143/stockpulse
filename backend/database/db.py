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
    return [dict(r) for r in rows]


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
