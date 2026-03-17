from datetime import datetime

from pydantic import BaseModel


class OptionRow(BaseModel):
    strike: float
    call_oi: int
    put_oi: int
    call_oi_change: int
    put_oi_change: int
    call_ltp: float
    put_ltp: float
    call_ltp_change: float
    put_ltp_change: float
    iv: float
    volume: int
    gamma: float


class MarketSnapshot(BaseModel):
    symbol: str
    spot_price: float
    timestamp: datetime
    chain: list[OptionRow]


class OptionAnalysis(BaseModel):
    pcr: float
    max_pain: float
    support_strike: float
    resistance_strike: float
    gamma_levels: list[float]
    liquidity_zones: list[float]
    regimes: list[str]
