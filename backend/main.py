"""StockPulse FastAPI backend."""
import os
import sys
import time as _time
import json as _json
import threading
from pathlib import Path

# Ensure backend directory is in path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from database.models import init_db
from database import db
from auth import get_current_user
from data.fetcher import get_stock_price, get_market_data, get_fundamentals, get_analyst_data, get_stock_history, get_news, get_insider_data
from data.india import get_india_signals, is_indian_stock
from intelligence.trust_score import get_trust_score_with_fallback
from intelligence.patterns import detect_all_patterns
from intelligence.claude_ai import get_verdict, generate_strategy_playbook
from intelligence.signals import evaluate_and_fire_signals
from intelligence.verification import verify_pick, get_verification_log
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


def _prewarm_portfolio_cache():
    """Background thread: warm price + fundamentals cache for all portfolio/watchlist tickers.

    Runs 5 seconds after startup so the server is fully ready first.
    yfinance calls are already serialised by _YF_LIB_LOCK inside fetcher.py,
    so we just call get_fundamentals() for each ticker and let the cache layer
    prevent duplicate yfinance requests for analyst_data / insider_data later.
    """
    import time as _t
    _t.sleep(5)
    try:
        tickers = list({p["ticker"] for p in db.get_portfolio()}
                       | {w["ticker"] for w in db.get_watchlist()})
        if not tickers:
            print("[prewarm] No portfolio/watchlist tickers — skipping.", flush=True)
            return
        print(f"[prewarm] Warming cache for {len(tickers)} tickers: {', '.join(tickers)}", flush=True)
        for i, ticker in enumerate(tickers, 1):
            try:
                get_stock_price(ticker)
                get_fundamentals(ticker)
                print(f"[prewarm] {i}/{len(tickers)} {ticker} cached", flush=True)
            except Exception as exc:
                print(f"[prewarm] {ticker} error: {exc}", flush=True)
        print("[prewarm] Done — first portfolio load will be fast.", flush=True)
    except Exception as exc:
        print(f"[prewarm] Startup warm failed: {exc}", flush=True)


@app.on_event("startup")
def startup():
    init_db()
    # Auto-trigger picks scan on startup if cache is empty or older than 23 hours.
    # Runs in background so the server starts instantly.
    _maybe_auto_scan()
    # Pre-warm price + fundamentals cache so the first /api/portfolio request is fast.
    threading.Thread(target=_prewarm_portfolio_cache, daemon=True).start()


# ── HEALTH ───────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/auth/me")
def auth_me(user_id: str = Depends(get_current_user)):
    """Called once on login. Triggers owner-data migration. Returns user UID."""
    db.migrate_owner_data(user_id)
    return {"uid": user_id, "status": "ok"}






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
def portfolio(user_id: str = Depends(get_current_user)):
    """All portfolio positions with live P&L."""
    return get_portfolio_with_pnl(user_id=user_id)


@app.post("/api/portfolio")
def add_portfolio(req: AddPositionRequest, user_id: str = Depends(get_current_user)):
    ticker = req.ticker.upper()
    if db.count_portfolio(user_id) >= 100:
        raise HTTPException(status_code=429, detail="Free tier limit reached (100 stocks)")
    already_exists = db.ticker_in_portfolio(ticker, user_id=user_id)
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
    db.add_position(ticker, req.shares, req.buy_price, req.buy_date, req.notes, user_id=user_id)
    return {"status": "added", "ticker": ticker, "already_had_position": already_exists}


@app.put("/api/portfolio/{pos_id}")
def update_portfolio(pos_id: int, req: UpdatePositionRequest, user_id: str = Depends(get_current_user)):
    db.update_position(pos_id, req.shares, req.buy_price, req.notes, user_id=user_id)
    return {"status": "updated"}


@app.delete("/api/portfolio/all")
def clear_all_portfolio(user_id: str = Depends(get_current_user)):
    """Remove all portfolio positions and watchlist entries. Must be before /{pos_id}."""
    db.clear_all_data(user_id=user_id)
    return {"status": "cleared"}


@app.delete("/api/portfolio/{pos_id}")
def delete_portfolio(pos_id: int, user_id: str = Depends(get_current_user)):
    db.delete_position(pos_id, user_id=user_id)
    return {"status": "deleted"}


# ── WATCHLIST ────────────────────────────────────────────────────────────────

class WatchlistRequest(BaseModel):
    ticker: str
    notes: Optional[str] = None


@app.get("/api/watchlist")
def watchlist(user_id: str = Depends(get_current_user)):
    return get_watchlist_with_signals(user_id=user_id)


@app.post("/api/watchlist")
def add_watchlist(req: WatchlistRequest, user_id: str = Depends(get_current_user)):
    ticker = req.ticker.upper()
    if db.count_watchlist(user_id) >= 100:
        raise HTTPException(status_code=429, detail="Free tier limit reached (100 watchlist items)")
    already_exists = db.ticker_in_watchlist(ticker, user_id=user_id)
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
    db.add_to_watchlist(ticker, req.notes, user_id=user_id)
    return {"status": "added", "ticker": ticker, "already_exists": already_exists}


@app.delete("/api/watchlist/{ticker}")
def remove_watchlist(ticker: str, user_id: str = Depends(get_current_user)):
    db.remove_from_watchlist(ticker.upper(), user_id=user_id)
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
def stock_verdict(ticker: str, user_id: str = Depends(get_current_user)):
    ticker = ticker.upper()
    price_data = get_stock_price(ticker)
    fundamentals = get_fundamentals(ticker)
    trust = get_trust_score_with_fallback(ticker, price_data)
    trust_score_val = trust["total_score"] or 0
    patterns = detect_all_patterns(ticker, trust_score_val, price_data, fundamentals)
    return get_verdict(ticker, trust_score_val, patterns, price_data, fundamentals)


