"""Technical indicator engine.

Each indicator inspects the candle series and casts a vote: up / down / neutral.
Votes carry a `kind` tag — "trend" (followers), "osc" (oscillators / mean
reversion) or "volume" — so the scorer can weight them by market regime
(ADX) instead of naive counting, which double-counts correlated signals.
"""
import numpy as np
import pandas as pd

MIN_CANDLES = 35  # enough for MACD(26) + signal(9); below this, votes are garbage


def _df(candles: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(candles)


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def ema(close: pd.Series, period: int) -> pd.Series:
    return close.ewm(span=period, adjust=False).mean()


def macd(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    fast, slow = ema(close, 12), ema(close, 26)
    line = fast - slow
    signal = line.ewm(span=9, adjust=False).mean()
    return line, signal, line - signal


def bollinger(close: pd.Series, period: int = 20, mult: float = 2.0):
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    return mid + mult * std, mid, mid - mult * std


def _true_range(df: pd.DataFrame) -> pd.Series:
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"] - df["close"].shift()).abs()
    return pd.concat([hl, hc, lc], axis=1).max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    return _true_range(df).ewm(alpha=1 / period, min_periods=period).mean()


def stochastic(df: pd.DataFrame, period: int = 14, smooth_k: int = 3, smooth_d: int = 3):
    ll = df["low"].rolling(period).min()
    hh = df["high"].rolling(period).max()
    k_raw = 100 * (df["close"] - ll) / (hh - ll).replace(0, np.nan)
    k = k_raw.rolling(smooth_k).mean()
    d = k.rolling(smooth_d).mean()
    return k, d


def adx(df: pd.DataFrame, period: int = 14):
    """Average Directional Index — trend STRENGTH plus the +DI/-DI direction lines."""
    up = df["high"].diff()
    dn = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    atr_s = _true_range(df).ewm(alpha=1 / period, min_periods=period).mean()
    pdi = 100 * plus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr_s
    mdi = 100 * minus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr_s
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, min_periods=period).mean(), pdi, mdi


def williams_r(df: pd.DataFrame, period: int = 14) -> pd.Series:
    hh = df["high"].rolling(period).max()
    ll = df["low"].rolling(period).min()
    return -100 * (hh - df["close"]) / (hh - ll).replace(0, np.nan)


def cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    return (tp - sma) / (0.015 * mad.replace(0, np.nan))


def roc(close: pd.Series, period: int = 12) -> pd.Series:
    return (close / close.shift(period) - 1) * 100


def mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    flow = tp * df["volume"]
    pos = flow.where(tp > tp.shift(), 0.0).rolling(period).sum()
    neg = flow.where(tp < tp.shift(), 0.0).rolling(period).sum()
    ratio = pos / neg.replace(0, np.nan)
    return 100 - (100 / (1 + ratio))


def obv(df: pd.DataFrame) -> pd.Series:
    direction = np.sign(df["close"].diff()).fillna(0)
    return (direction * df["volume"]).cumsum()


def rolling_vwap(df: pd.DataFrame, period: int = 50) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    pv = (tp * df["volume"]).rolling(period).sum()
    v = df["volume"].rolling(period).sum().replace(0, np.nan)
    return pv / v


def parabolic_sar(df: pd.DataFrame, af_step: float = 0.02, af_max: float = 0.2) -> float:
    """Returns the current SAR value (classic Wilder algorithm)."""
    high, low = df["high"].to_numpy(), df["low"].to_numpy()
    rising = True
    sar, ep, af = low[0], high[0], af_step
    for i in range(1, len(high)):
        sar = sar + af * (ep - sar)
        if rising:
            sar = min(sar, low[i - 1], low[i - 2] if i >= 2 else low[i - 1])
            if low[i] < sar:
                rising, sar, ep, af = False, ep, low[i], af_step
            elif high[i] > ep:
                ep, af = high[i], min(af + af_step, af_max)
        else:
            sar = max(sar, high[i - 1], high[i - 2] if i >= 2 else high[i - 1])
            if high[i] > sar:
                rising, sar, ep, af = True, ep, high[i], af_step
            elif low[i] < ep:
                ep, af = low[i], min(af + af_step, af_max)
    return float(sar)


def supertrend(df: pd.DataFrame, period: int = 10, mult: float = 3.0):
    """Returns (trend_is_up: bool, line_value: float) for the latest bar."""
    atr_s = _true_range(df).ewm(alpha=1 / period, min_periods=period).mean()
    mid = (df["high"] + df["low"]) / 2
    upper = (mid + mult * atr_s).to_numpy()
    lower = (mid - mult * atr_s).to_numpy()
    close = df["close"].to_numpy()
    trend_up, line = True, lower[period]
    for i in range(period + 1, len(close)):
        if trend_up:
            line = max(line, lower[i]) if not np.isnan(lower[i]) else line
            if close[i] < line:
                trend_up, line = False, upper[i]
        else:
            line = min(line, upper[i]) if not np.isnan(upper[i]) else line
            if close[i] > line:
                trend_up, line = True, lower[i]
    return trend_up, float(line)


def ichimoku(df: pd.DataFrame):
    """Returns (tenkan, kijun, cloud_top, cloud_bottom) for the latest bar."""
    def midpoint(period: int, offset: int = 0) -> float:
        sl = df.iloc[len(df) - period - offset : len(df) - offset] if offset else df.tail(period)
        return float((sl["high"].max() + sl["low"].min()) / 2)

    tenkan = midpoint(9)
    kijun = midpoint(26)
    # cloud at the current bar was projected 26 bars ago
    senkou_a = (midpoint(9, 26) + midpoint(26, 26)) / 2
    senkou_b = midpoint(52, 26)
    return tenkan, kijun, max(senkou_a, senkou_b), min(senkou_a, senkou_b)


def swing_levels(df: pd.DataFrame, lookback: int = 120, wing: int = 3):
    """Nearest support below / resistance above current price, from swing points."""
    d = df.tail(lookback)
    h, lo = d["high"].to_numpy(), d["low"].to_numpy()
    price = float(d["close"].iloc[-1])
    highs = [h[i] for i in range(wing, len(d) - wing) if h[i] == h[i - wing : i + wing + 1].max()]
    lows = [lo[i] for i in range(wing, len(d) - wing) if lo[i] == lo[i - wing : i + wing + 1].min()]
    resistance = min((x for x in highs if x > price), default=None)
    support = max((x for x in lows if x < price), default=None)
    return (
        round(float(support), 6) if support is not None else None,
        round(float(resistance), 6) if resistance is not None else None,
    )


def trend_of(candles: list[dict]) -> str:
    """Coarse trend read for higher-timeframe confluence: up / down / neutral."""
    if len(candles) < 60:
        return "neutral"
    close = _df(candles)["close"]
    e9, e21, e50 = (float(ema(close, p).iloc[-1]) for p in (9, 21, 50))
    price = float(close.iloc[-1])
    if e9 > e21 and price > e50:
        return "up"
    if e9 < e21 and price < e50:
        return "down"
    return "neutral"


def _na(name: str, kind: str, reason: str) -> dict:
    """Placeholder for an indicator that can't be computed (insufficient data)."""
    return {"name": name, "value": "n/a", "vote": "neutral", "note": reason,
            "kind": kind, "available": False}


def analyze(candles: list[dict]) -> dict:
    """Run all indicators on a candle series and return votes + details.

    Every indicator ALWAYS appears in `details`; ones that lack data carry
    available=False so the UI can grey them out instead of silently dropping them.
    """
    if len(candles) < MIN_CANDLES:
        raise ValueError(
            f"Only {len(candles)} candles available (need {MIN_CANDLES}+). "
            "Market may be closed or just opened — try a longer timeframe."
        )
    df = _df(candles)
    close = df["close"]
    price = float(close.iloc[-1])
    details: list[dict] = []

    # --- RSI (momentum / mean reversion) ---
    r = rsi(close)
    r_now = float(r.iloc[-1])
    if np.isnan(r_now):  # zero losses in window → rs undefined → treat as maxed-out
        r_now = 100.0
    if r_now < 30:
        v, note = "up", "oversold — bounce likely"
    elif r_now > 70:
        v, note = "down", "overbought — pullback risk"
    elif r_now > 55:
        v, note = "up", "bullish momentum"
    elif r_now < 45:
        v, note = "down", "bearish momentum"
    else:
        v, note = "neutral", "no clear momentum"
    details.append({"name": "RSI(14)", "value": f"{r_now:.1f}", "vote": v, "note": note, "kind": "osc"})

    # --- Stochastic %K/%D (14,3,3) ---
    k, d = stochastic(df)
    k_now, d_now = float(k.iloc[-1]), float(d.iloc[-1])
    if not np.isnan(k_now) and not np.isnan(d_now):
        if k_now < 20:
            v, note = "up", "oversold zone"
        elif k_now > 80:
            v, note = "down", "overbought zone"
        elif k_now > d_now:
            v, note = "up", "%K above %D — upside pressure"
        else:
            v, note = "down", "%K below %D — downside pressure"
        details.append({"name": "Stoch(14,3)", "value": f"K {k_now:.0f} / D {d_now:.0f}", "vote": v, "note": note, "kind": "osc"})
    else:
        details.append(_na("Stoch(14,3)", "osc", "warming up — needs more bars"))

    # --- MACD (trend momentum) ---
    line, sig, hist = macd(close)
    h_now, h_prev = float(hist.iloc[-1]), float(hist.iloc[-2])
    if h_now > 0 and h_prev <= 0:
        v, note = "up", "fresh bullish cross"
    elif h_now < 0 and h_prev >= 0:
        v, note = "down", "fresh bearish cross"
    elif h_now > 0:
        v, note = ("up", "bullish, momentum building") if h_now > h_prev else ("neutral", "bullish but fading")
    else:
        v, note = ("down", "bearish, momentum building") if h_now < h_prev else ("neutral", "bearish but fading")
    details.append({"name": "MACD", "value": f"{h_now:+.4g}", "vote": v, "note": note, "kind": "trend"})

    # --- EMA trend (9 vs 21) ---
    e9, e21 = float(ema(close, 9).iloc[-1]), float(ema(close, 21).iloc[-1])
    spread_pct = (e9 - e21) / e21 * 100
    if spread_pct > 0.05:
        v, note = "up", "short-term trend above long-term"
    elif spread_pct < -0.05:
        v, note = "down", "short-term trend below long-term"
    else:
        v, note = "neutral", "trend lines flat / crossing"
    details.append({"name": "EMA 9/21", "value": f"{spread_pct:+.2f}%", "vote": v, "note": note, "kind": "trend"})

    # --- EMA 50/200 (major trend, when we have enough bars) ---
    if len(close) >= 200:
        e50, e200 = float(ema(close, 50).iloc[-1]), float(ema(close, 200).iloc[-1])
        if e50 > e200 and price > e50:
            v, note = "up", "price above rising long-term trend"
        elif e50 < e200 and price < e50:
            v, note = "down", "price below falling long-term trend"
        else:
            v, note = "neutral", "mixed long-term trend"
        details.append({"name": "EMA 50/200", "value": f"{(e50 - e200) / e200 * 100:+.2f}%", "vote": v, "note": note, "kind": "trend"})
    else:
        details.append(_na("EMA 50/200", "trend", f"needs 200 bars ({len(close)} available)"))

    # --- Bollinger position ---
    upper, mid, lower = bollinger(close)
    u, lo_b = float(upper.iloc[-1]), float(lower.iloc[-1])
    width = max(u - lo_b, 1e-12)
    pos = (price - lo_b) / width  # 0 = lower band, 1 = upper band
    if pos < 0.1:
        v, note = "up", "hugging lower band — stretched down"
    elif pos > 0.9:
        v, note = "down", "hugging upper band — stretched up"
    elif pos > 0.6:
        v, note = "up", "trading in upper half"
    elif pos < 0.4:
        v, note = "down", "trading in lower half"
    else:
        v, note = "neutral", "mid-band"
    details.append({"name": "Bollinger", "value": f"{pos * 100:.0f}% of band", "vote": v, "note": note, "kind": "osc"})

    # --- Williams %R (14) ---
    wr = float(williams_r(df).iloc[-1])
    if not np.isnan(wr):
        if wr < -80:
            v, note = "up", "deeply oversold"
        elif wr > -20:
            v, note = "down", "deeply overbought"
        else:
            v, note = "neutral", "mid-range"
        details.append({"name": "Williams %R", "value": f"{wr:.0f}", "vote": v, "note": note, "kind": "osc"})
    else:
        details.append(_na("Williams %R", "osc", "warming up — needs more bars"))

    # --- CCI (20) ---
    cci_now = float(cci(df).iloc[-1])
    if not np.isnan(cci_now):
        if cci_now > 100:
            v, note = "up", "strong upward deviation"
        elif cci_now < -100:
            v, note = "down", "strong downward deviation"
        else:
            v, note = "neutral", "within normal range"
        details.append({"name": "CCI(20)", "value": f"{cci_now:.0f}", "vote": v, "note": note, "kind": "osc"})
    else:
        details.append(_na("CCI(20)", "osc", "warming up — needs more bars"))

    # --- ROC momentum, scaled against the asset's own volatility ---
    a_tmp = atr(df)
    atr_pct_tmp = float(a_tmp.iloc[-1]) / price * 100 if not np.isnan(a_tmp.iloc[-1]) and price else 0.0
    roc_now = float(roc(close).iloc[-1])
    if not np.isnan(roc_now) and atr_pct_tmp > 0:
        if roc_now > atr_pct_tmp:
            v, note = "up", "momentum above normal volatility"
        elif roc_now < -atr_pct_tmp:
            v, note = "down", "momentum below normal volatility"
        else:
            v, note = "neutral", "momentum within noise"
        details.append({"name": "ROC(12)", "value": f"{roc_now:+.2f}%", "vote": v, "note": note, "kind": "trend"})
    else:
        details.append(_na("ROC(12)", "trend", "warming up — needs more bars"))

    # --- Parabolic SAR ---
    psar = parabolic_sar(df.tail(120))
    if price > psar:
        v, note = "up", "price above SAR — uptrend intact"
    else:
        v, note = "down", "price below SAR — downtrend intact"
    details.append({"name": "PSAR", "value": f"{psar:.6g}", "vote": v, "note": note, "kind": "trend"})

    # --- SuperTrend (10, 3) ---
    st_up, st_line = supertrend(df)
    v, note = ("up", "price above SuperTrend line") if st_up else ("down", "price below SuperTrend line")
    details.append({"name": "SuperTrend", "value": f"{st_line:.6g}", "vote": v, "note": note, "kind": "trend"})

    # --- DMI: +DI vs -DI (directional movement) ---
    a_dx_series, pdi_s, mdi_s = adx(df)
    pdi_now, mdi_now = float(pdi_s.iloc[-1]), float(mdi_s.iloc[-1])
    if not np.isnan(pdi_now) and not np.isnan(mdi_now):
        if pdi_now > mdi_now * 1.1:
            v, note = "up", "bullish directional movement dominates"
        elif mdi_now > pdi_now * 1.1:
            v, note = "down", "bearish directional movement dominates"
        else:
            v, note = "neutral", "directional movement balanced"
        details.append({"name": "DMI +/-", "value": f"{pdi_now:.0f}/{mdi_now:.0f}", "vote": v, "note": note, "kind": "trend"})
    else:
        details.append(_na("DMI +/-", "trend", "warming up — needs more bars"))

    # --- Ichimoku (needs 78+ bars: 52 lookback + 26 cloud shift) ---
    if len(df) >= 78:
        tenkan, kijun, cloud_top, cloud_bot = ichimoku(df)
        if price > cloud_top and tenkan > kijun:
            v, note = "up", "above cloud, Tenkan over Kijun"
        elif price < cloud_bot and tenkan < kijun:
            v, note = "down", "below cloud, Tenkan under Kijun"
        else:
            v, note = "neutral", "inside or fighting the cloud"
        details.append({"name": "Ichimoku", "value": f"T {tenkan:.6g} / K {kijun:.6g}", "vote": v, "note": note, "kind": "trend"})
    else:
        details.append(_na("Ichimoku", "trend", f"needs 78 bars ({len(df)} available)"))

    # --- Volume indicators (only if the asset reports volume; forex has none) ---
    vol = df["volume"]
    has_volume = float(vol.tail(20).sum()) > 0
    if has_volume:
        v_recent = float(vol.tail(5).mean())
        v_base = float(vol.tail(20).mean())
        ratio = v_recent / v_base if v_base else 1.0
        price_dir = "up" if close.iloc[-1] > close.iloc[-6] else "down"
        if ratio > 1.3:
            v, note = price_dir, f"rising volume confirms {price_dir} move"
        elif ratio < 0.7:
            v, note = "neutral", "volume drying up — weak conviction"
        else:
            v, note = "neutral", "average volume"
        details.append({"name": "Volume", "value": f"{ratio:.2f}x avg", "vote": v, "note": note, "kind": "volume"})

        # --- MFI: volume-weighted RSI ---
        mfi_now = float(mfi(df).iloc[-1])
        if not np.isnan(mfi_now):
            if mfi_now < 20:
                v, note = "up", "money flow oversold"
            elif mfi_now > 80:
                v, note = "down", "money flow overbought"
            elif mfi_now > 55:
                v, note = "up", "money flowing in"
            elif mfi_now < 45:
                v, note = "down", "money flowing out"
            else:
                v, note = "neutral", "balanced money flow"
            details.append({"name": "MFI(14)", "value": f"{mfi_now:.0f}", "vote": v, "note": note, "kind": "volume"})

        # --- OBV vs its own trend ---
        obv_s = obv(df)
        obv_ema = obv_s.ewm(span=20, adjust=False).mean()
        if obv_s.iloc[-1] > obv_ema.iloc[-1]:
            v, note = "up", "accumulation — OBV above its trend"
        else:
            v, note = "down", "distribution — OBV below its trend"
        details.append({"name": "OBV", "value": "rising" if v == "up" else "falling", "vote": v, "note": note, "kind": "volume"})

        # --- Rolling VWAP(50) position ---
        vwap_now = float(rolling_vwap(df).iloc[-1])
        if not np.isnan(vwap_now):
            dev = (price - vwap_now) / vwap_now * 100
            if dev > 0.05:
                v, note = "up", "trading above volume-weighted average"
            elif dev < -0.05:
                v, note = "down", "trading below volume-weighted average"
            else:
                v, note = "neutral", "at volume-weighted average"
            details.append({"name": "VWAP(50)", "value": f"{dev:+.2f}%", "vote": v, "note": note, "kind": "volume"})
        else:
            details.append(_na("VWAP(50)", "volume", "warming up — needs more bars"))
    else:
        for nm in ("Volume", "MFI(14)", "OBV", "VWAP(50)"):
            details.append(_na(nm, "volume", "no volume data for this asset (e.g. spot forex)"))

    # --- ADX: trend strength — context for the scorer, not a directional vote ---
    adx_now = float(a_dx_series.iloc[-1]) if not np.isnan(a_dx_series.iloc[-1]) else 0.0
    trend_strength = "strong" if adx_now >= 25 else "weak" if adx_now < 20 else "moderate"

    # --- ATR volatility flag (informs risk, not direction) ---
    a = atr(df)
    atr_abs = float(a.iloc[-1]) if not np.isnan(a.iloc[-1]) else 0.0
    atr_pct = atr_abs / price * 100 if price else 0.0
    volatility = "low" if atr_pct < 0.5 else "moderate" if atr_pct < 1.5 else "high"

    # --- Nearest support / resistance from swing points ---
    support, resistance = swing_levels(df)

    live = [d_ for d_ in details if d_.get("available", True)]
    votes = {
        "up": sum(1 for d_ in live if d_["vote"] == "up"),
        "down": sum(1 for d_ in live if d_["vote"] == "down"),
        "neutral": sum(1 for d_ in live if d_["vote"] == "neutral"),
    }
    return {
        "votes": votes,
        "details": details,
        "volatility": volatility,
        "atr_pct": round(atr_pct, 3),
        "atr_abs": atr_abs,
        "adx": round(adx_now, 1),
        "trend_strength": trend_strength,
        "support": support,
        "resistance": resistance,
        "price": price,
    }
