from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.schemas.market import MarketSnapshot, OptionAnalysis
from app.schemas.signal import IndicatorSnapshot, RiskPlan, TradeSignal

_INSTRUMENT_RE = re.compile(r"^(NIFTY|BANKNIFTY)\s+(\d+)\s+(CE|PE)$")


@dataclass
class ActiveTrade:
    symbol: str
    instrument: str
    signal_type: str
    entry: float
    stop_loss: float
    target_1: float
    target_2: float
    quantity: int
    opened_at: datetime
    performance_id: int | None = None
    target1_booked: bool = False

    def to_risk_plan(self) -> RiskPlan:
        risk_per_unit = max(self.entry - self.stop_loss, 0.01)
        risk_reward = round((self.target_1 - self.entry) / risk_per_unit, 2)
        return RiskPlan(
            entry=round(self.entry, 2),
            stop_loss=round(self.stop_loss, 2),
            target_1=round(self.target_1, 2),
            target_2=round(self.target_2, 2),
            quantity=self.quantity,
            risk_reward=risk_reward,
        )


class TradeAdvisor:
    def initial_guidance(self, signal: TradeSignal) -> tuple[str, str]:
        if not signal.risk_plan:
            return ("No actionable plan.", "No exit guidance available.")

        guidance = (
            "Enter only on premium holding near entry for 1-2 ticks. "
            "Avoid chasing after a spike. Keep risk fixed to planned quantity."
        )
        exit_guidance = (
            f"Hard SL: {signal.risk_plan.stop_loss}. "
            f"At Target1 ({signal.risk_plan.target_1}) book 50% and trail SL to entry. "
            f"At Target2 ({signal.risk_plan.target_2}) exit remaining quantity."
        )
        return guidance, exit_guidance

    def open_trade(self, signal: TradeSignal, now: datetime | None = None) -> ActiveTrade:
        if not signal.risk_plan:
            raise ValueError("Cannot open trade without risk plan")

        return ActiveTrade(
            symbol=signal.symbol,
            instrument=signal.instrument,
            signal_type=signal.signal_type,
            entry=signal.risk_plan.entry,
            stop_loss=signal.risk_plan.stop_loss,
            target_1=signal.risk_plan.target_1,
            target_2=signal.risk_plan.target_2,
            quantity=signal.risk_plan.quantity,
            opened_at=now or datetime.now(UTC),
        )

    def manage(
        self,
        trade: ActiveTrade,
        snapshot: MarketSnapshot,
        analysis: OptionAnalysis,
        indicators: IndicatorSnapshot,
        now: datetime | None = None,
    ) -> tuple[TradeSignal, bool]:
        now = now or datetime.now(UTC)
        option_price = self._current_option_price(snapshot, trade.instrument)
        base_plan = trade.to_risk_plan()

        if option_price is None:
            signal = TradeSignal(
                symbol=trade.symbol,
                instrument=trade.instrument,
                signal_type=trade.signal_type,  # type: ignore[arg-type]
                confidence=0.0,
                reason="Live option quote unavailable for active trade monitoring.",
                lifecycle_status="MANAGE",
                guidance="Hold with caution until fresh quote is available.",
                exit_guidance=f"Use hard stop-loss {trade.stop_loss}.",
                current_option_price=None,
                risk_plan=base_plan,
            )
            return signal, False

        pnl_pct = ((option_price - trade.entry) / max(trade.entry, 0.01)) * 100
        elapsed = now - trade.opened_at

        if option_price <= trade.stop_loss:
            signal = self._build_management_signal(
                trade=trade,
                option_price=option_price,
                pnl_pct=pnl_pct,
                reason=f"Stop-loss breached ({option_price:.2f} <= {trade.stop_loss:.2f}).",
                lifecycle="EXIT_NOW",
                guidance="Exit immediately. Do not average this position.",
                exit_guidance="Exit at market. Re-entry only after fresh setup confirmation.",
            )
            return signal, True

        if option_price >= trade.target_2:
            signal = self._build_management_signal(
                trade=trade,
                option_price=option_price,
                pnl_pct=pnl_pct,
                reason=f"Target2 reached ({option_price:.2f} >= {trade.target_2:.2f}).",
                lifecycle="TARGET2_HIT",
                guidance="Book full profits.",
                exit_guidance="Exit remaining quantity now.",
            )
            return signal, True

        if option_price >= trade.target_1 and not trade.target1_booked:
            trade.target1_booked = True
            trade.stop_loss = max(trade.stop_loss, trade.entry)
            signal = self._build_management_signal(
                trade=trade,
                option_price=option_price,
                pnl_pct=pnl_pct,
                reason=f"Target1 reached ({option_price:.2f}).",
                lifecycle="TARGET1_BOOKED",
                guidance="Book 50% and trail stop-loss to entry.",
                exit_guidance=f"New trailing stop-loss: {trade.stop_loss:.2f}.",
            )
            return signal, False

        if self._reversal_detected(trade, snapshot, indicators):
            signal = self._build_management_signal(
                trade=trade,
                option_price=option_price,
                pnl_pct=pnl_pct,
                reason="Momentum reversal detected against active trade.",
                lifecycle="EXIT_NOW",
                guidance="Exit to protect capital.",
                exit_guidance="Exit at market due to VWAP+EMA reversal confirmation.",
            )
            return signal, True

        if elapsed >= timedelta(minutes=20) and option_price < trade.entry * 0.98:
            signal = self._build_management_signal(
                trade=trade,
                option_price=option_price,
                pnl_pct=pnl_pct,
                reason="Time-stop triggered. Trade did not move in expected direction.",
                lifecycle="EXIT_NOW",
                guidance="Exit stale trade and wait for new setup.",
                exit_guidance="Close position now. Re-assess after next signal cycle.",
            )
            return signal, True

        signal = self._build_management_signal(
            trade=trade,
            option_price=option_price,
            pnl_pct=pnl_pct,
            reason=(
                f"Active management mode. Premium={option_price:.2f}, "
                f"PnL={pnl_pct:.2f}%, PCR={analysis.pcr:.2f}."
            ),
            lifecycle="MANAGE",
            guidance="Hold while structure remains valid. Trail stop tighter if momentum weakens.",
            exit_guidance=f"Current stop-loss {trade.stop_loss:.2f}, Target1 {trade.target_1:.2f}, Target2 {trade.target_2:.2f}.",
        )
        return signal, False

    def _build_management_signal(
        self,
        trade: ActiveTrade,
        option_price: float,
        pnl_pct: float,
        reason: str,
        lifecycle: str,
        guidance: str,
        exit_guidance: str,
    ) -> TradeSignal:
        return TradeSignal(
            symbol=trade.symbol,
            instrument=trade.instrument,
            signal_type=trade.signal_type,  # type: ignore[arg-type]
            confidence=92.0,
            reason=reason,
            lifecycle_status=lifecycle,  # type: ignore[arg-type]
            guidance=guidance,
            exit_guidance=exit_guidance,
            unrealized_pnl_pct=round(pnl_pct, 2),
            current_option_price=round(option_price, 2),
            risk_plan=trade.to_risk_plan(),
        )

    def _reversal_detected(
        self,
        trade: ActiveTrade,
        snapshot: MarketSnapshot,
        indicators: IndicatorSnapshot,
    ) -> bool:
        if trade.signal_type == "BUY_CALL":
            return (
                snapshot.spot_price < indicators.vwap
                and indicators.ema_9 < indicators.ema_21
                and indicators.rsi < 45
            )
        return (
            snapshot.spot_price > indicators.vwap
            and indicators.ema_9 > indicators.ema_21
            and indicators.rsi > 55
        )

    def _current_option_price(self, snapshot: MarketSnapshot, instrument: str) -> float | None:
        parsed = _INSTRUMENT_RE.match(instrument.strip())
        if not parsed:
            return None

        _, strike_text, opt_type = parsed.groups()
        strike = float(strike_text)
        row = min(snapshot.chain, key=lambda item: abs(item.strike - strike), default=None)
        if row is None or abs(row.strike - strike) > 0.1:
            return None
        return row.call_ltp if opt_type == "CE" else row.put_ltp
