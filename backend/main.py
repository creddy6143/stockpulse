"""StockPulse FastAPI backend."""
import os
import sys
from pathlib import Path

# Ensure backend directory is in path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from database.models import init_db
from database import db
from data.fetcher import get_stock_price, get_market_data, get_fundamentals, get_analyst_data, get_stock_history
from data.india import get_india_signals, is_indian_stock
from intelligence.trust_score import get_trust_score_with_fallback
from intelligence.patterns import detect_all_patterns
from intelligence.claude_ai import get_verdict, generate_strategy_playbook
from intelligence.signals import evaluate_and_fire_signals
from portfolio.tracker import get_portfolio_with_pnl, get_watchlist_with_signals

app = FastAPI(title="StockPulse API", version="1.0.0")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")
ALLOWED_ORIGINS += ["http://localhost:3000", "http://localhost:3002", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


# ── HEALTH ───────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.delete("/api/reset")
def reset_all_data():
    """Clear all portfolio, watchlist, signals and alerts."""
    db.clear_all_data()
    return {"status": "cleared"}


# ── SEARCH ───────────────────────────────────────────────────────────────────

@app.get("/api/search")
def search_stocks(q: str = ""):
    """Search tickers by name or symbol."""
    if len(q.strip()) < 2:
        return []
    from data.fetcher import search_ticker
    return search_ticker(q.strip())


# ── MARKET ───────────────────────────────────────────────────────────────────

@app.get("/api/market")
def market():
    """VIX + 4 market indices + market status."""
    return get_market_data()


# ── PORTFOLIO ────────────────────────────────────────────────────────────────

class AddPositionRequest(BaseModel):
    ticker: str
    shares: float
    buy_price: float
    buy_date: Optional[str] = None
    notes: Optional[str] = None


class UpdatePositionRequest(BaseModel):
    shares: Optional[float] = None
    buy_price: Optional[float] = None
    notes: Optional[str] = None


@app.get("/api/portfolio")
def portfolio():
    """All portfolio positions with live P&L."""
    return get_portfolio_with_pnl()


@app.post("/api/portfolio")
def add_portfolio(req: AddPositionRequest):
    ticker = req.ticker.upper()
    price_data = get_stock_price(ticker)
    market = _detect_market(ticker)
    currency = "INR" if is_indian_stock(ticker) else "USD" if not ticker.endswith(".DE") else "EUR"
    db.upsert_stock(ticker, name=price_data.get("name"), market=market, currency=currency)
    db.add_position(ticker, req.shares, req.buy_price, req.buy_date, req.notes)
    return {"status": "added", "ticker": ticker}


@app.put("/api/portfolio/{pos_id}")
def update_portfolio(pos_id: int, req: UpdatePositionRequest):
    db.update_position(pos_id, req.shares, req.buy_price, req.notes)
    return {"status": "updated"}


@app.delete("/api/portfolio/all")
def clear_all_portfolio():
    """Remove all portfolio positions and watchlist entries. Must be before /{pos_id}."""
    db.clear_all_data()
    return {"status": "cleared"}


@app.delete("/api/portfolio/{pos_id}")
def delete_portfolio(pos_id: int):
    db.delete_position(pos_id)
    return {"status": "deleted"}


# ── WATCHLIST ────────────────────────────────────────────────────────────────

class WatchlistRequest(BaseModel):
    ticker: str
    notes: Optional[str] = None


@app.get("/api/watchlist")
def watchlist():
    return get_watchlist_with_signals()


@app.post("/api/watchlist")
def add_watchlist(req: WatchlistRequest):
    ticker = req.ticker.upper()
    price_data = get_stock_price(ticker)
    market = _detect_market(ticker)
    currency = "INR" if is_indian_stock(ticker) else "USD"
    db.upsert_stock(ticker, name=price_data.get("name"), market=market, currency=currency)
    db.add_to_watchlist(ticker, req.notes)
    return {"status": "added", "ticker": ticker}


@app.delete("/api/watchlist/{ticker}")
def remove_watchlist(ticker: str):
    db.remove_from_watchlist(ticker.upper())
    return {"status": "removed"}


# ── STOCK ────────────────────────────────────────────────────────────────────

@app.get("/api/stock/{ticker}")
def stock_full(ticker: str):
    """Full stock data: price + trust + signals + verdict."""
    ticker = ticker.upper()
    price_data = get_stock_price(ticker)
    fundamentals = get_fundamentals(ticker)
    trust = get_trust_score_with_fallback(ticker, price_data)
    patterns = detect_all_patterns(ticker, trust["total_score"], price_data, fundamentals)
    verdict = get_verdict(ticker, trust["total_score"], patterns, price_data, fundamentals)
    analyst = get_analyst_data(ticker)

    india_signals = {}
    if is_indian_stock(ticker):
        india_signals = get_india_signals(ticker)

    return {
        "ticker": ticker,
        "price_data": price_data,
        "fundamentals": fundamentals,
        "trust": trust,
        "patterns": patterns,
        "verdict": verdict,
        "analyst": analyst,
        "india_signals": india_signals,
    }


@app.get("/api/stock/{ticker}/trust")
def stock_trust(ticker: str):
    ticker = ticker.upper()
    price_data = get_stock_price(ticker)
    return get_trust_score_with_fallback(ticker, price_data)


@app.get("/api/stock/{ticker}/signals")
def stock_signals(ticker: str):
    return db.get_signals(ticker.upper())


@app.get("/api/stock/{ticker}/detail")
def stock_detail_full(ticker: str):
    """Full detail for StockDetail overlay: history, 52W, analyst, verdict, fundamentals."""
    ticker = ticker.upper()
    price_data = get_stock_price(ticker)
    fundamentals = get_fundamentals(ticker)
    trust = get_trust_score_with_fallback(ticker, price_data)
    analyst = get_analyst_data(ticker)
    patterns = detect_all_patterns(ticker, trust["total_score"], price_data, fundamentals)
    verdict = get_verdict(ticker, trust["total_score"], patterns, price_data, fundamentals)
    history = get_stock_history(ticker)

    india_signals = {}
    if is_indian_stock(ticker):
        india_signals = get_india_signals(ticker)

    return {
        "ticker": ticker,
        "price_data": price_data,
        "fundamentals": fundamentals,
        "trust": trust,
        "analyst": analyst,
        "verdict": verdict,
        "history": history,
        "india_signals": india_signals,
    }


@app.get("/api/stock/{ticker}/verdict")
def stock_verdict(ticker: str):
    ticker = ticker.upper()
    price_data = get_stock_price(ticker)
    fundamentals = get_fundamentals(ticker)
    trust = get_trust_score_with_fallback(ticker, price_data)
    patterns = detect_all_patterns(ticker, trust["total_score"], price_data, fundamentals)
    return get_verdict(ticker, trust["total_score"], patterns, price_data, fundamentals)


# ── ALERTS ───────────────────────────────────────────────────────────────────

@app.get("/api/alerts")
def alerts():
    return db.get_alerts()


@app.put("/api/alerts/{alert_id}/read")
def mark_read(alert_id: int):
    db.mark_alert_read(alert_id)
    return {"status": "read"}


# ── SMART PICKS ───────────────────────────────────────────────────────────────

@app.get("/api/picks")
def picks():
    """AI-generated smart picks — stocks with trust >= 75."""
    portfolio = db.get_portfolio()
    watchlist = db.get_watchlist()
    all_tickers = list({p["ticker"] for p in portfolio} | {w["ticker"] for w in watchlist})

    result = []
    for ticker in all_tickers:
        price_data = get_stock_price(ticker)
        trust = get_trust_score_with_fallback(ticker, price_data)
        if trust["total_score"] >= 75 and not trust["auto_disqualified"]:
            fundamentals = get_fundamentals(ticker)
            patterns = detect_all_patterns(ticker, trust["total_score"], price_data, fundamentals)
            verdict = get_verdict(ticker, trust["total_score"], patterns, price_data, fundamentals)
            result.append({
                "ticker": ticker,
                "name": price_data.get("name", ticker),
                "price": price_data.get("price", 0),
                "trust": trust,
                "verdict": verdict,
                "patterns": patterns,
            })

    result.sort(key=lambda x: x["trust"]["total_score"], reverse=True)
    return result


@app.get("/api/picks/disqualified")
def picks_disqualified():
    """Auto-disqualified stocks."""
    portfolio = db.get_portfolio()
    watchlist = db.get_watchlist()
    all_tickers = list({p["ticker"] for p in portfolio} | {w["ticker"] for w in watchlist})

    result = []
    for ticker in all_tickers:
        price_data = get_stock_price(ticker)
        trust = get_trust_score_with_fallback(ticker, price_data)
        if trust["auto_disqualified"]:
            result.append({
                "ticker": ticker,
                "trust_score": trust["total_score"],
                "reason": trust["disqualify_reason"],
            })
    return result


# ── ACCURACY ──────────────────────────────────────────────────────────────────

@app.get("/api/accuracy")
def accuracy():
    return db.get_signal_accuracy(days=90)


# ── STRATEGY ─────────────────────────────────────────────────────────────────

@app.get("/api/strategy")
def strategy():
    """Strategy situations for all stocks."""
    market_data = get_market_data()
    portfolio_data = get_portfolio_with_pnl()
    watchlist_data = get_watchlist_with_signals()

    my_stocks = []
    for pos in portfolio_data.get("positions", []):
        sit = _detect_situation(pos, market_data)
        if sit:
            playbook = generate_strategy_playbook(
                sit["situation_type"], pos["ticker"], pos, market_data
            )
            my_stocks.append({
                "ticker": pos["ticker"],
                "flag": _get_flag(pos.get("market", "US")),
                "situation_type": sit["situation_type"],
                "label": sit["label"],
                "icon": sit["icon"],
                "action": sit["action"],
                "color": sit["color"],
                "summary": sit["summary"],
                "playbook": playbook,
                "priority": sit["priority"],
            })

    wl_situations = []
    for item in watchlist_data:
        sit = _detect_wl_situation(item, market_data)
        if sit:
            playbook = generate_strategy_playbook(
                sit["situation_type"], item["ticker"], item, market_data
            )
            wl_situations.append({
                "ticker": item["ticker"],
                "flag": _get_flag(item.get("market", "US")),
                "situation_type": sit["situation_type"],
                "label": sit["label"],
                "icon": sit["icon"],
                "action": sit["action"],
                "color": sit["color"],
                "summary": sit["summary"],
                "playbook": playbook,
                "priority": sit["priority"],
            })

    my_stocks.sort(key=lambda x: x["priority"])
    wl_situations.sort(key=lambda x: x["priority"])
    total = len(my_stocks) + len(wl_situations)

    return {
        "total_situations": total,
        "my_stocks": my_stocks,
        "watchlist": wl_situations,
        "smart_picks": [],
    }


# ── EARNINGS ─────────────────────────────────────────────────────────────────

@app.get("/api/earnings")
def earnings():
    """Earnings calendar for portfolio + watchlist stocks."""
    portfolio = db.get_portfolio()
    result = []
    for pos in portfolio:
        ticker = pos["ticker"]
        fundamentals = get_fundamentals(ticker)
        next_date = fundamentals.get("next_earnings_date")
        if next_date:
            price_data = get_stock_price(ticker)
            result.append({
                "ticker": ticker,
                "name": pos.get("name", ticker),
                "next_earnings_date": next_date,
                "eps_estimate": fundamentals.get("earnings_history", [{}])[0].get("estimate") if fundamentals.get("earnings_history") else None,
                "in_portfolio": True,
                "shares": pos["shares"],
                "buy_price": pos["buy_price"],
                "current_price": price_data.get("price", 0),
            })
    return result


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _detect_market(ticker: str) -> str:
    if ticker.endswith(".NS") or ticker.endswith(".BO"):
        return "IN"
    if ticker.endswith(".DE") or ticker.endswith(".AS") or ticker.endswith(".PA"):
        return "EU"
    return "US"


def _get_flag(market: str) -> str:
    return {"US": "🇺🇸", "EU": "🇪🇺", "IN": "🇮🇳"}.get(market, "🇺🇸")


def _detect_situation(pos: dict, market_data: dict) -> Optional[dict]:
    pnl_pct = pos.get("pnl_pct", 0)
    trust = pos.get("trust_score", 50)
    auto_disq = pos.get("auto_disqualified", False)

    if auto_disq:
        return {
            "situation_type": "exit_now", "label": "Exit Required", "icon": "🚨",
            "action": "EXIT", "color": "var(--rose)", "priority": 0,
            "summary": f"Auto-disqualified. {pos.get('disqualify_reason', 'Exit now.')}",
        }
    if pnl_pct < -30:
        return {
            "situation_type": "crash_decision", "label": "Crash Decision", "icon": "📉",
            "action": "HOLD" if trust >= 60 else "SELL", "color": "var(--amber)", "priority": 2,
            "summary": f"Down {abs(pnl_pct):.0f}%. {'Business still intact.' if trust >= 60 else 'Fundamentals weak — consider exit.'}",
        }
    if pnl_pct > 30:
        return {
            "situation_type": "profit_decision", "label": "Profit Decision", "icon": "💰",
            "action": "HOLD", "color": "var(--emerald)", "priority": 3,
            "summary": f"Up {pnl_pct:.0f}%. Consider trimming to lock in gains.",
        }
    return None


def _detect_wl_situation(item: dict, market_data: dict) -> Optional[dict]:
    trust = item.get("trust_score", 50)
    wl_group = item.get("wl_group", "watching")

    if wl_group == "ready":
        return {
            "situation_type": "ready_to_buy", "label": "Ready to Buy", "icon": "🟢",
            "action": "BUY", "color": "var(--emerald)", "priority": 1,
            "summary": f"Trust {trust}. Entry conditions aligned.",
        }
    if wl_group == "avoid":
        return {
            "situation_type": "dont_buy", "label": "Don't Buy Yet", "icon": "🔴",
            "action": "WAIT", "color": "var(--rose)", "priority": 3,
            "summary": f"Trust {trust}. Red flags present.",
        }
    return None


def _seed_demo_data():
    """Seeds demo portfolio data only when SEED_DEMO_DATA=true env var is set."""
    if os.getenv("SEED_DEMO_DATA", "").lower() != "true":
        return
    existing = db.get_portfolio()
    if existing:
        return

    demo_stocks = [
        ("TNXP", "Tonix Pharma", "US", "NASDAQ", "USD"),
        ("XGN",  "Exagen Inc",   "US", "NASDAQ", "USD"),
        ("GRRR", "Gorilla Technology", "US", "NASDAQ", "USD"),
        ("INSM", "Insmed Inc",   "US", "NASDAQ", "USD"),
        ("CVNA", "Carvana Co",   "US", "NYSE",   "USD"),
        ("NVDA", "NVIDIA Corp",  "US", "NASDAQ", "USD"),
        ("AXON", "Axon Enterprise","US","NASDAQ","USD"),
        ("PLTR", "Palantir",     "US", "NYSE",   "USD"),
        ("MSFT", "Microsoft",    "US", "NASDAQ", "USD"),
        ("ASML.AS","ASML Holding","EU","AMS",    "EUR"),
        ("HDFCBANK.NS","HDFC Bank","IN","NSE",   "INR"),
        ("RELIANCE.NS","Reliance Industries","IN","NSE","INR"),
    ]
    for t, name, mkt, exch, cur in demo_stocks:
        db.upsert_stock(t, name, mkt, exch, cur)

    # Portfolio positions
    positions = [
        ("TNXP", 107, 46.0),
        ("XGN",  50,  10.50),
        ("GRRR", 100, 41.0),
        ("INSM", 10,  115.0),
        ("CVNA", 15,  90.0),
        ("NVDA", 5,   420.0),
        ("AXON", 8,   245.0),
        ("PLTR", 50,  18.0),
        ("MSFT", 3,   380.0),
        ("ASML.AS", 2, 820.0),
        ("HDFCBANK.NS", 10, 1400.0),
        ("RELIANCE.NS", 5, 2400.0),
    ]
    for ticker, shares, buy_price in positions:
        db.add_position(ticker, shares, buy_price)

    # Watchlist
    watchlist = ["AXON", "NVDA", "ASML.AS", "HDFCBANK.NS", "TSLA"]
    for ticker in watchlist:
        db.add_to_watchlist(ticker)

    # Demo alerts
    db.create_alert("XGN",  "urgent", "⚡ Pre-market +13% — board resigned before earnings. Exit window open NOW.")
    db.create_alert("TNXP", "urgent", "Auto-disqualified: 8 reverse splits. Do not hold through earnings today.")
    db.create_alert("NVDA", "signal", "AI supercycle intact. Revenue +122% YoY. Hold with trailing stop.")
    db.create_alert("AXON", "signal", "CEO bought $1.2M own money. Entry zone $285-310 active.")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
