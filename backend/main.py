"""StockPulse FastAPI backend."""
import os
import sys
import time as _time
from pathlib import Path

# Ensure backend directory is in path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from database.models import init_db
from database import db
from data.fetcher import get_stock_price, get_market_data, get_fundamentals, get_analyst_data, get_stock_history, get_news, get_insider_data
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


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    t0 = _time.monotonic()
    response = await call_next(request)
    elapsed = _time.monotonic() - t0
    ms = int(elapsed * 1000)
    response.headers["X-Response-Time"] = f"{ms}ms"
    # Log slow requests (>1s) so Railway logs show the bottlenecks
    if elapsed > 1.0:
        print(f"[SLOW] {request.method} {request.url.path} → {ms}ms", flush=True)
    return response


@app.on_event("startup")
def startup():
    init_db()


# ── HEALTH ───────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/ping")
def ping():
    """Keep-alive endpoint — frontend pings every 10 min to prevent Railway sleep."""
    return {"ok": True}


@app.delete("/api/reset")
def reset_all_data():
    """Clear all portfolio, watchlist, signals and alerts."""
    db.clear_all_data()
    return {"status": "cleared"}


@app.post("/api/cache/clear")
def clear_data_cache():
    """Clear in-memory data cache — forces fresh data fetch for all stocks.
    Use this after deploying fixes to get updated trust scores immediately.
    """
    from data.cache import clear_cache
    clear_cache()
    return {"status": "cache cleared"}


# ── SEARCH ───────────────────────────────────────────────────────────────────

@app.get("/api/rates")
def exchange_rates():
    """Live exchange rates: SEK per 1 USD/EUR/INR. Cached 15 min."""
    from data.fetcher import get_exchange_rates
    return get_exchange_rates()


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
    already_exists = db.ticker_in_portfolio(ticker)
    price_data = get_stock_price(ticker)
    market = _detect_market(ticker)
    # For tickers without exchange suffix, use price currency to infer market.
    # e.g. user types "INFY" (NYSE ADR, USD) vs "INFY.NS" (NSE India, INR).
    if "." not in ticker:
        pc = (price_data.get("currency") or "").upper()
        if pc == "INR":
            market = "IN"
        elif pc in ("EUR", "SEK"):
            market = "EU"
    from portfolio.tracker import _detect_currency
    currency = _detect_currency(ticker) or price_data.get("currency", "USD")
    db.upsert_stock(ticker, name=price_data.get("name"), market=market, currency=currency)
    db.add_position(ticker, req.shares, req.buy_price, req.buy_date, req.notes)
    return {"status": "added", "ticker": ticker, "already_had_position": already_exists}


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
    already_exists = db.ticker_in_watchlist(ticker)
    price_data = get_stock_price(ticker)
    market = _detect_market(ticker)
    if "." not in ticker:
        pc = (price_data.get("currency") or "").upper()
        if pc == "INR":
            market = "IN"
        elif pc in ("EUR", "SEK"):
            market = "EU"
    from portfolio.tracker import _detect_currency
    currency = _detect_currency(ticker) or price_data.get("currency", "USD")
    db.upsert_stock(ticker, name=price_data.get("name"), market=market, currency=currency)
    db.add_to_watchlist(ticker, req.notes)
    return {"status": "added", "ticker": ticker, "already_exists": already_exists}


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
    trust_score_val = trust["total_score"] or 0  # None → 0 for downstream callers
    patterns = detect_all_patterns(ticker, trust_score_val, price_data, fundamentals)
    verdict = get_verdict(ticker, trust_score_val, patterns, price_data, fundamentals)
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
    """Fast detail — price, history, fundamentals, analyst, trust, news. No AI call."""
    ticker = ticker.upper()
    price_data = get_stock_price(ticker)
    fundamentals = get_fundamentals(ticker)
    trust = get_trust_score_with_fallback(ticker, price_data)
    analyst = get_analyst_data(ticker)
    history = get_stock_history(ticker)
    news = get_news(ticker, days=7)

    india_signals = {}
    if is_indian_stock(ticker):
        india_signals = get_india_signals(ticker)

    return {
        "ticker": ticker,
        "price_data": price_data,
        "fundamentals": fundamentals,
        "trust": trust,
        "analyst": analyst,
        "history": history,
        "india_signals": india_signals,
        "news": [{"headline": n.get("headline",""), "url": n.get("url",""), "source": n.get("source",""), "datetime": n.get("datetime",0)} for n in (news or [])[:8]],
    }


