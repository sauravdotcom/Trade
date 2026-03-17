from __future__ import annotations

from collections import deque
from datetime import UTC, datetime

from app.schemas.backtest import BacktestRequest, BacktestResult
from app.schemas.market import MarketSnapshot, OptionRow
from app.services.options_analysis import OptionsAnalysisEngine
from app.services.risk import RiskManager
from app.services.signal_engine import SignalEngine
from app.services.technical_indicators import IndicatorEngine, PriceBar


class BacktestEngine:
    def __init__(self) -> None:
        self.indicator_engine = IndicatorEngine()
        self.analysis_engine = OptionsAnalysisEngine()
        self.signal_engine = SignalEngine()
        self.risk_manager = RiskManager()

    def run(self, payload: BacktestRequest) -> BacktestResult:
        bars_window: deque[PriceBar] = deque(maxlen=180)
        trades = 0
        wins = 0
        losses = 0
        net_pnl = 0.0
        equity = payload.initial_capital
        peak = equity
        max_drawdown = 0.0

        candles = payload.candles
        if len(candles) < 40:
            return BacktestResult(
                symbol=payload.symbol,
                trades=0,
                wins=0,
                losses=0,
                win_rate=0,
                net_pnl=0,
                max_drawdown=0,
            )

        for idx, candle in enumerate(candles):
            bar = PriceBar(
                timestamp=datetime.fromisoformat(candle.timestamp.replace("Z", "+00:00")),
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
            )
            bars_window.append(bar)

            if idx < 30:
                continue

            chain = self._synthetic_chain(candle.close)
            snapshot = MarketSnapshot(
                symbol=payload.symbol,
                spot_price=candle.close,
                timestamp=datetime.now(UTC),
                chain=chain,
            )
            indicators = self.indicator_engine.compute(list(bars_window))
            analysis = self.analysis_engine.analyze(chain, candle.close)
            signal, option_price = self.signal_engine.generate(snapshot, analysis, indicators)

            if signal.signal_type == "NO_TRADE" or option_price is None or idx + 5 >= len(candles):
                continue

            risk_plan = self.risk_manager.generate_plan(
                symbol=payload.symbol,
                option_price=option_price,
                capital=equity,
                risk_per_trade=payload.risk_per_trade,
            )
            trades += 1

            future_close = candles[idx + 5].close
            move = future_close - candle.close
            bullish = signal.signal_type == "BUY_CALL"
            success = (bullish and move > 0) or ((not bullish) and move < 0)

            if success:
                pnl = (risk_plan.target_1 - risk_plan.entry) * risk_plan.quantity
                wins += 1
            else:
                pnl = (risk_plan.stop_loss - risk_plan.entry) * risk_plan.quantity
                losses += 1

            net_pnl += pnl
            equity += pnl
            peak = max(peak, equity)
            dd = (peak - equity) / peak if peak else 0
            max_drawdown = max(max_drawdown, dd)

        win_rate = round((wins / trades) * 100, 2) if trades else 0.0
        return BacktestResult(
            symbol=payload.symbol,
            trades=trades,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            net_pnl=round(net_pnl, 2),
            max_drawdown=round(max_drawdown * 100, 2),
        )

    def _synthetic_chain(self, spot: float) -> list[OptionRow]:
        step = 50
        atm = round(spot / step) * step
        rows: list[OptionRow] = []

        for strike in range(int(atm - 300), int(atm + 350), step):
            rows.append(
                OptionRow(
                    strike=float(strike),
                    call_oi=max(500, int(12000 - abs(strike - spot) * 12)),
                    put_oi=max(500, int(12000 - abs(strike - spot) * 12)),
                    call_oi_change=int((spot - strike) * -2),
                    put_oi_change=int((spot - strike) * 2),
                    call_ltp=max(20, (spot - strike) * 0.4 + 100),
                    put_ltp=max(20, (strike - spot) * 0.4 + 100),
                    call_ltp_change=(spot - strike) * 0.02,
                    put_ltp_change=(strike - spot) * 0.02,
                    iv=14.0,
                    volume=10000,
                    gamma=0.01,
                )
            )

        return rows
