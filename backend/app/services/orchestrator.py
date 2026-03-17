from __future__ import annotations

import asyncio
import contextlib
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, desc, func, insert, select, update

from app.core.config import get_settings
from app.db.session import AsyncSessionFactory
from app.models.performance import StrategyTuningState, TradePerformance
from app.models.signal import SignalRecord
from app.schemas.market import MarketSnapshot, OptionAnalysis
from app.schemas.signal import IndicatorSnapshot, SignalEnvelope, TradeSignal
from app.services.ai_reasoner import AIReasoner
from app.services.alerts import AlertService
from app.services.market_data import MarketDataService
from app.services.nse_clock import NseMarketClock
from app.services.options_analysis import OptionsAnalysisEngine
from app.services.risk import RiskManager
from app.services.signal_engine import SignalEngine
from app.services.technical_indicators import IndicatorEngine, PriceBar
from app.services.trade_advisor import ActiveTrade, TradeAdvisor
from app.utils.redis_cache import RedisCache
from app.utils.ws_manager import ConnectionManager


class SignalOrchestrator:
    def __init__(self, ws_manager: ConnectionManager) -> None:
        self.settings = get_settings()
        self.ws_manager = ws_manager
        self.market_data = MarketDataService()
        self.analysis_engine = OptionsAnalysisEngine()
        self.indicator_engine = IndicatorEngine()
        self.signal_engine = SignalEngine()
        self.risk_manager = RiskManager()
        self.ai_reasoner = AIReasoner()
        self.alerts = AlertService()
        self.cache = RedisCache()
        self.market_clock = NseMarketClock()
        self.trade_advisor = TradeAdvisor()

        self._task: asyncio.Task | None = None
        self._running = False
        self.watchlist = self._resolve_watchlist()
        self.histories: dict[str, deque[PriceBar]] = defaultdict(lambda: deque(maxlen=360))
        self.latest_payloads: dict[str, SignalEnvelope] = {}
        self.active_trades: dict[str, ActiveTrade] = {}
        self.daily_call_counts: dict[str, int] = {}
        self.last_call_timestamp_by_symbol: dict[str, datetime] = {}
        self.dynamic_min_confidence = self.settings.min_signal_confidence
        self.dynamic_call_cooldown_minutes = self.settings.call_cooldown_minutes
        self.last_learning_run_utc: datetime | None = None

    async def start(self) -> None:
        if self._running:
            return
        await self._load_adaptive_state()
        await self._restore_open_trades()
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        await self.market_data.close()
        await self.alerts.close()
        await self.cache.close()
        await self.market_clock.close()

    def _resolve_watchlist(self) -> list[str]:
        raw = self.settings.watchlist
        if isinstance(raw, list):
            return [item.upper() for item in raw] or [self.settings.default_index]
        return [item.strip().upper() for item in raw.split(",") if item.strip()] or [self.settings.default_index]

    async def _run_loop(self) -> None:
        while self._running:
            await self.market_clock.refresh_holidays()
            await self._maybe_update_adaptive_controls(datetime.now(UTC))

            if not self.market_clock.is_market_open():
                for symbol in self.watchlist:
                    envelope = self._market_closed_envelope(symbol)
                    await self._publish_envelope(envelope, persist_actionable=False)

                await asyncio.sleep(max(self.settings.market_refresh_seconds, 30))
                continue

            for symbol in self.watchlist:
                try:
                    envelope = await self._single_cycle(symbol)
                except Exception as exc:
                    envelope = self._data_unavailable_envelope(symbol, str(exc))

                await self._publish_envelope(envelope, persist_actionable=True)

            await asyncio.sleep(self.settings.market_refresh_seconds)

    async def _single_cycle(self, symbol: str) -> SignalEnvelope:
        now = datetime.now(UTC)
        snapshot = await self.market_data.get_snapshot(symbol)

        history = self.histories[symbol]
        history.append(
            PriceBar(
                timestamp=datetime.now(UTC),
                open=snapshot.spot_price,
                high=snapshot.spot_price + 5,
                low=snapshot.spot_price - 5,
                close=snapshot.spot_price,
                volume=sum(item.volume for item in snapshot.chain),
            )
        )

        analysis = self.analysis_engine.analyze(snapshot.chain, snapshot.spot_price)
        indicators = self.indicator_engine.compute(list(history))
        active_trade = self.active_trades.get(symbol)
        if active_trade:
            signal, should_close = self.trade_advisor.manage(active_trade, snapshot, analysis, indicators, now)
            signal.daily_calls_used = self._calls_used_today(now)
            if should_close:
                await self._close_trade_record(active_trade, signal, now)
                self.active_trades.pop(symbol, None)

            ai_reasoning = await self.ai_reasoner.explain(signal, analysis, indicators)
            return SignalEnvelope(
                timestamp=now,
                snapshot=snapshot,
                analysis=analysis,
                indicators=indicators,
                signal=signal,
                ai_reasoning=ai_reasoning,
            )

        signal, option_price = self.signal_engine.generate(snapshot, analysis, indicators)

        if option_price is not None and signal.signal_type != "NO_TRADE":
            signal.risk_plan = self.risk_manager.generate_plan(snapshot.symbol, option_price)
            signal.lifecycle_status = "NEW_CALL"

            allowed, deny_reason = self._allow_new_call(symbol, signal, now)
            if not allowed:
                signal = self._suppressed_call_signal(symbol, deny_reason, now)
            else:
                guidance, exit_guidance = self.trade_advisor.initial_guidance(signal)
                signal.guidance = guidance
                signal.exit_guidance = exit_guidance
                signal.daily_calls_used = self._register_new_call(symbol, now)
                active_trade = self.trade_advisor.open_trade(signal, now)
                active_trade.performance_id = await self._open_trade_record(signal, now)
                self.active_trades[symbol] = active_trade
        else:
            signal.daily_calls_used = self._calls_used_today(now)

        ai_reasoning = await self.ai_reasoner.explain(signal, analysis, indicators)

        return SignalEnvelope(
            timestamp=now,
            snapshot=snapshot,
            analysis=analysis,
            indicators=indicators,
            signal=signal,
            ai_reasoning=ai_reasoning,
        )

    async def _publish_envelope(self, envelope: SignalEnvelope, persist_actionable: bool) -> None:
        symbol = envelope.snapshot.symbol
        self.latest_payloads[symbol] = envelope
        await self.cache.set_json(
            f"latest-signal:{symbol}",
            envelope.model_dump(mode="json"),
            ttl=self.settings.market_refresh_seconds * 10,
        )
        await self.ws_manager.broadcast(envelope.model_dump(mode="json"))

        if not persist_actionable:
            return

        lifecycle = envelope.signal.lifecycle_status
        if lifecycle == "NEW_CALL":
            await self._store_signal(envelope)
            await self.alerts.dispatch(envelope.signal, envelope.ai_reasoning)
        elif lifecycle in {"TARGET1_BOOKED", "EXIT_NOW", "TARGET2_HIT"}:
            await self.alerts.dispatch(envelope.signal, envelope.ai_reasoning)

    def _market_closed_envelope(self, symbol: str) -> SignalEnvelope:
        spot = self._reference_spot(symbol)
        timestamp = datetime.now(UTC)
        status = self.market_clock.status_message()

        return SignalEnvelope(
            timestamp=timestamp,
            snapshot=MarketSnapshot(symbol=symbol, spot_price=spot, timestamp=timestamp, chain=[]),
            analysis=OptionAnalysis(
                pcr=1.0,
                max_pain=spot,
                support_strike=spot,
                resistance_strike=spot,
                gamma_levels=[spot],
                liquidity_zones=[spot],
                regimes=["market_closed"],
            ),
            indicators=IndicatorSnapshot(
                vwap=spot,
                ema_9=spot,
                ema_21=spot,
                rsi=50.0,
                macd=0.0,
                macd_signal=0.0,
                atr=0.0,
                bollinger_upper=spot,
                bollinger_lower=spot,
            ),
            signal=TradeSignal(
                symbol=symbol,
                instrument=f"{symbol} MARKET CLOSED",
                signal_type="NO_TRADE",
                confidence=0.0,
                reason=status,
                lifecycle_status="NO_TRADE",
                guidance="Signal engine is paused until NSE session opens.",
                exit_guidance="No new positions. Re-evaluate after market open.",
                daily_calls_used=self._calls_used_today(),
                current_option_price=None,
                risk_plan=None,
            ),
            ai_reasoning="Signal generation is paused outside official NSE market hours.",
        )

    def _data_unavailable_envelope(self, symbol: str, error: str) -> SignalEnvelope:
        spot = self._reference_spot(symbol)
        timestamp = datetime.now(UTC)

        return SignalEnvelope(
            timestamp=timestamp,
            snapshot=MarketSnapshot(symbol=symbol, spot_price=spot, timestamp=timestamp, chain=[]),
            analysis=OptionAnalysis(
                pcr=1.0,
                max_pain=spot,
                support_strike=spot,
                resistance_strike=spot,
                gamma_levels=[spot],
                liquidity_zones=[spot],
                regimes=["data_unavailable"],
            ),
            indicators=IndicatorSnapshot(
                vwap=spot,
                ema_9=spot,
                ema_21=spot,
                rsi=50.0,
                macd=0.0,
                macd_signal=0.0,
                atr=0.0,
                bollinger_upper=spot,
                bollinger_lower=spot,
            ),
            signal=TradeSignal(
                symbol=symbol,
                instrument=f"{symbol} DATA UNAVAILABLE",
                signal_type="NO_TRADE",
                confidence=0.0,
                reason=f"Live NSE data unavailable: {error}",
                lifecycle_status="NO_TRADE",
                guidance="Wait for live chain recovery before entering any trade.",
                exit_guidance="No fresh trade until data quality is restored.",
                daily_calls_used=self._calls_used_today(),
                current_option_price=None,
                risk_plan=None,
            ),
            ai_reasoning="No signal generated because live NSE data could not be fetched safely.",
        )

    def _reference_spot(self, symbol: str) -> float:
        existing = self.latest_payloads.get(symbol)
        if existing:
            return existing.snapshot.spot_price
        return 23500.0 if symbol == "NIFTY" else 51200.0

    async def _store_signal(self, envelope: SignalEnvelope) -> None:
        signal = envelope.signal
        if signal.risk_plan is None:
            return

        async with AsyncSessionFactory() as session:
            await session.execute(
                insert(SignalRecord).values(
                    symbol=signal.symbol,
                    instrument=signal.instrument,
                    signal_type=signal.signal_type,
                    entry=signal.risk_plan.entry,
                    stop_loss=signal.risk_plan.stop_loss,
                    target_1=signal.risk_plan.target_1,
                    target_2=signal.risk_plan.target_2,
                    confidence=signal.confidence,
                    reason=signal.reason,
                )
            )
            await session.commit()

    def _allow_new_call(self, symbol: str, signal: TradeSignal, now: datetime) -> tuple[bool, str]:
        if signal.confidence < self.dynamic_min_confidence:
            return (
                False,
                (
                    f"Setup filtered: confidence {signal.confidence:.2f}% is below "
                    f"{self.dynamic_min_confidence:.0f}%."
                ),
            )

        calls_used = self._calls_used_today(now)
        if calls_used >= self.settings.daily_max_calls:
            return (
                False,
                f"Daily limit reached: {calls_used}/{self.settings.daily_max_calls} calls issued today.",
            )

        last_call = self.last_call_timestamp_by_symbol.get(symbol)
        if last_call:
            elapsed = now - last_call
            cooldown = timedelta(minutes=self.dynamic_call_cooldown_minutes)
            if elapsed < cooldown:
                remaining = int((cooldown - elapsed).total_seconds() // 60) + 1
                return (
                    False,
                    f"Cooldown active for {symbol}. Next call allowed in ~{remaining} minutes.",
                )

        if signal.risk_plan and signal.risk_plan.risk_reward < 1.2:
            return False, "Setup filtered: risk-reward below 1.2."

        return True, ""

    def _suppressed_call_signal(self, symbol: str, reason: str, now: datetime) -> TradeSignal:
        calls_used = self._calls_used_today(now)
        return TradeSignal(
            symbol=symbol,
            instrument=f"{symbol} WAIT",
            signal_type="NO_TRADE",
            confidence=0.0,
            reason=reason,
            lifecycle_status="NO_TRADE",
            guidance=(
                "No fresh entry right now. Keep watching breakout/breakdown plus OI + VWAP alignment."
            ),
            exit_guidance="Capital protection mode: wait for next high-conviction setup.",
            daily_calls_used=calls_used,
            current_option_price=None,
            risk_plan=None,
        )

    def _register_new_call(self, symbol: str, now: datetime) -> int:
        day_key = self._day_key(now)
        current = self.daily_call_counts.get(day_key, 0) + 1
        self.daily_call_counts = {day_key: current}
        self.last_call_timestamp_by_symbol[symbol] = now
        return current

    def _calls_used_today(self, now: datetime | None = None) -> int:
        key = self._day_key(now or datetime.now(UTC))
        return self.daily_call_counts.get(key, 0)

    def _day_key(self, now: datetime) -> str:
        local_dt = now.astimezone(self.market_clock.timezone)
        return local_dt.date().isoformat()

    async def _open_trade_record(self, signal: TradeSignal, now: datetime) -> int | None:
        if not signal.risk_plan:
            return None

        async with AsyncSessionFactory() as session:
            result = await session.execute(
                insert(TradePerformance)
                .values(
                    symbol=signal.symbol,
                    instrument=signal.instrument,
                    signal_type=signal.signal_type,
                    entry_price=signal.risk_plan.entry,
                    stop_loss=signal.risk_plan.stop_loss,
                    target_1=signal.risk_plan.target_1,
                    target_2=signal.risk_plan.target_2,
                    quantity=signal.risk_plan.quantity,
                    confidence=signal.confidence,
                    opened_at=now,
                    status="OPEN",
                    result=None,
                    exit_reason=None,
                    exit_price=None,
                    pnl_amount=None,
                    pnl_pct=None,
                    strategy_min_confidence=self.dynamic_min_confidence,
                    strategy_cooldown_minutes=self.dynamic_call_cooldown_minutes,
                )
                .returning(TradePerformance.id)
            )
            await session.commit()
            return result.scalar_one_or_none()

    async def _close_trade_record(self, trade: ActiveTrade, signal: TradeSignal, now: datetime) -> None:
        if trade.performance_id is None:
            return

        exit_price = signal.current_option_price or trade.entry
        pnl_amount = round((exit_price - trade.entry) * trade.quantity, 2)
        pnl_pct = round(((exit_price - trade.entry) / max(trade.entry, 0.01)) * 100, 2)
        if pnl_amount > 0:
            result = "WIN"
        elif pnl_amount < 0:
            result = "LOSS"
        else:
            result = "BREAKEVEN"

        async with AsyncSessionFactory() as session:
            await session.execute(
                update(TradePerformance)
                .where(TradePerformance.id == trade.performance_id)
                .values(
                    status="CLOSED",
                    result=result,
                    closed_at=now,
                    exit_price=exit_price,
                    pnl_amount=pnl_amount,
                    pnl_pct=pnl_pct,
                    exit_reason=signal.reason,
                )
            )
            await session.commit()

    async def _load_adaptive_state(self) -> None:
        if not self.settings.adaptive_learning_enabled:
            return

        async with AsyncSessionFactory() as session:
            result = await session.execute(
                select(StrategyTuningState).order_by(desc(StrategyTuningState.as_of)).limit(1)
            )
            state = result.scalars().first()

        if state:
            self.dynamic_min_confidence = state.min_signal_confidence
            self.dynamic_call_cooldown_minutes = state.call_cooldown_minutes

    async def _restore_open_trades(self) -> None:
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                select(TradePerformance)
                .where(TradePerformance.status == "OPEN")
                .order_by(TradePerformance.opened_at.desc())
            )
            rows = result.scalars().all()

        restored: dict[str, ActiveTrade] = {}
        for row in rows:
            if row.symbol in restored:
                continue
            restored[row.symbol] = ActiveTrade(
                symbol=row.symbol,
                instrument=row.instrument,
                signal_type=row.signal_type,
                entry=row.entry_price,
                stop_loss=row.stop_loss,
                target_1=row.target_1,
                target_2=row.target_2,
                quantity=row.quantity,
                opened_at=row.opened_at,
                performance_id=row.id,
                target1_booked=False,
            )

        self.active_trades = restored

    async def _maybe_update_adaptive_controls(self, now: datetime) -> None:
        if not self.settings.adaptive_learning_enabled:
            return

        interval = timedelta(minutes=self.settings.adaptive_learning_interval_minutes)
        if self.last_learning_run_utc and (now - self.last_learning_run_utc) < interval:
            return
        self.last_learning_run_utc = now

        lookback_start = now - timedelta(days=self.settings.adaptive_lookback_days)
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                select(
                    func.count(TradePerformance.id),
                    func.sum(case((TradePerformance.result == "WIN", 1), else_=0)),
                    func.sum(case((TradePerformance.result == "LOSS", 1), else_=0)),
                    func.sum(func.coalesce(TradePerformance.pnl_amount, 0.0)),
                ).where(
                    TradePerformance.status == "CLOSED",
                    TradePerformance.closed_at.is_not(None),
                    TradePerformance.closed_at >= lookback_start,
                )
            )
            row = result.one()

            closed_trades = int(row[0] or 0)
            wins = int(row[1] or 0)
            losses = int(row[2] or 0)
            net_pnl = float(row[3] or 0.0)
            win_rate = round((wins / closed_trades) * 100, 2) if closed_trades else 0.0

            new_conf = self.dynamic_min_confidence
            new_cooldown = self.dynamic_call_cooldown_minutes
            note = "No change: insufficient data."

            if closed_trades >= self.settings.adaptive_min_closed_trades:
                if win_rate < 55.0 or net_pnl < 0:
                    new_conf = min(self.settings.adaptive_confidence_ceiling, new_conf + 1.0)
                    new_cooldown = min(90, new_cooldown + 5)
                    note = "Tightened filters due to weak rolling performance."
                elif win_rate > 68.0 and net_pnl > 0 and losses > 0:
                    new_conf = max(self.settings.adaptive_confidence_floor, new_conf - 1.0)
                    new_cooldown = max(20, new_cooldown - 5)
                    note = "Relaxed filters due to strong rolling performance."
                else:
                    note = "No change: performance in neutral zone."

            self.dynamic_min_confidence = round(new_conf, 2)
            self.dynamic_call_cooldown_minutes = int(new_cooldown)

            await session.execute(
                insert(StrategyTuningState).values(
                    as_of=now,
                    lookback_days=self.settings.adaptive_lookback_days,
                    closed_trades=closed_trades,
                    win_rate=win_rate,
                    net_pnl=round(net_pnl, 2),
                    min_signal_confidence=self.dynamic_min_confidence,
                    call_cooldown_minutes=self.dynamic_call_cooldown_minutes,
                    note=note,
                )
            )
            await session.commit()

    async def latest(self, symbol: str | None = None) -> SignalEnvelope | None:
        symbol = (symbol or self.settings.default_index).upper()
        if symbol in self.latest_payloads:
            return self.latest_payloads[symbol]

        cached = await self.cache.get_json(f"latest-signal:{symbol}")
        if cached:
            return SignalEnvelope(**cached)
        return None
