import { useMemo } from "react";
import type { BacktestResult } from "../types";

/** Cumulative-R equity curve drawn as a self-contained SVG area+line — no chart
 *  library, scales to its container, green when net-positive and red otherwise. */
function EquityCurve({ equity }: { equity: BacktestResult["equity"] }) {
  const W = 520;
  const H = 130;
  const PAD = 6;
  const { line, area, last, zeroY } = useMemo(() => {
    if (equity.length < 2) return { line: "", area: "", last: 0, zeroY: H / 2 };
    const rs = equity.map((p) => p.r);
    let min = Math.min(...rs, 0);
    let max = Math.max(...rs, 0);
    if (max - min < 1e-9) { max += 1; min -= 1; }
    const x = (i: number) => PAD + (i / (equity.length - 1)) * (W - 2 * PAD);
    const y = (r: number) => PAD + (1 - (r - min) / (max - min)) * (H - 2 * PAD);
    const pts = equity.map((p, i) => `${x(i)},${y(p.r)}`);
    return {
      line: `M${pts.join("L")}`,
      area: `M${x(0)},${y(0)} L${pts.join("L")} L${x(equity.length - 1)},${y(0)} Z`,
      last: rs[rs.length - 1],
      zeroY: y(0),
    };
  }, [equity]);

  const cls = last >= 0 ? "up" : "down";
  if (!line) return null;
  return (
    <svg className={`equity-svg ${cls}`} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none"
      role="img" aria-label="Equity curve (cumulative R)">
      <line className="equity-zero" x1={PAD} x2={W - PAD} y1={zeroY} y2={zeroY} />
      <path className="equity-area" d={area} />
      <path className="equity-line" d={line} />
    </svg>
  );
}

const fmtR = (n: number | null) => (n === null ? "—" : `${n > 0 ? "+" : ""}${n}R`);
const fmtTime = (ts: number) =>
  new Date(ts * 1000).toLocaleDateString(undefined, { month: "short", day: "numeric" });

export default function BacktestPanel({ bt, label }: { bt: BacktestResult; label: string }) {
  if (!bt.trades) {
    return (
      <>
        <h2>Strategy backtest — {label}</h2>
        <p className="report-empty">{bt.note ?? "Not enough history to backtest yet."}</p>
      </>
    );
  }
  const pos = bt.net_r >= 0;
  return (
    <>
      <h2>Strategy backtest — {label}</h2>
      <div className="bt-grid">
        <div className="bt-stat">
          <div className="bt-label">Net result</div>
          <div className={`bt-value ${pos ? "good" : "bad"}`}>{fmtR(bt.net_r)}</div>
          <div className="bt-sub">over {bt.trades} trades</div>
        </div>
        <div className="bt-stat">
          <div className="bt-label">Win rate</div>
          <div className={`bt-value ${(bt.win_rate ?? 0) >= 50 ? "good" : "bad"}`}>
            {bt.win_rate !== null ? `${bt.win_rate}%` : "—"}
          </div>
          <div className="bt-sub">{bt.wins}W · {bt.losses}L</div>
        </div>
        <div className="bt-stat">
          <div className="bt-label">Profit factor</div>
          <div className={`bt-value ${(bt.profit_factor ?? 0) >= 1 ? "good" : "bad"}`}>
            {bt.profit_factor !== null ? bt.profit_factor : "—"}
          </div>
          <div className="bt-sub">gross win ÷ loss</div>
        </div>
        <div className="bt-stat">
          <div className="bt-label">Max drawdown</div>
          <div className="bt-value bad">−{bt.max_drawdown_r}R</div>
          <div className="bt-sub">peak-to-trough</div>
        </div>
        <div className="bt-stat">
          <div className="bt-label">Expectancy</div>
          <div className={`bt-value ${(bt.expectancy_r ?? 0) >= 0 ? "good" : "bad"}`}>
            {fmtR(bt.expectancy_r)}
          </div>
          <div className="bt-sub">avg per trade</div>
        </div>
        <div className="bt-stat">
          <div className="bt-label">Avg win / loss</div>
          <div className="bt-value">
            <span className="good">{fmtR(bt.avg_win_r)}</span>
            <span className="bt-slash"> / </span>
            <span className="bad">{fmtR(bt.avg_loss_r)}</span>
          </div>
          <div className="bt-sub">per outcome</div>
        </div>
      </div>

      <div className="equity-wrap">
        <div className="equity-head">
          <span>Equity curve — cumulative R</span>
          <span className={pos ? "good" : "bad"}>{fmtR(bt.net_r)}</span>
        </div>
        <EquityCurve equity={bt.equity} />
      </div>

      {bt.recent.length > 0 && (
        <table className="report-table bt-table">
          <thead>
            <tr><th>Exit</th><th>Side</th><th>Entry</th><th>Exit px</th><th>Conf</th><th>R</th></tr>
          </thead>
          <tbody>
            {bt.recent.map((t, i) => (
              <tr key={`${t.exit_time}-${i}`}>
                <td>{fmtTime(t.exit_time)}</td>
                <td className={t.direction === "long" ? "vote-up" : "vote-down"}>
                  {t.direction === "long" ? "▲ long" : "▼ short"}
                </td>
                <td className="mono">{t.entry}</td>
                <td className="mono">{t.exit}</td>
                <td>{t.confidence}%</td>
                <td className={t.r > 0 ? "good" : "bad"}>{fmtR(t.r)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="bt-note">
        Hypothetical, friction-free replay of the live signal + ATR plan over recent history
        (no spread, slippage or fees). Evidence of edge, not a brokerage statement.
      </div>
    </>
  );
}