@app.get("/api/stock/{ticker}/verdict")
def stock_verdict(ticker: str):
    ticker = ticker.upper()
    price_data = get_stock_price(ticker)
    fundamentals = get_fundamentals(ticker)
    trust = get_trust_score_with_fallback(ticker, price_data)
    trust_score_val = trust["total_score"] or 0
    patterns = detect_all_patterns(ticker, trust_score_val, price_data, fundamentals)
    return get_verdict(ticker, trust_score_val, patterns, price_data, fundamentals)


# ── ALERTS ───────────────────────────────────────────────────────────────────

@app.get("/api/alerts")
def alerts():
    return db.get_alerts()


@app.put("/api/alerts/{alert_id}/read")
def mark_read(alert_id: int):
    db.mark_alert_read(alert_id)
    return {"status": "read"}


# ── SMART PICKS ───────────────────────────────────────────────────────────────

# Curated high-quality universe scanned every day for best picks
_CURATED_UNIVERSE = [
    "AXON","NVDA","MSFT","AAPL","AMZN","META","GOOGL","TSLA","AVGO","AMD",
    "CRWD","PLTR","SNOW","NET","DDOG","MNDY","ZS","HUBS","TTD","CELH",
    "LLY","ABBV","ISRG","DXCM","ALGN","PAYC","PCTY","TMDX","RXRX","CLOV",
]

from data.cache import cache_get as _cache_get, cache_set as _cache_set, TTL_STRATEGY

def _score_one_ticker(ticker: str) -> dict | None:
    """Evaluate one ticker and return a picks entry if it qualifies."""
    try:
        price_data = get_stock_price(ticker)
        if not price_data.get("price"):
            return None
        trust = get_trust_score_with_fallback(ticker, price_data)
        if trust["auto_disqualified"] or trust["total_score"] is None:
            return None
        fundamentals = get_fundamentals(ticker)
        change_pct = float(price_data.get("change_pct", 0) or 0)
        trust_score_val = trust["total_score"]
        # Buy-the-dip: quality stock down on market fear (not company news)
        is_dip = (trust_score_val >= 65 and change_pct <= -4
                  and not trust.get("disqualify_reason"))
        qualifies = trust_score_val >= 75 or is_dip
        if not qualifies:
            return None
        patterns = detect_all_patterns(ticker, trust_score_val, price_data, fundamentals)
        verdict = get_verdict(ticker, trust_score_val, patterns, price_data, fundamentals)
        return {
            "ticker": ticker,
            "name": price_data.get("name", ticker),
            "price": price_data.get("price", 0),
            "change_pct": change_pct,
            "trust": trust,
            "verdict": verdict,
            "patterns": patterns,
            "is_dip": is_dip,
        }
    except Exception:
        return None


@app.get("/api/picks")
def picks():
    """AI-generated smart picks — trust >= 75 OR quality buy-the-dip opportunity.
    Scans portfolio + watchlist + user picks universe + curated universe.
    Result cached 30 min; verdict caching (1hr) keeps AI calls minimal.
    """
    from data.cache import cache_get as cg, cache_set as cs, TTL_STRATEGY
    cached = cg("picks:result", 60 * 60)  # 60 min cache — prevents result churn on refresh
    if cached is not None:
        return cached

    portfolio = db.get_portfolio()
    watchlist = db.get_watchlist()
    user_universe = db.get_picks_universe()
    all_tickers = list(
        {p["ticker"] for p in portfolio}
        | {w["ticker"] for w in watchlist}
        | set(user_universe)
        | set(_CURATED_UNIVERSE)
    )

    result = []
    for ticker in all_tickers:
        entry = _score_one_ticker(ticker)
        if entry:
            result.append(entry)

    # Sort: high trust first, then alphabetically by ticker for deterministic order.
    # Deterministic sort prevents results from changing on every refresh when scores tie.
    dips = [r for r in result if r["is_dip"]]
    highs = [r for r in result if not r["is_dip"]]
    highs.sort(key=lambda x: (-(x["trust"]["total_score"] or 0), x["ticker"]))
    dips.sort(key=lambda x: x["ticker"])
    final = highs + dips
    # Exclude stocks already in portfolio — picks are for discovery, not review of owned stocks
    portfolio_tickers = {p["ticker"] for p in portfolio}
    final = [r for r in final if r["ticker"] not in portfolio_tickers]
    cs("picks:result", final)
    return final


