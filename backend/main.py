"""Trading AI — FastAPI backend.

Run locally:  uvicorn main:app --reload --port 8000
"""
import time

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from data import cache, calendar, context, crypto, market, orderbook, store
from data.assets import ASSETS, TIMEFRAMES, get_asset
from engine import (
    ai, avgline, backtest, chartpatterns, forecast, indicators, news, overlays, paper, patterns, scoring,
    signal, timing, trendcast, trends, volprofile,
)

TF_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400, "1wk": 604800}

app = FastAPI(title="Trading AI", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your Vercel domain in production
    allow_methods=["*"],
    allow_headers=["*"],
)

DISCLAIMER = "Trading AI — real-time market intelligence."


def _analyze_closed(data: list[dict]) -> dict:
    """Indicators run on CLOSED candles only — the last bar is still forming
    and including it makes signals flip back and forth mid-candle."""
    closed = data[:-1] if len(data) > indicators.MIN_CANDLES else data
    return indicators.analyze(closed)


# Which higher timeframe to check for trend confluence
_HTF = {"1m": "15m", "5m": "1h", "15m": "4h", "1h": "4h", "4h": "1d", "1d": "1wk"}


def _htf_trend(symbol: str, tf: str) -> tuple[str | None, str | None]:
    """(higher_tf, trend) — never breaks the request if the fetch fails."""
    htf = _HTF.get(tf)
    if htf is None:
        return None, None
    try:
        candles = _candles_for(symbol, htf, 120)
        return htf, indicators.trend_of(candles[:-1])
    except Exception:
        return None, None


def _best_window(symbol: str) -> dict | None:
    """Cached per-asset 'best hours to trade' from hourly volatility."""
    key = f"timing:{symbol}"
    bw = cache.get(key)
    if bw is None:
        try:
            bw = timing.best_window(_candles_for(symbol, "1h", 300))
        except Exception:
            bw = None
        cache.put(key, bw, ttl=3600)  # slow-changing stat; refresh hourly
    return bw


def _technical_block(analysis: dict, scored: dict, plan: dict | None,
                     htf: str | None, htf_trend: str | None, symbol: str) -> dict:
    return {
        "bias": scored["bias"], "confidence": scored["confidence"],
        "votes": analysis["votes"], "indicators": analysis["details"],
        "volatility": analysis["volatility"], "atr_pct": analysis["atr_pct"],
        "adx": analysis["adx"], "trend_strength": analysis["trend_strength"],
        "levels": {"support": analysis["support"], "resistance": analysis["resistance"]},
        "htf": {"tf": htf, "trend": htf_trend, "note": scored.get("htf_note")} if htf else None,
        "plan": plan,
        "safety": signal.assess_safety(scored, analysis),
        "market": signal.assess_market(analysis, htf_trend),
        "best_window": _best_window(symbol),
    }


def _candles_for(symbol: str, tf: str, limit: int = 300) -> list[dict]:
    asset = get_asset(symbol)
    if tf not in TIMEFRAMES:
        raise HTTPException(400, f"Unsupported timeframe '{tf}'. Use one of {TIMEFRAMES}")
    if asset["source"] == "binance":
        return crypto.fetch_candles(asset["symbol"], tf, limit)
    return market.fetch_candles(asset["yahoo"], tf, limit)


@app.get("/")
def root():
    return {"app": "Trading AI", "status": "ok", "disclaimer": DISCLAIMER}


@app.get("/assets")
def assets():
    return [
        {"symbol": s, "name": a["name"], "asset_class": a["asset_class"], "source": a["source"]}
        for s, a in ASSETS.items()
    ]


@app.get("/candles/{symbol}")
def candles(symbol: str, tf: str = Query("1h"), limit: int = Query(300, le=1000)):
    try:
        data = _candles_for(symbol, tf, limit)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return {"symbol": symbol.upper(), "tf": tf, "candles": data}


