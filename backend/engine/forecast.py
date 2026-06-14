"""Next-candle projection — statistical, not magical.

Projects the NEXT candle's likely size and placement from the asset's own
recent candle distribution: median body and wick sizes of the last 60 closed
candles, with the body scaled by signal confidence and pointed by the bias.
It is an expectation with error bars, not a promise — the UI must say so.
"""
import pandas as pd


def project(candles: list[dict], tf_sec: int, bias: str, confidence: int) -> dict | None:
    if len(candles) < 20:
        return None

    closed = pd.DataFrame(candles[:-1]).tail(60)  # exclude the still-forming bar
    bodies = (closed["close"] - closed["open"]).abs()
    up_wicks = closed["high"] - closed[["open", "close"]].max(axis=1)
    dn_wicks = closed[["open", "close"]].min(axis=1) - closed["low"]
    med_body = float(bodies.median())
    med_up = float(up_wicks.median())
    med_dn = float(dn_wicks.median())

    last = candles[-1]
    open_p = float(last["close"])  # next candle opens where this one closes

    # confidence 50 → quarter-size body, 70 → ~0.75x, 88+ → capped at 1.2x
    scale = min(1.2, max(0.2, (confidence - 40) / 40))
    if bias == "up":
        close_p = open_p + med_body * scale
    elif bias == "down":
        close_p = open_p - med_body * scale
    else:
        # no edge: near-flat body drifting with the current candle
        drift = 1 if last["close"] >= last["open"] else -1
        close_p = open_p + drift * med_body * 0.15

    high_p = max(open_p, close_p) + med_up
    low_p = min(open_p, close_p) - med_dn
    t = (int(last["time"]) // tf_sec) * tf_sec + tf_sec

    return {
        "time": t,
        "open": round(open_p, 6),
        "high": round(high_p, 6),
        "low": round(low_p, 6),
        "close": round(close_p, 6),
        "direction": "up" if close_p > open_p else "down",
        "body_pct": round(abs(close_p - open_p) / open_p * 100, 3) if open_p else 0,
        "range_pct": round((high_p - low_p) / open_p * 100, 3) if open_p else 0,
        "basis": "median body/wick of last 60 closed candles × signal confidence",
    }


def reconstruct(candles: list[dict], tf_sec: int, lookback: int = 90) -> list[dict]:
    """Replay the engine over recent history: for each past candle, compute the
    forecast the system WOULD have made for it (from prior bars only) and tag it
    with the actual outcome. Gives an instant chart of predicted-vs-real candles
    without waiting hours for live history to accumulate.
    """
    from engine import indicators, signal  # local import avoids a cycle

    n = len(candles)
    start = max(indicators.MIN_CANDLES + 2, n - lookback)
    out: list[dict] = []
    for i in range(start, n):
        window = candles[:i]  # window[-1] is the bar forming just before target i
        try:
            analysis = indicators.analyze(window[:-1])  # closed bars only (matches live)
        except Exception:
            continue
        scored = signal.score(analysis)
        fc = project(window, tf_sec, scored["bias"], scored["confidence"])
        if not fc:
            continue
        fc["bias"] = scored["bias"]
        actual = candles[i]
        actual_up = actual["close"] >= actual["open"]
        pred_move = abs(fc["close"] - fc["open"])
        actual_move = abs(actual["close"] - actual["open"])
        if scored["bias"] == "neutral":
            # we made no directional call — not graded for direction
            fc["correct"] = None
            fc["quality"] = "noedge"
        else:
            correct = (fc["direction"] == "up" and actual_up) or (
                fc["direction"] == "down" and not actual_up
            )
            fc["correct"] = correct
            if correct:
                fc["quality"] = "correct"
            elif actual_move <= pred_move:
                fc["quality"] = "slight"  # wrong way, but only a small move — near miss
            else:
                fc["quality"] = "complete"  # wrong way and a big move — big miss
        out.append(fc)
    return out


def summarize(forecasts: list[dict]) -> dict:
    """Bucket counts for the report. Accuracy is over COMMITTED directional calls
    only; 'no edge' calls are tracked separately (calibration trades them for
    higher accuracy on the calls we do make)."""
    correct = sum(1 for f in forecasts if f.get("quality") == "correct")
    slight = sum(1 for f in forecasts if f.get("quality") == "slight")
    complete = sum(1 for f in forecasts if f.get("quality") == "complete")
    noedge = sum(1 for f in forecasts if f.get("quality") == "noedge")
    directional = correct + slight + complete
    return {
        "total": directional,
        "correct": correct,
        "slight": slight,
        "complete": complete,
        "noedge": noedge,
        "graded": len(forecasts),
        "accuracy": round(correct / directional * 100, 1) if directional else None,
    }