# ── ALERTS ───────────────────────────────────────────────────────────────────

@app.get("/api/alerts")
def alerts(user_id: str = Depends(get_current_user)):
    return db.get_alerts()


@app.put("/api/alerts/{alert_id}/read")
def mark_read(alert_id: int, user_id: str = Depends(get_current_user)):
    db.mark_alert_read(alert_id)
    return {"status": "read"}


# ── SMART PICKS ───────────────────────────────────────────────────────────────

# ── GICS SECTOR UNIVERSE (~325 stocks: US S&P500/Nasdaq100 + Europe + India) ──
# GICS standard sector names used throughout. No "Other" — every stock maps to
# one of the 11 official GICS sectors.
_SECTOR_MAP: dict[str, str] = {
    # ── Information Technology ─────────────────────────────────────────────────
    # US — mega-cap platforms + semis + software + hardware
    "MSFT":"Information Technology","AAPL":"Information Technology",
    "NVDA":"Information Technology","AVGO":"Information Technology",
    "AMD":"Information Technology","QCOM":"Information Technology",
    "TXN":"Information Technology","AMAT":"Information Technology",
    "KLAC":"Information Technology","LRCX":"Information Technology",
    "MRVL":"Information Technology","ON":"Information Technology",
    "CRWD":"Information Technology","AXON":"Information Technology",
    "NET":"Information Technology","DDOG":"Information Technology",
    "ZS":"Information Technology","SNOW":"Information Technology",
    "PLTR":"Information Technology","PANW":"Information Technology",
    "FTNT":"Information Technology","HUBS":"Information Technology",
    "NOW":"Information Technology","ADBE":"Information Technology",
    "CRM":"Information Technology","INTU":"Information Technology",
    "WDAY":"Information Technology","ANSS":"Information Technology",
    "CDNS":"Information Technology","SNPS":"Information Technology",
    "ACN":"Information Technology","CTSH":"Information Technology",
    "IBM":"Information Technology","CSCO":"Information Technology",
    "ORCL":"Information Technology","INTC":"Information Technology",
    "MU":"Information Technology","STX":"Information Technology",
    "WDC":"Information Technology","GLW":"Information Technology",
    "TEL":"Information Technology","APH":"Information Technology",
    "MNDY":"Information Technology","PTC":"Information Technology",
    "EPAM":"Information Technology","HPQ":"Information Technology",
    "DELL":"Information Technology","JNPR":"Information Technology",
    "FFIV":"Information Technology","NTAP":"Information Technology",
    # Europe
    "ASML.AS":"Information Technology","SAP.DE":"Information Technology",
    "CAP.PA":"Information Technology",
    # India
    "TCS.NS":"Information Technology","INFY.NS":"Information Technology",
    "HCLTECH.NS":"Information Technology","WIPRO.NS":"Information Technology",
    "TECHM.NS":"Information Technology","LTIM.NS":"Information Technology",
    "COFORGE.NS":"Information Technology","PERSISTENT.NS":"Information Technology",
    "OFSS.NS":"Information Technology","MPHASIS.NS":"Information Technology",

    # ── Health Care ─────────────────────────────────────────────────────────────
    # US — large pharma + managed care + devices + life science tools
    "LLY":"Health Care","ABBV":"Health Care","JNJ":"Health Care",
    "MRK":"Health Care","UNH":"Health Care","ISRG":"Health Care",
    "DXCM":"Health Care","ABT":"Health Care","TMO":"Health Care",
    "DHR":"Health Care","REGN":"Health Care","VRTX":"Health Care",
    "AMGN":"Health Care","GILD":"Health Care","BMY":"Health Care",
    "CI":"Health Care","CVS":"Health Care","HUM":"Health Care",
    "MDT":"Health Care","SYK":"Health Care","EW":"Health Care",
    "ZBH":"Health Care","BDX":"Health Care","IQV":"Health Care",
    "IDXX":"Health Care","RMD":"Health Care","BSX":"Health Care",
    "GEHC":"Health Care","HCA":"Health Care","LH":"Health Care",
    "HOLX":"Health Care","PODD":"Health Care","ALGN":"Health Care",
    "BAX":"Health Care","RVTY":"Health Care","MRNA":"Health Care",
    "BIIB":"Health Care","ILMN":"Health Care","A":"Health Care",
    # Europe
    "AZN.L":"Health Care","GSK.L":"Health Care","BAYN.DE":"Health Care",
    "NOVN.SW":"Health Care",
    # India
    "SUNPHARMA.NS":"Health Care","DRREDDY.NS":"Health Care",
    "CIPLA.NS":"Health Care","DIVISLAB.NS":"Health Care",
    "APOLLOHOSP.NS":"Health Care","MANKIND.NS":"Health Care",

    # ── Financials ──────────────────────────────────────────────────────────────
    # US — banks + payments + insurance + exchanges + asset managers
    "JPM":"Financials","V":"Financials","MA":"Financials",
    "BAC":"Financials","GS":"Financials","MS":"Financials",
    "BLK":"Financials","SPGI":"Financials","ICE":"Financials",
    "CME":"Financials","AXP":"Financials","COF":"Financials",
    "WFC":"Financials","C":"Financials","USB":"Financials",
    "PNC":"Financials","TFC":"Financials","SCHW":"Financials",
    "CB":"Financials","AON":"Financials","MMC":"Financials",
    "PGR":"Financials","TRV":"Financials","ALL":"Financials",
    "MET":"Financials","PRU":"Financials","MCO":"Financials",
    "MSCI":"Financials","FDS":"Financials","TROW":"Financials",
    "RJF":"Financials","WTW":"Financials","AFL":"Financials",
    "AIG":"Financials","DFS":"Financials","SYF":"Financials",
    # Europe
    "HSBA.L":"Financials","BNP.PA":"Financials","SAN.MC":"Financials",
    "ING.AS":"Financials","DBK.DE":"Financials","ISP.MI":"Financials",
    # India
    "HDFCBANK.NS":"Financials","ICICIBANK.NS":"Financials",
    "KOTAKBANK.NS":"Financials","AXISBANK.NS":"Financials",
    "SBIN.NS":"Financials","BAJFINANCE.NS":"Financials",
    "BAJAJFINSV.NS":"Financials","SHRIRAMFIN.NS":"Financials",
    "HDFCLIFE.NS":"Financials","SBILIFE.NS":"Financials",
    "INDUSINDBK.NS":"Financials","ICICIGI.NS":"Financials",

    # ── Consumer Discretionary ───────────────────────────────────────────────────
    # US — e-commerce + restaurants + retail + autos + homebuilders + travel
    "AMZN":"Consumer Discretionary","TSLA":"Consumer Discretionary",
    "NKE":"Consumer Discretionary","LULU":"Consumer Discretionary",
    "SBUX":"Consumer Discretionary","MCD":"Consumer Discretionary",
    "BKNG":"Consumer Discretionary","TJX":"Consumer Discretionary",
    "ROST":"Consumer Discretionary","DRI":"Consumer Discretionary",
    "CMG":"Consumer Discretionary","ORLY":"Consumer Discretionary",
    "AZO":"Consumer Discretionary","HD":"Consumer Discretionary",
    "LOW":"Consumer Discretionary","DHI":"Consumer Discretionary",
    "LEN":"Consumer Discretionary","PHM":"Consumer Discretionary",
    "NVR":"Consumer Discretionary","MAR":"Consumer Discretionary",
    "HLT":"Consumer Discretionary","ABNB":"Consumer Discretionary",
    "EXPE":"Consumer Discretionary","DECK":"Consumer Discretionary",
    "TPR":"Consumer Discretionary","RL":"Consumer Discretionary",
    "F":"Consumer Discretionary","GM":"Consumer Discretionary",
    "APTV":"Consumer Discretionary","BWA":"Consumer Discretionary",
    # Europe
    "MC.PA":"Consumer Discretionary","BMW.DE":"Consumer Discretionary",
    "MBG.DE":"Consumer Discretionary",
    # India
    "MARUTI.NS":"Consumer Discretionary","TATAMOTORS.NS":"Consumer Discretionary",
    "TITAN.NS":"Consumer Discretionary","TRENT.NS":"Consumer Discretionary",
    "EICHERMOT.NS":"Consumer Discretionary","HEROMOTOCO.NS":"Consumer Discretionary",
    "BAJAJ-AUTO.NS":"Consumer Discretionary",

    # ── Consumer Staples ─────────────────────────────────────────────────────────
    # US — personal care + food + beverage + tobacco + household
    "PG":"Consumer Staples","KO":"Consumer Staples","PEP":"Consumer Staples",
    "COST":"Consumer Staples","WMT":"Consumer Staples","MDLZ":"Consumer Staples",
    "CL":"Consumer Staples","EL":"Consumer Staples","CHD":"Consumer Staples",
    "GIS":"Consumer Staples","HSY":"Consumer Staples","KMB":"Consumer Staples",
    "CLX":"Consumer Staples","PM":"Consumer Staples","MO":"Consumer Staples",
    "SYY":"Consumer Staples","KR":"Consumer Staples","TSN":"Consumer Staples",
    "HRL":"Consumer Staples","K":"Consumer Staples","SJM":"Consumer Staples",
    "CAG":"Consumer Staples","CPB":"Consumer Staples","MKC":"Consumer Staples",
    # Europe
    "ULVR.L":"Consumer Staples","DANO.PA":"Consumer Staples",
    # India
    "HINDUNILVR.NS":"Consumer Staples","ITC.NS":"Consumer Staples",
    "NESTLEIND.NS":"Consumer Staples","BRITANNIA.NS":"Consumer Staples",
    "DABUR.NS":"Consumer Staples","MARICO.NS":"Consumer Staples",
    "TATACONSUM.NS":"Consumer Staples","COLPAL.NS":"Consumer Staples",
    "GODREJCP.NS":"Consumer Staples",

    # ── Industrials ─────────────────────────────────────────────────────────────
    # US — aerospace + defence + machinery + rail + waste + logistics
    "CAT":"Industrials","DE":"Industrials","HON":"Industrials",
    "RTX":"Industrials","LMT":"Industrials","GE":"Industrials",
    "UPS":"Industrials","FDX":"Industrials","ETN":"Industrials",
    "PH":"Industrials","ROK":"Industrials","FAST":"Industrials",
    "MMM":"Industrials","EMR":"Industrials","ITW":"Industrials",
    "DOV":"Industrials","GWW":"Industrials","CTAS":"Industrials",
    "WM":"Industrials","RSG":"Industrials","NSC":"Industrials",
    "UNP":"Industrials","CSX":"Industrials","DAL":"Industrials",
    "UAL":"Industrials","LUV":"Industrials","GNRC":"Industrials",
    "CARR":"Industrials","TT":"Industrials","ROP":"Industrials",
    "OTIS":"Industrials","JCI":"Industrials","IR":"Industrials",
    "HUBB":"Industrials","NOC":"Industrials","GD":"Industrials",
    "BA":"Industrials","HII":"Industrials","LDOS":"Industrials",
    "SAIC":"Industrials","CACI":"Industrials","EXPD":"Industrials",
    # Europe
    "SIE.DE":"Industrials","AIR.PA":"Industrials","RR.L":"Industrials",
    # India
    "LT.NS":"Industrials","POWERGRID.NS":"Industrials","NTPC.NS":"Industrials",
    "ADANIPORTS.NS":"Industrials","BEL.NS":"Industrials","HAL.NS":"Industrials",
    "COALINDIA.NS":"Industrials","ADANIENT.NS":"Industrials",

    # ── Energy ──────────────────────────────────────────────────────────────────
    # US — integrated + exploration + refining + midstream + services
    "XOM":"Energy","CVX":"Energy","COP":"Energy","EOG":"Energy",
    "SLB":"Energy","PSX":"Energy","MPC":"Energy","VLO":"Energy",
    "OKE":"Energy","WMB":"Energy","KMI":"Energy","DVN":"Energy",
    "HAL":"Energy","BKR":"Energy","HES":"Energy","APA":"Energy",
    "MRO":"Energy","FANG":"Energy","OXY":"Energy",
    # Europe
    "SHEL.L":"Energy","BP.L":"Energy","TTE.PA":"Energy","ENI.MI":"Energy",
    # India
    "RELIANCE.NS":"Energy","ONGC.NS":"Energy","BPCL.NS":"Energy",

    # ── Materials ────────────────────────────────────────────────────────────────
    # US — chemicals + metals + mining + construction materials
    "LIN":"Materials","APD":"Materials","SHW":"Materials","ECL":"Materials",
    "NEM":"Materials","FCX":"Materials","NUE":"Materials","ALB":"Materials",
    "DOW":"Materials","PPG":"Materials","CF":"Materials","MOS":"Materials",
    "VMC":"Materials","MLM":"Materials","STLD":"Materials","RS":"Materials",
    "IP":"Materials","PKG":"Materials","CE":"Materials","DD":"Materials",
    # Europe
    "RIO.L":"Materials","GLEN.L":"Materials","AAL.L":"Materials",
    "BASF.DE":"Materials",
    # India
    "TATASTEEL.NS":"Materials","JSWSTEEL.NS":"Materials",
    "HINDALCO.NS":"Materials","ULTRACEMCO.NS":"Materials",
    "GRASIM.NS":"Materials","ASIANPAINT.NS":"Materials",

    # ── Real Estate ─────────────────────────────────────────────────────────────
    # US — cell towers + industrial + data centres + retail + residential
    "AMT":"Real Estate","PLD":"Real Estate","EQIX":"Real Estate",
    "CCI":"Real Estate","SPG":"Real Estate","O":"Real Estate",
    "PSA":"Real Estate","EXR":"Real Estate","WELL":"Real Estate",
    "ARE":"Real Estate","BXP":"Real Estate","VICI":"Real Estate",
    "IRM":"Real Estate","EGP":"Real Estate","KIM":"Real Estate",

    # ── Utilities ────────────────────────────────────────────────────────────────
    # US — electric + gas + water
    "NEE":"Utilities","DUK":"Utilities","SO":"Utilities","D":"Utilities",
    "AEP":"Utilities","EXC":"Utilities","SRE":"Utilities","XEL":"Utilities",
    "WEC":"Utilities","AWK":"Utilities","PEG":"Utilities","ETR":"Utilities",
    "ES":"Utilities","CMS":"Utilities","LNT":"Utilities","EVRG":"Utilities",
    # Europe
    "ENEL.MI":"Utilities","RWE.DE":"Utilities",

    # ── Communication Services ────────────────────────────────────────────────────
    # US — internet platforms + streaming + telecom + media
    "GOOGL":"Communication Services","META":"Communication Services",
    "NFLX":"Communication Services","SPOT":"Communication Services",
    "DIS":"Communication Services","TMUS":"Communication Services",
    "TTD":"Communication Services","PINS":"Communication Services",
    "ROKU":"Communication Services","SNAP":"Communication Services",
    "T":"Communication Services","VZ":"Communication Services",
    "CHTR":"Communication Services","WBD":"Communication Services",
    "FOXA":"Communication Services","FOX":"Communication Services",
    "OMC":"Communication Services","IPG":"Communication Services",
    "LYV":"Communication Services","EA":"Communication Services",
    "ATVI":"Communication Services","MTCH":"Communication Services",
    # Europe
    "VOD.L":"Communication Services","DTE.DE":"Communication Services",
    "BT-A.L":"Communication Services","TEF.MC":"Communication Services",
    # India
    "BHARTIARTL.NS":"Communication Services",
}

