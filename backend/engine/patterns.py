"""Candlestick patterns + RSI/MACD divergence detection.

Price-action reads layered on top of the indicator board:
  - Candlestick patterns (engulfing / hammer / shooting star / doji) detected on
    CLOSED candles, each with a bullish / bearish / neutral lean.
  - Regular RSI & MACD divergences: price makes a higher high while the
    oscillator makes a lower high (bearish), or a lower low while the oscillator
    makes a higher low (bullish) — classic momentum-exhaustion signals.

Returned as time-stamped markers for the chart plus a short summary. Statistical
context, not a guarantee — patterns fail.
"""
import numpy as np
import pandas as pd

from engine import indicators as ind


def _trend_before(close: np.ndarray, i: int, look: int = 5) -> str:
    """Rough local trend of the `look` bars leading into bar i."""
    a = max(0, i - look)
    if i <= a or close[a] == 0:
        return "flat"
    chg = (close[i - 1] - close[a]) / close[a]
    return "up" if chg > 0.004 else "down" if chg < -0.004 else "flat"


def candlesticks(candles: list[dict], lookback: int = 60) -> list[dict]:
    """Single/two-bar candlestick patterns on recent CLOSED candles."""
    if len(candles) < 6:
        return []
    df = pd.DataFrame(candles)
    o, h = df["open"].to_numpy(float), df["high"].to_numpy(float)
    low, c = df["low"].to_numpy(float), df["close"].to_numpy(float)
    t = df["time"].to_numpy()
    n = len(c)
    out: list[dict] = []
    for i in range(max(2, n - lookback), n - 1):  # skip the still-forming last bar
        body = abs(c[i] - o[i])
        rng = h[i] - low[i]
        if rng <= 0:
            continue
        upper = h[i] - max(o[i], c[i])
        lower = min(o[i], c[i]) - low[i]
        pat = direction = None
        if body <= rng * 0.1:
            pat, direction = "Doji", "neutral"
        elif lower >= 2 * body and upper <= body and _trend_before(c, i) == "down":
            pat, direction = "Hammer", "bullish"
        elif upper >= 2 * body and lower <= body and _trend_before(c, i) == "up":
            pat, direction = "Shooting Star", "bearish"
        elif c[i] > o[i] and c[i - 1] < o[i - 1] and c[i] >= o[i - 1] and o[i] <= c[i - 1]:
            pat, direction = "Bullish Engulfing", "bullish"
        elif c[i] < o[i] and c[i - 1] > o[i - 1] and o[i] >= c[i - 1] and c[i] <= o[i - 1]:
            pat, direction = "Bearish Engulfing", "bearish"
        if pat:
            out.append({"time": int(t[i]), "name": pat, "direction": direction,
                        "price": float(h[i] if direction == "bearish" else low[i]),
                        "kind": "candlestick"})
    return out


def _pivots(v: np.ndarray, left: int = 3, right: int = 3):
    """Indices of pivot highs and lows (extreme within +/- window)."""
    highs, lows = [], []
    for i in range(left, len(v) - right):
        seg = v[i - left:i + right + 1]
        if v[i] >= seg.max() - 1e-12:
            highs.append(i)
        if v[i] <= seg.min() + 1e-12:
            lows.append(i)
    return highs, lows


def divergences(candles: list[dict], lookback: int = 90) -> list[dict]:
    """Regular RSI & MACD divergences from the last two price pivots."""
    if len(candles) < 40:
        return []
    df = pd.DataFrame(candles)
    close = df["close"]
    t = df["time"].to_numpy()
    price = close.to_numpy(float)
    rsi = ind.rsi(close).to_numpy()
    macd_line, _, _ = ind.macd(close)
    macd_line = macd_line.to_numpy()
    n = len(price)
    lo = max(30, n - lookback)
    p_highs, p_lows = _pivots(price[:n - 1], 3, 3)  # ignore forming bar
    out: list[dict] = []
    for label, osc in (("RSI", rsi), ("MACD", macd_line)):
        hi = [i for i in p_highs if i >= lo and not np.isnan(osc[i])]
        if len(hi) >= 2:
            a, b = hi[-2], hi[-1]
            if b - a >= 4 and price[b] > price[a] and osc[b] < osc[a]:
                out.append({"time": int(t[b]), "name": f"{label} Bearish Divergence",
                            "direction": "bearish", "price": float(price[b]), "kind": "divergence"})
        lows = [i for i in p_lows if i >= lo and not np.isnan(osc[i])]
        if len(lows) >= 2:
            a, b = lows[-2], lows[-1]
            if b - a >= 4 and price[b] < price[a] and osc[b] > osc[a]:
                out.append({"time": int(t[b]), "name": f"{label} Bullish Divergence",
                            "direction": "bullish", "price": float(price[b]), "kind": "divergence"})
    return out


def build(candles: list[dict]) -> dict:
    cs = candlesticks(candles)
    dv = divergences(candles)
    everything = sorted(cs + dv, key=lambda x: x["time"])
    window = everything[-6:]
    bull = sum(1 for x in window if x["direction"] == "bullish")
    bear = sum(1 for x in window if x["direction"] == "bearish")
    bias = "bullish" if bull > bear else "bearish" if bear > bull else "neutral"
    return {
        "candlesticks": cs,
        "divergences": dv,
        "summary": {
            "bias": bias, "bullish": bull, "bearish": bear,
            "latest": list(reversed(everything[-6:])),
        },
    }
