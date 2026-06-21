import { useEffect, useRef, useState } from "react";
import type { AssetInfo } from "../types";

interface Cat {
  key: string;
  label: string;
  icon: string;
}

// display order + icons for the category step
const CATEGORIES: Cat[] = [
  { key: "crypto", label: "Crypto", icon: "🪙" },
  { key: "forex", label: "Forex", icon: "💱" },
  { key: "commodity", label: "Commodities", icon: "🛢️" },
  { key: "index", label: "Indices", icon: "📈" },
  { key: "stock", label: "Stocks", icon: "🏢" },
];
const CLASS_LABELS: Record<string, string> = Object.fromEntries(
  CATEGORIES.map((c) => [c.key, c.label]),
);

interface Props {
  assets: AssetInfo[];
  symbol: string;
  onSelect: (symbol: string) => void;
}

/** Two-step picker: choose a category, then the asset within it (with search).
 *  Smooth slide between the two panels. */
export default function AssetPicker({ assets, symbol, onSelect }: Props) {
  const [open, setOpen] = useState(false);
  const [cat, setCat] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  const current = assets.find((a) => a.symbol === symbol);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  // always start at the category step each time the menu opens
  useEffect(() => {
    if (open) {
      setCat(null);
      setQuery("");
    }
  }, [open]);

  // focus the search box when entering a category
  useEffect(() => {
    if (open && cat) searchRef.current?.focus();
  }, [open, cat]);

  const cats = CATEGORIES.filter((c) => assets.some((a) => a.asset_class === c.key));
  const inCat = cat ? assets.filter((a) => a.asset_class === cat) : [];
  const q = query.trim().toLowerCase();
  const filtered = q
    ? inCat.filter((a) => a.name.toLowerCase().includes(q) || a.symbol.toLowerCase().includes(q))
    : inCat;

  const choose = (s: string) => {
    onSelect(s);
    setOpen(false);
  };

  return (
    <div className="picker" ref={rootRef}>
      <button className="picker-btn" onClick={() => setOpen((o) => !o)}>
        <span className="picker-symbol">{current?.name ?? symbol}</span>
        <span className="picker-class">{CLASS_LABELS[current?.asset_class ?? ""] ?? ""}</span>
        <span className={open ? "chev up" : "chev"}>▾</span>
      </button>

      {open && (
        <div className="picker-menu">
          {!cat ? (
            <div className="picker-step">
              <div className="picker-step-title">Choose a market</div>
              {cats.map((c) => (
                <button key={c.key} className="picker-cat" onClick={() => setCat(c.key)}>
                  <span className="picker-cat-icon">{c.icon}</span>
                  <span className="picker-cat-name">{c.label}</span>
                  <span className="picker-count">
                    {assets.filter((a) => a.asset_class === c.key).length}
                  </span>
                  <span className="picker-cat-arrow">›</span>
                </button>
              ))}
            </div>
          ) : (
            <div className="picker-step">
              <div className="picker-step-head">
                <button className="picker-back" onClick={() => { setCat(null); setQuery(""); }}>
                  ‹ Back
                </button>
                <span className="picker-step-cat">
                  {CATEGORIES.find((c) => c.key === cat)?.icon} {CLASS_LABELS[cat]}
                </span>
              </div>
              <input
                ref={searchRef}
                className="picker-search"
                placeholder={`Search ${CLASS_LABELS[cat]}…`}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <div className="picker-list">
                {filtered.length === 0 ? (
                  <div className="picker-empty">No matches</div>
                ) : (
                  filtered.map((a) => (
                    <button
                      key={a.symbol}
                      className={a.symbol === symbol ? "picker-item active" : "picker-item"}
                      onClick={() => choose(a.symbol)}
                    >
                      <span>{a.name}</span>
                      <span className="picker-ticker">{a.symbol}</span>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
