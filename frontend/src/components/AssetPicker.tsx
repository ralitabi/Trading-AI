import { useEffect, useRef, useState } from "react";
import type { AssetInfo } from "../types";

const CLASS_LABELS: Record<string, string> = {
  crypto: "Crypto",
  forex: "Forex",
  commodity: "Commodities",
  index: "Indices",
};

interface Props {
  assets: AssetInfo[];
  symbol: string;
  onSelect: (symbol: string) => void;
}

export default function AssetPicker({ assets, symbol, onSelect }: Props) {
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const rootRef = useRef<HTMLDivElement>(null);

  const current = assets.find((a) => a.symbol === symbol);

  // close when clicking anywhere outside the picker
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const toggleGroup = (cls: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(cls)) next.delete(cls);
      else next.add(cls);
      return next;
    });

  const groups = Object.keys(CLASS_LABELS).filter((cls) =>
    assets.some((a) => a.asset_class === cls),
  );

  return (
    <div className="picker" ref={rootRef}>
      <button className="picker-btn" onClick={() => setOpen(!open)}>
        <span className="picker-symbol">{current?.name ?? symbol}</span>
        <span className="picker-class">{CLASS_LABELS[current?.asset_class ?? ""] ?? ""}</span>
        <span className={open ? "chev up" : "chev"}>▾</span>
      </button>

      {open && (
        <div className="picker-menu">
          {groups.map((cls) => {
            const isCollapsed = collapsed.has(cls);
            const items = assets.filter((a) => a.asset_class === cls);
            return (
              <div key={cls} className="picker-group">
                <button className="picker-group-head" onClick={() => toggleGroup(cls)}>
                  <span>{CLASS_LABELS[cls]}</span>
                  <span className="picker-count">{items.length}</span>
                  <span className={isCollapsed ? "chev" : "chev up"}>▾</span>
                </button>
                {!isCollapsed &&
                  items.map((a) => (
                    <button
                      key={a.symbol}
                      className={a.symbol === symbol ? "picker-item active" : "picker-item"}
                      onClick={() => {
                        onSelect(a.symbol);
                        setOpen(false);
                      }}
                    >
                      <span>{a.name}</span>
                      <span className="picker-ticker">{a.symbol}</span>
                    </button>
                  ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
