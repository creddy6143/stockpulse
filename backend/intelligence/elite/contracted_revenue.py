"""Contracted future revenue ÷ market cap — a screening metric (NOT a return forecast).

The idea: a company sitting on years of already-won, contracted work that is large relative
to its market cap may be under-appreciated by the market. The ONLY free, structured, reliable
measure of contracted future revenue is the ASC 606 / IFRS 15 **Remaining Performance
Obligation (RPO)** reported in SEC filings, reachable via EDGAR XBRL.

Coverage (see rpo_screen_methodology.md):
  • US companies                        → us-gaap:RevenueRemainingPerformanceObligation
  • Foreign issuers filing a 20-F (ADRs) → us-gaap RPO (native currency) or
                                           ifrs-full:TransactionPriceAllocatedToRemainingPerformanceObligations
  • Indian order book / ARR / non-SEC EU → NOT available for free → reported as such, never guessed.

Under US GAAP a single concept (RPO) is what SaaS calls "RPO", defence calls "backlog", and
engineering calls "order book" — so we source RPO uniformly and LABEL the variant by business
model, always stating the figure is RPO. Nothing is estimated; missing data is "not available".
"""
from datetime import date, datetime

_RPO_USGAAP = "RevenueRemainingPerformanceObligation"
_RPO_IFRS = "TransactionPriceAllocatedToRemainingPerformanceObligations"
_STALE_DAYS = 183   # ~6 months — an RPO figure older than this is flagged stale

# Business-model → variant LABEL (applies only when RPO actually exists). Derived from the
# real GICS sector/industry, never from hard-coded tickers.
_VARIANT_RULES = [
    (("aerospace", "defense", "defence"), "Backlog"),
    (("construction", "engineering", "infrastructure", "building", "capital goods",
      "machinery", "industrial"), "Order book"),
    (("software", "information technology services", "internet"), "RPO"),
    (("communication", "telecom", "media"), "RPO"),
]
# Business models that genuinely have NO contracted forward revenue → honest N/A.
_NA_SECTORS = ("financ", "bank", "insur", "retail", "consumer", "staples", "food",
               "beverage", "apparel", "pharmaceutical", "biotech", "drug", "real estate",
               "reit", "utilit", "energy", "oil", "gas", "materials", "mining", "metals",
               "chemical", "hospitality", "restaurant", "airline", "hotel")


def fetch_rpo(ticker: str) -> dict | None:
    """Latest RPO for a ticker from SEC EDGAR XBRL, or None if no RPO concept is filed.

    Returns ``{rpo, currency, as_of, filed, form, namespace}``. Tries us-gaap first, then
    the IFRS concept used by foreign 20-F filers. Picks the most recent period; if several
    facts share that period (e.g. current/noncurrent members) takes the largest = the total.
    """
    import requests
    from data.fetcher import _edgar_load_cik_map, _EDGAR_HEADERS
    cik = _edgar_load_cik_map().get((ticker or "").upper())
    if not cik:
        return None
    cik10 = f"{int(cik):010d}"
    for ns, concept in ((("us-gaap"), _RPO_USGAAP), ("ifrs-full", _RPO_IFRS)):
        try:
            url = (f"https://data.sec.gov/api/xbrl/companyconcept/"
                   f"CIK{cik10}/{ns}/{concept}.json")
            r = requests.get(url, headers=_EDGAR_HEADERS, timeout=20)
            if r.status_code != 200:
                continue
            best = None
            for unit, arr in (r.json().get("units", {}) or {}).items():
                if unit == "pure":
                    continue
                for x in arr:
                    if x.get("val") is None or not x.get("end"):
                        continue
                    key = (x["end"], x["val"], x.get("filed", ""))
                    bkey = (best["end"], best["val"], best.get("filed", "")) if best else None
                    if best is None or key > bkey:
                        best = {**x, "unit": unit}
            if best:
                return {"rpo": float(best["val"]), "currency": best["unit"],
                        "as_of": best["end"], "filed": best.get("filed"),
                        "form": best.get("form"), "namespace": ns}
        except Exception:
            continue
    return None


def variant_and_applicability(sector, industry, has_rpo, is_indian):
    """→ (variant_label, status, reason). status ∈ {'ok','na','unavailable'}."""
    text = f"{sector or ''} {industry or ''}".lower()
    if has_rpo:
        for keys, label in _VARIANT_RULES:
            if any(k in text for k in keys):
                return label, "ok", None
        return "RPO", "ok", None   # has contracted revenue but sector unmapped
    # No RPO figure available.
    if is_indian:
        return None, "unavailable", ("Indian order book is not published in free structured "
                                     "filings (only investor presentations / exchange PDFs).")
    if any(k in text for k in _NA_SECTORS):
        return None, "na", "This business model has no contracted forward revenue."
    return None, "unavailable", ("No remaining-performance-obligation figure filed — this "
                                 "company reports backlog (if any) outside structured filings.")


def _to_usd(value, ccy, rates):
    """Convert an amount to USD using the app's SEK-pair rates. None if not convertible
    (never guessed)."""
    if value is None:
        return None
    ccy = (ccy or "USD").upper()
    if ccy == "USD":
        return float(value)
    usdsek = rates.get("USDSEK")
    ccysek = rates.get(f"{ccy}SEK")
    if not usdsek or not ccysek:
        return None
    return float(value) * (ccysek / usdsek)


def _days_since(iso_date):
    try:
        return (date.today() - datetime.strptime(iso_date, "%Y-%m-%d").date()).days
    except Exception:
        return None


_FETCH = object()   # sentinel: fetch RPO ourselves unless the caller passes it


def build_row(ticker: str, fundamentals: dict, rates: dict, is_indian: bool = False,
              rpo=_FETCH) -> dict:
    """One screen row for a ticker — never raises, never estimates. Pass ``rpo`` to reuse
    an already-fetched EDGAR result (avoids a second call)."""
    mcap = fundamentals.get("market_cap") or 0
    mcap_ccy = (fundamentals.get("currency") or "USD").upper()
    sector = fundamentals.get("sector")
    industry = fundamentals.get("industry")

    if rpo is _FETCH:
        rpo = None if is_indian else fetch_rpo(ticker)
    variant, status, reason = variant_and_applicability(
        sector, industry, rpo is not None, is_indian)

    row = {"ticker": ticker, "sector": sector, "industry": industry,
           "market_cap": mcap or None, "market_cap_ccy": mcap_ccy,
           "variant": variant, "status": status, "reason": reason}

    if status != "ok" or not rpo:
        return row

    rpo_usd = _to_usd(rpo["rpo"], rpo["currency"], rates)
    mcap_usd = _to_usd(mcap, mcap_ccy, rates) if mcap else None
    ratio = round(rpo_usd / mcap_usd, 2) if (rpo_usd and mcap_usd) else None
    days = _days_since(rpo["as_of"])

    row.update({
        "rpo": rpo["rpo"], "rpo_ccy": rpo["currency"],
        "rpo_as_of": rpo["as_of"], "rpo_filed": rpo.get("filed"),
        "rpo_form": rpo.get("form"), "rpo_source": f"SEC EDGAR ({rpo['namespace']})",
        "ratio": ratio,
        "stale": bool(days is not None and days > _STALE_DAYS),
        "as_of_days_ago": days,
    })
    return row
