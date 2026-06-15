import type { Portfolio } from "../types";
import CollapsiblePanel from "./CollapsiblePanel";

const fmt = (n: number) =>
  n >= 100 ? n.toLocaleString(undefined, { maximumFractionDigits: 2 }) : n.toFixed(5);

const tickerOf = (s: string) => (s.endsWith("USDT") ? s.slice(0, -4) : s);

/**
 * Paper-trading track record: hypothetical trades auto-opened from directional
 * signals (same ATR stop/target the dashboard shows) and scored as they hit.
 */
export default function PaperPortfolio({ p }: { p: Portfolio }) {
  const hasAny = p.open_count > 0 || p.closed_count > 0;
  if (!hasAny) return null;
  const net = p.net_r;
  return (
    <CollapsiblePanel title="Paper Trading"
      right={<span className={`pp-net ${net >= 0 ? "pos" : "neg"}`}>{net >= 0 ? "+" : ""}{net}R</span>}>
      <div className="pp-stats">
        <div className="pp-stat">
          <span className="pp-stat-val">{p.win_rate !== null ? `${p.win_rate}%` : "—"}</span>
          <span className="pp-stat-lbl">win rate</span>
        </div>
        <div className="pp-stat">
          <span className="pp-stat-val">{p.wins}/{p.losses}</span>
          <span className="pp-stat-lbl">W / L</span>
        </div>
        <div className="pp-stat">
          <span className="pp-stat-val">{p.open_count}</span>
          <span className="pp-stat-lbl">open</span>
        </div>
        <div className="pp-stat">
          <span className="pp-stat-val">{p.closed_count}</span>
          <span className="pp-stat-lbl">closed</span>
        </div>
      </div>

      {p.open.length > 0 && (
        <div className="pp-section">
          <div className="pp-head">Open positions</div>
          {p.open.map((t) => (
            <div key={t.id} className={`pp-row dir-${t.direction}`}>
              <span className="pp-sym">{tickerOf(t.symbol)} <span className="pp-tf">{t.tf}</span></span>
              <span className={`pp-dir ${t.direction}`}>{t.direction === "long" ? "▲ LONG" : "▼ SHORT"}</span>
              <span className="pp-px">@ {fmt(t.entry)}</span>
              <span className="pp-rr">1:{t.rr}</span>
            </div>
          ))}
        </div>
      )}

      {p.recent.length > 0 && (
        <div className="pp-section">
          <div className="pp-head">Recent closed</div>
          {p.recent.map((t) => (
            <div key={t.id} className="pp-row">
              <span className="pp-sym">{tickerOf(t.symbol)} <span className="pp-tf">{t.tf}</span></span>
              <span className={`pp-dir ${t.direction}`}>{t.direction === "long" ? "▲" : "▼"}</span>
              <span className={`pp-result ${t.result}`}>{t.result === "win" ? "WIN" : "LOSS"}</span>
              <span className={`pp-r ${(t.r_multiple ?? 0) >= 0 ? "pos" : "neg"}`}>
                {(t.r_multiple ?? 0) >= 0 ? "+" : ""}{t.r_multiple}R
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="pp-foot">Hypothetical, hands-off — not advice. Stop −1R · target +R:R.</div>
    </CollapsiblePanel>
  );
}
