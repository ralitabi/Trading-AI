"""AI reasoning layer — digests indicators + news into a directional call.

Two providers supported, picked automatically (or forced via AI_PROVIDER):
  - Claude (Anthropic) — used when ANTHROPIC_API_KEY is set. JSON output is
    schema-enforced via structured outputs, so parsing can never fail.
  - OpenAI — used when only OPENAI_API_KEY is set.
Without any key the endpoint still works: it returns the technical signal
with a clear note that AI analysis is off. Responses are cached to keep cost
near zero.
"""
import json
import os

from data import cache
from engine import news

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")
AI_PROVIDER = os.environ.get("AI_PROVIDER", "auto")  # auto | claude | openai

_SYSTEM = """You are a professional market analyst engine inside a trading dashboard.
You receive technical indicator readings (with ADX trend-strength regime, higher-timeframe
trend, key support/resistance levels and an ATR-based trade plan) plus recent news headlines.
Respond ONLY with valid JSON, no markdown, matching exactly:
{
  "direction": "up" | "down" | "neutral",
  "confidence": <int 0-100, be conservative; >75 only with strong confluence>,
  "rationale": "<3-5 sentences, plain English, professional. Weigh trend regime (in a strong
    trend, overbought/oversold matters less), higher-timeframe alignment, proximity to
    support/resistance, and any headlines that plausibly move THIS asset>",
  "key_drivers": ["<driver 1>", "<driver 2>", "<driver 3>"],
  "risk_note": "<one sentence on the main risk, referencing a concrete level when relevant>"
}
Never claim certainty. If technicals and news conflict, or price sits right at a key level,
lower confidence and say so. Ignore headlines irrelevant to this asset."""

# Structured-output schema for Claude — guarantees valid, parseable JSON.
_CLAUDE_SCHEMA = {
    "type": "object",
    "properties": {
        "direction": {"type": "string", "enum": ["up", "down", "neutral"]},
        "confidence": {"type": "integer"},
        "rationale": {"type": "string"},
        "key_drivers": {"type": "array", "items": {"type": "string"}},
        "risk_note": {"type": "string"},
    },
    "required": ["direction", "confidence", "rationale", "key_drivers", "risk_note"],
    "additionalProperties": False,
}


def _provider() -> str | None:
    has_claude = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))
    if AI_PROVIDER == "claude":
        return "claude" if has_claude else None
    if AI_PROVIDER == "openai":
        return "openai" if has_openai else None
    # auto: prefer Claude when both keys are present
    if has_claude:
        return "claude"
    if has_openai:
        return "openai"
    return None


def _call_claude(user_msg: str) -> tuple[dict, str]:
    from anthropic import Anthropic

    client = Anthropic()
    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1000,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
        output_config={"format": {"type": "json_schema", "schema": _CLAUDE_SCHEMA}},
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("Claude declined this request")
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text), ANTHROPIC_MODEL


def _call_openai(user_msg: str) -> tuple[dict, str]:
    from openai import OpenAI

    client = OpenAI()
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user_msg}],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=500,
    )
    return json.loads(resp.choices[0].message.content), OPENAI_MODEL


def analyze(symbol: str, name: str, asset_class: str, tf: str, technical: dict, signal: dict) -> dict:
    key = f"ai:{symbol}:{tf}"
    cached = cache.get(key)
    if cached is not None:
        return {**cached, "cached": True}

    heads = news.headlines(asset_class)
    provider = _provider()
    if provider is None:
        return {
            "symbol": symbol, "tf": tf,
            "direction": signal["bias"], "confidence": signal["confidence"],
            "rationale": "AI analysis is offline (no ANTHROPIC_API_KEY or OPENAI_API_KEY set). "
                         "Showing the technical-indicator signal only: "
                         + f"{technical['votes']['up']} indicators bullish, {technical['votes']['down']} bearish, "
                         + f"{technical['votes']['neutral']} neutral.",
            "key_drivers": [f"{d['name']}: {d['note']}" for d in technical["details"][:3]],
            "risk_note": "Set an API key in backend/.env to enable news-aware AI reasoning.",
            "headlines_used": heads[:5], "model": "none", "cached": False,
        }

    user_msg = json.dumps({
        "asset": {"symbol": symbol, "name": name, "class": asset_class, "timeframe": tf,
                   "price": technical["price"]},
        "technical_signal": {"bias": signal["bias"], "confidence": signal["confidence"],
                              "votes": technical["votes"], "volatility": technical["volatility"],
                              "atr_pct": technical["atr_pct"],
                              "adx_trend_strength": f"{technical['trend_strength']} (ADX {technical['adx']})",
                              "higher_timeframe": technical.get("htf"),
                              "key_levels": {"support": technical["support"], "resistance": technical["resistance"]},
                              "atr_trade_plan": technical.get("plan"),
                              "next_candle_projection": technical.get("next_candle")},
        "indicators": technical["details"],
        "recent_headlines": heads,
    })

    try:
        if provider == "claude":
            data, model_used = _call_claude(user_msg)
        else:
            data, model_used = _call_openai(user_msg)
    except Exception:
        # failover: a bad key or outage on one provider must not kill analysis
        if provider == "claude" and os.environ.get("OPENAI_API_KEY"):
            data, model_used = _call_openai(user_msg)
        elif provider == "openai" and os.environ.get("ANTHROPIC_API_KEY"):
            data, model_used = _call_claude(user_msg)
        else:
            raise

    result = {
        "symbol": symbol, "tf": tf,
        "direction": data.get("direction", "neutral"),
        "confidence": int(data.get("confidence", 50)),
        "rationale": data.get("rationale", ""),
        "key_drivers": data.get("key_drivers", [])[:4],
        "risk_note": data.get("risk_note", ""),
        "headlines_used": heads[:5], "model": model_used, "cached": False,
    }
    # Cache AI calls: intraday 5 min, daily+ 30 min — keeps spend low.
    cache.put(key, result, ttl=300 if tf in ("1m", "5m", "15m", "1h") else 1800)
    return result