@app.get("/signal/{symbol}")
def get_signal(symbol: str, tf: str = Query("1h"),
               indicators_on: str | None = Query(None)):
    """Live technical signal. indicators_on: optional comma-separated names of
    indicators left ON in the UI; when given, only those are scored/tallied."""
    try:
        asset = get_asset(symbol)
        data = _candles_for(symbol, tf, 300)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))

    try:
        analysis = _analyze_closed(data)
    except ValueError as e:
        raise HTTPException(422, str(e))

    # Honor the user's on/off toggles: mark disabled rows (kept for display) and
    # recompute the vote tally so bias/confidence reflect the live selection.
    if indicators_on is not None:
        on = {n.strip() for n in indicators_on.split(",") if n.strip()}
        for d in analysis["details"]:
            d["disabled"] = d.get("available", True) and d["name"] not in on
        live = [d for d in analysis["details"] if d.get("available", True) and not d["disabled"]]
        analysis["votes"] = {
            "up": sum(1 for d in live if d["vote"] == "up"),
            "down": sum(1 for d in live if d["vote"] == "down"),
            "neutral": sum(1 for d in live if d["vote"] == "neutral"),
        }
    htf, htf_trend = _htf_trend(symbol, tf)
    scored = signal.score(analysis, htf_trend)
    price_now = data[-1]["close"]
    plan = signal.make_plan(scored["bias"], price_now, analysis["atr_abs"])
    next_candle = forecast.project(data, TF_SECONDS[tf], scored["bias"], scored["confidence"])
    if next_candle:
        try:
            store.log_forecast(asset["symbol"], tf, next_candle)
        except Exception:
            pass  # forecast logging must never break the live signal
    try:
        paper.maybe_open(asset["symbol"], tf, scored["bias"], plan, price_now)
    except Exception:
        pass  # paper-trade bookkeeping must never break the live signal
    change_pct = (price_now - data[-2]["close"]) / data[-2]["close"] * 100 if len(data) > 1 else 0.0

    return {
        "symbol": asset["symbol"], "name": asset["name"], "asset_class": asset["asset_class"], "tf": tf,
        "price": price_now, "change_pct": round(change_pct, 3),
        **_technical_block(analysis, scored, plan, htf, htf_trend, asset["symbol"]),
        "next_candle": next_candle,
        "updated": int(time.time()), "disclaimer": DISCLAIMER,
    }


@app.get("/forecasts/{symbol}")
def get_forecast_history(symbol: str, tf: str = Query("1h")):
    """Predicted-candle history overlay: replays the engine over recent bars so
    every past candle shows what was predicted vs what happened (correct flag)."""
    try:
        asset = get_asset(symbol)
        data = _candles_for(symbol, tf, 300)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))

    key = f"recon:{asset['symbol']}:{tf}"
    fcs = cache.get(key)
    if fcs is None:
        fcs = forecast.reconstruct(data, TF_SECONDS[tf])
        cache.put(key, fcs, ttl=cache.ttl_for(tf))
    return {"symbol": asset["symbol"], "tf": tf, "forecasts": fcs,
            "summary": forecast.summarize(fcs)}


