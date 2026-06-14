"""Outcome evaluator — scores logged predictions against what actually happened.

A prediction made at time T on timeframe tf targets the NEXT candle (the one
opening at the next tf boundary). Once that candle has closed, we compare its
close to the price at prediction time:
    actual went up   & we said up   → hit
    actual went down & we said down → hit
    anything else                    → miss
Neutral ("no edge") calls are deliberately NOT counted as right or wrong —
declining to call is its own honest category.
"""
import time

from data import store

TF_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400, "1wk": 604800}
_CLOSE_BUFFER = 30  # let the exchange finish printing the candle


def _grade(predicted: str, actual: str) -> int | None:
    if predicted not in ("up", "down"):
        return None  # neutral = no call, excluded from accuracy
    return 1 if predicted == actual else 0


def evaluate_pending(fetch_candles) -> int:
    """Evaluate all predictions whose target candle has closed. Returns count."""
    rows = store.unevaluated()
    if not rows:
        return 0
    now = time.time()
    evaluated = 0

    groups: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        groups.setdefault((r["symbol"], r["tf"]), []).append(r)

    for (symbol, tf), grp in groups.items():
        tf_sec = TF_SECONDS.get(tf)
        if not tf_sec:
            continue
        # target candle opens at the boundary after ts, closes one tf later
        ready = [r for r in grp if now >= (r["ts"] // tf_sec + 2) * tf_sec + _CLOSE_BUFFER]
        if not ready:
            continue
        try:
            candles = fetch_candles(symbol, tf, 1000)
        except Exception:
            continue  # market data hiccup — try again next report
        by_time = {c["time"]: c for c in candles}
        oldest = candles[0]["time"] if candles else 0

        for r in ready:
            target_open = (r["ts"] // tf_sec) * tf_sec + tf_sec
            candle = by_time.get(target_open)
            if candle is None:
                if target_open < oldest:
                    # too old to ever fetch — close it out as unscoreable
                    store.mark_evaluated(r["id"], None, "unknown", None, None)
                    evaluated += 1
                continue
            actual = "up" if candle["close"] > r["price"] else "down" if candle["close"] < r["price"] else "flat"
            store.mark_evaluated(
                r["id"], candle["close"], actual,
                _grade(r["tech_bias"], actual), _grade(r["ai_direction"], actual),
            )
            evaluated += 1
    return evaluated
