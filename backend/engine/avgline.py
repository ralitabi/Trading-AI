"""Average trend line with directional prediction colouring.

A smoothed average (EMA) of price. The line predicts the trend continues in its
current direction; each segment is coloured:
  - YELLOW : the average kept its predicted direction (trend held)
  - ORANGE : the average reversed against the prediction (trend broke here)
A GRAY dashed projection extends the average forward by its recent slope —
"where the trend would go" if it continues. Statistical projection, not a promise.
"""
import numpy as np
import pandas as pd

from engine import indicators as ind

YELLOW = "#f5c518"
ORANGE = "#ff8a1f"
GRAY = "#8891a5"


def build(candles: list[dict], tf_sec: int, period: int = 20, project: int = 8) -> dict:
    df = pd.DataFrame(candles)
    times = df["time"].tolist()
    ma = ind.ema(df["close"], period).to_numpy()

    points: list[dict] = []
    for i in range(period + 1, len(ma)):
        if np.isnan(ma[i]) or np.isnan(ma[i - 1]) or np.isnan(ma[i - 2]):
            continue
        slope_prev = ma[i - 1] - ma[i - 2]      # the direction we'd extrapolate
        realized = ma[i] - ma[i - 1]            # what actually happened
        held = (slope_prev >= 0 and realized >= 0) or (slope_prev < 0 and realized < 0)
        points.append({"time": int(times[i]), "value": round(float(ma[i]), 6),
                       "color": YELLOW if held else ORANGE})

    # forward projection: extend by the average slope over the last few bars
    valid = ma[~np.isnan(ma)]
    if len(valid) >= 6 and points:
        k = min(5, len(valid) - 1)
        slope = (valid[-1] - valid[-1 - k]) / k
        last_t, last_v = int(times[-1]), float(valid[-1])
        for j in range(1, project + 1):
            points.append({"time": last_t + j * tf_sec,
                           "value": round(last_v + slope * j, 6), "color": GRAY})

    return {"period": period, "points": points,
            "legend": {"trend": YELLOW, "broke": ORANGE, "projection": GRAY}}
