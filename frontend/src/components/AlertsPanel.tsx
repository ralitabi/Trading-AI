import { useCallback, useEffect, useRef, useState } from "react";
import { fetchNotifyConfig, postNotify } from "../api";

interface Props {
  symbol: string;
  tf: string;
  name: string;
  bias: "up" | "down" | "neutral";
  price: number | null;
}

interface PriceTarget {
  symbol: string;
  value: number;
  dir: "above" | "below";
}

const BIAS_WORD: Record<string, string> = { up: "bullish ▲", down: "bearish ▼", neutral: "no edge" };

function showNotification(title: string, body: string) {
  if (typeof Notification === "undefined" || Notification.permission !== "granted") return;
  try {
    new Notification(title, { body, icon: "/logo-mark-dark.jpeg", tag: title });
  } catch {
    /* some browsers throw on construct (e.g. requires a service worker) */
  }
}

/** Signal-flip + price-cross alerts. The browser is the always-on channel
 *  (native notifications); when the server has Telegram/Discord configured the
 *  same alert is relayed there too. State is entirely client-side + persisted. */
export default function AlertsPanel({ symbol, tf, name, bias, price }: Props) {
  const [enabled, setEnabled] = useState(() => localStorage.getItem("trend-alerts-on") === "true");
  const [perm, setPerm] = useState<NotificationPermission>(
    typeof Notification !== "undefined" ? Notification.permission : "denied",
  );
  const [channels, setChannels] = useState<string[]>([]);
  const [target, setTarget] = useState<PriceTarget | null>(() => {
    try {
      return JSON.parse(localStorage.getItem("trend-alert-price") || "null");
    } catch {
      return null;
    }
  });
  const [priceInput, setPriceInput] = useState("");
  const [priceDir, setPriceDir] = useState<"above" | "below">("above");
  const [lastFired, setLastFired] = useState<string>("");

  useEffect(() => {
    localStorage.setItem("trend-alerts-on", String(enabled));
  }, [enabled]);
  useEffect(() => {
    if (target) localStorage.setItem("trend-alert-price", JSON.stringify(target));
    else localStorage.removeItem("trend-alert-price");
  }, [target]);
  useEffect(() => {
    fetchNotifyConfig().then((c) => setChannels(c.channels)).catch(() => {});
  }, []);

  const fire = useCallback((title: string, message: string) => {
    showNotification(title, message);
    postNotify(title, message); // fire-and-forget relay; no-op if no channels
    setLastFired(new Date().toLocaleTimeString());
  }, []);

  // Signal-flip alert — fire when the committed direction changes to up/down.
  const prevRef = useRef<{ key: string; bias: string } | null>(null);
  useEffect(() => {
    const key = `${symbol}|${tf}`;
    const prev = prevRef.current;
    prevRef.current = { key, bias };
    if (!prev || prev.key !== key) return; // new market/timeframe → set baseline only
    if (enabled && bias !== prev.bias && (bias === "up" || bias === "down")) {
      fire(
        `${name} ${tf} → ${bias.toUpperCase()}`,
        `Signal flipped ${BIAS_WORD[bias]}${price != null ? ` · ${price}` : ""}`,
      );
    }
  }, [bias, symbol, tf, enabled, name, price, fire]);

  // Price-cross alert — fire once when price reaches the target, then clear it.
  useEffect(() => {
    if (!enabled || price == null || !target || target.symbol !== symbol) return;
    const hit = target.dir === "above" ? price >= target.value : price <= target.value;
    if (hit) {
      fire(
        `${name} price ${target.dir} ${target.value}`,
        `${symbol} is now ${price} (target ${target.dir} ${target.value})`,
      );
      setTarget(null);
    }
  }, [price, enabled, target, symbol, name, fire]);

  const toggle = useCallback(async () => {
    if (!enabled) {
      if (typeof Notification !== "undefined" && Notification.permission === "default") {
        try {
          setPerm(await Notification.requestPermission());
        } catch {
          /* ignore */
        }
      }
      setEnabled(true);
    } else {
      setEnabled(false);
    }
  }, [enabled]);

  const setPriceAlert = () => {
    const v = parseFloat(priceInput);
    if (!Number.isFinite(v)) return;
    setTarget({ symbol, value: v, dir: priceDir });
    setPriceInput("");
  };

  const blocked = perm === "denied";
  return (
    <div className="panel alerts-panel">
      <div className="alerts-head">
        <span className="panel-title-inline">🔔 Alerts</span>
        <button
          className={`switch-btn${enabled ? " on" : ""}`}
          onClick={toggle}
          role="switch"
          aria-checked={enabled}
          title={enabled ? "Alerts on — click to turn off" : "Turn alerts on"}
        >
          <span className="switch-knob" />
        </button>
      </div>

      <div className="alerts-status">
        {blocked ? (
          <span className="alerts-warn">Browser notifications blocked — allow them in site settings.</span>
        ) : enabled ? (
          <span>
            Watching <b>{name} {tf}</b> for signal flips.{" "}
            {channels.length > 0 ? (
              <>Also relaying to <b>{channels.join(" + ")}</b>.</>
            ) : (
              <>Browser notifications only.</>
            )}
          </span>
        ) : (
          <span className="alerts-dim">Off — turn on to get notified when the signal flips or price hits a level.</span>
        )}
      </div>

      <div className="alerts-price">
        <label className="alerts-label">Price alert</label>
        {target && target.symbol === symbol ? (
          <div className="alerts-active">
            <span>
              Notify when <b>{symbol}</b> {target.dir === "above" ? "≥" : "≤"} <b>{target.value}</b>
            </span>
            <button className="alerts-clear" title="Clear price alert" onClick={() => setTarget(null)}>✕</button>
          </div>
        ) : (
          <div className="alerts-row">
            <select className="alerts-select" value={priceDir} onChange={(e) => setPriceDir(e.target.value as "above" | "below")}>
              <option value="above">crosses above</option>
              <option value="below">crosses below</option>
            </select>
            <input
              className="alerts-input"
              type="number"
              inputMode="decimal"
              placeholder={price != null ? String(price) : "price"}
              value={priceInput}
              onChange={(e) => setPriceInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && setPriceAlert()}
            />
            <button className="alerts-set" onClick={setPriceAlert} disabled={!priceInput}>Set</button>
          </div>
        )}
      </div>

      <div className="alerts-foot">
        <button
          className="alerts-test"
          onClick={() => fire(`${name} ${tf} · test alert`, "Alerts are working ✓")}
          disabled={!enabled}
        >
          Send test alert
        </button>
        {lastFired && <span className="alerts-dim">last fired {lastFired}</span>}
      </div>
    </div>
  );
}
