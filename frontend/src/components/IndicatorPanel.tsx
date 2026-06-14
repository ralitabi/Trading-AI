import { useState } from "react";
import type { IndicatorDetail } from "../types";
import type { useIndicators } from "../useIndicators";

const ARROWS = { up: "▲", down: "▼", neutral: "■" } as const;

interface Props {
  indicators: IndicatorDetail[];
  overlayable: string[];
  ctrl: ReturnType<typeof useIndicators>;
}

const KIND_LABEL: Record<string, string> = { trend: "Trend", osc: "Oscillator", volume: "Volume" };

export default function IndicatorPanel({ indicators, overlayable, ctrl }: Props) {
  const [open, setOpen] = useState(true);
  const allNames = indicators.map((i) => i.name);
  const overlaySet = new Set(overlayable);

  // group by kind for a terminal-like layout
  const groups: Record<string, IndicatorDetail[]> = { trend: [], osc: [], volume: [] };
  for (const ind of indicators) groups[ind.kind ?? "trend"]?.push(ind);

  return (
    <div className="panel ind-panel">
      <button className="ind-panel-head" onClick={() => setOpen(!open)}>
        <span className="panel-title-inline">Indicators</span>
        <span className="ind-count">{allNames.length}</span>
        <span className={open ? "chev up" : "chev"}>▾</span>
      </button>

      {open && (
        <>
          <div className="ind-bulk">
            <span className="ind-bulk-label">All:</span>
            <button className="mini-btn" onClick={() => ctrl.bulk(allNames, { on: true })}>on</button>
            <button className="mini-btn" onClick={() => ctrl.bulk(allNames, { on: false })}>off</button>
            <span className="ind-bulk-sep">AI:</span>
            <button className="mini-btn" onClick={() => ctrl.bulk(allNames, { on: true, ai: true })}>all</button>
            <button className="mini-btn" onClick={() => ctrl.bulk(allNames, { ai: false })}>none</button>
            <span className="ind-bulk-sep">Chart:</span>
            <button className="mini-btn" onClick={() => ctrl.bulk([...overlaySet], { on: true, chart: true })}>all</button>
            <button className="mini-btn" onClick={() => ctrl.bulk(allNames, { chart: false })}>none</button>
          </div>

          <div className="ind-legend">
            <span>indicator</span>
            <span className="ind-legend-toggles">
              <span title="Include in the signal & AI weighting">on</span>
              <span title="Feed this indicator to the AI analysis">AI</span>
              <span title="Draw this indicator on the price chart">chart</span>
            </span>
          </div>

          {(["trend", "osc", "volume"] as const).map((kind) =>
            groups[kind].length === 0 ? null : (
              <div key={kind} className="ind-group">
                <div className="ind-group-label">{KIND_LABEL[kind]}</div>
                {groups[kind].map((ind) => {
                  const s = ctrl.get(ind.name);
                  const na = ind.available === false;
                  const canChart = overlaySet.has(ind.name);
                  return (
                    <div key={ind.name} className={`ind-row ${s.on && !na ? "" : "ind-off"} ${na ? "ind-na" : ""}`}>
                      <label className="switch" title={s.on ? "On" : "Off"}>
                        <input type="checkbox" checked={s.on} disabled={na}
                          onChange={(e) => ctrl.set(ind.name, { on: e.target.checked })} />
                        <span className="slider" />
                      </label>
                      <span className="ind-row-name">{ind.name}</span>
                      <span className="ind-row-value">{ind.value}</span>
                      <span className={`ind-row-vote vote-${na ? "neutral" : ind.vote}`}>
                        {na ? "–" : ARROWS[ind.vote]}
                      </span>
                      <input type="checkbox" className="cb cb-ai" title="Feed to AI"
                        checked={s.ai} disabled={!s.on || na}
                        onChange={(e) => ctrl.set(ind.name, { ai: e.target.checked })} />
                      <input type="checkbox" className="cb cb-chart"
                        title={canChart ? "Show on chart" : "Oscillator — not a price overlay"}
                        checked={s.chart} disabled={!s.on || na || !canChart}
                        onChange={(e) => ctrl.set(ind.name, { chart: e.target.checked })} />
                    </div>
                  );
                })}
              </div>
            ),
          )}
        </>
      )}
    </div>
  );
}
