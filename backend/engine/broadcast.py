"""Telegram signal-service — posts high-conviction setups to the group on a
schedule, one per market per candle, with a rendered chart.

Runs server-side off the same scheduled trigger as the snapshot collector, so it
works 24/7 with nobody on the site. For every tracked asset on 1h it computes the
live read (same scorer + higher-timeframe confluence the dashboard uses), saves
the snapshot, and — only when the call is a confident directional one — renders a
chart and broadcasts it (deduped per candle so it never spams).
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from data import store
from data.assets import ASSETS
from engine import alerts, avgline, chartimg, forecast, indicators, signal, timing, trendcast

TF_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400, "1wk": 604800}
MIN_CONFIDENCE = 80  # only broadcast trades the engine is highly confident in (≥80%)

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
            out.append(f"{label} {clk}")
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
    emoji = "🟢" if bias == "up" else "🔴"
    action = "BUY" if bias == "up" else "SELL"
    updown = "UP" if bias == "up" else "DOWN"
    arrow = "▲" if bias == "up" else "▼"
    entry, stop, target, rr = plan["entry"], plan["stop"], plan["target"], plan["rr"]
    risk_pct = abs((stop - entry) / entry * 100) if entry else 0
    rew_pct = abs((target - entry) / entry * 100) if entry else 0

    lines = [
        f"{emoji} {name} — {action} (price going {updown})",
        f"Strong signal · {scored['confidence']}% confident",
        "",
        "WHAT'S HAPPENING",
        f"• Direction: {updown} {arrow}",
    ]
    if fc:
        nc = "UP" if fc["close"] >= fc["open"] else "DOWN"
        lines.append(f"• Next candle: likely {nc} (about {abs(fc.get('body_pct', 0)):.2f}%, to {_fmt(fc['close'])})")
    if avg_proj:
        lines.append(f"• Average line: {avg_proj['direction']} → heading to {_fmt(avg_proj['to'])}")
    if tcast and tcast.get("horizons"):
        h = next((x for x in tcast["horizons"] if x["direction"] == bias), tcast["horizons"][0])
        lines.append(f"• Likely to keep going {updown} for about {h['label']} (target {_fmt(h['target'])})")

    lines += [
        "",
        "YOUR TRADE",
        f"• {action} now:    {_fmt(entry)}",
        f"• Stop loss:   {_fmt(stop)}   (you risk −{risk_pct:.1f}%)",
        f"• Take profit: {_fmt(target)}   (you gain +{rew_pct:.1f}%)",
        f"• Risk : Reward — 1 : {rr}",
        "",
        f"⏰ ENTER NOW — this {tf} candle closes at:",
    ]
    clocks = _times_block(candle_open + tf_sec)
    if clocks:
        lines.append("   " + "   ".join(clocks[:2]))
        if len(clocks) > 2:
            lines.append("   " + "   ".join(clocks[2:]))
    if bw:
        lines.append(f"\nBest hours to trade: {int(bw['start_utc']):02d}:00–{int(bw['end_utc']):02d}:00 UTC")
    lines.append("Trading AI · sent only when ≥80% confident")
    return "\n".join(lines)


def run(candles_for, htf_of, min_conf: int = MIN_CONFIDENCE, force: bool = False) -> dict:
    """One broadcast pass over all assets on 1h. `candles_for(sym, tf, n)` and
    `htf_of(sym, tf) -> (htf, htf_trend)` are injected by the API layer."""
    tf, tf_sec = "1h", TF_SECONDS["1h"]
    sent = skipped = saved = errors = 0
    posted: list[str] = []

    for sym, asset in ASSETS.items():
        try:
            data = candles_for(sym, tf, 300)
            closed = data[:-1] if len(data) > indicators.MIN_CANDLES else data
            analysis = indicators.analyze(closed)
            _, htf_trend = htf_of(sym, tf)
            scored = signal.score(analysis, htf_trend)
            price = data[-1]["close"]
            plan = signal.make_plan(scored["bias"], price, analysis["atr_abs"])
            fc = forecast.project(data, tf_sec, scored["bias"], scored["confidence"])

            # always save the snapshot/prediction/forecast (this also feeds the
            # accuracy report + saved history, durable when Turso is configured)
            try:
                store.log_signal(sym, tf, analysis["price"], scored, analysis)
                store.log_prediction(
                    sym, tf, analysis["price"],
                    {"bias": scored["bias"], "confidence": scored["confidence"],
                     "volatility": analysis["volatility"]},
                    {"direction": "neutral", "confidence": 0},
                )
                if fc:
                    store.log_forecast(sym, tf, fc)
                saved += 1
            except Exception:
                pass

            # broadcast gate: configured + confident directional + once per candle
            if not alerts.telegram_configured():
                continue
            if scored["bias"] not in ("up", "down") or scored["confidence"] < min_conf or not plan:
                skipped += 1
                continue
            candle_open = int(data[-1]["time"])
            if not force and not store.mark_broadcast(sym, tf, candle_open):
                skipped += 1  # already sent this candle
                continue

            try:
                tcast = trendcast.project(data, tf_sec)
            except Exception:
                tcast = None
            try:
                bw = timing.best_window(data)
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
                    title=f"{asset['name']} · {action} · {scored['bias'].upper()}",
                    subtitle=f"{scored['confidence']}% confident · {tf}",
                    avg_points=avg_points,
                )
            except Exception:
                png = None

            ok = alerts.send_telegram_photo(caption, png) if png else alerts.send_telegram(caption)
            if ok:
                sent += 1
                posted.append(sym)
            else:
                errors += 1
        except Exception:
            errors += 1

    return {"sent": sent, "skipped": skipped, "saved": saved, "errors": errors,
            "posted": posted, "min_confidence": min_conf}
