"""Asset registry — which symbols we track and where their data comes from."""

ASSETS: dict[str, dict] = {
    "BTCUSDT": {"name": "Bitcoin", "asset_class": "crypto", "source": "binance"},
    "ETHUSDT": {"name": "Ethereum", "asset_class": "crypto", "source": "binance"},
    "EURUSD": {"name": "EUR/USD", "asset_class": "forex", "source": "yahoo", "yahoo": "EURUSD=X"},
    "GBPUSD": {"name": "GBP/USD", "asset_class": "forex", "source": "yahoo", "yahoo": "GBPUSD=X"},
    "GOLD": {"name": "Gold Futures", "asset_class": "commodity", "source": "yahoo", "yahoo": "GC=F"},
    "OIL": {"name": "Crude Oil WTI", "asset_class": "commodity", "source": "yahoo", "yahoo": "CL=F"},
    "SPX": {"name": "S&P 500", "asset_class": "index", "source": "yahoo", "yahoo": "^GSPC"},
    "NASDAQ": {"name": "Nasdaq 100", "asset_class": "index", "source": "yahoo", "yahoo": "^NDX"},
}

TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d", "1wk"]


def get_asset(symbol: str) -> dict:
    asset = ASSETS.get(symbol.upper())
    if asset is None:
        raise KeyError(f"Unknown symbol: {symbol}")
    return {"symbol": symbol.upper(), **asset}
