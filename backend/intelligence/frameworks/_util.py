"""Shared helpers for the framework modules.

Statement series are period-aligned (oldest → newest) with None padding, so
index -1 is the latest fiscal year and -2 the prior year for EVERY metric.
"""


def n_periods(stmts: dict) -> int:
    return len(stmts.get("periods") or [])


def at(stmts: dict, field: str, i: int):
    """Value of `field` at period index i (negative allowed). None if missing."""
    v = stmts.get(field) or []
    try:
        x = v[i]
    except (IndexError, TypeError):
        return None
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def safe_div(a, b):
    try:
        return a / b if (a is not None and b) else None
    except (TypeError, ZeroDivisionError):
        return None
