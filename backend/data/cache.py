import time
from functools import wraps

_CACHE: dict = {}

# Tiered TTLs — different data goes stale at different rates
TTL_PRICE        = 60          # 1 min  — prices change every minute
TTL_MARKET       = 60          # 1 min  — VIX / indices
TTL_RATES        = 15 * 60     # 15 min — exchange rates (ECB publishes once/day)
TTL_TRUST        = 60 * 60     # 1 hr   — trust scores (fundamentals rarely change intraday)
TTL_FUNDAMENTALS = 24 * 60 * 60 # 24 hr  — Screener.in scraping is slow; cache aggressively
TTL_ANALYST      = 60 * 60     # 1 hr   — analyst recommendations
TTL_INSIDER      = 60 * 60     # 1 hr   — insider transactions
TTL_HISTORY      = 5 * 60      # 5 min  — chart history / perf %
TTL_NEWS         = 10 * 60     # 10 min — news headlines
TTL_SEARCH       = 5 * 60      # 5 min  — search results
TTL_STRATEGY     = 2 * 60 * 60 # 2 hr   — AI strategy playbooks (cached per-stock, generated on-demand)
TTL_DEFAULT      = 15 * 60     # 15 min — everything else


def cache_get(key: str, ttl: int = TTL_DEFAULT):
    entry = _CACHE.get(key)
    if not entry:
        return None
    # Per-entry TTL overrides caller TTL (e.g. failed fetches use short retry window)
    effective_ttl = entry["ttl"] if entry.get("ttl") is not None else ttl
    if (time.time() - entry["ts"]) < effective_ttl:
        return entry["value"]
    return None


def cache_get_stale(key: str):
    """Return cached value even if expired (for background-refresh pattern)."""
    entry = _CACHE.get(key)
    return entry["value"] if entry else None


def cache_set(key: str, value, ttl: int = None):
    """Store value. Pass ttl to override the default checked at read time.
    Use a short ttl (e.g. 300) for failed/empty fetches so they retry quickly
    instead of being locked in the 24-hour fundamentals cache."""
    _CACHE[key] = {"value": value, "ts": time.time(), "ttl": ttl}


def cached(key_fn=None, ttl=TTL_DEFAULT):
    """Decorator: caches the return value of a function."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = key_fn(*args, **kwargs) if key_fn else f"{fn.__name__}:{args}:{kwargs}"
            hit = _CACHE.get(key)
            if hit and (time.time() - hit["ts"]) < ttl:
                return hit["value"]
            result = fn(*args, **kwargs)
            _CACHE[key] = {"value": result, "ts": time.time()}
            return result
        return wrapper
    return decorator


def clear_cache():
    _CACHE.clear()
