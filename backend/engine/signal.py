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

    # Calibration floor — abstain on low-conviction directional calls. In replay
    # across BTC/ETH/SPX/EURUSD, calls below ~60 confidence hit BELOW 50% (a
    # coin flip or worse), dragging accuracy down; calls at/above 60 clear 51%+.
    # So committing to them costs accuracy — return "no edge" instead.
    CONF_FLOOR = 60
    if bias != "neutral" and confidence < CONF_FLOOR:
        bias = "neutral"

    if bias == "neutral":
        confidence = min(confidence, 48)
    return {"bias": bias, "confidence": confidence, "htf_note": htf_note}


def _risk_factors(conf: int, adx: float, vol: str, countertrend: bool) -> list[dict]:
    """The handful of inputs behind the risk score, each as good/ok/weak — so the
    meter can show WHY it reads the way it does."""
    return [
        {"label": "Conviction",
         "state": "good" if conf >= 65 else "weak" if conf < 55 else "ok",
         "detail": f"{conf}%"},
        {"label": "Trend strength",
         "state": "good" if adx >= 25 else "weak" if adx < 18 else "ok",
         "detail": f"ADX {round(adx)}"},
        {"label": "Volatility",
         "state": "good" if vol == "low" else "weak" if vol == "high" else "ok",
         "detail": vol},
        {"label": "Higher timeframe",
         "state": "weak" if countertrend else "good",
         "detail": "against trend" if countertrend else "aligned"},
    ]


def assess_safety(scored: dict, analysis: dict) -> dict:
    """A plain-English read on how safe it is to act right now, plus a 0–100 risk
    score for the meter (0 = very safe to act, 100 = very risky).

    Combines conviction, higher-timeframe alignment, trend strength and
    volatility into one verdict — and is happy to say "stay out".
    """
    conf = scored["confidence"]
    bias = scored["bias"]
    vol = analysis.get("volatility", "moderate")
    adx = analysis.get("adx", 0)
    countertrend = bool(scored.get("htf_note") and "AGAINST" in scored["htf_note"])

    # Continuous risk score so the meter needle can sit anywhere, not just in
    # three buckets. Higher conviction lowers risk; fighting the bigger trend,
    # high volatility and a dead-flat (low-ADX) tape all raise it.
    risk = 52.0 - (conf - 55) * 1.25
    if countertrend:
        risk += 28
    if vol == "high":
        risk += 16
    elif vol == "low":
        risk -= 8
    if adx >= 25:
        risk -= 10
    elif adx < 15:
        risk += 10
    if bias == "neutral":
        risk = max(risk, 72)  # no direction = never "safe to act"
    risk = int(max(2, min(98, round(risk))))
    level = "safe" if risk < 40 else "caution" if risk < 68 else "risky"
    factors = _risk_factors(conf, adx, vol, countertrend)

    if bias == "neutral":
        return {"level": "risky", "score": risk,
                "headline": "No clear edge right now — better to wait",
                "action": "Stay out", "direction": "none", "factors": factors}

    dir_word = "long (upward)" if bias == "up" else "short (downward)"
    if level == "safe":
        headline = f"Looks safe to trade {dir_word} now"
        action = f"Consider {dir_word}"
    elif level == "caution":
        headline = f"Mixed conditions — only trade {dir_word} with tight risk"
        action = f"Small {dir_word}, tight stop"
    else:
        reason = ("against the bigger trend" if countertrend
                  else "very volatile" if vol == "high" else "low conviction")
        headline = f"Risky right now ({reason}) — better to stay out"
        action = "Stay out / wait"
    return {"level": level, "score": risk, "headline": headline, "action": action,
            "direction": bias, "factors": factors}


def assess_market(analysis: dict, htf_trend: str | None = None) -> dict:
    """Market-condition read — is the tape itself worth trading right now,
    independent of any one entry? A clean, trending, structured market scores
    low (green); a choppy, whippy, directionless one scores high (red).

    Returns a 0–100 score (0 = clean/tradeable … 100 = choppy/avoid) for the
    second meter that sits next to the trade-entry risk meter.
    """
    adx = float(analysis.get("adx", 0))
    vol = analysis.get("volatility", "moderate")
    votes = analysis.get("votes", {}) or {}
    up, down, neu = votes.get("up", 0), votes.get("down", 0), votes.get("neutral", 0)
    tot = up + down + neu or 1
    breadth = abs(up - down) / tot       # how lopsided the board is (clear lean)
    neutral_share = neu / tot            # indecision

    cond = 50.0
    if adx >= 30:
        cond -= 24
    elif adx >= 25:
        cond -= 15
    elif adx >= 20:
        cond -= 5
    elif adx < 15:
        cond += 18
    else:
        cond += 6
    cond += {"high": 18, "moderate": -8, "low": -4}.get(vol, 0)
    cond -= 8 if htf_trend in ("up", "down") else -6   # clear HTF structure helps
    cond -= breadth * 14
    cond += neutral_share * 12
    cond = int(max(2, min(98, round(cond))))
    level = "good" if cond < 38 else "mixed" if cond < 66 else "poor"

    if up > down and adx >= 20:
        direction = "up"
    elif down > up and adx >= 20:
        direction = "down"
    else:
        direction = "flat"

    headline = {
        "good": "Clean, trending market — good conditions to trade",
        "mixed": "Tradeable but choppy in spots — pick your spots",
        "poor": "Choppy, directionless tape — hard to trade right now",
    }[level]
    factors = [
        {"label": "Trend clarity",
         "state": "good" if adx >= 25 else "weak" if adx < 18 else "ok",
         "detail": f"ADX {round(adx)}"},
        {"label": "Volatility",
         "state": "good" if vol == "moderate" else "weak" if vol == "high" else "ok",
         "detail": vol},
        {"label": "Structure",
         "state": "good" if htf_trend in ("up", "down") else "weak",
         "detail": f"{htf_trend}trend" if htf_trend in ("up", "down") else "no clear HTF"},
        {"label": "Agreement",
         "state": "good" if breadth >= 0.3 else "weak" if neutral_share > 0.4 else "ok",
         "detail": f"{int(breadth * 100)}% lean"},
    ]
    return {"level": level, "score": cond, "headline": headline,
            "direction": direction, "factors": factors}


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
