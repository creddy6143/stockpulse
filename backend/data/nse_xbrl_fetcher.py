"""
NSE XBRL fundamentals fetcher — fallback for Indian stocks when Screener.in
is blocked on Railway's datacenter IP.

Data source: NSE India financial results API + nsearchives.nseindia.com
No authentication, no API key, official SEBI-mandated public filings.
Coverage: All .NS/.BO stocks that file with NSE (all listed Indian companies).

XBRL context convention (SEBI taxonomy):
  FourD = 4-quarter cumulative (full fiscal year April–March) ← USE THIS
  OneD  = Q4 standalone quarter only
Both contexts have the SAME date range in XML — differentiated by name only.
This is a SEBI quirk: the start date in OneD and FourD XML blocks are both
Jan 1, but FourD data values represent the April–March full year.

Namespace: Elements use hyphenated prefixes (e.g. in-bse-fin:Tag).
Regex must use [-\\w]+ for namespace matching, not \\w+.

Caching: 24 hours for successful fetches, 5 minutes for failures.
"""

import re
import time
import requests

from data.cache import cache_get, cache_set, TTL_FUNDAMENTALS

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.nseindia.com",
}

# Module-level session — reuse connection (NSE requires session cookies)
_SESSION: requests.Session | None = None


def _session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update(_HEADERS)
    return _SESSION