_CURATED_UNIVERSE: list[str] = list(_SECTOR_MAP.keys())

# yfinance sector name → GICS standard name mapping.
# Used as fallback when a ticker is not in _SECTOR_MAP (e.g. user-added stocks).
_YF_TO_GICS: dict[str, str] = {
    "Technology":             "Information Technology",
    "Financial Services":     "Financials",
    "Financial":              "Financials",
    "Healthcare":             "Health Care",
    "Communication Services": "Communication Services",
    "Consumer Cyclical":      "Consumer Discretionary",
    "Consumer Defensive":     "Consumer Staples",
    "Basic Materials":        "Materials",
    "Industrials":            "Industrials",
    "Energy":                 "Energy",
    "Real Estate":            "Real Estate",
    "Utilities":              "Utilities",
    # GICS names passed through unchanged
    "Information Technology": "Information Technology",
    "Health Care":            "Health Care",
    "Financials":             "Financials",
    "Consumer Discretionary": "Consumer Discretionary",
    "Consumer Staples":       "Consumer Staples",
    "Materials":              "Materials",
}


def _get_sector(ticker: str, fundamentals: dict) -> str:
    """Resolve GICS sector for a ticker.
    Priority: hardcoded _SECTOR_MAP → yfinance info.sector → 'Diversified'.
    NEVER returns 'Other'.
    """
    s = _SECTOR_MAP.get(ticker)
    if s:
        return s
    yf_sector = fundamentals.get("sector") or ""
    return _YF_TO_GICS.get(yf_sector, yf_sector or "Diversified")

