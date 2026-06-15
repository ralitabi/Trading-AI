export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface AssetInfo {
  symbol: string;
  name: string;
  asset_class: string;
  source: string;
}

export interface IndicatorDetail {
  name: string;
  value: string;
  vote: "up" | "down" | "neutral";
  note: string;
  kind?: "trend" | "osc" | "volume";
  available?: boolean;
  disabled?: boolean;
}

export interface OverlayLine {
  time: number;
  value: number;
}

export interface OverlaySpec {
  lines: Record<string, OverlayLine[]>;
  colors: Record<string, string>;
}

export interface OverlaysResponse {
  symbol: string;
  tf: string;
  overlayable: string[];
  overlays: Record<string, OverlaySpec>;
}

export interface ForecastHistItem {
  time: number;
  target_time?: number;
  open: number;
  high: number;
  low: number;
  close: number;
  direction: "up" | "down" | "neutral";
  correct?: boolean;
}

export interface ForecastSummary {
  total: number;
  correct: number;
  slight: number;
  complete: number;
  noedge?: number;
  graded?: number;
  accuracy: number | null;
}

export interface ForecastHistResponse {
  symbol: string;
  tf: string;
  forecasts: ForecastHistItem[];
  summary?: ForecastSummary;
}

export interface TrendSegment {
  dir: "up" | "down";
  bars: number;
  change_pct: number;
}

export interface TrendInfo {
  direction: "up" | "down";
  age_bars: number;
  age_label: string;
  change_pct: number;
  adx: number;
  strength: "weak" | "moderate" | "strong";
  sample: number;
  recent_segments: TrendSegment[];
  median_bars?: number;
  typical_low?: number;
  typical_high?: number;
  expected_remaining_bars?: number;
  expected_remaining_label?: string;
  continue_probability?: number;
  mature?: boolean;
  note?: string;
}

export interface TrendResponse {
  symbol: string;
  tf: string;
  trend: TrendInfo | null;
}

export interface AvgLinePoint {
  time: number;
  value: number;
  color: string;
  /** "trend" = realized average, "proj" = forward (predicted) projection */
  seg?: "trend" | "proj";
}

export interface AvgLineResponse {
  symbol: string;
  tf: string;
  period: number;
  points: AvgLinePoint[];
  legend: { trend: string; broke: string; projection: string };
}

export interface Levels {
  support: number | null;
  resistance: number | null;
}

export interface HTF {
  tf: string | null;
  trend: "up" | "down" | "neutral" | null;
  note: string | null;
}

export interface TradePlan {
  direction: "long" | "short";
  entry: number;
  stop: number;
  target: number;
  rr: number;
}

export interface RiskFactor {
  label: string;
  state: "good" | "ok" | "weak";
  detail: string;
}

export interface SafetyInfo {
  level: "safe" | "caution" | "risky";
  /** 0 = very safe to act … 100 = very risky. Drives the trade risk meter. */
  score: number;
  headline: string;
  action: string;
  direction: string;
  factors?: RiskFactor[];
}

export interface MarketInfo {
  level: "good" | "mixed" | "poor";
  /** 0 = clean/tradeable … 100 = choppy/avoid. Drives the market meter. */
  score: number;
  headline: string;
  direction: "up" | "down" | "flat";
  factors?: RiskFactor[];
}

export interface TrendHorizon {
  bars: number;
  label: string;
  direction: "up" | "down" | "sideways";
  move_pct: number;
  target: number;
  low: number;
  high: number;
  confidence: number;
}

export interface TrendForecast {
  price: number;
  adx: number;
  bias: "up" | "down" | "sideways";
  headline: string;
  horizons: TrendHorizon[];
}

export interface TrendcastResponse {
  symbol: string;
  tf: string;
  forecast: TrendForecast | null;
}

export interface PatternItem {
  time: number;
  name: string;
  direction: "bullish" | "bearish" | "neutral";
  price: number;
  kind: "candlestick" | "divergence";
}

