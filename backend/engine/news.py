"""Free news via RSS — no API key, no rate limits worth worrying about."""
from concurrent.futures import ThreadPoolExecutor

import feedparser
import httpx

from data import cache

# Per asset-class feeds; broad finance feeds apply to everything.
FEEDS = {
    "global": [
        "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "https://www.investing.com/rss/news_25.rss",  # market overview
    ],
    "crypto": [
        "https://cointelegraph.com/rss",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
    ],
    "forex": ["https://www.investing.com/rss/news_1.rss"],
    "commodity": ["https://www.investing.com/rss/news_11.rss"],
    "index": ["https://www.investing.com/rss/news_25.rss"],
}


def headlines(asset_class: str, limit: int = 10) -> list[str]:
    key = f"news:{asset_class}"
    cached = cache.get(key)
    if cached is not None:
        return cached[:limit]

    def _fetch(url: str) -> list[str]:
        try:
            # fetch ourselves with a hard timeout — feedparser.parse(url) has none
            # and one slow RSS server would hang the whole /predict request
            resp = httpx.get(url, timeout=6, follow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0 (TrendPredictor RSS)"})
            feed = feedparser.parse(resp.content)
            return [e.title.strip() for e in feed.entries[:6] if getattr(e, "title", None)]
        except Exception:
            return []  # a dead feed should never break a prediction

    urls = FEEDS.get(asset_class, []) + FEEDS["global"]
    titles: list[str] = []
    # parallel fetch: worst case = slowest single feed, not the sum of all
    with ThreadPoolExecutor(max_workers=len(urls)) as pool:
        for batch in pool.map(_fetch, urls):
            titles += batch

    # de-dupe, keep order
    seen, unique = set(), []
    for t in titles:
        if t.lower() not in seen:
            seen.add(t.lower())
            unique.append(t)

    cache.put(key, unique, ttl=600)  # news refresh: 10 min
    return unique[:limit]
