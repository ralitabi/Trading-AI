"""Pydantic response models — the JSON contract between backend and React UI."""
from typing import Literal, Optional
from pydantic import BaseModel


class Candle(BaseModel):
    time: int  # unix seconds (UTC)
    open: float
    high: float
    low: float
    close: float
    volume: float


class CandleResponse(BaseModel):
    symbol: str
    tf: str
    candles: list[Candle]


class IndicatorVotes(BaseModel):
    up: int
    down: int
    neutral: int


class IndicatorDetail(BaseModel):
    name: str
    value: str
    vote: Literal["up", "down", "neutral"]
    note: str


class Signal(BaseModel):
    symbol: str
    name: str
    asset_class: str
    tf: str
    price: float
    change_pct: float
    bias: Literal["up", "down", "neutral"]
    confidence: int  # 0-100
    votes: IndicatorVotes
    indicators: list[IndicatorDetail]
    volatility: Literal["low", "moderate", "high"]
    atr_pct: float
    updated: int  # unix seconds


class AIAnalysis(BaseModel):
    symbol: str
    tf: str
    direction: Literal["up", "down", "neutral"]
    confidence: int
    rationale: str
    key_drivers: list[str]
    risk_note: str
    headlines_used: list[str]
    model: str
    cached: bool = False


class AssetInfo(BaseModel):
    symbol: str
    name: str
    asset_class: str
    source: str