export interface PatternsResponse {
  symbol: string;
  tf: string;
  candlesticks: PatternItem[];
  divergences: PatternItem[];
  summary: {
    bias: "bullish" | "bearish" | "neutral";
    bullish: number;
    bearish: number;
    latest: PatternItem[];
  };
}

export interface FearGreed {
  value: number;
  classification: string;
  timestamp: number;
}

export interface Funding {
  symbol: string;
  rate_pct: number;
  annualized_pct: number;
  next_funding_time: number;
  mark_price: number;
  sentiment: string;
}

export interface MarketContextResponse {
  symbol: string;
  fear_greed: FearGreed | null;
  funding: Funding | null;
}

export interface VolBucket {
  price: number;
  volume: number;
}

export interface VolProfile {
  bins: VolBucket[];
  poc: number;
  value_area_low: number;
  value_area_high: number;
  max_volume: number;
}

export interface VolProfileResponse {
  symbol: string;
  tf: string;
  profile: VolProfile | null;
}

export interface OrderLevel {
  price: number;
  qty: number;
}

export interface OrderBook {
  mid: number;
  spread: number;
  spread_pct: number;
  bid_volume: number;
  ask_volume: number;
  imbalance_pct: number;
  bids: OrderLevel[];
  asks: OrderLevel[];
}

export interface OrderBookResponse {
  symbol: string;
  book: OrderBook | null;
}

export interface BestWindow {
  start_utc: number;
  end_utc: number;
  intensity: number;
  basis: string;
}

export interface Technical {
  bias: "up" | "down" | "neutral";
  confidence: number;
  votes: { up: number; down: number; neutral: number };
  indicators: IndicatorDetail[];
  volatility: "low" | "moderate" | "high";
  atr_pct: number;
  adx: number;
  trend_strength: "weak" | "moderate" | "strong";
  levels: Levels;
  htf: HTF | null;
  plan: TradePlan | null;
  safety?: SafetyInfo;
  market?: MarketInfo;
  best_window?: BestWindow | null;
}

export interface AIView {
  direction: "up" | "down" | "neutral";
  confidence: number;
  safety?: string;
  best_time?: string;
  rationale: string;
  key_drivers: string[];
  risk_note: string;
  headlines_used: string[];
  model: string;
  cached: boolean;
}

export interface NextCandle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  direction: "up" | "down" | "neutral";
  body_pct: number;
  range_pct: number;
  basis: string;
}

/** Full /signal payload: Technical fields flattened + market context. */
export interface SignalData extends Technical {
  symbol: string;
  name: string;
  asset_class: string;
  tf: string;
  price: number;
  change_pct: number;
  next_candle: NextCandle | null;
  updated: number;
  disclaimer: string;
}

export interface AccuracyStat {
  calls: number;
  hits: number;
  accuracy: number | null;
}

export interface MarketAccuracy {
  symbol: string;
  tf: string;
  tech_calls: number;
  tech_hits: number;
  tech_accuracy: number | null;
  ai_calls: number;
  ai_hits: number;
  ai_accuracy: number | null;
}

export interface EvaluatedPrediction {
  id: number;
  ts: number;
  symbol: string;
  tf: string;
  price: number;
  tech_bias: string;
  tech_confidence: number;
  ai_direction: string;
  ai_confidence: number;
  actual_price: number | null;
  actual_direction: string | null;
  tech_correct: number | null;
  ai_correct: number | null;
}

export interface AccuracyReport {
  totals: { logged: number; pending: number; evaluated: number; unknown: number; no_call: number };
  technical: AccuracyStat;
  ai: AccuracyStat;
  by_market: MarketAccuracy[];
  recent: EvaluatedPrediction[];
  disclaimer: string;
}

export interface Prediction {
  symbol: string;
  name: string;
  asset_class: string;
  tf: string;
  price: number;
  change_pct: number;
  technical: Technical;
  next_candle: NextCandle | null;
  ai: AIView;
  updated: number;
  disclaimer: string;
}
