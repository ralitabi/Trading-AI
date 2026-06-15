import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchAssets, fetchAvgLine, fetchCandles, fetchForecastHistory, fetchOverlays, fetchPatterns,
  fetchPrediction, fetchSignal, fetchTrendcast,
} from "./api";
import type {
  AssetInfo, AvgLinePoint, Candle, ForecastHistItem, OverlaysResponse, PatternItem, PatternsResponse,
  Prediction, SignalData, TrendForecast as TrendForecastData,
} from "./types";
import Chart, { type LiveFeed, type OverlaySeries } from "./components/Chart";
import AssetPicker from "./components/AssetPicker";
import TimeframePicker from "./components/TimeframePicker";
import IndicatorMenu from "./components/IndicatorMenu";
import SignalPanel from "./components/SignalPanel";
import IndicatorPanel from "./components/IndicatorPanel";
import TradeSetup from "./components/TradeSetup";
import TrendForecast from "./components/TrendForecast";
import PatternsPanel from "./components/PatternsPanel";
import AICard from "./components/AICard";
import ReportPage from "./components/ReportPage";
import { useIndicators } from "./useIndicators";

const IS_REPORT_VIEW = new URLSearchParams(window.location.search).get("view") === "report";

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d", "1wk"];
const INTRADAY = new Set(["1m", "5m", "15m", "1h"]);
const TF_SECONDS: Record<string, number> = {
  "1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400, "1wk": 604800,
};

// Free real-time spot ticks via Finnhub (finnhub.io, free key). Forex only:
// OANDA spot matches Yahoo's spot forex history; gold/oil/indices use
// futures/cash history where CFD ticks would visibly mismatch the candles.
const FINNHUB_KEY: string | undefined = import.meta.env.VITE_FINNHUB_KEY;
const FINNHUB_SYMBOLS: Record<string, string> = {
  EURUSD: "OANDA:EUR_USD",
  GBPUSD: "OANDA:GBP_USD",
};

