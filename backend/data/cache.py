"""Tiny in-memory TTL cache so we stay well inside free-tier API limits."""
import time
from threading import Lock

_store: dict[str, tuple[float, object]] = {}
_lock = Lock()


def get(key: str):
    with _lock:
        hit = _store.get(key)
        if hit is None:
            return None
        expires, value = hit
        if time.time() > expires:
            del _store[key]
            return None
        return value


def put(key: str, value, ttl: float):
    with _lock:
        _store[key] = (time.time() + ttl, value)


def ttl_for(tf: str) -> float:
    """Refresh cadence per timeframe — intraday stays fresh, daily can chill."""
    return {"1m": 8, "5m": 15, "15m": 30, "1h": 60, "4h": 300, "1d": 600, "1wk": 1800}.get(tf, 60)
