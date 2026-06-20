"""Strategy backtest — replays the live engine over history into a track record.

This answers the first question any trader asks: *does it actually work?* It
walks the candles forward bar by bar, and at each newly-closed bar runs the
exact same signal scorer the dashboard uses (no look-ahead — only bars that had
closed at that point are analyzed). When the board commits to a direction it
"enters" at the next bar's open with the same ATR stop/target from
``signal.make_plan``, then later bars decide the outcome: target hit = +R:R,
stop hit = -1R (if one bar straddles both, the stop is assumed first).

Out of that fall the numbers that matter — win rate, net R, profit factor,
expectancy and max drawdown — plus the cumulative-R equity curve for the chart.
It is a hypothetical, friction-free simulation (no spread/slippage/fees), so
treat it as evidence the logic has an edge, not a brokerage statement.
"""
from engine import indicators, signal

# Enough history for EMA200 to be meaningful without re-crunching 300 bars each
# step; the signal only ever looks back this far anyway.
_WINDOW = 210


def run(candles: list[dict], tf_sec: int, lookback: int = 160) -> dict:
    n = len(candles)
    start = max(indicators.MIN_CANDLES + 2, n - lookback)
    if start >= n - 1:
        return _empty()

    trades: list[dict] = []
    pos: dict | None = None

    for i in range(start, n):
        bar = candles[i]

        # 1) Manage an open position against this bar (never the entry bar itself).
        if pos and i > pos["entry_idx"]:
            is_long = pos["direction"] == "long"
            hit_stop = bar["low"] <= pos["stop"] if is_long else bar["high"] >= pos["stop"]
            hit_target = bar["high"] >= pos["target"] if is_long else bar["low"] <= pos["target"]
            if hit_stop:  # straddle → assume the stop filled first (conservative)
                trades.append(_close(pos, bar, pos["stop"], -1.0))
                pos = None
            elif hit_target:
                trades.append(_close(pos, bar, pos["target"], pos["rr"]))
                pos = None

        # 2) If flat, decide an entry for the NEXT bar from bars closed through i.
        if pos is None and i + 1 < n:
            window = candles[max(0, i + 1 - _WINDOW):i + 1]
            try:
                analysis = indicators.analyze(window)
            except Exception:
                continue
            scored = signal.score(analysis)
            if scored["bias"] not in ("up", "down"):
                continue
            entry = float(candles[i + 1]["open"])
            plan = signal.make_plan(scored["bias"], entry, analysis["atr_abs"])
            if not plan:
                continue
            pos = {
                "direction": plan["direction"],
                "entry": entry,
                "stop": plan["stop"],
                "target": plan["target"],
                "rr": float(plan["rr"]),
                "confidence": scored["confidence"],
                "entry_idx": i + 1,
                "entry_time": int(candles[i + 1]["time"]),
            }

    return _summarize(trades, candles[start]["time"])


def _close(pos: dict, bar: dict, exit_price: float, r: float) -> dict:
    return {
        "direction": pos["direction"],
        "entry": round(pos["entry"], 6),
        "exit": round(float(exit_price), 6),
        "entry_time": pos["entry_time"],
        "exit_time": int(bar["time"]),
        "result": "win" if r > 0 else "loss",
        "r": round(r, 2),
        "confidence": pos["confidence"],
    }


def _empty() -> dict:
    return {
        "trades": 0, "wins": 0, "losses": 0, "win_rate": None,
        "net_r": 0.0, "avg_win_r": None, "avg_loss_r": None, "profit_factor": None,
        "expectancy_r": None, "max_drawdown_r": 0.0, "best_r": None, "worst_r": None,
        "equity": [], "recent": [],
        "note": "Not enough closed trades over the available history yet.",
    }


def _summarize(trades: list[dict], start_time: int) -> dict:
    n = len(trades)
    if n == 0:
        return _empty()

    wins = [t for t in trades if t["r"] > 0]
    losses = [t for t in trades if t["r"] <= 0]
    gross_win = sum(t["r"] for t in wins)
    gross_loss = -sum(t["r"] for t in losses)  # positive magnitude
    net_r = gross_win - gross_loss

    # Cumulative-R equity curve + peak-to-trough max drawdown (in R).
    equity = [{"t": int(start_time), "r": 0.0}]
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in trades:
        cum = round(cum + t["r"], 2)
        equity.append({"t": t["exit_time"], "r": cum})
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)

    return {
        "trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / n * 100, 1),
        "net_r": round(net_r, 2),
        "avg_win_r": round(gross_win / len(wins), 2) if wins else None,
        "avg_loss_r": round(-gross_loss / len(losses), 2) if losses else None,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else None,
        "expectancy_r": round(net_r / n, 2),
        "max_drawdown_r": round(max_dd, 2),
        "best_r": round(max(t["r"] for t in trades), 2),
        "worst_r": round(min(t["r"] for t in trades), 2),
        "equity": equity,
        "recent": list(reversed(trades[-15:])),
    }