function fmtCountdown(secs: number): string {
  if (secs < 0) secs = 0;
  const d = Math.floor(secs / 86400);
  const h = Math.floor((secs % 86400) / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = Math.floor(secs % 60);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

const fmtNum = (n: number) =>
  n >= 100 ? n.toLocaleString(undefined, { maximumFractionDigits: 2 }) : n.toFixed(5);

function fmtCompact(n: number): string {
  if (n >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(2) + "K";
  return n.toFixed(2);
}

/** "BTCUSDT" → "BTC/USDT", "EURUSD" → "EUR/USD", else the raw symbol. */
function tickerLabel(symbol: string): string {
  if (symbol.endsWith("USDT")) return `${symbol.slice(0, -4)}/USDT`;
  if (/^[A-Z]{6}$/.test(symbol)) return `${symbol.slice(0, 3)}/${symbol.slice(3)}`;
  return symbol;
}

export default function App() {
  if (IS_REPORT_VIEW) return <ReportPage />;
  return <Dashboard />;
}

function Dashboard() {
  const [assets, setAssets] = useState<AssetInfo[]>([]);
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [tf, setTf] = useState("1h");
  const [candles, setCandles] = useState<Candle[]>([]);
  const [signal, setSignal] = useState<SignalData | null>(null);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [overlayData, setOverlayData] = useState<OverlaysResponse | null>(null);
  const [forecastHist, setForecastHist] = useState<ForecastHistItem[]>([]);
  const [showForecastHist, setShowForecastHist] = useState(
    () => localStorage.getItem("trend-forecast-hist") === "true",
  );
  useEffect(() => {
    localStorage.setItem("trend-forecast-hist", String(showForecastHist));
  }, [showForecastHist]);
  const [avgLine, setAvgLine] = useState<AvgLinePoint[]>([]);
  // Average trend line is ON by default — it only hides if the user explicitly
  // turned it off. (Defaulting it off was why it "never showed up".)
  const [showAvgLine, setShowAvgLine] = useState(
    () => localStorage.getItem("trend-avg-line") !== "false",
  );
  useEffect(() => {
    localStorage.setItem("trend-avg-line", String(showAvgLine));
  }, [showAvgLine]);
  const indCtrl = useIndicators();
  const [trendcast, setTrendcast] = useState<TrendForecastData | null>(null);
  const [patterns, setPatterns] = useState<PatternsResponse | null>(null);
  const [showPatterns, setShowPatterns] = useState(
    () => localStorage.getItem("trend-patterns") !== "false",
  );
  useEffect(() => {
    localStorage.setItem("trend-patterns", String(showPatterns));
  }, [showPatterns]);
  const [livePrice, setLivePrice] = useState<number | null>(null);
  const [tickDir, setTickDir] = useState<"up" | "down" | "">("");
  const prevTickRef = useRef<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const [timeOpen, setTimeOpen] = useState(
    () => localStorage.getItem("trend-time-open") !== "false",
  );
  useEffect(() => {
    localStorage.setItem("trend-time-open", String(timeOpen));
  }, [timeOpen]);

  // in-app accuracy report drawer (collapsible + drag-resizable)
  const [reportOpen, setReportOpen] = useState(false);
  const [reportCollapsed, setReportCollapsed] = useState(false);
  const [reportWidth, setReportWidth] = useState(
    () => Number(localStorage.getItem("trend-report-width")) || 460,
  );
  useEffect(() => {
    localStorage.setItem("trend-report-width", String(reportWidth));
  }, [reportWidth]);
  const reportResizing = useRef(false);
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!reportResizing.current) return;
      setReportWidth(Math.min(900, Math.max(360, window.innerWidth - e.clientX)));
    };
    const onUp = () => {
      reportResizing.current = false;
      document.body.style.userSelect = "";
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  useEffect(() => {
    fetchAssets().then(setAssets).catch((e) => setError(String(e)));
  }, []);

  // 1-second heartbeat for the clock and candle-close countdown
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const current = assets.find((a) => a.symbol === symbol);
  const isBinance = current?.source === "binance";

  const live = useMemo<LiveFeed | null>(() => {
    if (isBinance) return { provider: "binance", symbol: symbol.toLowerCase() };
    if (FINNHUB_KEY && FINNHUB_SYMBOLS[symbol])
      return { provider: "finnhub", symbol: FINNHUB_SYMBOLS[symbol], token: FINNHUB_KEY };
    return null;
  }, [symbol, isBinance]);

  // Indicator selections derived from the live signal's names + user toggles
  const indNames = useMemo(() => (signal?.indicators ?? []).map((i) => i.name), [signal]);
  const onCsv = useMemo(
    () => indNames.filter((n) => indCtrl.get(n).on).join(","),
    [indNames, indCtrl],
  );
  const aiCsv = useMemo(
    () => indNames.filter((n) => { const s = indCtrl.get(n); return s.on && s.ai; }).join(","),
    [indNames, indCtrl],
  );
  const chartNames = useMemo(
    () => indNames.filter((n) => indCtrl.get(n).chart),
    [indNames, indCtrl],
  );
  // keep the latest selections in refs so polling intervals read fresh values
  const selRef = useRef({ on: "", ai: "" });
  selRef.current = { on: onCsv, ai: aiCsv };

  // Build chart overlay line series from toggled indicators + fetched overlay data
  const overlaySeries = useMemo<OverlaySeries[]>(() => {
    if (!overlayData) return [];
    const out: OverlaySeries[] = [];
    for (const name of chartNames) {
      const spec = overlayData.overlays[name];
      if (!spec) continue;
      for (const [lineName, data] of Object.entries(spec.lines)) {
        out.push({ key: `${name}:${lineName}`, color: spec.colors[lineName] ?? "#888", data });
      }
    }
    return out;
  }, [overlayData, chartNames]);

  // Guards against a slow response for the PREVIOUS symbol/timeframe arriving
  // late and overwriting the screen with the wrong asset's data.
  const viewKey = useRef("");
  useEffect(() => {
    viewKey.current = `${symbol}|${tf}`;
    setLivePrice(null);
    setTickDir("");
    prevTickRef.current = null;
  }, [symbol, tf]);

  const friendly = (e: unknown) =>
    String(e).includes("Failed to fetch")
      ? "Can't reach the backend on port 8742 — start it with dev.bat"
      : String(e);

  const loadCandles = useCallback(async (sym: string, timeframe: string) => {
    const key = `${sym}|${timeframe}`;
    try {
      const c = await fetchCandles(sym, timeframe);
      if (viewKey.current !== key) return;
      setCandles(c);
      setError(null);
    } catch (e) {
      if (viewKey.current === key) setError(friendly(e));
    }
  }, []);

  // Guard so the ~1-2s signal poll never stacks requests if one is slow.
  const signalBusy = useRef(false);
  const loadSignal = useCallback(async (sym: string, timeframe: string) => {
    if (signalBusy.current) return;
    signalBusy.current = true;
    const key = `${sym}|${timeframe}`;
    try {
      const s = await fetchSignal(sym, timeframe, selRef.current.on || undefined);
      if (viewKey.current !== key) return;
      setSignal(s);
      setError(null);
    } catch (e) {
      if (viewKey.current === key) setError(friendly(e));
    } finally {
      signalBusy.current = false;
    }
  }, []);

  const loadOverlays = useCallback(async (sym: string, timeframe: string) => {
    const key = `${sym}|${timeframe}`;
    try {
      const o = await fetchOverlays(sym, timeframe);
      if (viewKey.current === key) setOverlayData(o);
    } catch {
      /* overlays are optional decoration */
    }
  }, []);

  const loadForecastHist = useCallback(async (sym: string, timeframe: string) => {
    const key = `${sym}|${timeframe}`;
    try {
      const r = await fetchForecastHistory(sym, timeframe);
      if (viewKey.current === key) setForecastHist(r.forecasts);
    } catch {
      /* forecast history is optional */
    }
  }, []);

  const loadAvgLine = useCallback(async (sym: string, timeframe: string) => {
    const key = `${sym}|${timeframe}`;
    try {
      const r = await fetchAvgLine(sym, timeframe);
      if (viewKey.current === key) setAvgLine(r.points);
    } catch {
      /* average line is optional */
    }
  }, []);

  const loadTrendcast = useCallback(async (sym: string, timeframe: string) => {
    const key = `${sym}|${timeframe}`;
    try {
      const r = await fetchTrendcast(sym, timeframe);
      if (viewKey.current === key) setTrendcast(r.forecast);
    } catch {
      /* trend forecast is supplementary */
    }
  }, []);

  const loadPatterns = useCallback(async (sym: string, timeframe: string) => {
    const key = `${sym}|${timeframe}`;
    try {
      const r = await fetchPatterns(sym, timeframe);
      if (viewKey.current === key) setPatterns(r);
    } catch {
      /* patterns are supplementary */
    }
  }, []);

  const loadPrediction = useCallback(async (sym: string, timeframe: string) => {
    const key = `${sym}|${timeframe}`;
    try {
      const ai = selRef.current.ai;
      const p = await fetchPrediction(sym, timeframe, ai ? ai.split(",") : undefined);
      if (viewKey.current !== key) return;
      setPrediction(p);
    } catch {
      /* AI hiccups must not blank the technical panel */
    }
  }, []);

  // Initial load on symbol/timeframe change
  useEffect(() => {
    setLoading(true);
    setSignal(null);
    setPrediction(null);
    setOverlayData(null);
    setTrendcast(null);
    Promise.all([
      loadCandles(symbol, tf),
      loadSignal(symbol, tf),
      loadPrediction(symbol, tf),
      loadOverlays(symbol, tf),
      loadTrendcast(symbol, tf),
    ]).finally(() => setLoading(false));
  }, [symbol, tf, loadCandles, loadSignal, loadPrediction, loadOverlays, loadTrendcast]);

  // LIVE technical signal — polled ~every 1.5s (intraday) with an in-flight guard,
  // so a newly-closed candle updates the report almost immediately.
  useEffect(() => {
    const ms = INTRADAY.has(tf) ? 1500 : 5000;
    const id = setInterval(() => {
      if (!document.hidden) loadSignal(symbol, tf);
    }, ms);
    return () => clearInterval(id);
  }, [symbol, tf, loadSignal]);

  // Chart overlays change slowly — refresh them on a relaxed cadence.
  useEffect(() => {
    const ms = INTRADAY.has(tf) ? 10_000 : 30_000;
    const id = setInterval(() => {
      if (!document.hidden) loadOverlays(symbol, tf);
    }, ms);
    return () => clearInterval(id);
  }, [symbol, tf, loadOverlays]);

  // Predicted-candle history: load on toggle-on, symbol/tf change, and refresh
  // alongside the signal so newly-closed forecasts get scored & colored.
  useEffect(() => {
    if (!showForecastHist) {
      setForecastHist([]);
      return;
    }
    loadForecastHist(symbol, tf);
    const ms = INTRADAY.has(tf) ? 15_000 : 60_000;
    const id = setInterval(() => {
      if (!document.hidden) loadForecastHist(symbol, tf);
    }, ms);
    return () => clearInterval(id);
  }, [showForecastHist, symbol, tf, loadForecastHist]);

  // Average trend line: load on toggle-on / symbol/tf change, refresh periodically.
  useEffect(() => {
    if (!showAvgLine) {
      setAvgLine([]);
      return;
    }
    loadAvgLine(symbol, tf);
    // refresh quickly so the average + its projection visibly track the candles
    const ms = INTRADAY.has(tf) ? 5000 : 20_000;
    const id = setInterval(() => {
      if (!document.hidden) loadAvgLine(symbol, tf);
    }, ms);
    return () => clearInterval(id);
  }, [showAvgLine, symbol, tf, loadAvgLine]);

  // Trend prediction: refresh alongside the signal so the multi-horizon read
  // tracks the latest price action.
  useEffect(() => {
    const ms = INTRADAY.has(tf) ? 6000 : 20_000;
    const id = setInterval(() => {
      if (!document.hidden) loadTrendcast(symbol, tf);
    }, ms);
    return () => clearInterval(id);
  }, [symbol, tf, loadTrendcast]);

  // Patterns + divergences: load on toggle-on / symbol/tf change, refresh on a
  // candle-paced cadence (they only change when a candle closes).
  useEffect(() => {
    if (!showPatterns) {
      setPatterns(null);
      return;
    }
    loadPatterns(symbol, tf);
    const ms = INTRADAY.has(tf) ? 10_000 : 30_000;
    const id = setInterval(() => {
      if (!document.hidden) loadPatterns(symbol, tf);
    }, ms);
    return () => clearInterval(id);
  }, [showPatterns, symbol, tf, loadPatterns]);

  // Toggling indicators on/off ⇒ immediately re-score the signal.
  useEffect(() => {
    if (signal) loadSignal(symbol, tf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onCsv]);

  // Changing which indicators feed the AI ⇒ refresh the AI call.
  useEffect(() => {
    if (prediction) loadPrediction(symbol, tf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aiCsv]);

  // AI prediction: slower cadence (server caches it anyway).
  useEffect(() => {
    if (!current) return;
    const ms = INTRADAY.has(tf) ? 45_000 : 90_000;
    const id = setInterval(() => {
      if (document.hidden) return;
      loadPrediction(symbol, tf);
      if (!live) loadCandles(symbol, tf); // polled chart for non-streamed assets
    }, ms);
    return () => clearInterval(id);
  }, [symbol, tf, live, current, loadCandles, loadPrediction]);

  // Faster chart refresh for non-streamed (Yahoo) assets
  useEffect(() => {
    if (live || !current) return;
    const ms = INTRADAY.has(tf) ? 12_000 : 45_000;
    const id = setInterval(() => {
      if (document.hidden) return;
      loadCandles(symbol, tf);
    }, ms);
    return () => clearInterval(id);
  }, [symbol, tf, live, current, loadCandles]);

  const onTick = useCallback((price: number) => {
    const prev = prevTickRef.current;
    if (prev !== null && price !== prev) setTickDir(price > prev ? "up" : "down");
    prevTickRef.current = price;
    setLivePrice(price);
  }, []);
  const onResync = useCallback(() => loadCandles(symbol, tf), [symbol, tf, loadCandles]);

  const shownPrice = livePrice ?? signal?.price ?? prediction?.price ?? null;
  const changePct = signal?.change_pct ?? prediction?.change_pct ?? null;

  // Candle-close countdown. Crypto/intraday candles open on clean clock
  // boundaries, so we count down to the next wall-clock boundary — this resets
  // to a full period the instant a new candle opens, even though the fetched
  // `candles` array stays frozen while the WebSocket streams the live bar.
  // Weekly candles don't align to the epoch, so anchor those to the real open.
  const tfSec = TF_SECONDS[tf] ?? 3600;
  const lastTime = candles.length ? candles[candles.length - 1].time : null;
  let countdown: number | null = null;
  if (lastTime !== null) {
    const nowSec = now / 1000;
    if (tf === "1wk") {
      const periodsAhead = Math.max(1, Math.ceil((nowSec - lastTime) / tfSec));
      countdown = lastTime + periodsAhead * tfSec - nowSec;
    } else {
      countdown = Math.ceil(nowSec / tfSec) * tfSec - nowSec;
    }
  }
  const clock = new Date(now).toLocaleTimeString();

  // 24h stats from whatever candles we have in view
  const dayAgo = now / 1000 - 86400;
  const dayCandles = candles.filter((c) => c.time >= dayAgo);
  const high24 = dayCandles.length ? Math.max(...dayCandles.map((c) => c.high)) : null;
  const low24 = dayCandles.length ? Math.min(...dayCandles.map((c) => c.low)) : null;
  const vol24 = dayCandles.reduce((s, c) => s + c.volume, 0);
  const dayOpen = dayCandles.length ? dayCandles[0].open : null;
  const change24 =
    dayOpen && shownPrice ? ((shownPrice - dayOpen) / dayOpen) * 100 : changePct;
  const changeAbs = dayOpen && shownPrice ? shownPrice - dayOpen : null;
  const up24 = (change24 ?? 0) >= 0;
  const dataSource = isBinance ? "Binance" : "Yahoo Finance";

  return (
    <div className="app">
      <header className="topbar">
        <div className="logo">
          AI <span>Trend Predictor</span>
        </div>
        <AssetPicker assets={assets} symbol={symbol} onSelect={setSymbol} />
        <TimeframePicker tf={tf} onSelect={setTf} />
        {signal && (
          <IndicatorMenu
            indicators={signal.indicators}
            overlayable={overlayData?.overlayable ?? []}
            ctrl={indCtrl}
            showForecastHist={showForecastHist}
            onToggleForecastHist={setShowForecastHist}
            showAvgLine={showAvgLine}
            onToggleAvgLine={setShowAvgLine}
            showPatterns={showPatterns}
            onTogglePatterns={setShowPatterns}
          />
        )}
        <button
          className={reportOpen ? "tab report-btn active" : "tab report-btn"}
          title="Prediction accuracy report — collapsible & resizable panel"
          onClick={() => {
            setReportOpen((o) => !o);
            setReportCollapsed(false);
          }}
        >
          📊 Accuracy Report
        </button>
      </header>

      <div className="price-header">
        <div className="ph-id">
          <span className="ph-star">★</span>
          <div className="ph-name">
            <span className="ph-title">{current?.name ?? symbol}</span>
            <span className="ph-ticker">{tickerLabel(symbol)}</span>
          </div>
        </div>

        <div className="ph-price-block">
          {shownPrice !== null && (
            <span className={`ph-price tick-${tickDir}`}>{fmtNum(shownPrice)}</span>
          )}
          <span className={up24 ? "ph-arrow up" : "ph-arrow down"}>{up24 ? "↗" : "↘"}</span>
          {change24 !== null && (
            <div className="ph-change">
              <span className={up24 ? "chg up" : "chg down"}>
                {up24 ? "+" : ""}{change24.toFixed(2)}%
              </span>
              {changeAbs !== null && (
                <span className={up24 ? "chg-abs up" : "chg-abs down"}>
                  {up24 ? "+" : ""}{fmtNum(Math.abs(changeAbs))}
                </span>
              )}
            </div>
          )}
        </div>

        <div className="ph-stats">
          <div className="ph-stat">
            <span className="ph-stat-label">24H High</span>
            <span className="ph-stat-val">{high24 !== null ? fmtNum(high24) : "—"}</span>
          </div>
          <div className="ph-stat">
            <span className="ph-stat-label">24H Low</span>
            <span className="ph-stat-val">{low24 !== null ? fmtNum(low24) : "—"}</span>
          </div>
          {vol24 > 0 && (
            <div className="ph-stat">
              <span className="ph-stat-label">24H Volume</span>
              <span className="ph-stat-val">{fmtCompact(vol24)}</span>
            </div>
          )}
        </div>

        <div className="ph-right">
          {live ? (
            <span className="ph-feed live"><span className="live-dot" /> Live</span>
          ) : (
            <span className="ph-feed delayed" title="Yahoo feed is ~10-15 min delayed intraday">
              delayed feed
            </span>
          )}
          <button
            className={timeOpen ? "time-toggle open" : "time-toggle"}
            onClick={() => setTimeOpen(!timeOpen)}
            title={timeOpen ? "Hide clock" : "Show clock"}
          >
            🕐
          </button>
          {timeOpen && (
            <span className="clock" title="Local time · candle close countdown">
              {clock}
              {countdown !== null && ` · ${fmtCountdown(countdown)}`}
            </span>
          )}
        </div>
      </div>

      {error && <div className="error-bar">{error}</div>}

      <main className="layout">
        <section className="chart-wrap">
          {loading && <div className="loading">Loading…</div>}
          <Chart
            candles={candles}
            live={live}
            tf={tf}
            levels={signal?.levels ?? prediction?.technical.levels ?? null}
            plan={signal?.plan ?? prediction?.technical.plan ?? null}
            forecast={signal?.next_candle ?? null}
            forecastHistory={showForecastHist ? forecastHist : undefined}
            overlays={overlaySeries}
            avgLine={showAvgLine ? avgLine : undefined}
            patterns={showPatterns && patterns ? [...patterns.candlesticks, ...patterns.divergences] : undefined}
            onTick={onTick}
            onResync={onResync}
          />
          {countdown !== null && (
            <div className="candle-timer" title="Time until the current candle closes">
              <span className="ct-label">{tf.toUpperCase()} candle closes in</span>
              <span className="ct-time">{fmtCountdown(countdown)}</span>
              <span className="ct-bar">
                <span
                  className="ct-bar-fill"
                  style={{ width: `${Math.max(0, Math.min(100, (1 - countdown / tfSec) * 100))}%` }}
                />
              </span>
            </div>
          )}
        </section>
        <aside className="sidebar">
          {signal ? <SignalPanel s={signal} /> : !error && <div className="panel">Loading signal…</div>}
          {signal && (
            <IndicatorPanel
              indicators={signal.indicators}
              overlayable={overlayData?.overlayable ?? []}
              ctrl={indCtrl}
            />
          )}
          {signal && <TradeSetup s={signal} />}
          {trendcast && <TrendForecast f={trendcast} />}
          {showPatterns && patterns && <PatternsPanel p={patterns} />}
          {prediction && <AICard p={prediction} />}
        </aside>
      </main>

      <footer className="app-footer">
        <div className="foot-disclaimer">
          <span className="foot-shield">▲</span>
          <div>
            <div className="foot-disc-title">AI Trend Predictor</div>
            <div className="foot-disc-sub">Professional market analysis &amp; signal engine</div>
          </div>
        </div>
        <div className="foot-meta">
          <div className="foot-meta-item">
            <span className="foot-meta-label">Connection</span>
            <span className="foot-meta-val">
              <span className={live ? "live-dot" : "delayed-dot"} /> {live ? "Live" : "Delayed"}
            </span>
          </div>
          <div className="foot-meta-item">
            <span className="foot-meta-label">Data Source</span>
            <span className="foot-meta-val">{dataSource}</span>
          </div>
          <div className="foot-meta-item">
            <span className="foot-meta-label">Last Update</span>
            <span className="foot-meta-val">{new Date((signal?.updated ?? now / 1000) * 1000).toLocaleTimeString()}</span>
          </div>
        </div>
      </footer>

      {reportOpen && (
        <div
          className={reportCollapsed ? "report-drawer collapsed" : "report-drawer"}
          style={{ width: reportCollapsed ? 44 : reportWidth }}
        >
          {!reportCollapsed && (
            <div
              className="report-resize"
              title="Drag to resize"
              onMouseDown={() => {
                reportResizing.current = true;
                document.body.style.userSelect = "none";
              }}
            />
          )}
          <div className="report-drawer-head">
            <button
              className="rd-icon"
              title={reportCollapsed ? "Expand" : "Collapse"}
              onClick={() => setReportCollapsed((c) => !c)}
            >
              {reportCollapsed ? "‹" : "›"}
            </button>
            {reportCollapsed ? (
              <span className="rd-title-vert">ACCURACY REPORT</span>
            ) : (
              <>
                <span className="rd-title">📊 Accuracy Report</span>
                <button className="rd-icon rd-close" title="Close" onClick={() => setReportOpen(false)}>
                  ✕
                </button>
              </>
            )}
          </div>
          {!reportCollapsed && (
            <div className="report-drawer-body">
              <ReportPage symbol={symbol} tf={tf} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
