from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class TradePerformance(Base):
    __tablename__ = "trade_performance"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    instrument: Mapped[str] = mapped_column(String(40), index=True)
    signal_type: Mapped[str] = mapped_column(String(20), index=True)

    entry_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    target_1: Mapped[float] = mapped_column(Float)
    target_2: Mapped[float] = mapped_column(Float)
    quantity: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float)

    opened_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)
    closed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    result: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    exit_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    strategy_min_confidence: Mapped[float] = mapped_column(Float, default=90.0)
    strategy_cooldown_minutes: Mapped[int] = mapped_column(Integer, default=35)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class StrategyTuningState(Base):
    __tablename__ = "strategy_tuning_state"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    as_of: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    lookback_days: Mapped[int] = mapped_column(Integer, default=30)
    closed_trades: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    net_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    min_signal_confidence: Mapped[float] = mapped_column(Float, default=90.0)
    call_cooldown_minutes: Mapped[int] = mapped_column(Integer, default=35)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
