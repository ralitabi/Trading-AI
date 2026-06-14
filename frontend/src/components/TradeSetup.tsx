import type { SignalData } from "../types";

const ARROWS = { up: "▲", down: "▼", neutral: "■" } as const;

const fmt = (n: number) =>
  n >= 100 ? n.toLocaleString(undefined, { maximumFractionDigits: 2 }) : n.toFixed(5);

export default function TradeSetup({ s }: { s: SignalData }) {
  const pctFrom = (level: number) => (((level - s.price) / s.price) * 100).toFixed(2);
  const nc = s.next_candle;

  return (
    <div className="panel">
      <div className="panel-title">Trade Setup</div>

      {nc && (
        <div className={`forecast forecast-${nc.direction}`}>
          <div className="forecast-head">
            Next candle forecast
            <span className={`forecast-dir vote-${nc.direction}`}>
              {ARROWS[nc.direction]} {nc.direction.toUpperCase()}
            </span>
          </div>
          <div className="forecast-ohlc">
            <span>O <b>{fmt(nc.open)}</b></span>
            <span>H <b>{fmt(nc.high)}</b></span>
            <span>L <b>{fmt(nc.low)}</b></span>
            <span>C <b>{fmt(nc.close)}</b></span>
          </div>
          <div className="forecast-meta">
            body ~{nc.body_pct}% · range ~{nc.range_pct}% · statistical projection, not a promise
          </div>
        </div>
      )}

      {(s.levels.support || s.levels.resistance) && (
        <div className="levels">
          {s.levels.resistance && (
            <div className="level">
              <span className="level-tag res">R</span>
              <span className="level-price">{fmt(s.levels.resistance)}</span>
              <span className="level-dist">{pctFrom(s.levels.resistance)}%</span>
            </div>
          )}
          {s.levels.support && (
            <div className="level">
              <span className="level-tag sup">S</span>
              <span className="level-price">{fmt(s.levels.support)}</span>
              <span className="level-dist">{pctFrom(s.levels.support)}%</span>
            </div>
          )}
        </div>
      )}

      {s.plan && (
        <div className={`plan plan-${s.plan.direction}`}>
          <div className="plan-head">
            ATR trade plan · {s.plan.direction.toUpperCase()} · R:R 1:{s.plan.rr}
          </div>
          <div className="plan-row">
            <span>Entry <b>{fmt(s.plan.entry)}</b></span>
            <span className="plan-stop">Stop <b>{fmt(s.plan.stop)}</b> ({pctFrom(s.plan.stop)}%)</span>
            <span className="plan-target">Target <b>{fmt(s.plan.target)}</b> ({pctFrom(s.plan.target)}%)</span>
          </div>
        </div>
      )}

      <button
        className="full-analysis-btn"
        onClick={() =>
          document.getElementById("ai-analysis-card")?.scrollIntoView({ behavior: "smooth", block: "start" })
        }
      >
        View Full Analysis <span className="fa-arrow">↗</span>
      </button>
    </div>
  );
}
