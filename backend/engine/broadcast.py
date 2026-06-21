"""Telegram signal-service — posts high-chance setups to the group on a schedule.

For each tracked asset it scans several timeframes (scalp → swing) and broadcasts
the ONE with the strongest read — so the trade duration matches the setup (a 5m
scalp, a 1h intraday, a 1d swing, …), not a fixed timeframe. It only sends when
the chance is ≥80%, one message per market per candle (deduped), with a polished
chart that includes the 17-indicator board. Runs server-side, 24/7.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from data import store
from data.assets import ASSETS
from engine import alerts, avgline, chartimg, forecast, indicators, signal, timing, trendcast

TF_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400, "1wk": 604800}
MIN_CONFIDENCE = 80          # only broadcast setups with a ≥80% chance
SCAN_TFS = ["5m", "15m", "1h", "1d"]  # pick the strongest of these per asset

_TF_HUMAN = {"5m": "5-minute (scalp)", "15m": "15-minute", "1h": "1-hour",
             "4h": "4-hour", "1d": "1-day (swing)", "1wk": "1-week"}

# entry-time clocks for the markets the user follows (shown in AM/PM)
_ZONES = [("🇺🇸 USA", "America/New_York"), ("🇬🇧 UK", "Europe/London"),
          ("🇵🇰 Pakistan", "Asia/Karachi"), ("🇮🇳 India", "Asia/Kolkata")]


def _fmt(p: float) -> str:
    return f"{p:,.2f}" if p >= 100 else f"{p:.5f}"


def _clock(ts: int, zone: str) -> str | None:
    try:
        return datetime.fromtimestamp(int(ts), ZoneInfo(zone)).strftime("%I:%M %p").lstrip("0")
    except Exception:
        return None


def _times_block(ts: int) -> list[str]:
    out = []
    for label, zone in _ZONES:
        clk = _clock(ts, zone)
        if clk:
            out.append(f"{label}: {clk}")
    return out


def _avg_projection(points: list[dict], horizon: int = 8) -> dict | None:
    """Where the average line is heading next: direction + a near projected value."""
    trend = [p for p in points if p.get("seg") == "trend"]
    proj = [p for p in points if p.get("seg") == "proj"]
    if not trend or not proj:
        return None
    cur = trend[-1]["value"]
    nxt = proj[min(horizon - 1, len(proj) - 1)]["value"]
    direction = "rising" if nxt > cur else "falling" if nxt < cur else "flat"
    return {"direction": direction, "to": nxt}


def build_message(name: str, tf: str, scored: dict, analysis: dict, plan: dict,
                  fc: dict | None, tcast: dict | None, bw: dict | None,
                  avg_proj: dict | None, candle_open: int, tf_sec: int) -> str:
    bias = scored["bias"]
    up = bias == "up"
    emoji = "🟢" if up else "🔴"
    action = "BUY" if up else "SELL"
    ud = "UP" if up else "DOWN"
    arrow = "▲" if up else "▼"
    entry, stop, target, rr = plan["entry"], plan["stop"], plan["target"], plan["rr"]
    risk = abs((stop - entry) / entry * 100) if entry else 0
    rew = abs((target - entry) / entry * 100) if entry else 0

    lines = [
        f"{emoji} {name} — {action}",
        f"Price likely going {ud} · {scored['confidence']}% chance",
        "",
        f"⏱ Timeframe: {_TF_HUMAN.get(tf, tf)} trade",
        "",
        "📊 WHAT'S HAPPENING",
        f"• Direction: {ud} {arrow}",
    ]
    if fc:
        nc_up = fc["close"] >= fc["open"]
        sign = "+" if nc_up else "−"
        lines.append(f"• Next candle: likely {'UP' if nc_up else 'DOWN'} "
                     f"({sign}{abs(fc.get('body_pct', 0)):.2f}%, to {_fmt(fc['close'])})")
    if avg_proj:
        lines.append(f"• Average line: {avg_proj['direction']} → toward {_fmt(avg_proj['to'])}")
    if tcast and tcast.get("horizons"):
        h = next((x for x in tcast["horizons"] if x["direction"] == bias), tcast["horizons"][0])
        lines.append(f"• Should keep {'rising' if up else 'falling'} ~{h['label']} "
                     f"(target {_fmt(h['target'])})")

    lines += [
        "",
        "🎯 YOUR TRADE",
        f"• {action} now: {_fmt(entry)}",
        f"• Stop loss: {_fmt(stop)}  (risk −{risk:.1f}%)",
        f"• Take profit: {_fmt(target)}  (gain +{rew:.1f}%)",
        f"• Risk/Reward: 1 : {rr}",
        "",
        f"⏰ ENTER NOW — {tf} candle closes:",
    ]
    lines += _times_block(candle_open + tf_sec)
    if bw:
        lines.append(f"\n🕒 Best hours: {int(bw['start_utc']):02d}:00–{int(bw['end_utc']):02d}:00 UTC")
    lines.append("\n📈 Chart + indicator board below")
    lines.append("Trading AI · only sends at ≥80% chance")
    return "\n".join(lines)


def run(candles_for, htf_of, min_conf: int = MIN_CONFIDENCE, force: bool = False,
        symbols: list[str] | None = None) -> dict:
    """One broadcast pass. For each asset, scan SCAN_TFS, save each snapshot, and
    broadcast the single strongest ≥min_conf setup (deduped per candle).
    `candles_for(sym, tf, n)` and `htf_of(sym, tf) -> (htf, htf_trend)` injected
    by the API layer; `symbols` optionally limits the scan (for a targeted test)."""
    targets = [s.upper() for s in symbols] if symbols else list(ASSETS)
    sent = skipped = saved = errors = 0
    posted: list[str] = []

    for sym in targets:
        asset = ASSETS.get(sym)
        if not asset:
            continue
        try:
            best = None
            for tf in SCAN_TFS:
                try:
                    data = candles_for(sym, tf, 300)
                    closed = data[:-1] if len(data) > indicators.MIN_CANDLES else data
                    analysis = indicators.analyze(closed)
                    scored = signal.score(analysis)  # no HTF during the scan (perf)
                except Exception:
                    continue
                try:  # save every scanned timeframe → feeds history + accuracy
                    store.log_signal(sym, tf, analysis["price"], scored, analysis)
                    store.log_prediction(
                        sym, tf, analysis["price"],
                        {"bias": scored["bias"], "confidence": scored["confidence"],
                         "volatility": analysis["volatility"]},
                        {"direction": "neutral", "confidence": 0})
                    saved += 1
                except Exception:
                    pass
                if scored["bias"] in ("up", "down") and (
                        best is None or scored["confidence"] > best["scored"]["confidence"]):
                    best = {"tf": tf, "data": data, "analysis": analysis, "scored": scored}

            if not alerts.telegram_configured() or not best:
                skipped += 1
                continue

            tf, data, analysis = best["tf"], best["data"], best["analysis"]
            tf_sec = TF_SECONDS[tf]
            _, htf_trend = htf_of(sym, tf)               # final score with HTF confluence
            scored = signal.score(analysis, htf_trend)
            if scored["bias"] not in ("up", "down") or scored["confidence"] < min_conf:
                skipped += 1
                continue
            price = data[-1]["close"]
            plan = signal.make_plan(scored["bias"], price, analysis["atr_abs"])
            if not plan:
                skipped += 1
                continue
            candle_open = int(data[-1]["time"])
            if not force and not store.mark_broadcast(sym, tf, candle_open):
                skipped += 1  # already sent this candle
                continue

            fc = forecast.project(data, tf_sec, scored["bias"], scored["confidence"])
            if fc:
                try:
                    store.log_forecast(sym, tf, fc)
                except Exception:
                    pass
            try:
                tcast = trendcast.project(data, tf_sec)
            except Exception:
                tcast = None
            try:  # best-hours only makes sense for intraday timeframes
                bw = timing.best_window(data) if tf in ("5m", "15m", "1h") else None
            except Exception:
                bw = None
            try:
                avg_points = avgline.build(data, tf_sec).get("points", [])
            except Exception:
                avg_points = []
            avg_proj = _avg_projection(avg_points)

            caption = build_message(asset["name"], tf, scored, analysis, plan, fc,
                                    tcast, bw, avg_proj, candle_open, tf_sec)
            action = "BUY" if scored["bias"] == "up" else "SELL"
            png = None
            try:
                png = chartimg.render(
                    data, plan, fc,
                    title=f"{asset['name']} · {action} · {tf}",
                    subtitle=f"{scored['confidence']}% chance · {_TF_HUMAN.get(tf, tf)}",
                    avg_points=avg_points, details=analysis.get("details"))
            except Exception:
                png = None

            ok = alerts.send_telegram_photo(caption, png) if png else alerts.send_telegram(caption)
            if ok:
                sent += 1
                posted.append(f"{sym}:{tf}")
            else:
                errors += 1
        except Exception:
            errors += 1

    return {"sent": sent, "skipped": skipped, "saved": saved, "errors": errors,
            "posted": posted, "min_confidence": min_conf, "scanned": SCAN_TFS}
