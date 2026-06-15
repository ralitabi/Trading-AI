"""Paper-trading engine.

Auto-opens a hypothetical trade whenever a directional signal appears (and none
is already open for that market/timeframe), using the same ATR entry/stop/target
the dashboard shows. A later candle that touches the stop or target closes it:
target hit = +R:R in R-multiples, stop hit = −1R. This builds an honest,
hands-off track record of what trading the signals would have done.
"""
from data import store


def maybe_open(symbol: str, tf: str, bias: str, plan: dict | None, price: float) -> None:
    if bias not in ("up", "down") or not plan or price <= 0:
        return
    if store.has_open_trade(symbol, tf):
        return
    store.open_paper_trade(
        symbol, tf, "long" if bias == "up" else "short",
        float(price), float(plan["stop"]), float(plan["target"]), float(plan["rr"]),
    )


def evaluate(candles_for) -> None:
    """Close any open trade whose stop or target a later candle has touched."""
    for t in store.open_trades():
        try:
            candles = candles_for(t["symbol"], t["tf"], 300)
        except Exception:
            continue
        is_long = t["direction"] == "long"
        for c in candles:
            if c["time"] <= t["opened_ts"]:
                continue  # no look-ahead into the entry candle
            hit_stop = c["low"] <= t["stop"] if is_long else c["high"] >= t["stop"]
            hit_target = c["high"] >= t["target"] if is_long else c["low"] <= t["target"]
            if hit_stop:  # if a single candle hits both, assume the stop first
                store.close_paper_trade(t["id"], t["stop"], "loss", -1.0)
                break
            if hit_target:
                store.close_paper_trade(t["id"], t["target"], "win", round(float(t["rr"]), 2))
                break
