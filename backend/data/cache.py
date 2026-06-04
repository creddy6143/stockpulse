import os
import json
import time
import threading
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
TTL_HISTORY      = 30 * 60     # 30 min — chart history / perf % (daily closes, stable)
TTL_NEWS         = 10 * 60     # 10 min — news headlines
TTL_SEARCH       = 5 * 60      # 5 min  — search results
TTL_STRATEGY     = 2 * 60 * 60 # 2 hr   — AI strategy playbooks (cached per-stock, generated on-demand)
TTL_DEFAULT      = 15 * 60     # 15 min — everything else

# ── Disk persistence ──────────────────────────────────────────────────────────
# Keys with TTL ≥ this threshold are written to disk so scan_picks.py
# doesn't start cold on every run. Covers fundamentals (24hr) and
# analyst/insider/trust (1hr) — all expensive to re-fetch.
_DISK_PERSIST_TTL_MIN = 60 * 60   # persist entries with TTL ≥ 1 hour

_DISK_CACHE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", ".scan_cache.json"
)
_DISK_LOCK = threading.Lock()
_disk_dirty = False           # write deferred to avoid hammering disk on every set
_LAST_DISK_SAVE = 0.0
_DISK_SAVE_INTERVAL = 60      # write to disk at most once per minute


def _load_disk_cache():
    """Load persisted entries into _CACHE on startup. Skips expired entries."""
    path = os.path.abspath(_DISK_CACHE_PATH)
    if not os.path.exists(path):
        return
    try:
        with open(path, "r") as f:
            data = json.load(f)
        now = time.time()
        loaded = 0
        for key, entry in data.items():
            ts  = entry.get("ts", 0)
            ttl = entry.get("ttl") or TTL_FUNDAMENTALS
            if (now - ts) < ttl:          # still valid — load into memory
                _CACHE[key] = entry
                loaded += 1
        if loaded:
            print(f"[cache] Loaded {loaded} entries from disk cache ({path})", flush=True)
    except Exception as e:
        print(f"[cache] Could not load disk cache: {e}", flush=True)


def _save_disk_cache():
    """Write all persist-worthy entries to disk (called in background thread)."""
    global _LAST_DISK_SAVE, _disk_dirty
    path = os.path.abspath(_DISK_CACHE_PATH)
    try:
        with _DISK_LOCK:
            persist = {
                k: v for k, v in _CACHE.items()
                if (v.get("ttl") or 0) >= _DISK_PERSIST_TTL_MIN
            }
            with open(path, "w") as f:
                json.dump(persist, f)
            _LAST_DISK_SAVE = time.time()
            _disk_dirty = False
    except Exception as e:
        print(f"[cache] Disk save failed: {e}", flush=True)


def _maybe_save_disk():
    """Trigger a background disk save if enough time has elapsed."""
    global _disk_dirty
    if not _disk_dirty:
        return
    if time.time() - _LAST_DISK_SAVE < _DISK_SAVE_INTERVAL:
        return
    t = threading.Thread(target=_save_disk_cache, daemon=True)
    t.start()


# Load disk cache on module import (runs once when backend starts / scan_picks.py starts)
_load_disk_cache()


# ── In-memory cache API ───────────────────────────────────────────────────────

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
    instead of being locked in the 24-hour fundamentals cache.

    Entries with ttl ≥ 1 hour are automatically persisted to disk so the
    next scan_picks.py run skips re-fetching stale fundamentals.
    """
    global _disk_dirty
    _CACHE[key] = {"value": value, "ts": time.time(), "ttl": ttl}
    if ttl and ttl >= _DISK_PERSIST_TTL_MIN:
        _disk_dirty = True
        _maybe_save_disk()


def flush_disk_cache():
    """Force an immediate disk save — call at end of scan_picks.py."""
    _save_disk_cache()


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
