"""Trend detection + persistence estimate.

Segments price history into up/down runs (EMA 9 vs EMA 21), reports the current
run's direction and age, and estimates how much longer it may last from the
asset's OWN historical run-length distribution. This is a statistical survival
estimate, not a prediction — markets can reverse at any time.
"""
import numpy as np
import pandas as pd

from engine import indicators as ind


def _human(secs: float) -> str:
    if secs < 3600:
        return f"~{round(secs / 60)} min"
    if secs < 86400:
        return f"~{round(secs / 3600)} hours"
    if secs < 7 * 86400:
        return f"~{round(secs / 86400, 1)} days"
    return f"~{round(secs / (7 * 86400), 1)} weeks"


def analyze(candles: list[dict], tf_sec: int) -> dict | None:
    if len(candles) < 40:
        return None
    df = pd.DataFrame(candles)
    close = df["close"]
    fast = ind.ema(close, 9).to_numpy()
    slow = ind.ema(close, 21).to_numpy()
    price = close.to_numpy()

    # per-bar regime (skip the EMA warmup region)
    start = 21
    state = ["up" if fast[i] > slow[i] else "down" for i in range(start, len(price))]
    if not state:
        return None

    # segment into consecutive same-direction runs
    runs: list[dict] = []
    seg_start = 0
    for i in range(1, len(state)):
        if state[i] != state[i - 1]:
            runs.append({"dir": state[i - 1], "a": seg_start, "b": i - 1})
            seg_start = i
    runs.append({"dir": state[-1], "a": seg_start, "b": len(state) - 1})

    def run_bars(r: dict) -> int:
        return r["b"] - r["a"] + 1

    def run_change(r: dict) -> float:
        ai, bi = r["a"] + start, r["b"] + start
        return (price[bi] - price[ai]) / price[ai] * 100 if price[ai] else 0.0

    current = runs[-1]
    cur_dir = current["dir"]
    cur_age = run_bars(current)
    cur_change = run_change(current)

    # completed runs of the same direction give the duration distribution
    completed = [r for r in runs[:-1] if r["dir"] == cur_dir]
    durations = sorted(run_bars(r) for r in completed)

    adx_series, _, _ = ind.adx(df)
    adx_now = float(adx_series.iloc[-1]) if not np.isnan(adx_series.iloc[-1]) else 0.0
    strength = "strong" if adx_now >= 25 else "weak" if adx_now < 20 else "moderate"

    result = {
        "direction": cur_dir,
        "age_bars": cur_age,
        "age_label": _human(cur_age * tf_sec),
        "change_pct": round(cur_change, 2),
        "adx": round(adx_now, 1),
        "strength": strength,
        "sample": len(durations),
        "recent_segments": [
            {"dir": r["dir"], "bars": run_bars(r), "change_pct": round(run_change(r), 2)}
            for r in runs[-7:]
        ],
    }

    if len(durations) >= 3:
        median = float(np.median(durations))
        p25 = float(np.percentile(durations, 25))
        p75 = float(np.percentile(durations, 75))
        remaining = max(0.0, median - cur_age)
        # survival: share of past same-direction runs that lasted longer than now
        longer = sum(1 for d in durations if d > cur_age)
        cont_prob = round(longer / len(durations) * 100)
        result.update({
            "median_bars": round(median, 1),
            "typical_low": round(p25, 1),
            "typical_high": round(p75, 1),
            "expected_remaining_bars": round(remaining, 1),
            "expected_remaining_label": _human(remaining * tf_sec) if remaining > 0 else "overextended",
            "continue_probability": cont_prob,
            "mature": cur_age >= p75,
        })
    else:
        result["note"] = "not enough completed trends on this timeframe to estimate duration"
    return result