@app.get("/api/picks/disqualified")
def picks_disqualified():
    """Auto-disqualified stocks from portfolio + watchlist + picks universe."""
    portfolio = db.get_portfolio()
    watchlist = db.get_watchlist()
    user_universe = db.get_picks_universe()
    all_tickers = list(
        {p["ticker"] for p in portfolio}
        | {w["ticker"] for w in watchlist}
        | set(user_universe)
    )

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


# ── PICKS UNIVERSE (user-curated) ─────────────────────────────────────────────

class PicksUniverseRequest(BaseModel):
    ticker: str


@app.get("/api/picks/universe")
def get_picks_universe():
    return db.get_picks_universe()


@app.post("/api/picks/universe")
def add_picks_universe(req: PicksUniverseRequest):
    ticker = req.ticker.upper()
    price_data = get_stock_price(ticker)
    market = _detect_market(ticker)
    from portfolio.tracker import _detect_currency
    currency = _detect_currency(ticker)
    db.upsert_stock(ticker, name=price_data.get("name"), market=market, currency=currency)
    db.add_picks_universe(ticker)
    from data.cache import cache_set as cs
    cs("picks:result", None)  # Invalidate picks cache
    return {"status": "added", "ticker": ticker}


@app.delete("/api/picks/universe/{ticker}")
def remove_picks_universe(ticker: str):
    db.remove_picks_universe(ticker.upper())
    from data.cache import cache_set as cs
    cs("picks:result", None)  # Invalidate picks cache
    return {"status": "removed"}


# ── ACCURACY ──────────────────────────────────────────────────────────────────

@app.get("/api/accuracy")
def accuracy():
    return db.get_signal_accuracy(days=90)


# ── STRATEGY ─────────────────────────────────────────────────────────────────

