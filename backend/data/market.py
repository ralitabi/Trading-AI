"""Forex / commodity / index candles via Yahoo Finance (yfinance, free)."""
import pandas as pd
import yfinance as yf

from data import cache

# Yahoo has no native 4h interval — we resample 1h ourselves.
# (interval, period) pairs chosen to return roughly 200-500 bars.
# 1m uses 5d so weekends/holidays still return the last sessions' data.
_PLAN = {
    "1m": ("1m", "5d"),
    "5m": ("5m", "5d"),
    "15m": ("15m", "5d"),
    "1h": ("1h", "1mo"),
    "4h": ("1h", "3mo"),
    "1d": ("1d", "2y"),
    "1wk": ("1wk", "5y"),
}


def fetch_candles(yahoo_symbol: str, tf: str, limit: int = 300) -> list[dict]:
    key = f"yahoo:{yahoo_symbol}:{tf}:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    interval, period = _PLAN[tf]
    df = yf.download(
        yahoo_symbol, interval=interval, period=period,
        progress=False, auto_adjust=True, multi_level_index=False,
    )
    if df is None or df.empty:
        raise RuntimeError(f"Yahoo returned no data for {yahoo_symbol} {tf}")

    if tf == "4h":
        df = (
            df.resample("4h")
            .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
            .dropna(subset=["Open", "Close"])
        )

    df = df.dropna(subset=["Open", "High", "Low", "Close"]).tail(limit)
    idx = df.index
    if isinstance(idx, pd.DatetimeIndex) and idx.tz is not None:
        idx = idx.tz_convert("UTC")

    candles = []
    for ts, row in zip(idx, df.to_dict("records")):
        vol = row.get("Volume")
        candles.append(
            {
                "time": int(ts.timestamp()),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                # NaN volume (common for forex) must never leak into JSON
                "volume": 0.0 if vol is None or pd.isna(vol) else float(vol),
            }
        )
    cache.put(key, candles, cache.ttl_for(tf))
    return candles
