"""Plottable indicator series for chart overlays.

The /signal endpoint returns each indicator's latest scalar; to DRAW an
indicator on the price chart we need its full time series. This module returns
line series keyed by indicator name, aligned to candle timestamps.
"""
import numpy as np
import pandas as pd

from engine import indicators as ind


def _line(times: list[int], series: pd.Series) -> list[dict]:
    out = []
    for t, v in zip(times, series.to_numpy()):
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            out.append({"time": int(t), "value": round(float(v), 6)})
    return out


# Which indicators can be drawn ON the price chart (price-scaled overlays).
OVERLAYABLE = [
    "EMA 9/21", "EMA 50/200", "Bollinger", "PSAR", "SuperTrend", "Ichimoku", "VWAP(50)",
]


def build(candles: list[dict]) -> dict:
    """Return {indicatorName: [{time,value}|{...lines}]} for overlay-able indicators."""
    df = pd.DataFrame(candles)
    times = df["time"].tolist()
    close = df["close"]
    out: dict[str, dict] = {}

    out["EMA 9/21"] = {
        "lines": {
            "EMA 9": _line(times, ind.ema(close, 9)),
            "EMA 21": _line(times, ind.ema(close, 21)),
        },
        "colors": {"EMA 9": "#4f8cff", "EMA 21": "#f0b90b"},
    }
    if len(close) >= 200:
        out["EMA 50/200"] = {
            "lines": {
                "EMA 50": _line(times, ind.ema(close, 50)),
                "EMA 200": _line(times, ind.ema(close, 200)),
            },
            "colors": {"EMA 50": "#9b8cff", "EMA 200": "#ff7a45"},
        }

    upper, mid, lower = ind.bollinger(close)
    out["Bollinger"] = {
        "lines": {
            "BB upper": _line(times, upper),
            "BB mid": _line(times, mid),
            "BB lower": _line(times, lower),
        },
        "colors": {"BB upper": "#787b86", "BB mid": "#787b86", "BB lower": "#787b86"},
    }

    out["VWAP(50)"] = {
        "lines": {"VWAP": _line(times, ind.rolling_vwap(df))},
        "colors": {"VWAP": "#26c6da"},
    }

    # PSAR + SuperTrend drawn as their running line (computed bar-by-bar)
    out["PSAR"] = {"lines": {"PSAR": _psar_series(df, times)}, "colors": {"PSAR": "#e040fb"}}
    out["SuperTrend"] = {"lines": {"SuperTrend": _supertrend_series(df, times)},
                          "colors": {"SuperTrend": "#16c784"}}

    if len(df) >= 78:
        tenkan, kijun = _ichimoku_series(df, times)
        out["Ichimoku"] = {
            "lines": {"Tenkan": tenkan, "Kijun": kijun},
            "colors": {"Tenkan": "#2962ff", "Kijun": "#b71c1c"},
        }
    return out


def _psar_series(df: pd.DataFrame, times: list[int]) -> list[dict]:
    high, low = df["high"].to_numpy(), df["low"].to_numpy()
    out, rising = [], True
    sar, ep, af = low[0], high[0], 0.02
    for i in range(1, len(high)):
        sar = sar + af * (ep - sar)
        if rising:
            if low[i] < sar:
                rising, sar, ep, af = False, ep, low[i], 0.02
            elif high[i] > ep:
                ep, af = high[i], min(af + 0.02, 0.2)
        else:
            if high[i] > sar:
                rising, sar, ep, af = True, ep, high[i], 0.02
            elif low[i] < ep:
                ep, af = low[i], min(af + 0.02, 0.2)
        out.append({"time": int(times[i]), "value": round(float(sar), 6)})
    return out


def _supertrend_series(df: pd.DataFrame, times: list[int], period: int = 10, mult: float = 3.0) -> list[dict]:
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    atr_s = tr.ewm(alpha=1 / period, min_periods=period).mean()
    mid = (df["high"] + df["low"]) / 2
    upper = (mid + mult * atr_s).to_numpy()
    lower = (mid - mult * atr_s).to_numpy()
    close = df["close"].to_numpy()
    out, trend_up, line = [], True, lower[period]
    for i in range(period + 1, len(close)):
        if trend_up:
            line = max(line, lower[i]) if not np.isnan(lower[i]) else line
            if close[i] < line:
                trend_up, line = False, upper[i]
        else:
            line = min(line, upper[i]) if not np.isnan(upper[i]) else line
            if close[i] > line:
                trend_up, line = True, lower[i]
        if not np.isnan(line):
            out.append({"time": int(times[i]), "value": round(float(line), 6)})
    return out


def _ichimoku_series(df: pd.DataFrame, times: list[int]):
    high, low = df["high"], df["low"]
    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
    return _line(times, tenkan), _line(times, kijun)