def _fetch_filings(symbol: str) -> list[dict]:
    """
    Fetch annual XBRL filing metadata from NSE API.
    Returns up to 2 candidates per FY (sorted newest-first, highest-seq-first
    within each FY) so the caller can fall back to the second candidate if
    the first filing's XBRL has no FourD context.
    """
    url = (
        "https://www.nseindia.com/api/corporates-financial-results"
        f"?index=equities&period=Annual&symbol={symbol}"
    )
    try:
        r = _session().get(url, timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
        items = data if isinstance(data, list) else data.get("data", [])

        annual = [i for i in items if i.get("period") == "Annual"]
        # Prefer consolidated view; fall back to standalone
        cons = [i for i in annual if "consolidated" in i.get("consolidated", "").lower()]
        chosen = cons or annual

        # Group by FY, keep up to 2 highest-seqNumber filings per FY
        from collections import defaultdict
        by_fy: dict[str, list] = defaultdict(list)
        for item in chosen:
            fy = item.get("financialYear", "")
            by_fy[fy].append(item)

        # Sort each FY group by seqNumber descending, keep top 2
        candidates = []
        for fy, group in by_fy.items():
            group.sort(key=lambda x: int(x.get("seqNumber", 0)), reverse=True)
            candidates.extend(group[:2])

        # Sort overall: most recent FY first, then by seq within FY
        candidates.sort(
            key=lambda x: (x.get("toDate", ""), int(x.get("seqNumber", 0))),
            reverse=True,
        )
        # Return top 4 (covers 2 FYs × 2 candidates each)
        return candidates[:4]

    except Exception:
        return []


def _fetch_xml(url: str) -> str | None:
    """Fetch XBRL XML from nsearchives.nseindia.com. Returns None on failure."""
    try:
        r = _session().get(url, timeout=20)
        return r.text if r.status_code == 200 else None
    except Exception:
        return None


def _find_annual_ctx(xml: str) -> str | None:
    """
    Return the SEBI FourD context ID (= 4-quarter cumulative full year).
    FourD is always present in SEBI Ind-AS XBRL quarterly filings.
    Fallback: any context starting with 'Four' and ending with 'D'.
    """
    if 'id="FourD"' in xml:
        return "FourD"
    m = re.search(r'id="(Four[A-Za-z]*D)"', xml)
    return m.group(1) if m else None


def _extract(xml: str, tag: str, ctx: str) -> float | None:
    """
    Extract numeric value for a given XBRL tag + context combination.

    Handles hyphenated namespace prefixes like 'in-bse-fin:' by using
    [-\\w]+ instead of \\w+ in the namespace capture group.
    """
    m = re.search(
        rf'<(?:[-\w]+:)?{re.escape(tag)}\s+contextRef="{re.escape(ctx)}"[^>]*>([^<]+)<',
        xml,
    )
    if not m:
        return None
    try:
        return float(m.group(1).strip())
    except (ValueError, TypeError):
        return None


# ── Schema helpers ─────────────────────────────────────────────────────────────

def _parse_non_banking(xml: str, ctx: str) -> dict:
    """
    Revenue + profit for non-banking companies (BPCL, RELIANCE, INFY, etc.).
    SEBI Ind-AS non-banking taxonomy.
    """
    rev = None
    rev_tag = None
    for tag in [
        "RevenueFromOperations",
        "Revenue",
        "NetRevenue",
        "IncomeFromOperations",
        "TotalRevenue",
        "GrossRevenue",
    ]:
        v = _extract(xml, tag, ctx)
        if v and abs(v) > 1e9:   # > ~₹100 Cr threshold to filter noise
            rev = v
            rev_tag = tag
            break

    prof = None
    prof_tag = None
    for tag in [
        "ProfitLossForThePeriod",   # Most common in recent SEBI taxonomy
        "ProfitLoss",
        "ProfitAfterTax",
        "NetProfit",
        "ProfitLossForPeriod",
        "ProfitBeforeTax",           # Last resort — pre-tax is better than nothing
    ]:
        v = _extract(xml, tag, ctx)
        if v is not None:
            prof = v
            prof_tag = tag
            break

    return {"rev": rev, "rev_tag": rev_tag, "prof": prof, "prof_tag": prof_tag}


def _parse_banking(xml: str, ctx: str) -> dict:
    """
    Revenue + profit for banking companies (SBIN, HDFCBANK, etc.).
    SEBI banking taxonomy uses different tag names.
    'Income' = InterestEarned + OtherIncome (total revenue for a bank).
    """
    rev = None
    rev_tag = None
    for tag in [
        "Income",                    # Aggregated total (best single-tag option)
        "InterestEarned",
        "RevenueFromOperations",
        "TotalIncome",
        "GrossIncome",
    ]:
        v = _extract(xml, tag, ctx)
        if v and abs(v) > 1e9:
            rev = v
            rev_tag = tag
            # If we got InterestEarned only, add OtherIncome for completeness
            if tag == "InterestEarned":
                oi = _extract(xml, "OtherIncome", ctx) or 0
                if oi:
                    rev += oi
                    rev_tag += "+OtherIncome"
            break

    prof = None
    prof_tag = None
    for tag in [
        "ProfitLossForThePeriod",
        "ProfitLossFromOrdinaryActivitiesAfterTax",
        "ProfitLoss",
        "ProfitAfterTax",
        "NetProfit",
        "ProfitLossForPeriod",
    ]:
        v = _extract(xml, tag, ctx)
        if v is not None:
            prof = v
            prof_tag = tag
            break

    return {"rev": rev, "rev_tag": rev_tag, "prof": prof, "prof_tag": prof_tag}


# ── Public API ─────────────────────────────────────────────────────────────────

def get_nse_xbrl_fundamentals(ticker: str) -> dict:
    """
    Fetch revenue_growth + profit_margins from SEBI-mandated XBRL filings.

    ticker: e.g. "SBIN.NS", "BPCL.BO", "RELIANCE.NS"
    Returns dict compatible with get_fundamentals() format, or {} on failure.

    Keys returned (when successful):
      revenue_growth    float  — YoY revenue growth (requires 2 years of filings)
      profit_margins    float  — Net profit margin (latest year)
      gaap_profitable   bool   — Net profit > 0
      data_source       str    — "nse:xbrl"
    """
    symbol = ticker.upper().replace(".NS", "").replace(".BO", "").strip()
    key = f"nse_xbrl:{symbol}"

    cached = cache_get(key, TTL_FUNDAMENTALS)
    if cached is not None:
        return cached

    filings = _fetch_filings(symbol)
    if not filings:
        cache_set(key, {}, ttl=5 * 60)
        return {}

    # NSE API includes a 'bank' flag — use it to pick the right parser
    is_bank = any(f.get("bank", "N").upper() == "Y" for f in filings)

    # Parse all candidates and collect results tagged with their toDate.
    # We need this full picture to handle two SEBI filing patterns:
    #
    # Pattern A — regular companies (BPCL, RELIANCE, INFY):
    #   Each FY has TWO filings: consolidated (higher rev) + standalone (lower).
    #   Both share the same financialYear label. Both have FourD.
    #   We want: consolidated FY24 + consolidated FY23 → 2 distinct toDate values.
    #
    # Pattern B — PSU banks (SBIN):
    #   FY23-labeled filings lack FourD entirely (segment-only XBRL).
    #   Instead, FY23 comparative data is filed as a second XBRL within the
    #   FY24 batch (both labeled "01-Apr-2023 To 31-Mar-2024" in NSE API).
    #   We want: FY24 actual (seq_high) + FY23 comparative (seq_lower).
    #   The two are distinguishable because their revenues differ by ~21%.
    #
    # Algorithm:
    #   1. Parse all 4 candidates, collect (toDate, rev, prof) per valid result.
    #   2. Group by toDate; keep max-revenue per toDate (= consolidated filing).
    #   3. If 2 distinct toDate values → use as current + prior year (Pattern A).
    #   4. If only 1 toDate has data → check if a second filing for the same date
    #      has revenue < 85% of max (= prior-year comparative, Pattern B).
    from collections import defaultdict

    all_parsed: list[dict] = []
    for filing in filings:
        xurl = filing.get("xbrl", "")
        if not xurl:
            continue
        xml = _fetch_xml(xurl)
        if not xml:
            continue
        ctx = _find_annual_ctx(xml)
        if not ctx:
            time.sleep(0.4)
            continue

        d = _parse_banking(xml, ctx) if is_bank else _parse_non_banking(xml, ctx)
        if not is_bank and (d["rev"] is None or d["rev"] == 0):
            d_bank = _parse_banking(xml, ctx)
            if d_bank["rev"] and abs(d_bank["rev"]) > abs(d["rev"] or 0):
                d = d_bank

        if d["rev"] and abs(d["rev"]) > 1e9:
            all_parsed.append({
                "toDate": filing.get("toDate", ""),
                "seq":    int(filing.get("seqNumber", 0)),
                "rev":    d["rev"],
                "prof":   d["prof"],
            })

        time.sleep(0.8)

    if not all_parsed:
        cache_set(key, {}, ttl=5 * 60)
        return {}

    # Group by toDate, sort each group by revenue desc
    by_date: dict[str, list] = defaultdict(list)
    for r in all_parsed:
        by_date[r["toDate"]].append(r)
    for td in by_date:
        by_date[td].sort(key=lambda x: abs(x["rev"]), reverse=True)

    # Select which 2 data points to use as current + prior year
    sorted_dates = sorted(by_date.keys(), reverse=True)[:2]

    if len(sorted_dates) >= 2:
        # Pattern A: two distinct periods — use consolidated (max) from each
        yearly = [by_date[sorted_dates[0]][0], by_date[sorted_dates[1]][0]]
    else:
        # Pattern B (or single-year): only one period date has FourD data.
        td = sorted_dates[0]
        group = by_date[td]
        yearly = [group[0]]
        if len(group) > 1:
            # Accept second filing as prior-year only if revenue differs >15%
            # (consolidated vs standalone share <1% difference, so >15% = comparative)
            if abs(group[1]["rev"]) < abs(group[0]["rev"]) * 0.85:
                yearly.append(group[1])

    if not yearly:
        cache_set(key, {}, ttl=5 * 60)
        return {}

    result: dict = {"data_source": "nse:xbrl"}

    # Revenue growth — needs 2 years
    if len(yearly) >= 2:
        r1, r2 = yearly[0]["rev"], yearly[1]["rev"]
        if r1 and r2 and r2 != 0:
            result["revenue_growth"] = round((r1 - r2) / abs(r2), 4)

    # Profit margin — from most recent year
    r1 = yearly[0]["rev"]
    p1 = yearly[0]["prof"]
    if r1 and p1 is not None:
        margin = p1 / r1
        result["profit_margins"] = round(margin, 4)
        result["gaap_profitable"] = p1 > 0
    elif p1 is not None:
        result["gaap_profitable"] = p1 > 0

    # Only cache as successful if we got at least one useful metric
    has_data = (
        result.get("revenue_growth") is not None
        or result.get("profit_margins") is not None
    )
    if not has_data:
        cache_set(key, {}, ttl=5 * 60)
        return {}

    print(
        f"[nse_xbrl] {symbol}: "
        f"rev_growth={result.get('revenue_growth', 'N/A')}, "
        f"profit_margin={result.get('profit_margins', 'N/A')}, "
        f"gaap={result.get('gaap_profitable', 'N/A')}",
        flush=True,
    )
    cache_set(key, result, ttl=TTL_FUNDAMENTALS)
    return result
