from __future__ import annotations

from app.schemas.market import MarketSnapshot, OptionAnalysis
from app.schemas.signal import IndicatorSnapshot, TradeSignal


class SignalEngine:
    def generate(
        self,
        snapshot: MarketSnapshot,
        analysis: OptionAnalysis,
        indicators: IndicatorSnapshot,
    ) -> tuple[TradeSignal, float | None]:
        spot = snapshot.spot_price
        chain = snapshot.chain

        if not chain:
            return (
                TradeSignal(
                    symbol=snapshot.symbol,
                    instrument=f"{snapshot.symbol} -",
                    signal_type="NO_TRADE",
                    confidence=0,
                    reason="No option chain data.",
                    risk_plan=None,
                ),
                None,
            )

        nearest_support = min(chain, key=lambda row: abs(row.strike - analysis.support_strike))
        nearest_resistance = min(chain, key=lambda row: abs(row.strike - analysis.resistance_strike))
        atm = min(chain, key=lambda row: abs(row.strike - spot))

        bearish_checks = {
            "price_below_vwap": spot < indicators.vwap,
            "pcr_bearish": analysis.pcr < 0.8,
            "call_writing": "call_writing" in analysis.regimes,
            "support_break": spot < analysis.support_strike,
            "ema_bearish": indicators.ema_9 < indicators.ema_21,
        }

        bullish_checks = {
            "price_above_vwap": spot > indicators.vwap,
            "pcr_bullish": analysis.pcr > 1.2,
            "put_writing": "put_writing" in analysis.regimes,
            "resistance_break": spot > analysis.resistance_strike,
            "ema_bullish": indicators.ema_9 > indicators.ema_21,
        }

        bearish_score = sum(1 for value in bearish_checks.values() if value)
        bullish_score = sum(1 for value in bullish_checks.values() if value)

        if bearish_score >= 4:
            strike = nearest_support.strike if spot < nearest_support.strike else atm.strike
            selected = min(chain, key=lambda row: abs(row.strike - strike))
            reason = self._reason("bearish", bearish_checks, analysis, indicators)
            confidence = self._confidence(bearish_checks, analysis, indicators)
            return (
                TradeSignal(
                    symbol=snapshot.symbol,
                    instrument=f"{snapshot.symbol} {int(selected.strike)} PE",
                    signal_type="BUY_PUT",
                    confidence=confidence,
                    reason=reason,
                    risk_plan=None,
                ),
                selected.put_ltp,
            )

        if bullish_score >= 4:
            strike = nearest_resistance.strike if spot > nearest_resistance.strike else atm.strike
            selected = min(chain, key=lambda row: abs(row.strike - strike))
            reason = self._reason("bullish", bullish_checks, analysis, indicators)
            confidence = self._confidence(bullish_checks, analysis, indicators)
            return (
                TradeSignal(
                    symbol=snapshot.symbol,
                    instrument=f"{snapshot.symbol} {int(selected.strike)} CE",
                    signal_type="BUY_CALL",
                    confidence=confidence,
                    reason=reason,
                    risk_plan=None,
                ),
                selected.call_ltp,
            )

        confidence = max(20.0, float(abs(analysis.pcr - 1.0) * 100))
        return (
            TradeSignal(
                symbol=snapshot.symbol,
                instrument=f"{snapshot.symbol} {int(atm.strike)} ATM",
                signal_type="NO_TRADE",
                confidence=round(min(confidence, 55.0), 2),
                reason="No high-probability setup. Waiting for alignment of VWAP, PCR, OI and breakout/breakdown.",
                risk_plan=None,
            ),
            None,
        )

    def _confidence(
        self,
        checks: dict[str, bool],
        analysis: OptionAnalysis,
        indicators: IndicatorSnapshot,
    ) -> float:
        score = 35 + (sum(1 for state in checks.values() if state) * 10)

        if indicators.rsi < 35 or indicators.rsi > 65:
            score += 5
        if abs(indicators.macd - indicators.macd_signal) > 5:
            score += 5
        if "mixed" not in analysis.regimes:
            score += 5

        return round(min(95.0, score), 2)

    def _reason(
        self,
        stance: str,
        checks: dict[str, bool],
        analysis: OptionAnalysis,
        indicators: IndicatorSnapshot,
    ) -> str:
        labels = {
            "price_below_vwap": "price below VWAP",
            "pcr_bearish": "PCR bearish",
            "call_writing": "call writing concentration",
            "support_break": "support breakdown",
            "ema_bearish": "EMA9 < EMA21",
            "price_above_vwap": "price above VWAP",
            "pcr_bullish": "PCR bullish",
            "put_writing": "put writing concentration",
            "resistance_break": "resistance breakout",
            "ema_bullish": "EMA9 > EMA21",
        }
        active = [labels[name] for name, passed in checks.items() if passed]
        regime_text = ", ".join(analysis.regimes)

        if stance == "bearish":
            return (
                f"Bearish setup: {' + '.join(active)}. "
                f"Regime={regime_text}. Spot vs VWAP={indicators.vwap}."
            )

        return (
            f"Bullish setup: {' + '.join(active)}. "
            f"Regime={regime_text}. Spot vs VWAP={indicators.vwap}."
        )
