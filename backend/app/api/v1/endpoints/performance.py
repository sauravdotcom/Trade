from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from sqlalchemy import case, func, select

from app.db.session import AsyncSessionFactory
from app.models.performance import StrategyTuningState, TradePerformance
from app.schemas.performance import PerformanceSummary, PerformanceTrade

router = APIRouter(prefix="/performance", tags=["performance"])


@router.get("/summary", response_model=PerformanceSummary)
async def performance_summary(days: int = 30) -> PerformanceSummary:
    now = datetime.now(UTC)
    since = now - timedelta(days=days)

    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(
                func.count(TradePerformance.id),
                func.sum(case((TradePerformance.status == "OPEN", 1), else_=0)),
                func.sum(case((TradePerformance.status == "CLOSED", 1), else_=0)),
                func.sum(case((TradePerformance.result == "WIN", 1), else_=0)),
                func.sum(case((TradePerformance.result == "LOSS", 1), else_=0)),
                func.sum(case((TradePerformance.result == "BREAKEVEN", 1), else_=0)),
                func.sum(func.coalesce(TradePerformance.pnl_amount, 0.0)),
                func.avg(TradePerformance.pnl_amount),
                func.avg(TradePerformance.pnl_pct),
                func.sum(case((TradePerformance.pnl_amount > 0, TradePerformance.pnl_amount), else_=0.0)),
                func.sum(case((TradePerformance.pnl_amount < 0, func.abs(TradePerformance.pnl_amount)), else_=0.0)),
            ).where(TradePerformance.opened_at >= since)
        )
        row = result.one()

        total_calls = int(row[0] or 0)
        open_trades = int(row[1] or 0)
        closed_trades = int(row[2] or 0)
        wins = int(row[3] or 0)
        losses = int(row[4] or 0)
        breakeven = int(row[5] or 0)
        net_pnl = float(row[6] or 0.0)
        avg_pnl = float(row[7] or 0.0)
        avg_pnl_pct = float(row[8] or 0.0)
        gross_profit = float(row[9] or 0.0)
        gross_loss = float(row[10] or 0.0)

        tuning_result = await session.execute(
            select(StrategyTuningState).order_by(StrategyTuningState.as_of.desc()).limit(1)
        )
        tuning = tuning_result.scalars().first()

    win_rate = round((wins / closed_trades) * 100, 2) if closed_trades else 0.0
    profit_factor = round(gross_profit / gross_loss, 3) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

    return PerformanceSummary(
        lookback_days=days,
        total_calls=total_calls,
        open_trades=open_trades,
        closed_trades=closed_trades,
        wins=wins,
        losses=losses,
        breakeven=breakeven,
        win_rate=win_rate,
        net_pnl=round(net_pnl, 2),
        avg_pnl_per_trade=round(avg_pnl, 2),
        avg_pnl_pct=round(avg_pnl_pct, 2),
        profit_factor=profit_factor,
        adaptive_min_confidence=tuning.min_signal_confidence if tuning else 90.0,
        adaptive_cooldown_minutes=tuning.call_cooldown_minutes if tuning else 35,
        updated_at=now,
    )


@router.get("/trades", response_model=list[PerformanceTrade])
async def performance_trades(days: int = 30, limit: int = 200) -> list[PerformanceTrade]:
    since = datetime.now(UTC) - timedelta(days=days)
    cap = min(max(limit, 1), 1000)

    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(TradePerformance)
            .where(TradePerformance.opened_at >= since)
            .order_by(TradePerformance.opened_at.desc())
            .limit(cap)
        )
        rows = result.scalars().all()

    return [
        PerformanceTrade(
            id=row.id,
            symbol=row.symbol,
            instrument=row.instrument,
            signal_type=row.signal_type,
            status=row.status,
            result=row.result,
            confidence=row.confidence,
            entry_price=row.entry_price,
            exit_price=row.exit_price,
            quantity=row.quantity,
            pnl_amount=row.pnl_amount,
            pnl_pct=row.pnl_pct,
            opened_at=row.opened_at,
            closed_at=row.closed_at,
            exit_reason=row.exit_reason,
        )
        for row in rows
    ]
