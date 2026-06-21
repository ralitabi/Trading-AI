import { useMemo } from "react";
import type { IndicatorDetail } from "../types";

/** Indicator board strip shown directly below the price chart — a stacked
 *  bullish / neutral / bearish sentiment bar + counts + the names in each group.
 *  Mirrors the board on the Telegram signal image, live in the product. */
export default function IndicatorBar({ indicators }: { indicators: IndicatorDetail[] }) {
  const { up, neu, down, total, lean } = useMemo(() => {
    const avail = indicators.filter((i) => i.available !== false);
    const up = avail.filter((i) => i.vote === "up");
    const down = avail.filter((i) => i.vote === "down");
    const neu = avail.filter((i) => i.vote === "neutral");
    const total = avail.length || 1;
    const diff = up.length - down.length;
    const lean =
      diff >= 3 ? "Leaning bullish" : diff <= -3 ? "Leaning bearish"
        : diff > 0 ? "Slightly bullish" : diff < 0 ? "Slightly bearish" : "Mixed / no edge";
    return { up, neu, down, total, lean };
  }, [indicators]);

  if (!indicators.length) return null;
  const pct = (n: number) => `${(n / total) * 100}%`;

  return (
    <div className="indbar">
      <div className="indbar-head">
        <span className="indbar-title">Indicator board · {up.length + neu.length + down.length} active</span>
        <span className="indbar-lean">{lean}</span>
      </div>

      <div className="indbar-track" role="img"
        aria-label={`${up.length} bullish, ${neu.length} neutral, ${down.length} bearish`}>
        {up.length > 0 && <span className="indbar-seg up" style={{ width: pct(up.length) }}>{up.length}</span>}
        {neu.length > 0 && <span className="indbar-seg neu" style={{ width: pct(neu.length) }}>{neu.length}</span>}
        {down.length > 0 && <span className="indbar-seg down" style={{ width: pct(down.length) }}>{down.length}</span>}
      </div>

      <div className="indbar-groups">
        <div className="indbar-group">
          <span className="indbar-tag up">▲ Bullish · {up.length}</span>
          <span className="indbar-names">{up.map((i) => i.name).join("  ·  ") || "—"}</span>
        </div>
        <div className="indbar-group">
          <span className="indbar-tag neu">■ Neutral · {neu.length}</span>
          <span className="indbar-names">{neu.map((i) => i.name).join("  ·  ") || "—"}</span>
        </div>
        <div className="indbar-group">
          <span className="indbar-tag down">▼ Bearish · {down.length}</span>
          <span className="indbar-names">{down.map((i) => i.name).join("  ·  ") || "—"}</span>
        </div>
      </div>
    </div>
  );
}
