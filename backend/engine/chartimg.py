"""Render a candlestick PNG for Telegram signals.

A self-contained matplotlib (Agg) drawing in the app's dark theme:
  - candles + the average (trend) line and its orange forward projection,
  - the projected next candle as a dashed ghost,
  - entry / stop / target lines with shaded risk (red) + reward (green) zones,
  - an INDICATOR BOARD strip below the chart showing, of the 17 indicators,
    which vote UP / NEUTRAL / DOWN (a stacked bar + the names).
Best-effort: callers fall back to a text message if this raises.
"""
import io

import matplotlib

matplotlib.use("Agg")  # headless — no display needed (serverless)
import matplotlib.pyplot as plt  # noqa: E402

_BG = "#0b0e14"
_PANEL = "#111722"
_GRID = "#1b2230"
_TEXT = "#aab3c5"
_FAINT = "#7f8aa3"
_HEAD = "#e8edf5"
_UP = "#26a69a"
_DOWN = "#ef5350"
_NEUTRAL = "#8a93a8"
_AVG = "#f5c518"      # average line (realized)
_PROJ = "#ff8a1f"     # average line projection (where it's heading)


def _fmt(p: float) -> str:
    return f"{p:,.2f}" if p >= 100 else f"{p:.5f}"


def _draw_board(ax, details: list[dict]) -> None:
    """Indicator vote breakdown: stacked bar + the names in each group."""
    avail = [d for d in details if d.get("available", True) and not d.get("disabled")]
    ups = [d["name"] for d in avail if d["vote"] == "up"]
    neu = [d["name"] for d in avail if d["vote"] == "neutral"]
    dns = [d["name"] for d in avail if d["vote"] == "down"]
    total = len(avail) or 1

    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(0, 0.97, f"INDICATOR BOARD · {len(avail)} active",
            fontsize=9, fontweight="bold", color=_HEAD, va="top")

    # stacked sentiment bar
    y, h, x = 0.6, 0.16, 0.0
    for cnt, col in ((len(ups), _UP), (len(neu), _NEUTRAL), (len(dns), _DOWN)):
        w = cnt / total
        if w > 0:
            ax.add_patch(plt.Rectangle((x, y), w, h, facecolor=col, edgecolor=_BG, lw=1.2))
            if w > 0.05:
                ax.text(x + w / 2, y + h / 2, str(cnt), ha="center", va="center",
                        color="#0b0e14", fontsize=8.5, fontweight="bold")
            x += w

    # name rows
    rows = [("▲ UP", _UP, ups), ("■ NEUTRAL", _NEUTRAL, neu), ("▼ DOWN", _DOWN, dns)]
    yy = 0.34
    for head, col, names in rows:
        ax.text(0.0, yy, f"{head} · {len(names)}", fontsize=7.5, fontweight="bold",
                color=col, va="center")
        ax.text(0.165, yy, "  ".join(names) if names else "—", fontsize=7,
                color=col, va="center")
        yy -= 0.17


