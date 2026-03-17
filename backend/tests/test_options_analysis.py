from app.schemas.market import OptionRow
from app.services.options_analysis import OptionsAnalysisEngine


def test_analysis_outputs_expected_shape():
    chain = [
        OptionRow(
            strike=23500,
            call_oi=10000,
            put_oi=15000,
            call_oi_change=100,
            put_oi_change=200,
            call_ltp=120,
            put_ltp=130,
            call_ltp_change=-1,
            put_ltp_change=-1,
            iv=15,
            volume=12000,
            gamma=0.01,
        ),
        OptionRow(
            strike=23550,
            call_oi=16000,
            put_oi=9000,
            call_oi_change=150,
            put_oi_change=-100,
            call_ltp=90,
            put_ltp=170,
            call_ltp_change=-2,
            put_ltp_change=2,
            iv=16,
            volume=9000,
            gamma=0.02,
        ),
    ]

    engine = OptionsAnalysisEngine()
    result = engine.analyze(chain, 23520)

    assert result.pcr > 0
    assert result.support_strike in (23500, 23550)
    assert result.resistance_strike in (23500, 23550)
    assert len(result.gamma_levels) >= 1