@app.get("/api/strategy")
def strategy():
    """Strategy situations — returns metadata instantly (NO AI calls).
    Playbooks are fetched on-demand via /api/strategy/{ticker}/playbook.
    This endpoint typically returns in <500ms.
    """
    market_data = get_market_data()
    portfolio_data = get_portfolio_with_pnl()
    watchlist_data = get_watchlist_with_signals()

    my_stocks = []
    for pos in portfolio_data.get("positions", []):
        sit = _detect_situation(pos, market_data)
        my_stocks.append({
            "ticker": pos["ticker"],
            "flag": _get_flag(pos.get("market", "US")),
            "situation_type": sit["situation_type"],
            "label": sit["label"],
            "icon": sit["icon"],
            "action": sit["action"],
            "color": sit["color"],
            "summary": sit["summary"],
            "priority": sit["priority"],
            "playbook": None,
            # Full context — used by playbook endpoint + frontend display
            "name": pos.get("name", pos["ticker"]),
            "current_price": pos.get("current_price", 0),
            "change_pct": pos.get("change_pct", 0),
            "pnl_pct": pos.get("pnl_pct", 0),
            "pnl_sek": pos.get("pnl_sek", 0),
            "shares": pos.get("shares"),
            "buy_price": pos.get("buy_price"),
            "trust_score": pos.get("trust_score", 50),
            "grade": pos.get("grade", ""),
            "is_speculative": pos.get("is_speculative", False),
        })

    wl_situations = []
    for item in watchlist_data:
        sit = _detect_wl_situation(item, market_data)
        wl_situations.append({
            "ticker": item["ticker"],
            "flag": _get_flag(item.get("market", "US")),
            "situation_type": sit["situation_type"],
            "label": sit["label"],
            "icon": sit["icon"],
            "action": sit["action"],
            "color": sit["color"],
            "summary": sit["summary"],
            "priority": sit["priority"],
            "playbook": None,
            "name": item.get("name", item["ticker"]),
            "current_price": item.get("current_price", 0),
            "change_pct": item.get("change_pct", 0),
            "trust_score": item.get("trust_score", 50),
            "grade": item.get("grade", ""),
            "is_speculative": item.get("is_speculative", False),
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


class PlaybookRequest(BaseModel):
    situation_type: str
    # Stock data snapshot to give AI context
    current_price: Optional[float] = None
    change_pct: Optional[float] = None
    trust_score: Optional[int] = None
    grade: Optional[str] = None
    business_score: Optional[int] = None
    smart_money_score: Optional[int] = None
    momentum_score: Optional[int] = None
    pnl_pct: Optional[float] = None
    pnl_sek: Optional[float] = None
    shares: Optional[float] = None
    buy_price: Optional[float] = None
    name: Optional[str] = None
    is_speculative: Optional[bool] = False


@app.post("/api/strategy/{ticker}/playbook")
def strategy_playbook(ticker: str, req: PlaybookRequest):
    """Generate AI playbook for a specific stock situation — on-demand, cached 2hrs.
    Called when user taps a Strategy card. Enriches AI with news, analyst,
    insider data, and fundamentals.
    """
    ticker = ticker.upper()
    market_data = get_market_data()

    # All data fetched from cache (already populated by portfolio/watchlist load)
    fundamentals = get_fundamentals(ticker)
    analyst = get_analyst_data(ticker)
    insider = get_insider_data(ticker)
    news = get_news(ticker, days=7)

    # Build stock_data dict from request + cached data
    stock_data = {
        "ticker": ticker,
        "name": req.name or ticker,
        "current_price": req.current_price or 0,
        "change_pct": req.change_pct or 0,
        "trust_score": req.trust_score or 50,
        "grade": req.grade or "Moderate",
        "business_score": req.business_score or 0,
        "smart_money_score": req.smart_money_score or 0,
        "momentum_score": req.momentum_score or 0,
        "pnl_pct": req.pnl_pct,
        "pnl_sek": req.pnl_sek,
        "shares": req.shares,
        "buy_price": req.buy_price,
        "is_speculative": req.is_speculative or False,
    }

    playbook = generate_strategy_playbook(
        situation_type=req.situation_type,
        ticker=ticker,
        stock_data=stock_data,
        market_data=market_data,
        fundamentals=fundamentals,
        analyst=analyst,
        insider=insider,
        news=news,
    )
    return {"ticker": ticker, "playbook": playbook}


# ── EARNINGS ─────────────────────────────────────────────────────────────────

@app.get("/api/earnings")
def earnings():
    """Earnings calendar for portfolio + watchlist stocks with analyst consensus."""
    portfolio = db.get_portfolio()
    watchlist_items = db.get_watchlist()
    result = []
    seen = set()

    all_items = [(pos, True) for pos in portfolio] + [(w, False) for w in watchlist_items]

    for item, in_portfolio in all_items:
        ticker = item["ticker"]
        if ticker in seen:
            continue
        seen.add(ticker)
        fundamentals = get_fundamentals(ticker)
        next_date = fundamentals.get("next_earnings_date")
        if not next_date:
            continue
        price_data = get_stock_price(ticker)
        analyst = get_analyst_data(ticker)
        history = fundamentals.get("earnings_history") or []
        last = history[0] if history else {}
        entry = {
            "ticker": ticker,
            "name": item.get("name", ticker),
            "next_earnings_date": next_date,
            "eps_estimate": last.get("estimate"),
            "eps_actual_last": last.get("actual"),
            "revenue_estimate": analyst.get("revenue_estimate"),
            "analyst_buy": analyst.get("buy_count", 0),
            "analyst_hold": analyst.get("hold_count", 0),
            "analyst_sell": analyst.get("sell_count", 0),
            "analyst_target": analyst.get("target_price"),
            "earnings_history": history[:4],
            "in_portfolio": in_portfolio,
            "shares": item.get("shares"),
            "buy_price": item.get("buy_price"),
            "current_price": price_data.get("price", 0),
        }
        result.append(entry)

    # Today's earnings first
    result.sort(key=lambda x: (x["next_earnings_date"] != "Today", x["next_earnings_date"] or ""))
    return result


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _detect_market(ticker: str) -> str:
    if ticker.endswith(".NS") or ticker.endswith(".BO"):
        return "IN"
    if any(ticker.endswith(s) for s in [".DE", ".AS", ".PA", ".ST", ".F", ".MI", ".L", ".MC", ".BR"]):
        return "EU"
    return "US"


def _get_flag(market: str) -> str:
    return {"US": "🇺🇸", "EU": "🇪🇺", "IN": "🇮🇳"}.get(market, "🇺🇸")


def _detect_situation(pos: dict, market_data: dict) -> dict:
    """Always returns a situation — every portfolio stock gets a strategy card."""
    pnl_pct = pos.get("pnl_pct", 0) or 0
    raw_trust = pos.get("trust_score")          # may be None for Data Unavailable
    trust = raw_trust if raw_trust is not None else 50
    auto_disq = pos.get("auto_disqualified", False)
    grade = pos.get("grade", "")
    trust_str = f"{trust}/100" if raw_trust is not None else "No Data"

    if auto_disq:
        return {
            "situation_type": "exit_now", "label": "Exit Required", "icon": "🚨",
            "action": "EXIT", "color": "var(--rose)", "priority": 0,
            "summary": f"Auto-disqualified. {pos.get('disqualify_reason', 'Exit now.')}",
        }
    if grade == "Data Unavailable":
        return {
            "situation_type": "no_data", "label": "No Data", "icon": "❓",
            "action": "HOLD", "color": "var(--t2)", "priority": 3,
            "summary": f"No fundamental data available for this exchange. P&L {pnl_pct:+.0f}%. Price tracking is active.",
        }
    if pnl_pct < -30:
        return {
            "situation_type": "crash_decision", "label": "Crash Decision", "icon": "📉",
            "action": "HOLD" if trust >= 60 else "REVIEW", "color": "var(--amber)", "priority": 1,
            "summary": f"Down {abs(pnl_pct):.0f}% from your entry. {'Business fundamentals still intact — hold.' if trust >= 60 else f'Trust score {trust_str}. Review recent reports before deciding.'}",
        }
    if pnl_pct > 30:
        return {
            "situation_type": "profit_decision", "label": "Profit Decision", "icon": "💰",
            "action": "HOLD", "color": "var(--emerald)", "priority": 2,
            "summary": f"Up {pnl_pct:.0f}% from entry. Consider trimming to lock in gains.",
        }
    if trust < 40:
        return {
            "situation_type": "weak_fundamentals", "label": "Weak Signal", "icon": "⚠️",
            "action": "REVIEW", "color": "var(--amber)", "priority": 2,
            "summary": f"Trust score {trust_str} ({grade}). Review fundamentals before holding further.",
        }
    if -10 <= pnl_pct <= 10:
        return {
            "situation_type": "monitor", "label": "On Track", "icon": "👁",
            "action": "HOLD", "color": "var(--indigo)", "priority": 3,
            "summary": f"Trust {trust_str}. P&L {pnl_pct:+.0f}%. No action required — monitoring.",
        }
    if pnl_pct < -10:
        return {
            "situation_type": "mild_loss", "label": "Under Pressure", "icon": "📉",
            "action": "HOLD" if trust >= 60 else "REVIEW", "color": "var(--amber)", "priority": 2,
            "summary": f"Down {abs(pnl_pct):.0f}%. Trust {trust_str}. {'Hold — fundamentals intact.' if trust >= 60 else 'Review position carefully.'}",
        }
    return {
        "situation_type": "monitor", "label": "Holding Well", "icon": "✅",
        "action": "HOLD", "color": "var(--emerald)", "priority": 3,
        "summary": f"Up {pnl_pct:.0f}%. Trust {trust_str}. Holding well — no action needed.",
    }


def _detect_wl_situation(item: dict, market_data: dict) -> dict:
    """Always returns a situation — every watchlist stock gets a strategy card."""
    raw_trust = item.get("trust_score")         # may be None for Data Unavailable
    trust = raw_trust if raw_trust is not None else 50
    trust_str = f"{trust}/100" if raw_trust is not None else "No Data"
    wl_group = item.get("wl_group", "watching")
    upside = item.get("analyst_upside_pct")
    grade = item.get("grade", "")

    if grade == "Data Unavailable":
        return {
            "situation_type": "no_data", "label": "No Data", "icon": "❓",
            "action": "WAIT", "color": "var(--t2)", "priority": 3,
            "summary": "No fundamental data available for this exchange. Price tracking is active.",
        }
    if wl_group == "ready":
        return {
            "situation_type": "ready_to_buy", "label": "Ready to Buy", "icon": "🟢",
            "action": "BUY", "color": "var(--emerald)", "priority": 1,
            "summary": f"Trust {trust_str}. Entry conditions aligned — consider buying now.",
        }
    if wl_group == "avoid":
        return {
            "situation_type": "dont_buy", "label": "Don't Buy Yet", "icon": "🔴",
            "action": "WAIT", "color": "var(--rose)", "priority": 2,
            "summary": f"Trust {trust_str}. Red flags present — wait for conditions to improve.",
        }
    # Still watching — always show
    upside_str = f" Analysts see +{upside:.0f}% upside." if upside and upside > 0 else ""
    return {
        "situation_type": "watching", "label": "Watching", "icon": "👁",
        "action": "WAIT", "color": "var(--indigo)", "priority": 3,
        "summary": f"Trust {trust_str} — not yet at entry threshold.{upside_str} Wait for ≥75 score.",
    }


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