# Mapping from disqualify_reason keywords → plain English unblock condition
_UNBLOCK_CONDITIONS: dict[str, str] = {
    "reverse split":     "No reverse split for 12+ consecutive months",
    "going concern":     "Auditor removes going-concern warning from filings",
    "sec investigation": "SEC closes investigation or clears the company",
    "board resignation": "30-day post-resignation window expires with stable leadership",
    "cash runway":       "Cash runway extended beyond 6 months via fundraising or revenue",
    "ceo":               "Stable leadership confirmed for 90+ days",
    "promoter pledge":   "Promoter pledge drops below 50% and is declining",
    "guidance cut":      "Company posts two consecutive quarters of raised guidance",
    "fraud":             "Legal resolution reached and restated financials filed",
}

from data.cache import cache_get as _cache_get, cache_set as _cache_set, TTL_STRATEGY

def _score_one_ticker(ticker: str) -> dict | None:
    """Evaluate one ticker and return a picks entry if it qualifies.
    Every candidate passes the Real Money Test via verify_pick before inclusion.
    """
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
        is_dip = (trust_score_val >= 60 and change_pct <= -4
                  and not trust.get("disqualify_reason"))

        # ── REAL MONEY TEST for picks ───────────────────────────────────────
        # verify_pick runs 6 gates (data quality, score threshold ≥60, no auto-disq,
        # market cap present, large-cap sanity floor, quality gate).
        # If it rejects, the stock does NOT appear in Smart Picks.
        approved, rejection_reason = verify_pick(ticker, trust, fundamentals)
        if not approved and not is_dip:
            return None
        # Dip picks still require real data
        if is_dip and trust.get("data_quality") == "unavailable":
            return None

        qualifies = approved or is_dip
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
            "sector": _get_sector(ticker, fundamentals),
            # Surface verification metadata so frontend can show confidence badge
            "verification": trust.get("verification"),
        }
    except Exception:
        return None


