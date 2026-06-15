"""Volume profile — how much volume traded at each price level.

Bins the visible range into horizontal price buckets and distributes each
candle's volume across the buckets its high–low range spans. Surfaces the
Point of Control (POC, the highest-volume price) and the 70% value area —
the zone where most business got done and price tends to gravitate.
"""


def build(candles: list[dict], bins: int = 24) -> dict | None:
    if len(candles) < 10:
        return None
    lo = min(c["low"] for c in candles)
    hi = max(c["high"] for c in candles)
    if hi <= lo:
        return None
    width = (hi - lo) / bins
    vol = [0.0] * bins

    for c in candles:
        a = int((c["low"] - lo) / width)
        b = int((c["high"] - lo) / width)
        a = max(0, min(bins - 1, a))
        b = max(0, min(bins - 1, b))
        share = (c["volume"] or 0.0) / (b - a + 1)
        for k in range(a, b + 1):
            vol[k] += share

    total = sum(vol) or 1.0
    poc_idx = max(range(bins), key=lambda k: vol[k])
    # value area: add the heaviest buckets until they hold 70% of volume
    acc, va = 0.0, set()
    for k in sorted(range(bins), key=lambda k: vol[k], reverse=True):
        acc += vol[k]
        va.add(k)
        if acc / total >= 0.70:
            break

    buckets = [{"price": round(lo + (k + 0.5) * width, 6), "volume": round(vol[k], 2)}
               for k in range(bins)]
    return {
        "bins": buckets,
        "poc": round(lo + (poc_idx + 0.5) * width, 6),
        "value_area_low": round(lo + min(va) * width, 6),
        "value_area_high": round(lo + (max(va) + 1) * width, 6),
        "max_volume": round(max(vol), 2),
    }
