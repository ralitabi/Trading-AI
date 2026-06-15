import type { PatternsResponse } from "../types";
import CollapsiblePanel from "./CollapsiblePanel";

const ICON = { bullish: "▲", bearish: "▼", neutral: "■" } as const;

const fmtAgo = (ts: number) => {
  const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
};

/**
 * Candlestick patterns + RSI/MACD divergences detected on the chart — a
 * price-action read alongside the indicator board. Markers also appear on the
 * chart itself; this panel lists the most recent few with their lean.
 */
export default function PatternsPanel({ p }: { p: PatternsResponse }) {
  const { summary } = p;
  const latest = summary.latest ?? [];
  return (
    <CollapsiblePanel title="Patterns & Divergences"
      right={<span className={`pat-bias pat-${summary.bias}`}>{ICON[summary.bias]} {summary.bias}</span>}>
      <div className="pat-tally">
        <span className="pat-tally-item bull">{summary.bullish} bullish</span>
        <span className="pat-tally-item bear">{summary.bearish} bearish</span>
        <span className="pat-tally-note">recent signals</span>
      </div>
      {latest.length === 0 ? (
        <p className="pat-empty">No notable patterns on this timeframe right now.</p>
      ) : (
        <ul className="pat-list">
          {latest.map((x, i) => (
            <li key={`${x.time}-${i}`} className={`pat-row pat-${x.direction}`}>
              <span className="pat-icon">{ICON[x.direction]}</span>
              <span className="pat-name">{x.name}</span>
              <span className={`pat-kind pk-${x.kind}`}>{x.kind === "divergence" ? "divergence" : "candle"}</span>
              <span className="pat-time">{fmtAgo(x.time)}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="pat-foot">Price-action context — patterns can fail; use with the signal, not alone.</div>
    </CollapsiblePanel>
  );
}
