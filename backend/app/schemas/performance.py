from datetime import datetime

from pydantic import BaseModel


class PerformanceTrade(BaseModel):
    id: int
    symbol: str
    instrument: str
    signal_type: str
    status: str
    result: str | None = None
    confidence: float
    entry_price: float
    exit_price: float | None = None
    quantity: int
    pnl_amount: float | None = None
    pnl_pct: float | None = None
    opened_at: datetime
    closed_at: datetime | None = None
    exit_reason: str | None = None


class PerformanceSummary(BaseModel):
    lookback_days: int
    total_calls: int
    open_trades: int
    closed_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    net_pnl: float
    avg_pnl_per_trade: float
    avg_pnl_pct: float
    profit_factor: float
    adaptive_min_confidence: float
    adaptive_cooldown_minutes: int
    updated_at: datetime
