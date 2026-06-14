"""Signal scorer v2 — regime-aware weighted votes + higher-timeframe confluence.

Naive vote counting double-counts correlated indicators (RSI, MACD and EMA
crosses all measure momentum). Instead, votes are weighted by market regime:
  - ADX >= 25 (trending): trend-followers count more, oscillators less —
    "overbought" is not a sell signal in a strong trend.
  - ADX < 20 (ranging): oscillators count more, trend signals less —
    crosses whipsaw constantly in a range.
A higher-timeframe trend that agrees adds confidence; one that disagrees
cuts it hard (fighting the bigger trend is how accounts die).
"""

_REGIME_WEIGHTS = {
    "strong": {"trend": 1.5, "osc": 0.8, "volume": 1.0},
    "moderate": {"trend": 1.0, "osc": 1.0, "volume": 1.0},
    "weak": {"trend": 0.8, "osc": 1.25, "volume": 1.0},
}


def score(analysis: dict, htf_trend: str | None = None) -> dict:
    # only indicators with real data AND left on vote; greyed/disabled ones don't
    details = [d for d in analysis["details"]
               if d.get("available", True) and not d.get("disabled")]
    weights = _REGIME_WEIGHTS[analysis["trend_strength"]]

    w_up = sum(weights[d["kind"]] for d in details if d["vote"] == "up")
    w_down = sum(weights[d["kind"]] for d in details if d["vote"] == "down")
    w_neutral = sum(weights[d["kind"]] for d in details if d["vote"] == "neutral")
    total = w_up + w_down + w_neutral
    if total == 0:
        return {"bias": "neutral", "confidence": 0, "htf_note": None}

    net = w_up - w_down
    agreement = abs(net) / total  # how decisively the weighted board leans (0..1)

    # Calibration: only commit to a direction when the board leans decisively.
    # Marginal boards return "no edge" — this raises the accuracy of the calls
    # we DO make (fewer false directional signals = better hit-rate). Require a
    # net weighted lean of >=18% of the board before committing.
    MARGIN = 0.18
    if agreement >= MARGIN and net > 0:
        bias = "up"
    elif agreement >= MARGIN and net < 0:
        bias = "down"
    else:
        bias = "neutral"

    confidence = 50 + agreement * 32  # 50 (split) .. ~82 (unanimous)

    # Neutral votes drag confidence — indecision is information
    confidence -= w_neutral / total * 10

    # High volatility = wider error bars
    if analysis["volatility"] == "high":
        confidence -= 7
    elif analysis["volatility"] == "low":
        confidence += 3

    # A clear ADX trend that backs the call is a real edge; a dead-flat market
    # (very low ADX) means even a leaning board is mostly noise → discount it.
    adx = analysis.get("adx", 20)
    if bias != "neutral":
        if adx >= 25:
            confidence += 4
        elif adx < 15:
            confidence -= 6

    # Higher-timeframe confluence: with the bigger trend or against it?
    htf_note = None
    if htf_trend in ("up", "down") and bias != "neutral":
        if htf_trend == bias:
            confidence += 8
            htf_note = f"aligned with higher-timeframe {htf_trend}trend"
        else:
            # fighting the bigger trend is the lowest-quality setup — demote it
            confidence -= 16
            htf_note = f"AGAINST higher-timeframe {htf_trend}trend — countertrend, low quality"

    confidence = int(max(5, min(92, round(confidence))))
    if bias == "neutral":
        confidence = min(confidence, 48)
    return {"bias": bias, "confidence": confidence, "htf_note": htf_note}


def make_plan(bias: str, price: float, atr_abs: float) -> dict | None:
    """ATR-based trade plan: stop at 1.5x ATR against you, target at 2.5x with
    you (risk:reward 1:1.67). Position-sizing guidance, not a guarantee."""
    if bias not in ("up", "down") or atr_abs <= 0 or price <= 0:
        return None
    stop_dist, target_dist = 1.5 * atr_abs, 2.5 * atr_abs
    if bias == "up":
        stop, target = price - stop_dist, price + target_dist
    else:
        stop, target = price + stop_dist, price - target_dist
    return {
        "direction": "long" if bias == "up" else "short",
        "entry": round(price, 6),
        "stop": round(stop, 6),
        "target": round(target, 6),
        "rr": round(target_dist / stop_dist, 2),
    }
