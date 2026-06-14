"""Live crypto candles from Binance public market-data API (no key needed)."""
import httpx

from data import cache

# data-api.binance.vision is Binance's official public market-data host —
# more reliable across regions than api.binance.com.
HOSTS = [
    "https://data-api.binance.vision",
    "https://api.binance.com",
    "https://api1.binance.com",
]

# Binance interval strings match ours except weekly.
_INTERVAL = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d", "1wk": "1w"}


def fetch_candles(symbol: str, tf: str, limit: int = 300) -> list[dict]:
    key = f"binance:{symbol}:{tf}:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    params = {"symbol": symbol, "interval": _INTERVAL[tf], "limit": min(limit, 1000)}
    last_err: Exception | None = None
    for host in HOSTS:
        try:
            resp = httpx.get(f"{host}/api/v3/klines", params=params, timeout=10)
            resp.raise_for_status()
            raw = resp.json()
            candles = [
                {
                    "time": int(k[0] // 1000),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                }
                for k in raw
            ]
            cache.put(key, candles, cache.ttl_for(tf))
            return candles
        except Exception as e:  # try next host
            last_err = e
    raise RuntimeError(f"Binance fetch failed for {symbol} {tf}: {last_err}")
