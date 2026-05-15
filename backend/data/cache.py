import time
from functools import wraps

_CACHE: dict = {}
TTL_SECONDS = 15 * 60  # 15 minutes


def cache_get(key: str):
    entry = _CACHE.get(key)
    if entry and (time.time() - entry["ts"]) < TTL_SECONDS:
        return entry["value"]
    return None


def cache_set(key: str, value):
    _CACHE[key] = {"value": value, "ts": time.time()}


def cached(key_fn=None, ttl=TTL_SECONDS):
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