# ── BACKGROUND PICKS SCAN ─────────────────────────────────────────────────────
# The scan takes 15-20 min on the free tier. It NEVER blocks an API request.
# Results are stored in smart_picks_cache table and read back instantly.

_scan_lock = threading.Lock()
_scan_running = False


def _run_picks_scan_background():
    """Full curated-universe scan — runs in a daemon thread, saves to DB when done."""
    global _scan_running
    if not _scan_lock.acquire(blocking=False):
        print("[PICKS] Scan already running — skipping duplicate start", flush=True)
        return
    try:
        _scan_running = True
        db.set_scan_status("running", started_at=datetime.utcnow().isoformat())
        print("[PICKS BG] Background scan started", flush=True)

        portfolio = db.get_portfolio()
        watchlist = db.get_watchlist()
        user_universe = db.get_picks_universe()
        # Build ticker list with priority ordering:
        #   1. Portfolio stocks (user-owned — must always score accurately)
        #   2. Watchlist stocks (user-tracked — should score accurately)
        #   3. Custom universe additions
        #   4. Curated universe — sector-stratified: top-15 per sector in round 1,
        #      remaining stocks in round 2. Ensures all 11 GICS sectors have early
        #      representation before rate limits affect later batches.
        priority = (
            [p["ticker"] for p in portfolio]
            + [w["ticker"] for w in watchlist]
            + list(user_universe)
        )
        seen = set(priority)
        curated_tail = [t for t in _CURATED_UNIVERSE if t not in seen]

        # Sector-stratified ordering: take top 15 from each sector first (round 1)
        # so every sector gets early representation before rate limits kick in.
        # Without this, IT's 52 stocks consume the first 13 batches and late sectors
        # (Real Estate, Materials, Communication Services) almost always time out.
        # Round 2 covers the remaining stocks in original curated (sector) order.
        from collections import defaultdict as _dd
        _TOP_PER_SECTOR = 15
        _sector_groups: dict = _dd(list)
        for _t in curated_tail:
            _sector_groups[_SECTOR_MAP.get(_t, "Other")].append(_t)
        _round1: list = []
        _round2: list = []
        for _sector_tickers in _sector_groups.values():
            _round1.extend(_sector_tickers[:_TOP_PER_SECTOR])
            _round2.extend(_sector_tickers[_TOP_PER_SECTOR:])

        all_tickers = list(dict.fromkeys(priority)) + _round1 + _round2
        portfolio_tickers = {p["ticker"] for p in portfolio}

        from concurrent.futures import ThreadPoolExecutor, wait as _wait
        from data.cache import flush_disk_cache

        result = []
        batch_size = 30   # smaller batches = finer progress granularity
        batch_pause = 12  # reduced from 20s — still safe for Finnhub free tier
        workers = 3       # increased from 2 — saturates free-tier budget faster
        # Per-batch timeout: 3 workers × 30 tickers, each ticker up to ~25s max.
        # 120s is generous; if a batch isn't done in 2 min something is hung.
        batch_timeout = 120
        batches = [all_tickers[i:i + batch_size] for i in range(0, len(all_tickers), batch_size)]
        total_tickers = len(all_tickers)
        tickers_done = 0
        _n_priority = len(list(dict.fromkeys(priority)))
        print(
            f"[PICKS BG] {total_tickers} tickers: "
            f"{_n_priority} priority + {len(_round1)} round1 (sector top-15) "
            f"+ {len(_round2)} round2, in {len(batches)} batches",
            flush=True,
        )
        # Initialise progress counters so frontend can show X of Y immediately
        db.update_scan_progress(0, total_tickers)

        for batch_num, batch in enumerate(batches):
            if batch_num > 0:
                _time.sleep(batch_pause)
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = {ex.submit(_score_one_ticker, t): t for t in batch}
                # Use wait() with timeout — as_completed() blocks forever if a
                # yfinance call hangs (e.g. Railway network stall holds _YF_LIB_LOCK).
                done, pending = _wait(list(futures.keys()), timeout=batch_timeout)
                for future in done:
                    try:
                        entry = future.result(timeout=1)
                        if entry:
                            result.append(entry)
                    except Exception:
                        pass
                if pending:
                    print(f"[PICKS BG] Batch {batch_num+1}: {len(pending)} tickers timed out — skipping", flush=True)
                    for f in pending:
                        f.cancel()
                tickers_done += len(futures)
            # Update progress after each batch completes
            db.update_scan_progress(tickers_done, total_tickers)

        flush_disk_cache()

        # Exclude owned stocks; sort by trust score descending
        all_picks = [r for r in result if r["ticker"] not in portfolio_tickers]
        all_picks.sort(key=lambda x: (-(x["trust"]["total_score"] or 0), x["ticker"]))

        # Build per-sector top-10 (using ALL qualified picks, not just global top-15)
        sector_data: dict = {}
        for pick in all_picks:
            sector = pick.get("sector") or "Diversified"
            if sector not in sector_data:
                sector_data[sector] = []
            if len(sector_data[sector]) < 10:
                sector_data[sector].append(pick)

        db.save_picks_cache(
            all_picks_json=_json.dumps(all_picks),
            sector_json=_json.dumps(sector_data),
            tickers_scanned=len(all_tickers),
            tickers_ok=len(result),
        )
        print(f"[PICKS BG] Done — {len(all_picks)} picks saved to DB", flush=True)

    except Exception as e:
        print(f"[PICKS BG] Error: {e}", flush=True)
        db.set_scan_status("error")
    finally:
        _scan_running = False
        _scan_lock.release()


