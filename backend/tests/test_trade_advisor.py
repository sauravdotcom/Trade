from datetime import UTC, datetime, timedelta

from app.schemas.market import MarketSnapshot, OptionAnalysis, OptionRow
from app.schemas.signal import IndicatorSnapshot, RiskPlan, TradeSignal
from app.services.trade_advisor import TradeAdvisor


def _snapshot(call_ltp: float, put_ltp: float) -> MarketSnapshot:
    return MarketSnapshot(
        symbol="NIFTY",
        spot_price=23520.0,
        timestamp=datetime.now(UTC),
        chain=[
            OptionRow(
                strike=23500.0,
                call_oi=10000,
                put_oi=9000,
                call_oi_change=120,
                put_oi_change=-30,
                call_ltp=call_ltp,
                put_ltp=put_ltp,
                call_ltp_change=2.0,
                put_ltp_change=-1.2,
                iv=15.0,
                volume=18000,
                gamma=0.01,
            )
        ],
    )


def _analysis() -> OptionAnalysis:
    return OptionAnalysis(
        pcr=1.25,
        max_pain=23500.0,
        support_strike=23450.0,
        resistance_strike=23550.0,
        gamma_levels=[23500.0],
        liquidity_zones=[23500.0],
        regimes=["put_writing"],
    )


def _indicators() -> IndicatorSnapshot:
    return IndicatorSnapshot(
        vwap=23500.0,
        ema_9=23530.0,
        ema_21=23510.0,
        rsi=58.0,
        macd=2.1,
        macd_signal=1.5,
        atr=40.0,
        bollinger_upper=23600.0,
        bollinger_lower=23400.0,
    )


def test_trade_advisor_target1_updates_state():
    advisor = TradeAdvisor()
    signal = TradeSignal(
        symbol="NIFTY",
        instrument="NIFTY 23500 CE",
        signal_type="BUY_CALL",
        confidence=92.0,
        reason="test",
        risk_plan=RiskPlan(entry=100, stop_loss=80, target_1=130, target_2=160, quantity=75, risk_reward=1.5),
    )
    trade = advisor.open_trade(signal)

    managed, should_close = advisor.manage(
        trade=trade,
        snapshot=_snapshot(call_ltp=132, put_ltp=92),
        analysis=_analysis(),
        indicators=_indicators(),
    )

    assert should_close is False
    assert managed.lifecycle_status == "TARGET1_BOOKED"
    assert managed.risk_plan is not None
    assert managed.risk_plan.stop_loss >= 100


def test_trade_advisor_exit_on_stop_loss():
    advisor = TradeAdvisor()
    signal = TradeSignal(
        symbol="NIFTY",
        instrument="NIFTY 23500 CE",
        signal_type="BUY_CALL",
        confidence=92.0,
        reason="test",
        risk_plan=RiskPlan(entry=100, stop_loss=80, target_1=130, target_2=160, quantity=75, risk_reward=1.5),
    )
    trade = advisor.open_trade(signal)

    managed, should_close = advisor.manage(
        trade=trade,
        snapshot=_snapshot(call_ltp=78, put_ltp=96),
        analysis=_analysis(),
        indicators=_indicators(),
    )

    assert should_close is True
    assert managed.lifecycle_status == "EXIT_NOW"


def test_trade_advisor_time_stop():
    advisor = TradeAdvisor()
    signal = TradeSignal(
        symbol="NIFTY",
        instrument="NIFTY 23500 CE",
        signal_type="BUY_CALL",
        confidence=92.0,
        reason="test",
        risk_plan=RiskPlan(entry=100, stop_loss=80, target_1=130, target_2=160, quantity=75, risk_reward=1.5),
    )
    trade = advisor.open_trade(signal, now=datetime.now(UTC) - timedelta(minutes=25))

    managed, should_close = advisor.manage(
        trade=trade,
        snapshot=_snapshot(call_ltp=96, put_ltp=92),
        analysis=_analysis(),
        indicators=_indicators(),
    )

    assert should_close is True
    assert managed.lifecycle_status == "EXIT_NOW"
