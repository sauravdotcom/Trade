from datetime import UTC, datetime

from app.schemas.market import MarketSnapshot, OptionAnalysis, OptionRow
from app.schemas.signal import IndicatorSnapshot
from app.services.signal_engine import SignalEngine


def test_signal_engine_returns_valid_signal_type():
    snapshot = MarketSnapshot(
        symbol="NIFTY",
        spot_price=23500,
        timestamp=datetime.now(UTC),
        chain=[
            OptionRow(
                strike=23500,
                call_oi=14000,
                put_oi=12000,
                call_oi_change=300,
                put_oi_change=-150,
                call_ltp=120,
                put_ltp=118,
                call_ltp_change=-3,
                put_ltp_change=2,
                iv=15.4,
                volume=17000,
                gamma=0.012,
            )
        ],
    )

    analysis = OptionAnalysis(
        pcr=0.75,
        max_pain=23500,
        support_strike=23500,
        resistance_strike=23550,
        gamma_levels=[23500],
        liquidity_zones=[23500],
        regimes=["call_writing"],
    )

    indicators = IndicatorSnapshot(
        vwap=23600,
        ema_9=23490,
        ema_21=23510,
        rsi=38,
        macd=-4,
        macd_signal=-1,
        atr=40,
        bollinger_upper=23650,
        bollinger_lower=23400,
    )

    signal, option_price = SignalEngine().generate(snapshot, analysis, indicators)

    assert signal.signal_type in {"BUY_CALL", "BUY_PUT", "NO_TRADE"}
    if signal.signal_type != "NO_TRADE":
        assert option_price is not None
