"""
Indian stock fundamentals via Screener.in HTML scraping.

Used for Indian stocks NOT in the ADR map (TCS, RELIANCE, SBIN, BPCL, etc.)
Returns a dict in the same format as get_fundamentals() in fetcher.py.

Screener.in confirmed working for: INFY, SBIN, TCS, RELIANCE, HDFCBANK.
HTML structure is stable and has been consistent for years.

Caching: 24 hours (TTL_FUNDAMENTALS = 1440 min) — scraping is slow,
never call this more than once per day per ticker.
"""

import re
import time
import random
import requests

from data.cache import cache_get, cache_set, TTL_FUNDAMENTALS

# ── User-agent rotation — avoid looking like a bot ───────────────────────────
_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(_UAS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    })
    return s


def _pnum(s: str) -> float | None:
    """Parse a number string (Indian comma format, may include % or Cr.)."""
    if not s:
        return None
    s = s.strip().replace(",", "").replace("%", "").replace("Cr.", "").replace("Cr", "").strip()
    # Handle ranges like "1,728 / 1,307" — take first value
    if "/" in s:
        s = s.split("/")[0].strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


# NSE ticker → Screener.in company slug overrides.
# Most NSE tickers match directly (BAJFINANCE, SUNPHARMA, INFY, TCS, etc.).
# These are exceptions where corporate restructuring changed the Screener.in slug.
_SCREENER_SLUG_OVERRIDES: dict[str, str] = {
    # TATAMOTORS restructured into separate entities; consolidated is at TMCV
    "TATAMOTORS": "/company/TMCV/consolidated/",
}


def _get_screener_page(symbol: str) -> str | None:
    """Fetch Screener.in page HTML with retry. Returns HTML or None."""
    # ── Static slug override (known NSE ticker ≠ Screener.in URL exceptions) ──
    override_path = _SCREENER_SLUG_OVERRIDES.get(symbol.upper())
    if override_path:
        try:
            r = _session().get(f"https://www.screener.in{override_path}", timeout=15)
            if r.status_code == 200 and len(r.text) > 5000:
                return r.text
        except Exception:
            pass

    # Try consolidated first, then standalone
    urls = [
        f"https://www.screener.in/company/{symbol}/consolidated/",
        f"https://www.screener.in/company/{symbol}/",
    ]
    for attempt in range(3):
        for url in urls:
            try:
                s = _session()
                r = s.get(url, timeout=15)
                if r.status_code == 200 and len(r.text) > 5000:
                    return r.text
                if r.status_code == 404:
                    continue  # try next URL
            except requests.exceptions.Timeout:
                pass
            except Exception:
                pass
        # Exponential backoff between attempts
        if attempt < 2:
            time.sleep(1.0 * (2 ** attempt))

    # ── SEARCH FALLBACK ───────────────────────────────────────────────────────
    # Some stocks use a different Screener.in slug than their NSE ticker.
    # Example: TATAMOTORS.NS → screener.in/company/TMCV/ (commercial vehicles division)
    # Use Screener.in's own search API to find the correct company page URL.
    try:
        sr = _session().get(
            f"https://www.screener.in/api/company/search/?q={symbol}",
            timeout=10,
        )
        if sr.status_code == 200:
            results = sr.json()
            if results:
                slug_path = results[0].get("url", "")   # e.g. "/company/TMCV/consolidated/"
                if slug_path:
                    pr = _session().get(
                        f"https://www.screener.in{slug_path}",
                        timeout=15,
                    )
                    if pr.status_code == 200 and len(pr.text) > 5000:
                        return pr.text
    except Exception:
        pass

    return None


