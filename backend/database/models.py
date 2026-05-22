import sqlite3
import os

# If Railway (or any host) has mounted a persistent volume at /data,
# always use it — this takes priority over the DATABASE_PATH env var.
# Without this, DATABASE_PATH=./stockpulse.db in .env overrides the
# smart detection and all data is lost on every container restart.
if os.path.isdir("/data"):
    DATABASE_PATH = "/data/stockpulse.db"
else:
    DATABASE_PATH = os.getenv("DATABASE_PATH", "./stockpulse.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS stocks (
  id INTEGER PRIMARY KEY,
  ticker TEXT UNIQUE NOT NULL,
  name TEXT,
  market TEXT,
  exchange TEXT,
  currency TEXT,
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS portfolio (
  id INTEGER PRIMARY KEY,
  ticker TEXT NOT NULL,
  shares REAL NOT NULL,
  buy_price REAL NOT NULL,
  buy_date DATE,
  notes TEXT,
  FOREIGN KEY (ticker) REFERENCES stocks(ticker)
);

CREATE TABLE IF NOT EXISTS watchlist (
  id INTEGER PRIMARY KEY,
  ticker TEXT NOT NULL,
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  notes TEXT,
  FOREIGN KEY (ticker) REFERENCES stocks(ticker)
);

CREATE TABLE IF NOT EXISTS trust_scores (
  ticker TEXT PRIMARY KEY,
  total_score INTEGER,
  business_score INTEGER,
  smart_money_score INTEGER,
  momentum_score INTEGER,
  grade TEXT,
  auto_disqualified BOOLEAN DEFAULT FALSE,
  disqualify_reason TEXT,
  calculated_at TIMESTAMP,
  FOREIGN KEY (ticker) REFERENCES stocks(ticker)
);

CREATE TABLE IF NOT EXISTS signals (
  id INTEGER PRIMARY KEY,
  ticker TEXT NOT NULL,
  pattern TEXT NOT NULL,
  confidence REAL,
  plain_english TEXT,
  recommendation TEXT,
  stop_loss_pct REAL,
  time_horizon_days INTEGER,
  fired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  resolved_at TIMESTAMP,
  outcome TEXT,
  FOREIGN KEY (ticker) REFERENCES stocks(ticker)
);

CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY,
  ticker TEXT,
  alert_type TEXT,
  message TEXT,
  is_read BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS price_cache (
  ticker TEXT PRIMARY KEY,
  price REAL,
  change_pct REAL,
  volume REAL,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_cache (
  key TEXT PRIMARY KEY,
  value REAL,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS picks_universe (
  id INTEGER PRIMARY KEY,
  ticker TEXT UNIQUE NOT NULL,
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS price_alerts (
  id INTEGER PRIMARY KEY,
  ticker TEXT NOT NULL,
  alert_name TEXT,
  alert_type TEXT NOT NULL,
  threshold REAL,
  entry_low REAL,
  entry_high REAL,
  is_active BOOLEAN DEFAULT TRUE,
  triggered_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS smart_picks_cache (
  id INTEGER PRIMARY KEY,
  all_picks_json TEXT NOT NULL DEFAULT '[]',
  sector_json TEXT NOT NULL DEFAULT '{}',
  scan_status TEXT NOT NULL DEFAULT 'idle',
  scan_started_at TIMESTAMP,
  scan_completed_at TIMESTAMP,
  tickers_scanned INTEGER DEFAULT 0,
  tickers_ok INTEGER DEFAULT 0,
  progress_current INTEGER DEFAULT 0,
  progress_total INTEGER DEFAULT 0,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA)
    # Safe migrations for existing databases — ALTER TABLE IF NOT EXISTS is not
    # supported in older SQLite, so we catch the "duplicate column" error instead.
    for col, typedef in [
        ("progress_current", "INTEGER DEFAULT 0"),
        ("progress_total",   "INTEGER DEFAULT 0"),
    ]:
        try:
            conn.execute(
                f"ALTER TABLE smart_picks_cache ADD COLUMN {col} {typedef}"
            )
        except Exception:
            pass  # column already exists
    conn.commit()
    conn.close()