def render(candles: list[dict], plan: dict | None, forecast: dict | None,
           title: str, subtitle: str = "", avg_points: list[dict] | None = None,
           details: list[dict] | None = None, proj_bars: int = 8, bars: int = 60) -> bytes:
    data = candles[-bars:]
    if len(data) < 5:
        raise ValueError("not enough candles to draw")

    if details:
        fig, (ax, ax2) = plt.subplots(2, 1, figsize=(9, 6.4), dpi=115,
                                      gridspec_kw={"height_ratios": [3.3, 1.25], "hspace": 0.12})
    else:
        fig, ax = plt.subplots(figsize=(9, 5), dpi=115)
        ax2 = None
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG)

    times = [c["time"] for c in data]
    step = (times[-1] - times[-2]) if len(times) > 1 else 3600
    base = times[0]
    x_of = lambda t: (t - base) / step  # noqa: E731
    n = len(data)
    x_max = n - 1 + proj_bars + 1

    if plan:
        e, s, t = plan.get("entry"), plan.get("stop"), plan.get("target")
        if e and t:
            ax.axhspan(min(e, t), max(e, t), color=_UP, alpha=0.06, zorder=0)
        if e and s:
            ax.axhspan(min(e, s), max(e, s), color=_DOWN, alpha=0.06, zorder=0)

    for i, c in enumerate(data):
        up = c["close"] >= c["open"]
        color = _UP if up else _DOWN
        ax.plot([i, i], [c["low"], c["high"]], color=color, linewidth=0.8, zorder=3)
        lo, hi = min(c["open"], c["close"]), max(c["open"], c["close"])
        ax.add_patch(plt.Rectangle((i - 0.3, lo), 0.6, max(hi - lo, (hi or 1) * 1e-6),
                                   facecolor=color, edgecolor=color, zorder=4))

    if avg_points:
        tr = [(x_of(p["time"]), p["value"]) for p in avg_points
              if p.get("seg") == "trend" and -1 <= x_of(p["time"]) <= n]
        pr = [(x_of(p["time"]), p["value"]) for p in avg_points
              if p.get("seg") == "proj" and x_of(p["time"]) <= x_max]
        if tr:
            ax.plot([x for x, _ in tr], [y for _, y in tr], color=_AVG,
                    linewidth=1.6, alpha=0.9, zorder=5, label="Average line")
        if pr:
            if tr:
                pr = [tr[-1]] + pr
            ax.plot([x for x, _ in pr], [y for _, y in pr], color=_PROJ,
                    linewidth=1.6, linestyle="--", alpha=0.95, zorder=5,
                    label="Projected (heading)")

    if forecast:
        x = n
        up = forecast["close"] >= forecast["open"]
        color = _UP if up else _DOWN
        ax.plot([x, x], [forecast["low"], forecast["high"]], color=color,
                linewidth=0.9, linestyle=":", alpha=0.9, zorder=4)
        lo, hi = min(forecast["open"], forecast["close"]), max(forecast["open"], forecast["close"])
        ax.add_patch(plt.Rectangle((x - 0.3, lo), 0.6, max(hi - lo, (hi or 1) * 1e-6),
                                   fill=False, edgecolor=color, linestyle="--", zorder=4))
        ax.text(x, hi, " next", color=color, fontsize=7, va="bottom", ha="center")

    if plan:
        for key, col, lab in (("entry", _TEXT, "Entry"), ("stop", _DOWN, "Stop"),
                              ("target", _UP, "Target")):
            y = plan.get(key)
            if y:
                ax.axhline(y, color=col, linewidth=1.0, linestyle="--", alpha=0.9, zorder=2)
                ax.text(x_max, y, f"{lab} {_fmt(y)} ", color=col, fontsize=8,
                        va="bottom", ha="right", zorder=6)

    ys = [c["low"] for c in data] + [c["high"] for c in data]
    if plan:
        ys += [v for v in (plan.get("entry"), plan.get("stop"), plan.get("target")) if v]
    if forecast:
        ys += [forecast["low"], forecast["high"]]
    pad = (max(ys) - min(ys)) * 0.07 or 1
    ax.set_ylim(min(ys) - pad, max(ys) + pad)

    ax.set_title(title, color=_HEAD, fontsize=14, fontweight="bold", loc="left", pad=16)
    if subtitle:
        ax.text(0, 1.025, subtitle, transform=ax.transAxes, color=_TEXT, fontsize=9.5, va="bottom")
    ax.grid(True, color=_GRID, linewidth=0.6, alpha=0.6)
    ax.tick_params(colors=_TEXT, labelsize=8)
    for sp in ax.spines.values():
        sp.set_color(_GRID)
    ax.set_xticks([])
    ax.set_xlim(-1, x_max)
    if ax.get_legend_handles_labels()[1]:
        ax.legend(loc="upper left", fontsize=7.5, framealpha=0.0, labelcolor=_TEXT).set_zorder(7)

    if ax2 is not None:
        ax2.set_facecolor(_PANEL)
        _draw_board(ax2, details or [])

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=_BG, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
