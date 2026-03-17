from fastapi import APIRouter

from app.schemas.backtest import BacktestRequest, BacktestResult
from app.services.backtesting import BacktestEngine

router = APIRouter(prefix="/backtest", tags=["backtest"])
engine = BacktestEngine()


@router.post("/run", response_model=BacktestResult)
async def run_backtest(payload: BacktestRequest) -> BacktestResult:
    return engine.run(payload)
