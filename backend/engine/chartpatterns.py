"""Classic chart-pattern recognition from swing pivots.

Detects candidate double tops/bottoms, head & shoulders (and inverse), and
triangles (ascending / descending / symmetric) from recent pivot highs and lows.
Each comes with the defining points (so the chart can outline it), a neckline /
breakout level, a target, a direction and a rough confidence.

Geometric pattern detection is inherently noisy — these are CANDIDATES to weigh
alongside the signal, not certainties.
"""
import numpy as np
import pandas as pd

from engine import indicators as ind


def _swings(highs: np.ndarray, lows: np.ndarray, left: int = 3, right: int = 3):
    """Return chronological swing points: list of (index, price, kind)."""
    n = len(highs)
    pts = []
    for i in range(left, n - right):
        if highs[i] >= highs[i - left:i + right + 1].max() - 1e-12:
            pts.append((i, float(highs[i]), "H"))
        elif lows[i] <= lows[i - left:i + right + 1].min() + 1e-12:
            pts.append((i, float(lows[i]), "L"))
    # collapse consecutive same-kind pivots, keeping the more extreme one
    out = []
    for p in pts:
        if out and out[-1][2] == p[2]:
            if (p[2] == "H" and p[1] > out[-1][1]) or (p[2] == "L" and p[1] < out[-1][1]):
                out[-1] = p
        else:
            out.append(p)
    return out


def _near(a: float, b: float, tol: float = 0.02) -> bool:
    return abs(a - b) / ((a + b) / 2 or 1e-9) <= tol


def detect(candles: list[dict], tf_sec: int) -> list[dict]:
    if len(candles) < 50:
        return []
    df = pd.DataFrame(candles)
    highs = df["high"].to_numpy(float)
    lows = df["low"].to_numpy(float)
    times = df["time"].to_numpy()
    price_now = float(df["close"].iloc[-1])
    sw = _swings(highs, lows)
    if len(sw) < 4:
        return []

    def pt(p):
        return {"time": int(times[p[0]]), "price": round(p[1], 6)}

    out: list[dict] = []
    Hs = [p for p in sw if p[2] == "H"]
    Ls = [p for p in sw if p[2] == "L"]

    # ---- Head & Shoulders (bearish) : last three highs, middle highest ----
    if len(Hs) >= 3:
        ls, head, rs = Hs[-3], Hs[-2], Hs[-1]
        if head[1] > ls[1] and head[1] > rs[1] and _near(ls[1], rs[1], 0.03):
            troughs = [p for p in Ls if ls[0] < p[0] < rs[0]]
            if troughs:
                neck = float(np.mean([t[1] for t in troughs]))
                out.append({
                    "name": "Head & Shoulders", "direction": "bearish",
                    "outline": [pt(ls), pt(head), pt(rs)],
                    "neckline": round(neck, 6),
                    "target": round(neck - (head[1] - neck), 6),
                    "confirmed": price_now < neck,
                    "confidence": 62 + (10 if price_now < neck else 0),
                })

    # ---- Inverse Head & Shoulders (bullish) : last three lows, middle lowest ----
    if len(Ls) >= 3:
        ls, head, rs = Ls[-3], Ls[-2], Ls[-1]
        if head[1] < ls[1] and head[1] < rs[1] and _near(ls[1], rs[1], 0.03):
            peaks = [p for p in Hs if ls[0] < p[0] < rs[0]]
            if peaks:
                neck = float(np.mean([t[1] for t in peaks]))
                out.append({
                    "name": "Inverse Head & Shoulders", "direction": "bullish",
                    "outline": [pt(ls), pt(head), pt(rs)],
                    "neckline": round(neck, 6),
                    "target": round(neck + (neck - head[1]), 6),
                    "confirmed": price_now > neck,
                    "confidence": 62 + (10 if price_now > neck else 0),
                })

    # ---- Double Top (bearish) / Double Bottom (bullish) ----
    if len(Hs) >= 2 and _near(Hs[-1][1], Hs[-2][1], 0.02):
        trough = min((p for p in Ls if Hs[-2][0] < p[0] < Hs[-1][0]),
                     default=None, key=lambda p: p[1])
        if trough:
            out.append({
                "name": "Double Top", "direction": "bearish",
                "outline": [pt(Hs[-2]), pt(trough), pt(Hs[-1])],
                "neckline": round(trough[1], 6),
                "target": round(trough[1] - (Hs[-1][1] - trough[1]), 6),
                "confirmed": price_now < trough[1],
                "confidence": 58 + (10 if price_now < trough[1] else 0),
            })
    if len(Ls) >= 2 and _near(Ls[-1][1], Ls[-2][1], 0.02):
        peak = max((p for p in Hs if Ls[-2][0] < p[0] < Ls[-1][0]),
                   default=None, key=lambda p: p[1])
        if peak:
            out.append({
                "name": "Double Bottom", "direction": "bullish",
                "outline": [pt(Ls[-2]), pt(peak), pt(Ls[-1])],
                "neckline": round(peak[1], 6),
                "target": round(peak[1] + (peak[1] - Ls[-1][1]), 6),
                "confirmed": price_now > peak[1],
                "confidence": 58 + (10 if price_now > peak[1] else 0),
            })

    # ---- Triangles : slope of recent highs vs lows ----
    if len(Hs) >= 3 and len(Ls) >= 3:
        hh, hl = Hs[-3:], Ls[-3:]
        sh = float(np.polyfit([p[0] for p in hh], [p[1] for p in hh], 1)[0])
        sl = float(np.polyfit([p[0] for p in hl], [p[1] for p in hl], 1)[0])
        scale = price_now / max(1, hh[-1][0] - hh[0][0])
        flat_h, flat_l = abs(sh) < 0.0006 * scale, abs(sl) < 0.0006 * scale
        tri = None
        if flat_h and sl > 0:
            tri = ("Ascending Triangle", "bullish")
        elif flat_l and sh < 0:
            tri = ("Descending Triangle", "bearish")
        elif sh < 0 and sl > 0:
            tri = ("Symmetric Triangle", "neutral")
        if tri:
            out.append({
                "name": tri[0], "direction": tri[1],
                "outline": [pt(hh[0]), pt(hl[0]), pt(hh[-1]), pt(hl[-1])],
                "neckline": round(hh[-1][1], 6),
                "target": None,
                "confirmed": False,
                "confidence": 52,
            })

    # most recent / most-confident first
    out.sort(key=lambda p: (p["outline"][-1]["time"], p["confidence"]), reverse=True)
    return out[:4]
