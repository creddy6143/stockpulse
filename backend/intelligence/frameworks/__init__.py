"""Investment frameworks — four independent analysis LENSES.

Each framework answers ONE question and NEVER feeds the recommendation engine:
    GARP        — is this growth already paid for?
    F-Score     — is the business getting healthier?
    Rule of 40  — is this SaaS balancing growth and profit?
    Altman Z    — is there balance-sheet survival risk?

Architecture: add a 5th framework by dropping in one file with a `compute(ctx)`
function and registering it in FRAMEWORKS. Each `compute` returns:

    {status: "ok"|"na"|"insufficient", value, label, verdict, color,
     inputs_used: [{label, value, period}], applicability, caveats: [...]}

`status`:
    ok            — computed, has a value + verdict
    na            — framework doesn't apply to this business (honest, a feature)
    insufficient  — data missing; NEVER fabricated
"""
import json
import os

from .garp import compute_garp
from .piotroski import compute_piotroski
from .rule_of_40 import compute_rule_of_40
from .altman_z import compute_altman_z

# (key, display name, the one question it answers, compute fn)
FRAMEWORKS = [
    ("garp",       "GARP",             "Is this growth already paid for?",          compute_garp),
    ("f_score",    "Piotroski F-Score", "Is the business getting healthier?",       compute_piotroski),
    ("rule_of_40", "Rule of 40",       "Is this SaaS balancing growth and profit?", compute_rule_of_40),
    ("altman_z",   "Altman Z-Score",   "Is there balance-sheet survival risk?",     compute_altman_z),
]

_MEMBERSHIP_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "theme_membership.json")

# Theme groups that drive applicability (from theme_membership.json keys).
CYCLICAL_THEMES = {"storage_memory", "semiconductors", "lithium_rare_earths",
                   "solar_renewables", "hydrogen", "ev_battery", "nuclear_smr"}
SAAS_THEMES     = {"ai_software", "cloud_hyperscalers", "cybersecurity",
                   "fintech_payments", "gaming"}
_FIN_THEMES     = {"indian_banks"}
_FIN_SECTORS    = {"financial services", "financials", "banks", "banking"}

_theme_index = None   # ticker(upper) → set(theme_keys)


def _load_theme_index() -> dict:
    global _theme_index
    if _theme_index is not None:
        return _theme_index
    idx: dict = {}
    try:
        with open(_MEMBERSHIP_PATH) as f:
            membership = json.load(f)
        for key, theme in membership.items():
            members = list(theme.get("candidates") or [])
            if theme.get("early_winner"):
                members.append(theme["early_winner"])
            for m in members:
                idx.setdefault(m.upper(), set()).add(key)
    except Exception:
        idx = {}
    _theme_index = idx
    return idx


def classify_ticker(ticker: str, sector: str | None, name: str | None = None) -> dict:
    """Applicability flags used by the frameworks (from themes + sector + name)."""
    themes = _load_theme_index().get((ticker or "").upper(), set())
    sec = (sector or "").lower()
    nm = (name or "").lower()
    is_financial = (
        any(s in sec for s in _FIN_SECTORS)
        or bool(themes & _FIN_THEMES)
        or any(w in nm for w in ("bank", "insurance", "insurer", "financ"))
    )
    return {
        "themes": sorted(themes),
        "is_cyclical": bool(themes & CYCLICAL_THEMES) or sec in ("materials", "energy"),
        "is_saas": bool(themes & SAAS_THEMES),
        "is_financial": is_financial,
    }


def compute_frameworks(ticker: str) -> dict:
    """Compute all four frameworks for one ticker. Never raises."""
    from data.fetcher import get_financial_statements, get_fundamentals, get_stock_price

    fund = get_fundamentals(ticker) or {}
    stmts = get_financial_statements(ticker) or {"periods": []}
    price = get_stock_price(ticker) or {}
    meta = classify_ticker(ticker, fund.get("sector"), price.get("name") or fund.get("name"))

    ctx = {"ticker": ticker, "statements": stmts, "fundamentals": fund,
           "price": price, "meta": meta}

    results = []
    for key, name, question, fn in FRAMEWORKS:
        try:
            r = fn(ctx) or {}
        except Exception as exc:
            r = {"status": "insufficient", "label": "Insufficient data",
                 "value": None, "inputs_used": [], "applicability": None,
                 "caveats": [f"compute error: {str(exc)[:80]}"]}
        r.setdefault("inputs_used", [])
        r.setdefault("caveats", [])
        r.setdefault("value", None)
        r.update({"key": key, "name": name, "question": question})
        results.append(r)

    summary = {
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "na": sum(1 for r in results if r["status"] == "na"),
        "insufficient": sum(1 for r in results if r["status"] == "insufficient"),
    }
    # Informational distress flag (inform only — never changes any recommendation)
    z = next((r for r in results if r["key"] == "altman_z"), {})
    distress = z.get("status") == "ok" and z.get("verdict") == "DISTRESS"

    return {
        "ticker": ticker,
        "sector": fund.get("sector"),
        "frameworks": results,
        "summary": summary,
        "distress_flag": distress,
    }
