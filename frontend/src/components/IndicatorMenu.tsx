import { useEffect, useRef, useState } from "react";
import type { IndicatorDetail } from "../types";
import type { useIndicators } from "../useIndicators";

const ARROWS = { up: "▲", down: "▼", neutral: "■" } as const;
const KIND_LABEL: Record<string, string> = { trend: "Trend", osc: "Oscillator", volume: "Volume" };

interface Props {
  indicators: IndicatorDetail[];
  overlayable: string[];
  ctrl: ReturnType<typeof useIndicators>;
  showForecastHist: boolean;
  onToggleForecastHist: (v: boolean) => void;
  showAvgLine: boolean;
  onToggleAvgLine: (v: boolean) => void;
  showPatterns: boolean;
  onTogglePatterns: (v: boolean) => void;
}

export default function IndicatorMenu({
  indicators, overlayable, ctrl, showForecastHist, onToggleForecastHist,
  showAvgLine, onToggleAvgLine, showPatterns, onTogglePatterns,
}: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const allNames = indicators.map((i) => i.name);
  const overlaySet = new Set(overlayable);
  const onCount = allNames.filter((n) => ctrl.get(n).on).length;

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const groups: Record<string, IndicatorDetail[]> = { trend: [], osc: [], volume: [] };
  for (const ind of indicators) groups[ind.kind ?? "trend"]?.push(ind);

  return (
    <div className="im" ref={rootRef}>
      <button className={open ? "im-btn open" : "im-btn"} onClick={() => setOpen(!open)}
        title="Turn indicators on/off, feed to AI, or draw on chart">
        <span className="im-icon">📊</span>
        <span className="im-label">Indicators</span>
        <span className="im-count">{onCount}/{allNames.length}</span>
        <span className={open ? "chev up" : "chev"}>▾</span>
      </button>

      {open && (
        <div className="im-menu">
          <label className="im-special">
            <span className="switch">
              <input type="checkbox" checked={showForecastHist}
                onChange={(e) => onToggleForecastHist(e.target.checked)} />
              <span className="slider" />
            </span>
            <span className="im-special-text">
              <b>Predicted candle history</b>
              <span className="im-special-sub">faint purple ghost candles show every past forecast over the real ones · correctness breakdown is in the Accuracy Report</span>
            </span>
          </label>

          <label className="im-special">
            <span className="switch">
              <input type="checkbox" checked={showAvgLine}
                onChange={(e) => onToggleAvgLine(e.target.checked)} />
              <span className="slider" />
            </span>
            <span className="im-special-text">
              <b>Average trend line</b>
              <span className="im-special-sub">🟡 yellow where the trend held · 🟣 purple where it broke (wrong-prediction branch) · 🟠 dashed orange = the predicted next line</span>
            </span>
          </label>

          <label className="im-special">
            <span className="switch">
              <input type="checkbox" checked={showPatterns}
                onChange={(e) => onTogglePatterns(e.target.checked)} />
              <span className="slider" />
            </span>
            <span className="im-special-text">
              <b>Patterns &amp; divergences</b>
              <span className="im-special-sub">candlestick patterns (engulfing, hammer, doji…) and RSI/MACD divergences, marked on the chart with a summary panel</span>
            </span>
          </label>

          <div className="im-bulk">
            <span>All:</span>
            <button className="mini-btn" onClick={() => ctrl.bulk(allNames, { on: true })}>on</button>
            <button className="mini-btn" onClick={() => ctrl.bulk(allNames, { on: false })}>off</button>
            <span className="im-bulk-sep">AI:</span>
            <button className="mini-btn" onClick={() => ctrl.bulk(allNames, { on: true, ai: true })}>all</button>
            <button className="mini-btn" onClick={() => ctrl.bulk(allNames, { ai: false })}>none</button>
            <span className="im-bulk-sep">Chart:</span>
            <button className="mini-btn" onClick={() => ctrl.bulk([...overlaySet], { on: true, chart: true })}>all</button>
            <button className="mini-btn" onClick={() => ctrl.bulk(allNames, { chart: false })}>none</button>
          </div>

          <div className="im-legend">
            <span>indicator</span>
            <span className="im-legend-toggles">
              <span title="On / off">on</span>
              <span title="Feed to AI">AI</span>
              <span title="Draw on chart">chart</span>
            </span>
          </div>

          <div className="im-scroll">
            {(["trend", "osc", "volume"] as const).map((kind) =>
              groups[kind].length === 0 ? null : (
                <div key={kind} className="im-group">
                  <div className="im-group-label">{KIND_LABEL[kind]}</div>
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
          </div>
        </div>
      )}
    </div>
  );
}
