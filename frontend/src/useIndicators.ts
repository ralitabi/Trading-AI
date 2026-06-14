import { useCallback, useEffect, useState } from "react";

export interface IndicatorSetting {
  on: boolean; // master: participates at all
  ai: boolean; // feed this indicator to the AI analysis
  chart: boolean; // overlay this indicator on the price chart
}

export type IndicatorSettings = Record<string, IndicatorSetting>;

const KEY = "trend-indicator-settings-v1";
const DEFAULT: IndicatorSetting = { on: true, ai: true, chart: false };

function load(): IndicatorSettings {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "{}");
  } catch {
    return {};
  }
}

export function useIndicators() {
  const [settings, setSettings] = useState<IndicatorSettings>(load);

  useEffect(() => {
    localStorage.setItem(KEY, JSON.stringify(settings));
  }, [settings]);

  const get = useCallback(
    (name: string): IndicatorSetting => settings[name] ?? DEFAULT,
    [settings],
  );

  const set = useCallback((name: string, patch: Partial<IndicatorSetting>) => {
    setSettings((prev) => {
      const cur = prev[name] ?? DEFAULT;
      const next = { ...cur, ...patch };
      // master off ⇒ nothing feeds AI or chart
      if (patch.on === false) {
        next.ai = false;
        next.chart = false;
      }
      return { ...prev, [name]: next };
    });
  }, []);

  const bulk = useCallback((names: string[], patch: Partial<IndicatorSetting>) => {
    setSettings((prev) => {
      const next = { ...prev };
      for (const n of names) {
        const cur = next[n] ?? DEFAULT;
        const merged = { ...cur, ...patch };
        if (patch.on === false) {
          merged.ai = false;
          merged.chart = false;
        }
        next[n] = merged;
      }
      return next;
    });
  }, []);

  return { get, set, bulk };
}