def _maybe_auto_scan():
    """Trigger background scan if cache is empty, stale (>23h), or zombie."""
    try:
        cache = db.get_picks_cache()

        # Zombie scan: DB says "running" but no in-process thread is alive.
        # This happens when Railway kills the container mid-scan — the lock is
        # recreated fresh on restart so _scan_running is False, but the DB still
        # records "running". Detect by checking elapsed time > 30 minutes.
        if (cache and cache.get("scan_status") == "running" and not _scan_running):
            try:
                start_str = cache.get("scan_started_at") or ""
                if start_str:
                    start = datetime.fromisoformat(start_str)
                    age_min = (datetime.utcnow() - start).total_seconds() / 60
                    if age_min > 30:
                        print(f"[PICKS] Zombie scan ({age_min:.0f}m old) — resetting to idle", flush=True)
                        db.set_scan_status("idle")
                        cache = db.get_picks_cache()  # re-read after reset
            except Exception:
                pass

        stale = True
        if cache and cache.get("updated_at") and cache.get("scan_status") == "complete":
            try:
                dt = datetime.fromisoformat(cache["updated_at"])
                age_hours = (datetime.utcnow() - dt).total_seconds() / 3600
                stale = age_hours > 23
            except Exception:
                stale = True
        if stale and not _scan_running:
            print("[PICKS] Cache stale/empty — triggering background scan", flush=True)
            threading.Thread(target=_run_picks_scan_background, daemon=True).start()
    except Exception as e:
        print(f"[PICKS] Auto-scan trigger failed: {e}", flush=True)


@app.get("/api/picks")
def picks():
    """Return pre-computed smart picks from DB cache — always instant (<100ms).
    The heavy scan runs in background; see POST /api/picks/refresh to trigger manually.
    """
    cache = db.get_picks_cache()
    if not cache or not cache.get("all_picks_json") or cache["all_picks_json"] == "[]":
        status_info = db.get_scan_status()
        return {
            "picks": [],
            "sector_picks": {},
            "updated_at": None,
            "scan_status": status_info.get("scan_status", "idle"),
            "tickers_scanned": 0,
            "tickers_ok": 0,
        }

    all_picks = _json.loads(cache["all_picks_json"])
    sector_picks = _json.loads(cache["sector_json"])

    # Return all qualified picks (threshold ≥60, quality gate passed).
    # Sector grouping (top 10 per sector) is in sector_picks.
    # Frontend shows sector_picks for the sector view and all_picks sorted
    # globally for the "All" view. Cap at 100 to keep response size reasonable.
    dips = [p for p in all_picks if p.get("is_dip")]
    mains = [p for p in all_picks if not p.get("is_dip")]
    top_picks = mains[:100] + dips[:10]

    return {
        "picks": top_picks,
        "sector_picks": sector_picks,
        "updated_at": cache.get("updated_at"),
        "scan_status": cache.get("scan_status", "complete"),
        "tickers_scanned": cache.get("tickers_scanned", 0),
        "tickers_ok": cache.get("tickers_ok", 0),
    }


@app.post("/api/picks/refresh")
def refresh_picks():
    """Trigger a background re-scan of the full universe. Non-blocking — returns immediately."""
    if _scan_running:
        return {"status": "already_running", "message": "Scan already in progress"}
    threading.Thread(target=_run_picks_scan_background, daemon=True).start()
    return {"status": "scan_started", "message": "Background scan started"}


