import type { ChartPattern } from "../types";
import CollapsiblePanel from "./CollapsiblePanel";

const ICON = { bullish: "▲", bearish: "▼", neutral: "◆" } as const;

const fmt = (n: number) =>
  n >= 100 ? n.toLocaleString(undefined, { maximumFractionDigits: 2 }) : n.toFixed(5);

/**
 * Classic chart patterns (head & shoulders, double top/bottom, triangles)
 * detected from swing pivots. Candidates, with a confidence — not certainties.
 */
export default function ChartPatternsPanel({ patterns }: { patterns: ChartPattern[] }) {
  if (patterns.length === 0) return null;
  return (
    <CollapsiblePanel title="Chart Patterns">
      <div className="cpat-list">
        {patterns.map((p, i) => (
          <div key={i} className={`cpat-row cpat-${p.direction}`}>
            <div className="cpat-top">
              <span className="cpat-icon">{ICON[p.direction]}</span>
              <span className="cpat-name">{p.name}</span>
              {p.confirmed
                ? <span className="cpat-badge confirmed">confirmed</span>
                : <span className="cpat-badge forming">forming</span>}
              <span className="cpat-conf">{p.confidence}%</span>
            </div>
            <div className="cpat-levels">
              <span>neckline <b>{fmt(p.neckline)}</b></span>
              {p.target !== null && <span>target <b>{fmt(p.target)}</b></span>}
            </div>
          </div>
        ))}
      </div>
      <div className="cpat-foot">Geometric candidates from swing pivots — weigh with the signal, not alone.</div>
    </CollapsiblePanel>
  );
}
