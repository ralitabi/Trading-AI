import type { Prediction } from "../types";

const ARROWS = { up: "▲", down: "▼", neutral: "■" } as const;

export default function AICard({ p }: { p: Prediction }) {
  const ai = p.ai;
  const offline = ai.model === "none" || ai.model === "error";
  return (
    <div className="panel" id="ai-analysis-card">
      <div className="panel-title">
        AI Analysis
        <span className="ai-model">{offline ? "offline" : ai.model + (ai.cached ? " · cached" : "")}</span>
      </div>

      <div className={`bias bias-${ai.direction}`}>
        <span className="bias-arrow">{ARROWS[ai.direction]}</span>
        <span className="bias-label">{ai.direction === "neutral" ? "NO EDGE" : ai.direction.toUpperCase()}</span>
        <span className="bias-conf">{ai.confidence}%</span>
      </div>

      <p className="rationale">{ai.rationale}</p>

      {ai.key_drivers.length > 0 && (
        <ul className="drivers">
          {ai.key_drivers.map((d, i) => (
            <li key={i}>{d}</li>
          ))}
        </ul>
      )}

      {ai.risk_note && <div className="risk-note">⚠ {ai.risk_note}</div>}

      {ai.headlines_used.length > 0 && (
        <details className="headlines">
          <summary>News considered ({ai.headlines_used.length})</summary>
          <ul>
            {ai.headlines_used.map((h, i) => (
              <li key={i}>{h}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
