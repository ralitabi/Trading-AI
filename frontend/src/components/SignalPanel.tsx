import type { SignalData } from "../types";

const ARROWS = { up: "↑", down: "↓", neutral: "→" } as const;
const RING_COLOR = { up: "#26a69a", down: "#ef5350", neutral: "#f0b90b" } as const;

function ConfidenceRing({ pct, bias }: { pct: number; bias: "up" | "down" | "neutral" }) {
  const r = 30;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - pct / 100);
  return (
    <div className="conf-ring">
      <svg width="76" height="76" viewBox="0 0 76 76">
        <circle cx="38" cy="38" r={r} fill="none" stroke="rgba(140,150,170,0.14)" strokeWidth="6" />
        <circle
          cx="38" cy="38" r={r} fill="none" stroke={RING_COLOR[bias]} strokeWidth="6"
          strokeLinecap="round" strokeDasharray={c} strokeDashoffset={offset}
          transform="rotate(-90 38 38)" style={{ transition: "stroke-dashoffset 0.5s ease" }}
        />
      </svg>
      <div className="conf-ring-text">
        <span className="conf-ring-pct">{pct}%</span>
        <span className="conf-ring-label">Confidence</span>
      </div>
    </div>
  );
}

export default function SignalPanel({ s }: { s: SignalData }) {
  const total = s.votes.up + s.votes.down + s.votes.neutral;
  return (
    <div className="panel sig-panel">
      <div className="panel-title">
        Technical Signal
        <span className="live-tag">● Live</span>
      </div>

      <div className="sig-main">
        <div className={`sig-bias bias-${s.bias}`}>
          <div className="sig-arrow-circle">
            <span className="sig-arrow">{ARROWS[s.bias]}</span>
          </div>
          <div className="sig-bias-text">
            <span className="sig-label">{s.bias === "neutral" ? "NO EDGE" : s.bias.toUpperCase()}</span>
            <div className="conf-bar">
              <div className={`conf-fill conf-${s.bias}`} style={{ width: `${s.confidence}%` }} />
            </div>
          </div>
        </div>
        <ConfidenceRing pct={s.confidence} bias={s.bias} />
      </div>

      <div className="chips">
        {s.htf?.trend && (
          <span className={`chip ${s.htf.note?.includes("AGAINST") ? "chip-warn" : "chip-ok"}`}>
            {s.htf.tf} Trend: {s.htf.trend.toUpperCase()}
            {s.htf.note ? (s.htf.note.includes("AGAINST") ? " ✕ Against" : " / Aligned") : ""}
          </span>
        )}
        <span className={`chip chip-${s.trend_strength}`}>
          {s.trend_strength} Trend · ADX {s.adx}
        </span>
      </div>

      <div className="vote-boxes">
        <div className="vbox vbox-up">
          <span className="vbox-num">{s.votes.up}</span>
          <span className="vbox-lbl">Bullish</span>
        </div>
        <div className="vbox vbox-neutral">
          <span className="vbox-num">{s.votes.neutral}</span>
          <span className="vbox-lbl">Neutral</span>
        </div>
        <div className="vbox vbox-down">
          <span className="vbox-num">{s.votes.down}</span>
          <span className="vbox-lbl">Bearish</span>
        </div>
      </div>

      <div className={`vol-flag vol-${s.volatility}`}>
        Volatility: <b>{s.volatility}</b> (ATR {s.atr_pct}%)
        {total > 0 && <span className="vol-count"> · {total} indicators voting</span>}
      </div>
    </div>
  );
}
