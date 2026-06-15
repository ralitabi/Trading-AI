import type { VolProfileResponse } from "../types";
import CollapsiblePanel from "./CollapsiblePanel";

const fmt = (n: number) =>
  n >= 100 ? n.toLocaleString(undefined, { maximumFractionDigits: 2 }) : n.toFixed(5);

/**
 * Volume profile — how much traded at each price. The Point of Control (POC) is
 * the highest-volume price; the value area is where ~70% of volume changed hands.
 */
export default function VolumeProfile({ p }: { p: VolProfileResponse }) {
  const vp = p.profile;
  if (!vp) return null;
  const rows = [...vp.bins].reverse(); // highest price at the top
  return (
    <CollapsiblePanel title="Volume Profile">
      <div className="vp-rows">
        {rows.map((b, i) => {
          const w = vp.max_volume ? (b.volume / vp.max_volume) * 100 : 0;
          const isPoc = Math.abs(b.price - vp.poc) < 1e-9;
          const inVa = b.price >= vp.value_area_low && b.price <= vp.value_area_high;
          return (
            <div key={i} className={`vp-row${isPoc ? " poc" : ""}${inVa ? " va" : ""}`}>
              <span className="vp-price">{fmt(b.price)}</span>
              <span className="vp-bar"><span className="vp-fill" style={{ width: `${w}%` }} /></span>
            </div>
          );
        })}
      </div>
      <div className="vp-foot">
        <span><span className="vp-poc-dot" /> POC <b>{fmt(vp.poc)}</b></span>
        <span>Value area <b>{fmt(vp.value_area_low)}–{fmt(vp.value_area_high)}</b></span>
      </div>
    </CollapsiblePanel>
  );
}
