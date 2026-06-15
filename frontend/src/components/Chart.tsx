import { useEffect, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  LineStyle,
  createChart,
  createSeriesMarkers,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import type { AvgLinePoint, Candle, ForecastHistItem, Levels, NextCandle, PatternItem, TradePlan } from "../types";

export interface OverlaySeries {
  key: string;
  color: string;
  data: { time: number; value: number }[];
}

// Binance kline stream interval names (only weekly differs from ours)
const WS_INTERVAL: Record<string, string> = {
  "1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d", "1wk": "1w",
};

const TF_SECONDS: Record<string, number> = {
  "1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400, "1wk": 604800,
};

// short marker labels so the chart stays readable
const PATTERN_ABBR: Record<string, string> = {
  "Doji": "Doji", "Hammer": "Hammer", "Shooting Star": "Star",
  "Bullish Engulfing": "Engulf", "Bearish Engulfing": "Engulf",
  "RSI Bullish Divergence": "RSI div", "RSI Bearish Divergence": "RSI div",
  "MACD Bullish Divergence": "MACD div", "MACD Bearish Divergence": "MACD div",
};

export interface LiveFeed {
  provider: "binance" | "finnhub";
  symbol: string;
  token?: string;
}

interface Bar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null; // null = feed doesn't report volume (forex ticks)
}

/** Fold a single trade into the current bar, rolling to a new bar when the
 *  trade falls past the bar's window (stream events later correct volume). */
function applyTick(bar: Bar | null, price: number, qty: number | null, tradeSec: number, tfSec: number): Bar {
  const barStart = Math.floor(tradeSec / tfSec) * tfSec;
  if (!bar || barStart > bar.time) {
    return { time: barStart, open: price, high: price, low: price, close: price, volume: qty };
  }
  return {
    ...bar,
    close: price,
    high: Math.max(bar.high, price),
    low: Math.min(bar.low, price),
    volume: qty !== null && bar.volume !== null ? bar.volume + qty : bar.volume,
  };
}

interface Props {
  candles: Candle[];
  live: LiveFeed | null;
  tf: string;
  levels?: Levels | null;
  plan?: TradePlan | null;
  /** Projected next candle, drawn as a translucent ghost bar */
  forecast?: NextCandle | null;
  /** Past projected candles, drawn as ghost bars colored by correctness */
  forecastHistory?: ForecastHistItem[];
  /** Indicator line overlays toggled on in the indicator panel */
  overlays?: OverlaySeries[];
  /** Average trend line (per-point coloured) + gray projection */
  avgLine?: AvgLinePoint[];
  /** Candlestick patterns + divergences, drawn as labelled markers */
  patterns?: PatternItem[];
  /** A chart pattern's outline to trace (the most significant one) */
  chartPattern?: { outline: { time: number; price: number }[]; direction: string } | null;
  /** Active drawing tool — click two points to draw a trendline / Fibonacci */
  drawMode?: "trendline" | "fib" | null;
  /** Increment to clear all user-drawn trendlines & Fibonacci levels */
  clearSignal?: number;
  /** active UI theme — re-themes the chart's text/grid/borders */
  theme?: string;
  onTick?: (price: number) => void;
  /** Called after a WebSocket reconnect — history may have gaps, so refetch */
  onResync?: () => void;
}

function themeColors() {
  const s = getComputedStyle(document.documentElement);
  return {
    text: s.getPropertyValue("--chart-text").trim() || "#8b93a7",
    grid: s.getPropertyValue("--chart-grid").trim() || "rgba(140,150,170,0.07)",
    border: s.getPropertyValue("--chart-border").trim() || "rgba(140,150,170,0.15)",
  };
}

// the avg line's "held" segments are gold (#f5c518) — too faint on light/pink,
// so swap to a deeper gold on those themes for contrast.
function fixAvgColor(c: string): string {
  if (c !== "#f5c518") return c;
  const t = document.documentElement.dataset.theme;
  return t === "light" || t === "pink" ? "#a16207" : c;
}