@app.get("/predict/{symbol}")
def predict(symbol: str, tf: str = Query("1h"),
            ai_indicators: str | None = Query(None)):
    """Full prediction: technical signal + GPT news-aware reasoning.

    ai_indicators: optional comma-separated indicator names; when given, only
    those are fed to the AI layer (the 'help AI' checkboxes in the UI).
    """
    try:
        asset = get_asset(symbol)
        data = _candles_for(symbol, tf, 300)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))

    try:
        analysis = _analyze_closed(data)
    except ValueError as e:
        raise HTTPException(422, str(e))
    htf, htf_trend = _htf_trend(symbol, tf)
    scored = signal.score(analysis, htf_trend)
    price_now = data[-1]["close"]
    plan = signal.make_plan(scored["bias"], price_now, analysis["atr_abs"])
    next_candle = forecast.project(data, TF_SECONDS[tf], scored["bias"], scored["confidence"])
    analysis["htf"] = {"tf": htf, "trend": htf_trend}  # context for the AI layer
    analysis["plan"] = plan
    analysis["next_candle"] = next_candle
    analysis["safety"] = signal.assess_safety(scored, analysis)  # grounds the AI's safety verdict
    analysis["best_window"] = _best_window(symbol)
    # AI sees the full technical block, but only the user-selected indicator rows
    ai_analysis = dict(analysis)
    if ai_indicators is not None:
        wanted = {n.strip() for n in ai_indicators.split(",") if n.strip()}
        ai_analysis["details"] = [d for d in analysis["details"] if d["name"] in wanted]
    try:
        ai_view = ai.analyze(asset["symbol"], asset["name"], asset["asset_class"], tf, ai_analysis, scored)
    except Exception as e:
        ai_view = {
            "symbol": asset["symbol"], "tf": tf, "direction": scored["bias"],
            "confidence": scored["confidence"],
            "rationale": f"AI layer error ({type(e).__name__}); showing technical signal only.",
            "safety": "", "best_time": "",
            "key_drivers": [], "risk_note": "", "headlines_used": [], "model": "error", "cached": False,
        }

    # Log every fresh prediction — this history is how we measure real accuracy.
    if not ai_view.get("cached"):
        try:
            store.log_prediction(
                asset["symbol"], tf, analysis["price"],
                {"bias": scored["bias"], "confidence": scored["confidence"],
                 "volatility": analysis["volatility"]},
                ai_view,
            )
        except Exception:
            pass  # logging must never break a prediction

    change_pct = (price_now - data[-2]["close"]) / data[-2]["close"] * 100 if len(data) > 1 else 0.0
    return {
        "symbol": asset["symbol"], "name": asset["name"], "asset_class": asset["asset_class"], "tf": tf,
        "price": price_now, "change_pct": round(change_pct, 3),
        "technical": _technical_block(analysis, scored, plan, htf, htf_trend, asset["symbol"]),
        "next_candle": next_candle,
        "ai": ai_view,
        "updated": int(time.time()), "disclaimer": DISCLAIMER,
    }


@app.get("/overlays/{symbol}")
def get_overlays(symbol: str, tf: str = Query("1h")):
    """Plottable indicator line series for chart overlays."""
    try:
        get_asset(symbol)
        data = _candles_for(symbol, tf, 300)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return {"symbol": symbol.upper(), "tf": tf,
            "overlayable": overlays.OVERLAYABLE, "overlays": overlays.build(data)}


@app.get("/avgline/{symbol}")
def get_avgline(symbol: str, tf: str = Query("1h")):
    """Average trend line: yellow where the trend held, orange where it broke,
    gray projection of where it would go next."""
    try:
        asset = get_asset(symbol)
        data = _candles_for(symbol, tf, 300)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return {"symbol": asset["symbol"], "tf": tf, **avgline.build(data, TF_SECONDS[tf])}


@app.get("/trends/{symbol}")
def get_trends(symbol: str, tf: str = Query("1h")):
    """Current trend + how long it has run + a survival-based remaining estimate."""
    try:
        asset = get_asset(symbol)
        data = _candles_for(symbol, tf, 300)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return {"symbol": asset["symbol"], "tf": tf, "trend": trends.analyze(data, TF_SECONDS[tf])}


@app.get("/portfolio")
def get_portfolio(symbol: str | None = Query(None), tf: str | None = Query(None)):
    """Paper-trading track record — scores open trades against the latest candles
    then returns the portfolio (net R, win rate, open + recent closed trades)."""
    try:
        paper.evaluate(_candles_for)
    except Exception:
        pass  # evaluation hiccups must not hide the existing book
    return store.paper_portfolio(symbol.upper() if symbol else None, tf)


@app.get("/news/{symbol}")
def get_news(symbol: str):
    """Headline sentiment for the asset's class (lexicon-based, key-free)."""
    try:
        asset = get_asset(symbol)
    except KeyError as e:
        raise HTTPException(404, str(e))
    return {"symbol": asset["symbol"], "asset_class": asset["asset_class"],
            "sentiment": news.sentiment(asset["asset_class"])}


@app.get("/calendar")
def get_calendar():
    """Upcoming high/medium-impact economic events."""
    return {"events": calendar.upcoming()}


@app.get("/volprofile/{symbol}")
def get_volprofile(symbol: str, tf: str = Query("1h")):
    """Volume profile — volume traded per price level, with POC + value area."""
    try:
        asset = get_asset(symbol)
        data = _candles_for(symbol, tf, 300)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    key = f"vp:{asset['symbol']}:{tf}"
    vp = cache.get(key)
    if vp is None:
        vp = volprofile.build(data)
        cache.put(key, vp, ttl=cache.ttl_for(tf))
    return {"symbol": asset["symbol"], "tf": tf, "profile": vp}


