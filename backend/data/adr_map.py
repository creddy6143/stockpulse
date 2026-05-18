"""
ADR / US-listing map for international stocks.

Many non-US stocks trade as ADRs or direct listings on US exchanges.
Finnhub free tier has full fundamental coverage for US-listed tickers
(133 fields) but zero coverage for NSE:/BSE: prefixed Indian tickers
or Stockholm/Amsterdam exchange suffixes.

Using the US-listed ticker for Finnhub lookups gets real data.
The original exchange-suffix ticker is kept for price data and display.

To add a new stock: find its US ADR/OTC ticker and add it here.
"""

ADR_MAP = {
    # ── INDIA (NYSE / NASDAQ ADRs) ────────────────────────────────────────────
    "INFY.NS":      "INFY",   # Infosys — NYSE
    "INFY.BO":      "INFY",
    "WIPRO.NS":     "WIT",    # Wipro — NYSE
    "WIPRO.BO":     "WIT",
    "HDFCBANK.NS":  "HDB",    # HDFC Bank — NYSE
    "HDFCBANK.BO":  "HDB",
    "HDFC.NS":      "HDB",
    "HDFC.BO":      "HDB",
    "ICICIBANK.NS": "IBN",    # ICICI Bank — NYSE
    "ICICIBANK.BO": "IBN",
    "TATAMOTORS.NS":"TTM",    # Tata Motors — NYSE
    "TATAMOTORS.BO":"TTM",
    "DRREDDY.NS":   "RDY",    # Dr. Reddy's — NYSE
    "DRREDDY.BO":   "RDY",
    "MFSL.NS":      "WIT",    # fallback
    # ── EUROPE (NASDAQ / NYSE / OTC listings) ─────────────────────────────────
    "ASML.AS":      "ASML",   # ASML — NASDAQ
    "SAP.DE":       "SAP",    # SAP — NYSE
    "NESN.SW":      "NSRGY",  # Nestle — OTC ADR
    "SIE.DE":       "SIEGY",  # Siemens — OTC ADR
    "AIR.PA":       "EADSY",  # Airbus — OTC ADR
    "NOVN.SW":      "NVS",    # Novartis — NYSE
    "ROG.SW":       "RHHBY",  # Roche — OTC ADR
    "ULVR.L":       "UL",     # Unilever — NYSE
    "SHEL.L":       "SHEL",   # Shell — NYSE
    "BP.L":         "BP",     # BP — NYSE
    "RIO.L":        "RIO",    # Rio Tinto — NYSE
    "AZN.L":        "AZN",    # AstraZeneca — NASDAQ
    "GSK.L":        "GSK",    # GSK — NYSE
    "HSBA.L":       "HSBC",   # HSBC — NYSE
    # ── SWEDEN (NASDAQ / OTC listings) ────────────────────────────────────────
    "ERIC-B.ST":    "ERIC",   # Ericsson — NASDAQ
    "VOLV-B.ST":    "VOLVF",  # Volvo — OTC
    "ATCO-A.ST":    "ATLCY",  # Atlas Copco — OTC ADR
    "SAND.ST":      "SANDVY", # Sandvik — OTC ADR
    "SECU-B.ST":    "SGSOY",  # Securitas — OTC (approximate)
    "SWED-A.ST":    "SWDBY",  # Swedbank — OTC ADR
    "HM-B.ST":      "HNNMY",  # H&M — OTC ADR
    "SKF-B.ST":     "SKFRY",  # SKF — OTC ADR
}


def get_adr_ticker(ticker: str) -> str | None:
    """Return Finnhub-compatible US-listed ticker, or None if not mapped."""
    return ADR_MAP.get(ticker.upper())
