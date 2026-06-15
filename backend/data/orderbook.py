"""Order-book depth snapshot from Binance (spot). Summarises buy/sell pressure
near the touch plus the top levels for a mini depth ladder."""
import httpx

from data import cache
from data.crypto import HOSTS


def depth(symbol: str, limit: int = 100) -> dict | None:
    key = f"depth:{symbol}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    out = None
    for host in HOSTS:
        try:
            r = httpx.get(f"{host}/api/v3/depth", params={"symbol": symbol, "limit": limit}, timeout=8)
            r.raise_for_status()
            d = r.json()
            bids = [(float(p), float(q)) for p, q in d["bids"]]
            asks = [(float(p), float(q)) for p, q in d["asks"]]
            if not bids or not asks:
                break
            bid_vol = sum(q for _, q in bids)
            ask_vol = sum(q for _, q in asks)
            tot = bid_vol + ask_vol or 1.0
            mid = (bids[0][0] + asks[0][0]) / 2
            spread = asks[0][0] - bids[0][0]
            out = {
                "mid": round(mid, 6),
                "spread": round(spread, 6),
                "spread_pct": round(spread / mid * 100, 4) if mid else 0.0,
                "bid_volume": round(bid_vol, 2),
                "ask_volume": round(ask_vol, 2),
                "imbalance_pct": round(bid_vol / tot * 100, 1),  # share of depth on the bid side
                "bids": [{"price": p, "qty": round(q, 3)} for p, q in bids[:12]],
                "asks": [{"price": p, "qty": round(q, 3)} for p, q in asks[:12]],
            }
            break
        except Exception:
            continue
    cache.put(key, out, ttl=5)  # order book moves fast; short cache
    return out
