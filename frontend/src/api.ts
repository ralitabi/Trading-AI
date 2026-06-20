import type {
  AccuracyReport, AssetInfo, AvgLineResponse, BacktestResponse, CalendarResponse, Candle,
  ChartPatternsResponse, ForecastHistResponse, MarketContextResponse, NewsResponse,
  OrderBookResponse, OverlaysResponse, PatternsResponse, Portfolio, Prediction, SignalData,
  TrendcastResponse, TrendResponse, VolProfileResponse,
} from "./types";

// Backend base URL resolution:
//  - VITE_API_URL wins if set (e.g. a separate Render backend).
//  - Local dev → 127.0.0.1:8742 (localhost resolves to IPv6 ::1 on Windows,
//    where uvicorn isn't listening; 8742 avoids stale zombie sockets on 8000).
//  - Production (Vercel) → "/_/backend", the same-origin FastAPI service.
const isLocal =
  typeof window !== "undefined" &&
  /^(localhost|127\.0\.0\.1|\[::1\])$/.test(window.location.hostname);
export const API =
  import.meta.env.VITE_API_URL ?? (isLocal ? "http://127.0.0.1:8742" : "/_/backend");

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

export const fetchAssets = () => get<AssetInfo[]>("/assets");

export const fetchCandles = (symbol: string, tf: string, limit = 300) =>
  get<{ candles: Candle[] }>(`/candles/${symbol}?tf=${tf}&limit=${limit}`).then((r) => r.candles);

export const fetchSignal = (symbol: string, tf: string, indicatorsOn?: string) => {
  const q = indicatorsOn ? `&indicators_on=${encodeURIComponent(indicatorsOn)}` : "";
  return get<SignalData>(`/signal/${symbol}?tf=${tf}${q}`);
};

export const fetchPrediction = (symbol: string, tf: string, aiIndicators?: string[]) => {
  const q = aiIndicators?.length
    ? `&ai_indicators=${encodeURIComponent(aiIndicators.join(","))}`
    : "";
  return get<Prediction>(`/predict/${symbol}?tf=${tf}${q}`);
};

export const fetchOverlays = (symbol: string, tf: string) =>
  get<OverlaysResponse>(`/overlays/${symbol}?tf=${tf}`);

export const fetchForecastHistory = (symbol: string, tf: string) =>
  get<ForecastHistResponse>(`/forecasts/${symbol}?tf=${tf}`);

export const fetchTrends = (symbol: string, tf: string) =>
  get<TrendResponse>(`/trends/${symbol}?tf=${tf}`);

export const fetchAvgLine = (symbol: string, tf: string) =>
  get<AvgLineResponse>(`/avgline/${symbol}?tf=${tf}`);

export const fetchTrendcast = (symbol: string, tf: string) =>
  get<TrendcastResponse>(`/trendcast/${symbol}?tf=${tf}`);

export const fetchPatterns = (symbol: string, tf: string) =>
  get<PatternsResponse>(`/patterns/${symbol}?tf=${tf}`);

export const fetchChartPatterns = (symbol: string, tf: string) =>
  get<ChartPatternsResponse>(`/chartpatterns/${symbol}?tf=${tf}`);

export const fetchContext = (symbol: string) =>
  get<MarketContextResponse>(`/context/${symbol}`);

export const fetchVolProfile = (symbol: string, tf: string) =>
  get<VolProfileResponse>(`/volprofile/${symbol}?tf=${tf}`);

export const fetchOrderBook = (symbol: string) =>
  get<OrderBookResponse>(`/orderbook/${symbol}`);

export const fetchNews = (symbol: string) =>
  get<NewsResponse>(`/news/${symbol}`);

export const fetchCalendar = () =>
  get<CalendarResponse>("/calendar");

export const fetchPortfolio = () =>
  get<Portfolio>("/portfolio");

export const fetchBacktest = (symbol: string, tf: string) =>
  get<BacktestResponse>(`/backtest/${symbol}?tf=${tf}`);

export const fetchNotifyConfig = () =>
  get<{ channels: string[] }>("/notify/config");

/** Relay an alert to the server's configured chat channels. Fire-and-forget:
 *  never throws — browser notifications are the primary, always-on channel. */
export const postNotify = (title: string, message = "") =>
  fetch(`${API}/notify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, message }),
  })
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null);

export const fetchReport = (symbol?: string, tf?: string) => {
  const q = new URLSearchParams();
  if (symbol) q.set("symbol", symbol);
  if (tf) q.set("tf", tf);
  const qs = q.toString();
  return get<AccuracyReport>(`/report${qs ? `?${qs}` : ""}`);
};
