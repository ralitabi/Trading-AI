"""Asset registry — which symbols we track and where their data comes from.

Sources (both free, no API key):
  - binance : real-time crypto (USDT pairs)
  - yahoo   : forex / commodities / indices / stocks (~15 min delayed intraday)

`broadcast: True` marks the lean subset the Telegram signal-service + snapshot
collector scan on a schedule (kept small so they stay fast). Every asset here is
fully chartable + analysable on demand regardless of that flag.
"""


def _c(name, broadcast=False):  # crypto (Binance USDT pair; key == symbol)
    a = {"name": name, "asset_class": "crypto", "source": "binance"}
    if broadcast:
        a["broadcast"] = True
    return a


def _y(name, asset_class, yahoo, broadcast=False):  # yahoo-backed
    a = {"name": name, "asset_class": asset_class, "source": "yahoo", "yahoo": yahoo}
    if broadcast:
        a["broadcast"] = True
    return a


ASSETS: dict[str, dict] = {
    # ---- Crypto (Binance, real-time) ----
    "BTCUSDT": _c("Bitcoin", broadcast=True),
    "ETHUSDT": _c("Ethereum", broadcast=True),
    "SOLUSDT": _c("Solana", broadcast=True),
    "BNBUSDT": _c("BNB"),
    "XRPUSDT": _c("XRP"),
    "ADAUSDT": _c("Cardano"),
    "DOGEUSDT": _c("Dogecoin"),
    "AVAXUSDT": _c("Avalanche"),
    "DOTUSDT": _c("Polkadot"),
    "LINKUSDT": _c("Chainlink"),
    "LTCUSDT": _c("Litecoin"),
    "TRXUSDT": _c("Tron"),
    "BCHUSDT": _c("Bitcoin Cash"),
    "ATOMUSDT": _c("Cosmos"),
    "NEARUSDT": _c("NEAR Protocol"),
    "UNIUSDT": _c("Uniswap"),
    "APTUSDT": _c("Aptos"),
    "ARBUSDT": _c("Arbitrum"),
    "OPUSDT": _c("Optimism"),
    "INJUSDT": _c("Injective"),
    "SUIUSDT": _c("Sui"),
    "PEPEUSDT": _c("Pepe"),
    "SHIBUSDT": _c("Shiba Inu"),

    # ---- Forex (Yahoo) ----
    "EURUSD": _y("EUR/USD", "forex", "EURUSD=X", broadcast=True),
    "GBPUSD": _y("GBP/USD", "forex", "GBPUSD=X", broadcast=True),
    "USDJPY": _y("USD/JPY", "forex", "USDJPY=X"),
    "AUDUSD": _y("AUD/USD", "forex", "AUDUSD=X"),
    "USDCAD": _y("USD/CAD", "forex", "USDCAD=X"),
    "NZDUSD": _y("NZD/USD", "forex", "NZDUSD=X"),
    "USDCHF": _y("USD/CHF", "forex", "USDCHF=X"),
    "EURJPY": _y("EUR/JPY", "forex", "EURJPY=X"),
    "GBPJPY": _y("GBP/JPY", "forex", "GBPJPY=X"),
    "EURGBP": _y("EUR/GBP", "forex", "EURGBP=X"),
    "USDINR": _y("USD/INR", "forex", "USDINR=X"),
    "USDPKR": _y("USD/PKR", "forex", "USDPKR=X"),

    # ---- Commodities (Yahoo futures) ----
    "GOLD": _y("Gold", "commodity", "GC=F", broadcast=True),
    "SILVER": _y("Silver", "commodity", "SI=F"),
    "OIL": _y("Crude Oil WTI", "commodity", "CL=F", broadcast=True),
    "BRENT": _y("Brent Crude", "commodity", "BZ=F"),
    "NATGAS": _y("Natural Gas", "commodity", "NG=F"),
    "COPPER": _y("Copper", "commodity", "HG=F"),
    "PLATINUM": _y("Platinum", "commodity", "PL=F"),
    "PALLADIUM": _y("Palladium", "commodity", "PA=F"),

    # ---- Indices (Yahoo) ----
    "SPX": _y("S&P 500", "index", "^GSPC", broadcast=True),
    "NASDAQ": _y("Nasdaq 100", "index", "^NDX", broadcast=True),
    "DOW": _y("Dow Jones", "index", "^DJI"),
    "RUSSELL": _y("Russell 2000", "index", "^RUT"),
    "VIX": _y("Volatility (VIX)", "index", "^VIX"),
    "FTSE": _y("FTSE 100", "index", "^FTSE"),
    "DAX": _y("DAX 40", "index", "^GDAXI"),
    "NIKKEI": _y("Nikkei 225", "index", "^N225"),
    "HANGSENG": _y("Hang Seng", "index", "^HSI"),
    "NIFTY": _y("Nifty 50", "index", "^NSEI"),
    "SENSEX": _y("Sensex", "index", "^BSESN"),

    # ---- Stocks (Yahoo) ----
    "AAPL": _y("Apple", "stock", "AAPL", broadcast=True),
    "MSFT": _y("Microsoft", "stock", "MSFT"),
    "NVDA": _y("Nvidia", "stock", "NVDA", broadcast=True),
    "TSLA": _y("Tesla", "stock", "TSLA"),
    "AMZN": _y("Amazon", "stock", "AMZN"),
    "GOOGL": _y("Alphabet (Google)", "stock", "GOOGL"),
    "META": _y("Meta", "stock", "META"),
    "NFLX": _y("Netflix", "stock", "NFLX"),
    "AMD": _y("AMD", "stock", "AMD"),
}

TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d", "1wk"]

# the lean subset auto-scanned by the Telegram signal-service + snapshot collector
BROADCAST_SYMBOLS = [s for s, a in ASSETS.items() if a.get("broadcast")]


def get_asset(symbol: str) -> dict:
    asset = ASSETS.get(symbol.upper())
    if asset is None:
        raise KeyError(f"Unknown symbol: {symbol}")
    return {"symbol": symbol.upper(), **asset}