export default function Chart({ candles, live, tf, levels, plan, forecast, forecastHistory, overlays, avgLine, patterns, chartPattern, drawMode, clearSignal, theme, onTick, onResync }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const ghostSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const histSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const avgSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const avgProjSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const patternSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const overlayRef = useRef<Map<string, ISeriesApi<"Line">>>(new Map());
  // user drawing tools (trendlines + Fibonacci)
  const drawModeRef = useRef<Props["drawMode"]>(null);
  const pendingPtRef = useRef<{ time: number; price: number } | null>(null);
  const drawnLinesRef = useRef<ISeriesApi<"Line">[]>([]);
  const drawnPriceLinesRef = useRef<IPriceLine[]>([]);
  const lastBarRef = useRef<Bar | null>(null);
  const lastTickNotify = useRef(0);

  useEffect(() => {
    if (!containerRef.current) return;
    const tc = themeColors();
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: tc.text,
        fontFamily: "'Inter', sans-serif",
      },
      grid: {
        vertLines: { color: tc.grid },
        horzLines: { color: tc.grid },
      },
      rightPriceScale: {
        borderColor: tc.border,
        // smooth, non-jumpy autoscale as live ticks arrive
        scaleMargins: { top: 0.08, bottom: 0.22 },
      },
      timeScale: {
        borderColor: tc.border,
        timeVisible: true,
        rightOffset: 6,
        shiftVisibleRangeOnNewBar: true,
      },
      crosshair: { mode: 0 },
      kineticScroll: { touch: true, mouse: true },
      autoSize: true,
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#16c784",
      downColor: "#ea3943",
      borderUpColor: "#16c784",
      borderDownColor: "#ea3943",
      wickUpColor: "#16c784",
      wickDownColor: "#ea3943",
    });
    // predicted-candle history: translucent ghosts in past slots, per-bar
    // colored by whether the prediction was right. Added before volume so it
    // sits just behind the real candles (which stay readable on top).
    const histSeries = chart.addSeries(CandlestickSeries, {
      priceLineVisible: false,
      lastValueVisible: false,
    });

    const volSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });

    // ghost series: the projected next candle. Clearly GREEN when the forecast
    // is up and clearly RED when it's down (not faint pink), with a dashed border
    // so it still reads as a forecast rather than a real bar.
    const ghostSeries = chart.addSeries(CandlestickSeries, {
      upColor: "rgba(38,166,154,0.55)",
      downColor: "rgba(239,83,80,0.55)",
      borderUpColor: "#2ee59d",
      borderDownColor: "#ff5252",
      wickUpColor: "#26a69a",
      wickDownColor: "#ef5350",
      priceLineVisible: false,
      lastValueVisible: false,
    });

    // average trend line — realized part, per-point colours (yellow held / purple broke)
    const avgSeries = chart.addSeries(LineSeries, {
      color: "#f5c518", lineWidth: 2,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
    });
    // predicted forward projection of the average — a dashed ORANGE line so it
    // clearly reads as "where the trend is heading next", not a realized value.
    const avgProjSeries = chart.addSeries(LineSeries, {
      color: "#ff8a1f", lineWidth: 2, lineStyle: LineStyle.Dashed,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
    });
    // chart-pattern outline (head & shoulders / double top / triangle) traced as
    // a dashed line through the defining swing pivots.
    const patternSeries = chart.addSeries(LineSeries, {
      color: "#9aa4b8", lineWidth: 2, lineStyle: LineStyle.Dashed,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volSeriesRef.current = volSeries;
    ghostSeriesRef.current = ghostSeries;
    histSeriesRef.current = histSeries;
    avgSeriesRef.current = avgSeries;
    avgProjSeriesRef.current = avgProjSeries;
    patternSeriesRef.current = patternSeries;
    markersRef.current = createSeriesMarkers(candleSeries, []);

    // --- user drawing tools: click two points to draw a trendline / Fib ---
    const FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
    chart.subscribeClick((param) => {
      const mode = drawModeRef.current;
      if (!mode || param.time === undefined || !param.point) return;
      const price = candleSeries.coordinateToPrice(param.point.y);
      if (price == null) return;
      const point = { time: param.time as unknown as number, price };
      if (!pendingPtRef.current) {
        pendingPtRef.current = point; // first anchor
        return;
      }
      const a = pendingPtRef.current;
      pendingPtRef.current = null;
      if (mode === "trendline") {
        const line = chart.addSeries(LineSeries, {
          color: "#2e7bff", lineWidth: 2,
          priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
        });
        line.setData(
          [a, point].sort((x, y) => x.time - y.time)
            .map((p) => ({ time: p.time as UTCTimestamp, value: p.price })),
        );
        drawnLinesRef.current.push(line);
      } else {
        const hi = Math.max(a.price, point.price);
        const diff = hi - Math.min(a.price, point.price);
        for (const r of FIB_LEVELS) {
          drawnPriceLinesRef.current.push(candleSeries.createPriceLine({
            price: hi - diff * r, color: "rgba(245,166,35,0.8)", lineWidth: 1,
            lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: `Fib ${r}`,
          }));
        }
      }
    });
    return () => chart.remove();
  }, []);

  // average trend line: realized part (per-point yellow/purple) on one series,
  // the predicted forward projection (dashed orange) on a second series so the
  // two read differently. Split by segment; the projection is anchored to the
  // last realized point so the dashed line connects cleanly.
  useEffect(() => {
    const series = avgSeriesRef.current;
    const proj = avgProjSeriesRef.current;
    if (!series || !proj) return;
    const pts = avgLine ?? [];
    const real = pts.filter((p) => p.seg !== "proj");
    const projected = pts.filter((p) => p.seg === "proj");
    series.setData(real.map((p) => ({ time: p.time as UTCTimestamp, value: p.value, color: fixAvgColor(p.color) })));
    const anchor = real.length ? [{ time: real[real.length - 1].time, value: real[real.length - 1].value }] : [];
    proj.setData(
      [...anchor, ...projected].map((p) => ({ time: p.time as UTCTimestamp, value: p.value })),
    );
  }, [avgLine, theme]);

  // re-theme the chart's text / grid / borders when the UI theme changes
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const tc = themeColors();
    chart.applyOptions({
      layout: { textColor: tc.text },
      grid: { vertLines: { color: tc.grid }, horzLines: { color: tc.grid } },
      rightPriceScale: { borderColor: tc.border },
      timeScale: { borderColor: tc.border },
    });
  }, [theme]);

  // keep the click handler's draw mode current; reset any half-finished anchor
  useEffect(() => {
    drawModeRef.current = drawMode ?? null;
    pendingPtRef.current = null;
  }, [drawMode]);

  // clear all user drawings when the clear signal changes
  useEffect(() => {
    const chart = chartRef.current;
    const series = candleSeriesRef.current;
    if (!chart || !series) return;
    drawnLinesRef.current.forEach((s) => chart.removeSeries(s));
    drawnLinesRef.current = [];
    drawnPriceLinesRef.current.forEach((pl) => series.removePriceLine(pl));
    drawnPriceLinesRef.current = [];
    pendingPtRef.current = null;
  }, [clearSignal]);

  // trace the most significant chart pattern's outline through its swing pivots
  useEffect(() => {
    const series = patternSeriesRef.current;
    if (!series) return;
    const pts = chartPattern?.outline ?? [];
    const color = chartPattern?.direction === "bullish" ? "#16c784"
      : chartPattern?.direction === "bearish" ? "#ea3943" : "#f5a623";
    series.applyOptions({ color });
    series.setData(
      pts.slice().sort((a, b) => a.time - b.time)
        .map((p) => ({ time: p.time as UTCTimestamp, value: p.price })),
    );
  }, [chartPattern]);

  // candlestick patterns + divergences as labelled markers on the price series
  useEffect(() => {
    const m = markersRef.current;
    if (!m) return;
    const markers: SeriesMarker<Time>[] = (patterns ?? [])
      .slice()
      .sort((a, b) => a.time - b.time)
      .map((p) => {
        const bull = p.direction === "bullish";
        const bear = p.direction === "bearish";
        return {
          time: p.time as UTCTimestamp,
          position: bull ? "belowBar" : "aboveBar",
          color: bull ? "#16c784" : bear ? "#ea3943" : "#8891a5",
          shape: bull ? "arrowUp" : bear ? "arrowDown" : "circle",
          text: PATTERN_ABBR[p.name] ?? p.name,
        };
      });
    m.setMarkers(markers);
  }, [patterns]);

  // predicted-candle history overlay, colored by correctness vs the real candle
  useEffect(() => {
    const series = histSeriesRef.current;
    if (!series) return;
    if (!forecastHistory || forecastHistory.length === 0 || candles.length === 0) {
      series.setData([]);
      return;
    }
    const realByTime = new Map(candles.map((c) => [c.time, c]));
    const lastReal = candles[candles.length - 1].time;
    // Faint, very transparent purple so the real candle stays clearly visible
    // underneath. Correctness lives in the Accuracy Report, not here.
    const FILL = "rgba(149,117,205,0.12)";
    const BORDER = "rgba(149,117,205,0.55)";
    const WICK = "rgba(149,117,205,0.4)";

    const rows = forecastHistory
      .map((f) => ({ ...f, t: f.target_time ?? f.time }))
      .filter((f) => f.t <= lastReal && realByTime.has(f.t)) // only formed candles
      .map((f) => ({
        time: f.t as UTCTimestamp,
        open: f.open, high: f.high, low: f.low, close: f.close,
        color: FILL, borderColor: BORDER, wickColor: WICK,
      }));
    series.setData(rows);
  }, [forecastHistory, candles]);

  // reconcile indicator line overlays with the current toggle selection
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const map = overlayRef.current;
    const wanted = new Map((overlays ?? []).map((o) => [o.key, o]));

    // remove series no longer selected
    for (const [key, series] of map) {
      if (!wanted.has(key)) {
        chart.removeSeries(series);
        map.delete(key);
      }
    }
    // add / update selected series
    for (const [key, o] of wanted) {
      let series = map.get(key);
      if (!series) {
        series = chart.addSeries(LineSeries, {
          color: o.color,
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        map.set(key, series);
      } else {
        series.applyOptions({ color: o.color });
      }
      series.setData(o.data.map((d) => ({ time: d.time as UTCTimestamp, value: d.value })));
    }
  }, [overlays]);

  // paint / clear the projected next candle
  useEffect(() => {
    const ghost = ghostSeriesRef.current;
    if (!ghost) return;
    if (forecast) {
      ghost.setData([
        {
          time: forecast.time as UTCTimestamp,
          open: forecast.open,
          high: forecast.high,
          low: forecast.low,
          close: forecast.close,
        },
      ]);
    } else {
      ghost.setData([]);
    }
  }, [forecast]);

  useEffect(() => {
    if (!candleSeriesRef.current || !volSeriesRef.current || candles.length === 0) return;
    candleSeriesRef.current.setData(
      candles.map((c) => ({
        time: c.time as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    );
    volSeriesRef.current.setData(
      candles.map((c) => ({
        time: c.time as UTCTimestamp,
        value: c.volume,
        color: c.close >= c.open ? "rgba(22,199,132,0.35)" : "rgba(234,57,67,0.35)",
      })),
    );
    const last = candles[candles.length - 1];
    lastBarRef.current = {
      time: last.time, open: last.open, high: last.high, low: last.low, close: last.close,
      volume: last.volume,
    };
  }, [candles]);

  // --- Key levels painted on the chart: support/resistance + stop/target ---
  const priceLinesRef = useRef<IPriceLine[]>([]);
  useEffect(() => {
    const series = candleSeriesRef.current;
    if (!series) return;
    priceLinesRef.current.forEach((l) => series.removePriceLine(l));
    priceLinesRef.current = [];
    const mk = (price: number, color: string, title: string, style = LineStyle.Dashed) =>
      priceLinesRef.current.push(
        series.createPriceLine({ price, color, title, lineWidth: 1, lineStyle: style, axisLabelVisible: true }),
      );
    if (levels?.resistance) mk(levels.resistance, "rgba(234,57,67,0.65)", "R");
    if (levels?.support) mk(levels.support, "rgba(22,199,132,0.65)", "S");
    if (plan) {
      mk(plan.stop, "rgba(234,57,67,0.9)", "SL", LineStyle.Dotted);
      mk(plan.target, "rgba(22,199,132,0.9)", "TP", LineStyle.Dotted);
    }
  }, [levels, plan, candles.length > 0]);

  // --- Live tick streaming: every individual trade moves the current candle ---
  useEffect(() => {
    if (!live) return;
    let ws: WebSocket | null = null;
    let disposed = false;
    let everConnected = false;
    const tfSec = TF_SECONDS[tf] ?? 3600;

    // Coalesce bursts of trades into one canvas paint per animation frame.
    // BTC can trade 50+ times/sec; redrawing on each is janky, so we keep the
    // newest bar and flush it on the next frame for buttery-smooth motion.
    // The authoritative bar we're animating toward. For Binance it's set ONLY by
    // the kline stream (so open/high/low/colour always match the exchange exactly);
    // trades just nudge the close. For Finnhub (no kline) we roll bars locally.
    let target: Bar | null = lastBarRef.current;
    let displayClose = target?.close ?? 0;
    let raf = 0;
    let running = true;
    let lastTime = -1;
    let lastShown = NaN;

    const setTarget = (bar: Bar) => {
      // bar rolled over → snap the glide to the new open (don't glide across bars)
      if (!target || bar.time !== target.time) displayClose = bar.open;
      target = bar;
      lastBarRef.current = bar;
    };

    const renderLoop = () => {
      if (!running) return;
      raf = requestAnimationFrame(renderLoop);
      const bar = target;
      if (!bar) return;
      // ease ~35% toward the real close each frame (~3 frames ≈ 50ms to land)
      const diff = bar.close - displayClose;
      const eps = Math.max(Math.abs(bar.close) * 1e-7, 1e-7);
      displayClose = Math.abs(diff) < eps ? bar.close : displayClose + diff * 0.35;
      if (bar.time === lastTime && displayClose === lastShown) return; // settled, idle
      lastTime = bar.time;
      lastShown = displayClose;
      const high = Math.max(bar.high, displayClose);
      const low = Math.min(bar.low, displayClose);
      candleSeriesRef.current?.update({
        time: bar.time as UTCTimestamp, open: bar.open, high, low, close: displayClose,
      });
      if (bar.volume !== null) {
        volSeriesRef.current?.update({
          time: bar.time as UTCTimestamp, value: bar.volume,
          color: displayClose >= bar.open ? "rgba(22,199,132,0.35)" : "rgba(234,57,67,0.35)",
        });
      }
      const now = performance.now();
      if (now - lastTickNotify.current > 80) {
        lastTickNotify.current = now;
        onTick?.(displayClose);
      }
    };
    raf = requestAnimationFrame(renderLoop);

    // Binance: kline = authoritative bar; aggTrade only moves the close within it.
    const onKline = (bar: Bar) => setTarget(bar);
    const onAggTrade = (price: number, tradeSec: number) => {
      const bar = target;
      if (!bar) return;
      if (tradeSec < bar.time || tradeSec >= bar.time + tfSec) return; // new period → wait for kline
      setTarget({ ...bar, close: price, high: Math.max(bar.high, price), low: Math.min(bar.low, price) });
    };
    // Finnhub: no kline stream, so roll bars from trades ourselves.
    const onTrade = (price: number, qty: number | null, tradeSec: number) => {
      setTarget(applyTick(target, price, qty, tradeSec, tfSec));
    };

    const connect = () => {
      if (disposed) return;

      if (live.provider === "binance") {
        // combined stream: aggTrade = tick-by-tick price, kline = authoritative
        // bar boundaries + volume (corrects our locally-rolled bars within ~2s)
        const s = live.symbol;
        ws = new WebSocket(
          `wss://data-stream.binance.vision/stream?streams=${s}@aggTrade/${s}@kline_${WS_INTERVAL[tf]}`,
        );
        ws.onmessage = (msg) => {
          try {
            const { stream, data } = JSON.parse(msg.data);
            if (stream.endsWith("@aggTrade")) {
              onAggTrade(parseFloat(data.p), data.T / 1000);
            } else {
              const k = data.k;
              onKline({
                time: k.t / 1000,
                open: parseFloat(k.o),
                high: parseFloat(k.h),
                low: parseFloat(k.l),
                close: parseFloat(k.c),
                volume: parseFloat(k.v),
              });
            }
          } catch { /* malformed frame — skip */ }
        };
      } else {
        // Finnhub: free real-time spot ticks (forex via OANDA feed)
        ws = new WebSocket(`wss://ws.finnhub.io?token=${live.token}`);
        ws.onmessage = (msg) => {
          try {
            const parsed = JSON.parse(msg.data);
            if (parsed.type !== "trade") return; // ignore pings/acks
            for (const t of parsed.data ?? []) {
              if (t.s === live.symbol) onTrade(t.p, null, t.t / 1000);
            }
          } catch { /* skip */ }
        };
      }

      ws.onopen = () => {
        if (live.provider === "finnhub") {
          ws?.send(JSON.stringify({ type: "subscribe", symbol: live.symbol }));
        }
        // after a dropped connection we may have missed whole candles
        if (everConnected) onResync?.();
        everConnected = true;
      };
      ws.onclose = () => {
        if (!disposed) setTimeout(connect, 2000); // auto-reconnect
      };
      ws.onerror = () => ws?.close();
    };
    connect();

    return () => {
      disposed = true;
      running = false;
      if (raf) cancelAnimationFrame(raf);
      ws?.close();
    };
  }, [live, tf, onTick, onResync]);

  return <div ref={containerRef} className="chart" />;
}
