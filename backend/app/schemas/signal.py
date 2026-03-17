from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.market import MarketSnapshot, OptionAnalysis


class IndicatorSnapshot(BaseModel):
    vwap: float
    ema_9: float
    ema_21: float
    rsi: float
    macd: float
    macd_signal: float
    atr: float
    bollinger_upper: float
    bollinger_lower: float


class RiskPlan(BaseModel):
    entry: float
    stop_loss: float
    target_1: float
    target_2: float
    quantity: int
    risk_reward: float


class TradeSignal(BaseModel):
    symbol: str
    instrument: str
    signal_type: Literal["BUY_CALL", "BUY_PUT", "NO_TRADE"]
    confidence: float
    reason: str
    lifecycle_status: Literal[
        "NO_TRADE",
        "NEW_CALL",
        "MANAGE",
        "TARGET1_BOOKED",
        "EXIT_NOW",
        "TARGET2_HIT",
    ] = "NO_TRADE"
    guidance: str | None = None
    exit_guidance: str | None = None
    unrealized_pnl_pct: float | None = None
    current_option_price: float | None = None
    daily_calls_used: int | None = None
    risk_plan: RiskPlan | None = None


class SignalEnvelope(BaseModel):
    timestamp: datetime
    snapshot: MarketSnapshot
    analysis: OptionAnalysis
    indicators: IndicatorSnapshot
    signal: TradeSignal
    ai_reasoning: str
