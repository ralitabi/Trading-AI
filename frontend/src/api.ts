import type {
  AccuracyReport, AssetInfo, AvgLineResponse, Candle, ForecastHistResponse,
  OverlaysResponse, PatternsResponse, Prediction, SignalData, TrendcastResponse, TrendResponse,
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

export const fetchReport = (symbol?: string, tf?: string) => {
  const q = new URLSearchParams();
  if (symbol) q.set("symbol", symbol);
  if (tf) q.set("tf", tf);
  const qs = q.toString();
  return get<AccuracyReport>(`/report${qs ? `?${qs}` : ""}`);
};