@app.get("/api/picks/status")
def picks_scan_status():
    """Return current scan status (idle | running | complete | error) + metadata."""
    status = db.get_scan_status()
    return {
        "scan_status": status.get("scan_status", "idle"),
        "scan_started_at": status.get("scan_started_at"),
        "scan_completed_at": status.get("scan_completed_at"),
        "tickers_scanned": status.get("tickers_scanned", 0),
        "tickers_ok": status.get("tickers_ok", 0),
        "progress_current": status.get("progress_current", 0),
        "progress_total": status.get("progress_total", 0),
        "updated_at": status.get("updated_at"),
        "is_running": _scan_running,
    }


@app.get("/api/picks/sector/{sector}")
def picks_by_sector(sector: str):
    """Return top-10 picks for a specific GICS sector from cache."""
    cache = db.get_picks_cache()
    if not cache or not cache.get("sector_json") or cache["sector_json"] == "{}":
        return {"picks": [], "sector": sector, "scan_status": "idle"}
    sector_data = _json.loads(cache["sector_json"])
    sector_picks = sector_data.get(sector, [])
    return {
        "picks": sector_picks,
        "sector": sector,
        "count": len(sector_picks),
        "updated_at": cache.get("updated_at"),
    }


@app.get("/api/picks/disqualified")
def picks_disqualified():
    """Auto-disqualified stocks from portfolio + watchlist + picks universe + curated universe.
    Includes unblock_condition so users understand what needs to change.
    """
    portfolio = db.get_portfolio()
    watchlist = db.get_watchlist()
    user_universe = db.get_picks_universe()
    priority = (
        [p["ticker"] for p in portfolio]
        + [w["ticker"] for w in watchlist]
        + list(user_universe)
    )
    seen = set(priority)
    curated_tail = [t for t in _CURATED_UNIVERSE if t not in seen]
    all_tickers = list(dict.fromkeys(priority)) + curated_tail

    result = []
    for ticker in all_tickers:
        price_data = get_stock_price(ticker)
        trust = get_trust_score_with_fallback(ticker, price_data)
        if trust["auto_disqualified"]:
            reason = trust.get("disqualify_reason") or ""
            # Derive unblock condition from reason text
            unblock = "Disqualifying condition must be resolved and cleared from data sources"
            reason_lower = reason.lower()
            for kw, condition in _UNBLOCK_CONDITIONS.items():
                if kw in reason_lower:
                    unblock = condition
                    break
            result.append({
                "ticker": ticker,
                "name": price_data.get("name", ticker),
                "trust_score": trust["total_score"],
                "reason": reason,
                "unblock_condition": unblock,
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


# ── PRICE ALERTS ─────────────────────────────────────────────────────────────

class PriceAlertRequest(BaseModel):
    ticker: str
    alert_type: str          # "price_below","price_above","entry_zone","trust_drop","auto_disq"
    threshold: Optional[float] = None
    entry_low: Optional[float] = None
    entry_high: Optional[float] = None
    alert_name: Optional[str] = None


class PriceAlertToggle(BaseModel):
    is_active: bool


@app.get("/api/price-alerts")
def get_price_alerts_endpoint(ticker: Optional[str] = None, user_id: str = Depends(get_current_user)):
    return db.get_price_alerts(ticker=ticker, user_id=user_id)


@app.post("/api/price-alerts")
def create_price_alert_endpoint(req: PriceAlertRequest, user_id: str = Depends(get_current_user)):
    alert_id = db.create_price_alert(
        ticker=req.ticker.upper(),
        alert_type=req.alert_type,
        threshold=req.threshold,
        entry_low=req.entry_low,
        entry_high=req.entry_high,
        alert_name=req.alert_name,
        user_id=user_id,
    )
    return {"status": "created", "id": alert_id}


@app.delete("/api/price-alerts/{alert_id}")
def delete_price_alert_endpoint(alert_id: int, user_id: str = Depends(get_current_user)):
    db.delete_price_alert(alert_id, user_id=user_id)
    return {"status": "deleted"}


@app.put("/api/price-alerts/{alert_id}")
def toggle_price_alert_endpoint(alert_id: int, req: PriceAlertToggle, user_id: str = Depends(get_current_user)):
    db.toggle_price_alert(alert_id, req.is_active, user_id=user_id)
    return {"status": "updated"}


def _check_price_alerts(ticker: str, current_price: float,
                        trust_score, auto_disq: bool) -> None:
    """Check active price alerts for a ticker and fire in-app notifications when triggered.
    Called after every price/trust refresh in tracker.py.
    Every alert only fires if the associated stock's display_score is not suppressed —
    we won't alert on data we don't trust (Real Money Test).
    """
    try:
        alerts = db.get_price_alerts(ticker=ticker)
        for a in alerts:
            if not a.get("is_active"):
                continue
            atype = a.get("alert_type", "")
            price = float(current_price or 0)
            triggered = False
            msg = ""

            if atype == "price_below":
                threshold = float(a.get("threshold") or 0)
                if threshold > 0 and price <= threshold and price > 0:
                    triggered = True
                    msg = f"{ticker} hit your price alert: ${price:.2f} (target: below ${threshold:.2f})"

            elif atype == "price_above":
                threshold = float(a.get("threshold") or 0)
                if threshold > 0 and price >= threshold and price > 0:
                    triggered = True
                    msg = f"{ticker} hit your price alert: ${price:.2f} (target: above ${threshold:.2f})"

            elif atype == "entry_zone":
                lo = float(a.get("entry_low") or 0)
                hi = float(a.get("entry_high") or 0)
                if lo > 0 and hi > 0 and lo <= price <= hi:
                    triggered = True
                    msg = f"{ticker} entered your entry zone ${lo:.2f}–${hi:.2f} — currently ${price:.2f}"

            elif atype == "trust_drop":
                threshold = float(a.get("threshold") or 50)
                score = int(trust_score or 0)
                if score > 0 and score <= threshold:
                    triggered = True
                    msg = f"{ticker} trust score dropped to {score}/100 — below your alert threshold of {int(threshold)}"

            elif atype == "auto_disq":
                if auto_disq:
                    triggered = True
                    msg = f"{ticker} has been auto-disqualified — review position immediately"

            if triggered:
                db.mark_price_alert_triggered(a["id"])
                db.create_alert(ticker, "price_alert", msg)
    except Exception:
        pass  # Never crash portfolio/watchlist load due to alert check failure


# ── ACCURACY ──────────────────────────────────────────────────────────────────

@app.get("/api/accuracy")
def accuracy():
    return db.get_signal_accuracy(days=90)


# ── VERIFICATION AUDIT LOG ─────────────────────────────────────────────────────

@app.get("/api/verification/log")
def verification_log(limit: int = 100):
    """
    Returns the most-recent verification decisions (newest first).
    Each entry shows which checks passed/failed and why an output was
    suppressed or downgraded.  Use this to audit the Real Money Test.
    """
    return get_verification_log(limit=min(limit, 500))


@app.get("/api/verification/summary")
def verification_summary():
    """Aggregate stats on verification decisions since last restart."""
    log = get_verification_log(limit=500)
    total      = len(log)
    suppressed = sum(1 for e in log if e.get("confidence") == "SUPPRESSED")
    medium     = sum(1 for e in log if e.get("confidence") == "MEDIUM")
    high       = sum(1 for e in log if e.get("confidence") == "HIGH")
    by_type: dict = {}
    for e in log:
        t = e.get("output_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1
    return {
        "total_decisions": total,
        "high": high,
        "medium": medium,
        "suppressed": suppressed,
        "suppression_rate_pct": round(suppressed / total * 100, 1) if total else 0,
        "by_output_type": by_type,
    }


# ── STRATEGY ─────────────────────────────────────────────────────────────────

@app.get("/api/strategy")
def strategy(user_id: str = Depends(get_current_user)):
    """Strategy situations — returns metadata instantly (NO AI calls).
    Playbooks are fetched on-demand via /api/strategy/{ticker}/playbook.
    This endpoint typically returns in <500ms.
    """
    market_data = get_market_data()
    portfolio_data = get_portfolio_with_pnl(user_id=user_id)
    watchlist_data = get_watchlist_with_signals(user_id=user_id)

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
            "display_score": pos.get("display_score"),
            "display_grade": pos.get("display_grade", ""),
            "grade": pos.get("grade", ""),
            "is_speculative": pos.get("is_speculative", False),
            "auto_disqualified": pos.get("auto_disqualified", False),
            "disqualify_reason": pos.get("disqualify_reason"),
            "analyst_buy": pos.get("analyst_buy", 0),
            "analyst_hold": pos.get("analyst_hold", 0),
            "analyst_sell": pos.get("analyst_sell", 0),
            "situation_label": pos.get("situation_label"),
            "situation_note": pos.get("situation_note"),
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
            "display_score": item.get("display_score"),
            "display_grade": item.get("display_grade", ""),
            "grade": item.get("grade", ""),
            "is_speculative": item.get("is_speculative", False),
            "analyst_buy": item.get("analyst_buy", 0),
            "analyst_hold": item.get("analyst_hold", 0),
            "analyst_sell": item.get("analyst_sell", 0),
            "situation_label": item.get("situation_label"),
            "situation_note": item.get("situation_note"),
        })

    my_stocks.sort(key=lambda x: x["priority"])
    wl_situations.sort(key=lambda x: x["priority"])

    # Populate smart_picks from cached picks result — reuse already-verified picks data.
    # Falls back to empty list if picks haven't been loaded yet (will populate on next /api/picks call).
    from data.cache import cache_get as _cg
    cached_picks = _cg("picks:result", 60 * 60) or []
    smart_picks_strat = []
    for pick in cached_picks[:5]:
        t = pick.get("trust", {})
        score = t.get("total_score") or 0
        smart_picks_strat.append({
            "ticker": pick["ticker"],
            "flag": _get_flag(_detect_market(pick["ticker"])),
            "situation_type": "ready_to_buy",
            "label": "Ready to Buy",
            "icon": "🟢",
            "action": "BUY" if score >= 80 else "WATCH",
            "color": "var(--emerald)",
            "summary": f"{t.get('grade','')!s} · {score}/100 — verified entry conditions met",
            "priority": 3,
            "playbook": None,
            "name": pick.get("name", pick["ticker"]),
            "current_price": pick.get("price", 0),
            "change_pct": pick.get("change_pct", 0),
            "trust_score": score,
            "grade": t.get("grade", ""),
            "business_score": t.get("business_score", 0),
            "smart_money_score": t.get("smart_money_score", 0),
            "momentum_score": t.get("momentum_score", 0),
            "is_speculative": t.get("is_speculative", False),
            "analyst_buy": t.get("analyst_buy", 0),
            "analyst_hold": t.get("analyst_hold", 0),
            "analyst_sell": t.get("analyst_sell", 0),
            "situation_label": t.get("situation_label"),
            "situation_note": t.get("situation_note"),
            "sector": pick.get("sector", ""),
        })

    total = len(my_stocks) + len(wl_situations) + len(smart_picks_strat)

    return {
        "total_situations": total,
        "my_stocks": my_stocks,
        "watchlist": wl_situations,
        "smart_picks": smart_picks_strat,
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
def earnings(user_id: str = Depends(get_current_user)):
    """Earnings calendar for portfolio + watchlist stocks with analyst consensus."""
    portfolio = db.get_portfolio(user_id=user_id)
    watchlist_items = db.get_watchlist(user_id=user_id)
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
