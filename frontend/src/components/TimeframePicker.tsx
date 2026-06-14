import { useEffect, useRef, useState } from "react";

const TIMEFRAMES: { code: string; label: string }[] = [
  { code: "1m", label: "1 minute" },
  { code: "5m", label: "5 minutes" },
  { code: "15m", label: "15 minutes" },
  { code: "1h", label: "1 hour" },
  { code: "4h", label: "4 hours" },
  { code: "1d", label: "1 day" },
  { code: "1wk", label: "1 week" },
];

interface Props {
  tf: string;
  onSelect: (tf: string) => void;
}

export default function TimeframePicker({ tf, onSelect }: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const current = TIMEFRAMES.find((t) => t.code === tf);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  return (
    <div className="tf-picker" ref={rootRef}>
      <button className="tf-picker-btn" onClick={() => setOpen(!open)} title="Select timeframe">
        <span className="tf-picker-code">{tf}</span>
        <span className="tf-picker-label">{current?.label ?? ""}</span>
        <span className={open ? "chev up" : "chev"}>▾</span>
      </button>

      {open && (
        <div className="tf-picker-menu">
          {TIMEFRAMES.map((t) => (
            <button
              key={t.code}
              className={t.code === tf ? "tf-picker-item active" : "tf-picker-item"}
              onClick={() => {
                onSelect(t.code);
                setOpen(false);
              }}
            >
              <span className="tf-picker-item-code">{t.code}</span>
              <span className="tf-picker-item-label">{t.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
