import { useCallback, useEffect, useState } from "react";
import { fetchAssets, fetchForecastHistory, fetchReport, fetchTrends } from "../api";
import type { AccuracyReport, AssetInfo, ForecastSummary, TrendInfo } from "../types";

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d", "1wk"];

const ARROWS: Record<string, string> = { up: "▲", down: "▼", neutral: "■", flat: "▬", unknown: "?" };

const fmtPrice = (n: number | null) =>
  n === null ? "—" : n >= 100 ? n.toLocaleString(undefined, { maximumFractionDigits: 2 }) : n.toFixed(5);

const fmtTime = (ts: number) =>
  new Date(ts * 1000).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });

function Mark({ v }: { v: number | null }) {
  if (v === null) return <span className="mark mark-na">–</span>;
  return v ? <span className="mark mark-hit">✓</span> : <span className="mark mark-miss">✗</span>;
}

export default function ReportPage({ symbol: pSymbol, tf: pTf }: { symbol?: string; tf?: string } = {}) {
  const params = new URLSearchParams(window.location.search);
  const [fSymbol, setFSymbol] = useState(pSymbol ?? params.get("symbol") ?? "");
  const [fTf, setFTf] = useState(pTf ?? params.get("tf") ?? "");

  // when embedded, follow the dashboard's current market/timeframe
  useEffect(() => {
    if (pSymbol !== undefined) setFSymbol(pSymbol);
  }, [pSymbol]);
  useEffect(() => {
    if (pTf !== undefined) setFTf(pTf);
  }, [pTf]);
  const [assets, setAssets] = useState<AssetInfo[]>([]);
  const [report, setReport] = useState<AccuracyReport | null>(null);
  const [quality, setQuality] = useState<ForecastSummary | null>(null);
  const [qualitySym, setQualitySym] = useState<string>("");
  const [trend, setTrend] = useState<TrendInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshedAt, setRefreshedAt] = useState<string>("");

  useEffect(() => {
    fetchAssets().then(setAssets).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    try {
      setReport(await fetchReport(fSymbol || undefined, fTf || undefined));
      setError(null);
      setRefreshedAt(new Date().toLocaleTimeString());
    } catch (e) {
      setError(String(e));
    }
    // Forecast-quality breakdown needs a concrete market — reconstruct for it.
    const sym = fSymbol || "BTCUSDT";
    const tf = fTf || "1h";
    try {
      const r = await fetchForecastHistory(sym, tf);
      setQuality(r.summary ?? null);
      setQualitySym(`${sym} · ${tf}`);
    } catch {
      setQuality(null);
    }
    try {
      const t = await fetchTrends(sym, tf);
      setTrend(t.trend);
    } catch {
      setTrend(null);
    }
  }, [fSymbol, fTf]);

  useEffect(() => {
    load();
    const id = setInterval(() => {
      if (!document.hidden) load();
    }, 30_000);
    return () => clearInterval(id);
  }, [load]);

  if (error) return <div className="report-page"><div className="error-bar">{error}</div></div>;
  if (!report) return <div className="report-page"><div className="loading">Loading report…</div></div>;

  const { totals, technical, ai, by_market, recent } = report;
  const smallSample = technical.calls + ai.calls < 30;

  return (
    <div className="report-page">
      <header className="report-head">
        <h1>Prediction Accuracy Report</h1>
        <div className="report-meta">
          <select className="report-filter" value={fSymbol} onChange={(e) => setFSymbol(e.target.value)}>
            <option value="">All markets</option>
            {assets.map((a) => (
              <option key={a.symbol} value={a.symbol}>{a.name}</option>
            ))}
          </select>
          <select className="report-filter" value={fTf} onChange={(e) => setFTf(e.target.value)}>
            <option value="">All timeframes</option>
            {TIMEFRAMES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          updated {refreshedAt} · auto-refreshes every 30s
          <button className="tab" onClick={load}>refresh now</button>
        </div>
      </header>

      <div className="stat-cards">
        <div className="stat-card">
          <div className="stat-label">Technical signal</div>
          <div className={`stat-value ${technical.accuracy !== null && technical.accuracy >= 50 ? "good" : "bad"}`}>
            {technical.accuracy !== null ? `${technical.accuracy}%` : "—"}
          </div>
          <div className="stat-sub">{technical.hits} of {technical.calls} directional calls correct</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">AI analysis</div>
          <div className={`stat-value ${ai.accuracy !== null && ai.accuracy >= 50 ? "good" : "bad"}`}>
            {ai.accuracy !== null ? `${ai.accuracy}%` : "—"}
          </div>
          <div className="stat-sub">{ai.hits} of {ai.calls} directional calls correct</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Logged</div>
          <div className="stat-value">{totals.logged}</div>
          <div className="stat-sub">
            {totals.pending} awaiting their candle · {totals.no_call} no-edge calls · {totals.unknown} unscoreable
          </div>
        </div>
      </div>

      {smallSample && (
        <div className="sample-note">
          ⚠ Small sample — accuracy numbers are not statistically meaningful until ~30+ scored
          calls per row. Let the system run; the truth accumulates.
        </div>
      )}

      {trend && (
        <>
          <h2>Trend analysis — {qualitySym}</h2>
          <div className={`trend-card trend-${trend.direction}`}>
            <div className="trend-top">
              <div className="trend-badge">
                <span className="trend-arrow">{trend.direction === "up" ? "▲" : "▼"}</span>
                <span className="trend-dir">{trend.direction.toUpperCase()}TREND</span>
              </div>
              <div className="trend-facts">
                <span>Running <b>{trend.age_label}</b> ({trend.age_bars} candles)</span>
                <span className={trend.change_pct >= 0 ? "chg up" : "chg down"}>
                  {trend.change_pct >= 0 ? "+" : ""}{trend.change_pct}%
                </span>
                <span className={`chip chip-${trend.strength}`}>{trend.strength} · ADX {trend.adx}</span>
              </div>
            </div>

            {trend.continue_probability !== undefined ? (
              <div className="trend-persist">
                <div className="trend-persist-row">
                  <div className="tp-item">
                    <span className="tp-label">Likely to continue</span>
                    <span className={`tp-val ${trend.continue_probability >= 50 ? "good" : "bad"}`}>
                      {trend.continue_probability}%
                    </span>
                    <span className="tp-sub">of past {trend.direction}trends lasted longer</span>
                  </div>
                  <div className="tp-item">
                    <span className="tp-label">Est. time left</span>
                    <span className="tp-val">{trend.expected_remaining_label}</span>
                    <span className="tp-sub">vs typical {trend.typical_low}–{trend.typical_high} candles</span>
                  </div>
                  <div className="tp-item">
                    <span className="tp-label">Median trend</span>
                    <span className="tp-val">{trend.median_bars}</span>
                    <span className="tp-sub">candles (n={trend.sample} past trends)</span>
                  </div>
                </div>
                {trend.mature && (
                  <div className="trend-warn">
                    ⚠ This {trend.direction}trend is already past its typical length — historically a
                    reversal/pause becomes more likely from here. Not a signal to act, just context.
                  </div>
                )}
              </div>
            ) : (
              <div className="trend-warn">{trend.note}</div>
            )}
            <div className="trend-note">
              Trend = EMA 9 vs 21 regime; duration estimated from this market's own past trend lengths.
              Statistical context, not a prediction — trends can reverse at any time.
            </div>
          </div>
        </>
      )}

      {quality && quality.total > 0 && (
        <>
          <h2>Predicted candle quality — {qualitySym}</h2>
          <div className="quality-wrap">
            <div className="quality-bar">
              <div className="q-seg q-correct" style={{ width: `${(quality.correct / quality.total) * 100}%` }}
                title={`${quality.correct} correct`} />
              <div className="q-seg q-slight" style={{ width: `${(quality.slight / quality.total) * 100}%` }}
                title={`${quality.slight} slightly off`} />
              <div className="q-seg q-complete" style={{ width: `${(quality.complete / quality.total) * 100}%` }}
                title={`${quality.complete} completely off`} />
            </div>
            <div className="quality-cards">
              <div className="q-card q-c-correct">
                <div className="q-num">{quality.correct}</div>
                <div className="q-pct">{Math.round((quality.correct / quality.total) * 100)}%</div>
                <div className="q-label">Correct</div>
                <div className="q-desc">candle went the predicted direction</div>
              </div>
              <div className="q-card q-c-slight">
                <div className="q-num">{quality.slight}</div>
                <div className="q-pct">{Math.round((quality.slight / quality.total) * 100)}%</div>
                <div className="q-label">Slightly off</div>
                <div className="q-desc">wrong way, but only a small move</div>
              </div>
              <div className="q-card q-c-complete">
                <div className="q-num">{quality.complete}</div>
                <div className="q-pct">{Math.round((quality.complete / quality.total) * 100)}%</div>
                <div className="q-label">Completely off</div>
                <div className="q-desc">wrong way and a big move</div>
              </div>
            </div>
            <div className="quality-note">
              {quality.total} committed directional calls
              {quality.noedge ? ` · ${quality.noedge} "no-edge" candles skipped (engine held back)` : ""}
              {" "}— replaying the engine over recent history.
            </div>
          </div>
        </>
      )}

      <h2>By market & timeframe</h2>
      {by_market.length === 0 ? (
        <p className="report-empty">No scored predictions yet — they're graded one candle after they're made.</p>
      ) : (
        <table className="report-table">
          <thead>
            <tr><th>Market</th><th>TF</th><th>Technical</th><th>AI</th></tr>
          </thead>
          <tbody>
            {by_market.map((m) => (
              <tr key={`${m.symbol}-${m.tf}`}>
                <td>{m.symbol}</td>
                <td>{m.tf}</td>
                <td>{m.tech_accuracy !== null ? `${m.tech_accuracy}% (${m.tech_hits}/${m.tech_calls})` : "—"}</td>
                <td>{m.ai_accuracy !== null ? `${m.ai_accuracy}% (${m.ai_hits}/${m.ai_calls})` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2>Recent scored predictions</h2>
      {recent.length === 0 ? (
        <p className="report-empty">Nothing scored yet.</p>
      ) : (
        <table className="report-table">
          <thead>
            <tr>
              <th>When</th><th>Market</th><th>TF</th><th>Price then</th>
              <th>Tech said</th><th>AI said</th><th>Actually went</th><th>Tech</th><th>AI</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((r) => (
              <tr key={r.id}>
                <td>{fmtTime(r.ts)}</td>
                <td>{r.symbol}</td>
                <td>{r.tf}</td>
                <td className="mono">{fmtPrice(r.price)}</td>
                <td className={`vote-${r.tech_bias}`}>{ARROWS[r.tech_bias] ?? ""} {r.tech_bias}</td>
                <td className={`vote-${r.ai_direction}`}>{ARROWS[r.ai_direction] ?? ""} {r.ai_direction}</td>
                <td className={`vote-${r.actual_direction ?? "unknown"}`}>
                  {ARROWS[r.actual_direction ?? "unknown"]} {r.actual_direction ?? "?"} ({fmtPrice(r.actual_price)})
                </td>
                <td><Mark v={r.tech_correct} /></td>
                <td><Mark v={r.ai_correct} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <footer className="disclaimer">{report.disclaimer}</footer>
    </div>
  );
}
