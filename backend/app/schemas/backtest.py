from pydantic import BaseModel


class CandleInput(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class BacktestRequest(BaseModel):
    symbol: str = "NIFTY"
    candles: list[CandleInput]
    initial_capital: float = 100000
    risk_per_trade: float = 0.02


class BacktestResult(BaseModel):
    symbol: str
    trades: int
    wins: int
    losses: int
    win_rate: float
    net_pnl: float
    max_drawdown: float
