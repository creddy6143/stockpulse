"""Single source of truth for ticker suffix → currency / market / flag.

Every place that needs to know "what currency does this stock trade in" or
"which market bucket does it belong to" must read from here.  Scattered copies
of these suffix lists caused Copenhagen stocks (MAERSK-A.CO, DKK) to be treated
as US dollars — inflating their SEK value ~6.6x.
"""

# suffix → (native currency, market bucket)
SUFFIX_MAP = {
    # India
    ".NS": ("INR", "IN"),
    ".BO": ("INR", "IN"),
    # Nordics — each has its OWN krona/krone. They are NOT interchangeable.
    ".ST": ("SEK", "EU"),   # Stockholm  — Swedish kronor
    ".CO": ("DKK", "EU"),   # Copenhagen — Danish kroner
    ".OL": ("NOK", "EU"),   # Oslo       — Norwegian kroner
    ".HE": ("EUR", "EU"),   # Helsinki   — euro (Finland)
    ".IC": ("ISK", "EU"),   # Iceland
    # Eurozone
    ".AS": ("EUR", "EU"),   # Amsterdam
    ".DE": ("EUR", "EU"),   # Xetra
    ".F":  ("EUR", "EU"),   # Frankfurt
    ".PA": ("EUR", "EU"),   # Paris
    ".MI": ("EUR", "EU"),   # Milan
    ".MC": ("EUR", "EU"),   # Madrid
    ".BR": ("EUR", "EU"),   # Brussels
    ".LS": ("EUR", "EU"),   # Lisbon
    ".VI": ("EUR", "EU"),   # Vienna
    ".IR": ("EUR", "EU"),   # Dublin
    ".AT": ("EUR", "EU"),   # Athens
    # Rest of Europe
    ".L":  ("GBP", "EU"),   # London
    ".SW": ("CHF", "EU"),   # Swiss exchange
    ".VX": ("CHF", "EU"),   # Swiss (legacy virt-x)
    ".WA": ("PLN", "EU"),   # Warsaw
    ".PR": ("CZK", "EU"),   # Prague
}

# Currencies we can price, convert and display — every ECB reference currency,
# so Frankfurter serves a SEK cross rate for all of them. Anything outside this
# set falls back to the ticker suffix / stored value rather than being trusted.
KNOWN_CURRENCIES = {
    "USD", "EUR", "SEK", "DKK", "NOK", "GBP", "CHF", "INR", "ISK",
    "AUD", "BRL", "CAD", "CNY", "CZK", "HKD", "HUF", "IDR", "ILS",
    "JPY", "KRW", "MXN", "MYR", "NZD", "PHP", "PLN", "RON", "SGD", "THB",
    "TRY", "ZAR",
}

# Currencies that imply the stock belongs to the European bucket. Used when a
# ticker carries no exchange suffix and only the price feed knows the currency.
EU_CURRENCIES = {"EUR", "SEK", "DKK", "NOK", "CHF", "GBP"}

MARKET_FLAGS = {"US": "🇺🇸", "EU": "🇪🇺", "IN": "🇮🇳"}

# Display symbols live in the frontend (App.jsx CCY_SYMBOL) — the backend never
# formats money for display, so there is no second copy to drift out of sync.


def _suffix(ticker: str) -> str | None:
    t = (ticker or "").upper()
    if "." not in t:
        return None
    sfx = "." + t.rsplit(".", 1)[1]
    return sfx if sfx in SUFFIX_MAP else None


def detect_currency(ticker: str) -> str:
    """Native trading currency inferred from the ticker suffix. Defaults to USD."""
    sfx = _suffix(ticker)
    return SUFFIX_MAP[sfx][0] if sfx else "USD"


def detect_market(ticker: str) -> str:
    """Market bucket ('US' | 'EU' | 'IN') inferred from the ticker suffix."""
    sfx = _suffix(ticker)
    return SUFFIX_MAP[sfx][1] if sfx else "US"


def detect_flag(ticker: str) -> str:
    """Country flag emoji inferred from the ticker suffix."""
    return MARKET_FLAGS.get(detect_market(ticker), "🇺🇸")


# Feeds quote some markets in the minor unit: London in pence ("GBp"), not
# pounds. Taken literally, a London holding reads 100x its real value.
# CASE MATTERS — "GBp" is pence, "GBP" is pounds.
MINOR_UNITS = {
    "GBp": ("GBP", 100.0),   # pence   (Yahoo's code for London)
    "GBX": ("GBP", 100.0),   # pence   (alternative code, unambiguous)
    "ZAc": ("ZAR", 100.0),   # SA cents
    "ILa": ("ILS", 100.0),   # agorot
    "ILA": ("ILS", 100.0),
}


def normalize_quote(currency: str, *values: float) -> tuple:
    """Convert a quote from a minor unit to its major currency.

    Returns (currency, *values). 'GBp' 521.95 → ('GBP', 5.2195).
    Currencies already in major units pass through untouched.
    """
    code = currency or ""
    if code not in MINOR_UNITS:
        return (code.upper() or "USD", *values)
    major, divisor = MINOR_UNITS[code]
    return (major, *[(v / divisor if isinstance(v, (int, float)) else v) for v in values])


def strip_suffix(ticker: str) -> str:
    """Ticker without its exchange suffix — 'MAERSK-A.CO' → 'MAERSK-A'.
    Used when calling providers that key on the bare symbol."""
    return ticker.rsplit(".", 1)[0] if _suffix(ticker) else ticker


def is_international(ticker: str) -> bool:
    """True when the ticker carries a recognised non-US exchange suffix."""
    return _suffix(ticker) is not None