@app.get("/orderbook/{symbol}")
def get_orderbook(symbol: str):
    """Live order-book depth snapshot (crypto only) — pressure + top levels."""
    try:
        asset = get_asset(symbol)
    except KeyError as e:
        raise HTTPException(404, str(e))
    if asset["source"] != "binance":
        return {"symbol": asset["symbol"], "book": None}
    return {"symbol": asset["symbol"], "book": orderbook.depth(asset["symbol"])}


@app.get("/context/{symbol}")
def get_context(symbol: str):
    """Market context — crypto Fear & Greed + perpetual funding (crypto only)."""
    try:
        asset = get_asset(symbol)
    except KeyError as e:
        raise HTTPException(404, str(e))
    if asset["source"] != "binance":
        return {"symbol": asset["symbol"], "fear_greed": None, "funding": None}
    return {
        "symbol": asset["symbol"],
        "fear_greed": context.fear_greed(),
        "funding": context.funding_rate(asset["symbol"]),
    }


@app.get("/patterns/{symbol}")
def get_patterns(symbol: str, tf: str = Query("1h")):
    """Candlestick patterns + RSI/MACD divergences, as chart markers + a summary."""
    try:
        asset = get_asset(symbol)
        data = _candles_for(symbol, tf, 300)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    key = f"patterns:{asset['symbol']}:{tf}"
    res = cache.get(key)
    if res is None:
        res = patterns.build(data)
        cache.put(key, res, ttl=cache.ttl_for(tf))
    return {"symbol": asset["symbol"], "tf": tf, **res}


@app.get("/chartpatterns/{symbol}")
def get_chartpatterns(symbol: str, tf: str = Query("1h")):
    """Classic chart patterns (H&S, double top/bottom, triangles) as candidates."""
    try:
        asset = get_asset(symbol)
        data = _candles_for(symbol, tf, 300)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    key = f"chartpat:{asset['symbol']}:{tf}"
    res = cache.get(key)
    if res is None:
        res = chartpatterns.detect(data, TF_SECONDS[tf])
        cache.put(key, res, ttl=cache.ttl_for(tf))
    return {"symbol": asset["symbol"], "tf": tf, "patterns": res}


@app.get("/trendcast/{symbol}")
def get_trendcast(symbol: str, tf: str = Query("1h")):
    """Multi-horizon trend projection — where price is likely to head over the
    next near / mid / far windows on this timeframe."""
    try:
        asset = get_asset(symbol)
        data = _candles_for(symbol, tf, 300)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return {"symbol": asset["symbol"], "tf": tf, "forecast": trendcast.project(data, TF_SECONDS[tf])}


@app.get("/backtest/{symbol}")
def get_backtest(symbol: str, tf: str = Query("1h")):
    """Replay the live signal + ATR plan over history → win rate, net R, profit
    factor, max drawdown and a cumulative-R equity curve. Cached per market/tf."""
    try:
        asset = get_asset(symbol)
        data = _candles_for(symbol, tf, 1000)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    key = f"backtest:{asset['symbol']}:{tf}"
    res = cache.get(key)
    if res is None:
        res = backtest.run(data, TF_SECONDS[tf])
        cache.put(key, res, ttl=cache.ttl_for(tf))
    return {"symbol": asset["symbol"], "tf": tf, "backtest": res}


@app.get("/report")
def accuracy_report(symbol: str | None = Query(None), tf: str | None = Query(None)):
    """Score every due prediction against the candle that followed, then report."""
    try:
        scoring.evaluate_pending(_candles_for)
    except Exception:
        pass  # scoring hiccups must not hide the existing stats
    return {**store.report(symbol.upper() if symbol else None, tf), "disclaimer": DISCLAIMER}


@app.get("/history/{symbol}")
def get_history(symbol: str, tf: str | None = Query(None), limit: int = Query(100, le=1000)):
    """Logged predictions — the raw material for accuracy scoring."""
    try:
        asset = get_asset(symbol)
    except KeyError as e:
        raise HTTPException(404, str(e))
    return {"symbol": asset["symbol"], "predictions": store.history(asset["symbol"], tf, limit)}