def _parse_ratios(html: str) -> dict:
    """Parse the #top-ratios section from Screener.in HTML."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {}

    try:
        soup = BeautifulSoup(html, "html.parser")
        ratios = {}

        # Try multiple selector patterns Screener uses
        section = soup.find("ul", id="top-ratios")
        if not section:
            section = soup.find("div", id="top-ratios")
        if not section:
            return {}

        for li in section.find_all("li"):
            name_el  = li.find("span", class_="name")
            num_els  = li.find_all("span", class_="number")
            if not name_el or not num_els:
                continue
            key = name_el.text.strip()
            # "High / Low" has two number spans — capture both as separate keys
            if "High" in key and "/" in key and len(num_els) >= 2:
                ratios["52W_High"] = num_els[0].text.strip()
                ratios["52W_Low"]  = num_els[1].text.strip()
            else:
                ratios[key] = num_els[0].text.strip()

        return ratios
    except Exception:
        return {}


def _parse_pl_table(html: str) -> dict:
    """
    Parse the #profit-loss section to extract:
    - Sales/Revenue by year
    - OPM% by year
    - Net Profit by year
    - EPS by year

    Returns dict with lists (oldest to newest) and derived metrics.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {}

    result = {}
    try:
        soup = BeautifulSoup(html, "html.parser")
        pl = soup.find("section", id="profit-loss")
        if not pl:
            return {}

        # Build a mapping: row_label → list of values
        rows = {}
        for tr in pl.find_all("tr"):
            cells = [td.text.strip() for td in tr.find_all(["td", "th"])]
            if not cells:
                continue
            label = cells[0].replace("+", "").replace("*", "").strip()
            values = cells[1:]
            if label and values:
                rows[label] = values

        # Helper: get cleaned numeric list from a row
        def _nums(row_key):
            for k, v in rows.items():
                if row_key.lower() in k.lower():
                    nums = []
                    for c in v:
                        n = _pnum(c)
                        if n is not None:
                            nums.append(n)
                    return nums
            return []

        # Sales / Revenue (banks use "Revenue", others use "Sales")
        sales = _nums("Sales") or _nums("Revenue")
        net_profit = _nums("Net Profit")
        opm_pct_vals = []  # OPM% as fractions
        for k, v in rows.items():
            if "OPM" in k and "%" in k:
                for c in v:
                    n = _pnum(c.replace("%", ""))
                    if n is not None:
                        opm_pct_vals.append(n / 100.0)
                break
        eps_vals = _nums("EPS")

        # Revenue growth (5-year CAGR)
        if len(sales) >= 6:
            latest = sales[-1]
            five_ago = sales[-6]
            if five_ago and five_ago > 0:
                cagr = (latest / five_ago) ** (1 / 5) - 1
                result["revenue_growth"] = round(cagr, 4)
        elif len(sales) >= 2:
            latest = sales[-1]
            prior = sales[-2]
            if prior and prior > 0:
                yoy = (latest - prior) / prior
                result["revenue_growth"] = round(yoy, 4)

        # Profit margins (NPM = net profit / sales, latest year)
        if sales and net_profit and len(sales) > 0 and len(net_profit) > 0:
            s_latest = sales[-1]
            np_latest = net_profit[-1]
            if s_latest and s_latest > 0:
                npm = np_latest / s_latest
                result["profit_margins"] = round(npm, 4)
                result["gaap_profitable"] = npm > 0

        # Gross margins proxy = OPM% (operating profit margin)
        if opm_pct_vals:
            result["gross_margins"] = round(opm_pct_vals[-1], 4)

        # EPS growth (YoY)
        if len(eps_vals) >= 2:
            latest_eps = eps_vals[-1]
            prior_eps = eps_vals[-2]
            if prior_eps and prior_eps != 0:
                result["earnings_growth"] = round((latest_eps - prior_eps) / abs(prior_eps), 4)

    except Exception:
        pass

    return result


