"""Indian market data from NSE free APIs."""
import requests
from .cache import cache_get, cache_set

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.nseindia.com",
}

NSE_FII_URL = "https://www.nseindia.com/api/fiidiiTradeReact"
NSE_BULK_URL = "https://www.nseindia.com/api/snapshot-capital-market-largedeal"


def _nse_session():
    s = requests.Session()
    s.headers.update(NSE_HEADERS)
    try:
        s.get("https://www.nseindia.com", timeout=5)
    except Exception:
        pass
    return s


def get_fii_dii_data() -> dict:
    """Returns latest FII/DII net buying data from NSE."""
    key = "nse_fii_dii"
    cached = cache_get(key)
    if cached:
        return cached

    try:
        s = _nse_session()
        resp = s.get(NSE_FII_URL, timeout=8)
        resp.raise_for_status()
        data = resp.json()

        result = {
            "fii_net": 0,
            "dii_net": 0,
            "fii_buying": False,
            "fii_selling": False,
            "consecutive_fii_buying_days": 0,
            "raw": [],
        }

        if isinstance(data, list) and data:
            recent = data[:5]
            result["raw"] = recent
            fii_vals = []
            for d in recent:
                net = d.get("netValue") or d.get("NET") or 0
                cat = (d.get("category") or "").upper()
                if "FII" in cat or "FPI" in cat:
                    fii_vals.append(float(net))
            if fii_vals:
                result["fii_net"] = fii_vals[0]
                result["fii_buying"] = fii_vals[0] > 0
                result["fii_selling"] = fii_vals[0] < -3000
                consecutive = 0
                for v in fii_vals:
                    if v > 0:
                        consecutive += 1
                    else:
                        break
                result["consecutive_fii_buying_days"] = consecutive

        cache_set(key, result)
        return result
    except Exception as e:
        return {
            "fii_net": 0, "dii_net": 0,
            "fii_buying": False, "fii_selling": False,
            "consecutive_fii_buying_days": 0,
            "error": str(e),
        }


def get_bulk_deals() -> list:
    """Returns today's NSE bulk/block deals."""
    key = "nse_bulk_deals"
    cached = cache_get(key)
    if cached:
        return cached

    try:
        s = _nse_session()
        resp = s.get(NSE_BULK_URL, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        deals = data.get("data", []) if isinstance(data, dict) else []
        cache_set(key, deals[:20])
        return deals[:20]
    except Exception:
        return []


def get_india_signals(ticker: str) -> dict:
    """
    Returns India-specific signals for .NS / .BO tickers.
    Uses NSE FII/DII data and bulk deal data.
    """
    base = ticker.replace(".NS", "").replace(".BO", "").upper()
    fii = get_fii_dii_data()
    deals = get_bulk_deals()

    block_buy = any(
        d.get("symbol", "").upper() == base and
        (d.get("buySell", "B") or "B").upper() == "B"
        for d in deals
    )

    signals = []
    if fii.get("consecutive_fii_buying_days", 0) >= 3:
        signals.append("Large overseas investors buying for 3+ consecutive days")
    if fii.get("fii_selling"):
        signals.append("Large overseas investors sold heavily today")
    if block_buy:
        signals.append("Institutions buying large blocks today")

    return {
        "ticker": ticker,
        "fii_net_cr": fii.get("fii_net", 0),
        "fii_buying": fii.get("fii_buying", False),
        "fii_selling": fii.get("fii_selling", False),
        "consecutive_fii_buying": fii.get("consecutive_fii_buying_days", 0),
        "block_deal_buy": block_buy,
        "signals": signals,
    }


def is_indian_stock(ticker: str) -> bool:
    return ticker.endswith(".NS") or ticker.endswith(".BO")