def _parse_shareholding(html: str) -> dict:
    """Parse the #shareholding section to get Promoter % and FII %."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {}

    result = {}
    try:
        soup = BeautifulSoup(html, "html.parser")
        sh = soup.find("section", id="shareholding")
        if not sh:
            return {}

        for tr in sh.find_all("tr"):
            cells = [td.text.strip() for td in tr.find_all(["td", "th"])]
            if not cells:
                continue
            label = cells[0].replace("\xa0", "").replace("+", "").strip().lower()
            # Take the most recent (last) quarter value
            nums = [_pnum(c) for c in cells[1:] if _pnum(c) is not None]
            if not nums:
                continue
            latest = nums[-1]

            if "promoter" in label:
                result["promoter_holding_pct"] = latest
            elif "fii" in label or "foreign" in label:
                result["fii_holding_pct"] = latest
            elif "dii" in label:
                result["dii_holding_pct"] = latest

    except Exception:
        pass

    return result


def get_screener_fundamentals(ticker: str) -> dict:
    """
    Main entry point: fetch fundamentals from Screener.in for an Indian stock.

    ticker: e.g. "TCS.NS", "RELIANCE.BO", "SBIN.NS"
    Returns dict compatible with get_fundamentals() format in fetcher.py.
    Returns {} if Screener is unreachable or stock not found.
    """
    symbol = ticker.upper().replace(".NS", "").replace(".BO", "").strip()
    key = f"screener:{symbol}"

    cached = cache_get(key, TTL_FUNDAMENTALS)
    if cached is not None:
        return cached

    html = _get_screener_page(symbol)
    if not html:
        cache_set(key, {})
        return {}

    # Parse all sections
    ratios = _parse_ratios(html)
    pl     = _parse_pl_table(html)
    sh     = _parse_shareholding(html)

    if not ratios and not pl:
        cache_set(key, {})
        return {}

    result = {"data_source": "screener.in"}

    # ── From ratios ────────────────────────────────────────────────────────────
    mkt_cap_cr = _pnum(ratios.get("Market Cap", ""))
    if mkt_cap_cr:
        # 1 Cr = 10,000,000 INR → store in INR
        result["market_cap"] = int(mkt_cap_cr * 10_000_000)

    pe = _pnum(ratios.get("Stock P/E", ""))
    if pe:
        result["pe_ratio"] = pe

    roe = _pnum(ratios.get("ROE", ""))
    if roe:
        result["roe"] = roe  # stored as percentage (e.g. 31.5)

    roce = _pnum(ratios.get("ROCE", ""))
    if roce:
        result["roce"] = roce  # stored as percentage (e.g. 40.0)

    div_yield = _pnum(ratios.get("Dividend Yield", ""))
    if div_yield:
        result["dividend_yield"] = div_yield

    # 52-week high / low — used for near-ATH momentum credit in trust_score.
    # Screener.in "High / Low" li has two span.number elements (parsed separately above).
    # Values are in INR (native currency — no conversion needed here).
    w52h = _pnum(ratios.get("52W_High", ""))
    w52l = _pnum(ratios.get("52W_Low", ""))
    if w52h:
        result["w52_high"] = w52h
    if w52l:
        result["w52_low"] = w52l

    # ── From P&L ──────────────────────────────────────────────────────────────
    result.update(pl)

    # ── From shareholding ─────────────────────────────────────────────────────
    result.update(sh)

    # ── Derived: gaap_profitable from ROE/profit_margins ─────────────────────
    if "gaap_profitable" not in result:
        if roe and roe > 0:
            result["gaap_profitable"] = True
        elif result.get("profit_margins") is not None:
            result["gaap_profitable"] = result["profit_margins"] > 0

    # ── Fallback gross_margins from ROCE if OPM not found ────────────────────
    if "gross_margins" not in result and roce:
        # ROCE is not gross margin but is a quality indicator — use as proxy
        # ROCE 40% → roughly maps to gross_margins 0.30 range for IT services
        # Scale: divide by 100 but cap at reasonable IT service level
        result["gross_margins"] = round(min(roce / 100.0, 0.45), 4)

    # ── Fallback revenue_growth from ROE trend if P&L parse failed ───────────
    # (last resort — if ROE is high, company is likely growing)
    if "revenue_growth" not in result and roe and roe > 15:
        # Don't guess — leave missing so sufficiency check fires
        pass

    cache_set(key, result)
    return result
