from __future__ import annotations

import math
from collections import Counter

from app.schemas.market import OptionAnalysis, OptionRow


class OptionsAnalysisEngine:
    def analyze(self, chain: list[OptionRow], spot_price: float) -> OptionAnalysis:
        if not chain:
            return OptionAnalysis(
                pcr=1.0,
                max_pain=spot_price,
                support_strike=spot_price,
                resistance_strike=spot_price,
                gamma_levels=[spot_price],
                liquidity_zones=[spot_price],
                regimes=["insufficient_data"],
            )

        total_put_oi = sum(row.put_oi for row in chain)
        total_call_oi = sum(row.call_oi for row in chain)
        pcr = round(total_put_oi / max(total_call_oi, 1), 4)

        support_row = max(chain, key=lambda item: item.put_oi)
        resistance_row = max(chain, key=lambda item: item.call_oi)
        max_pain = round(self._max_pain(chain), 2)

        gamma_levels = [row.strike for row in sorted(chain, key=lambda item: abs(item.gamma), reverse=True)[:3]]
        liquidity_zones = [row.strike for row in sorted(chain, key=lambda item: item.volume, reverse=True)[:4]]

        regimes = self._detect_regimes(chain)

        return OptionAnalysis(
            pcr=pcr,
            max_pain=max_pain,
            support_strike=support_row.strike,
            resistance_strike=resistance_row.strike,
            gamma_levels=gamma_levels,
            liquidity_zones=liquidity_zones,
            regimes=regimes,
        )

    def _max_pain(self, chain: list[OptionRow]) -> float:
        strikes = [row.strike for row in chain]
        min_pain = math.inf
        pain_strike = strikes[0]

        for test_strike in strikes:
            call_pain = sum(max(test_strike - row.strike, 0) * row.call_oi for row in chain)
            put_pain = sum(max(row.strike - test_strike, 0) * row.put_oi for row in chain)
            total_pain = call_pain + put_pain
            if total_pain < min_pain:
                min_pain = total_pain
                pain_strike = test_strike

        return pain_strike

    def _detect_regimes(self, chain: list[OptionRow]) -> list[str]:
        counters: Counter[str] = Counter()

        for row in chain:
            if row.call_oi_change > 0 and row.call_ltp_change <= 0:
                counters["call_writing"] += 1
            if row.put_oi_change > 0 and row.put_ltp_change <= 0:
                counters["put_writing"] += 1
            if row.call_oi_change < 0 and row.call_ltp_change > 0:
                counters["call_short_covering"] += 1
            if row.put_oi_change < 0 and row.put_ltp_change > 0:
                counters["put_short_covering"] += 1
            if row.call_oi_change > 0 and row.call_ltp_change > 0:
                counters["call_long_buildup"] += 1
            if row.put_oi_change > 0 and row.put_ltp_change > 0:
                counters["put_long_buildup"] += 1

        threshold = max(2, int(len(chain) * 0.15))
        regimes = [name for name, count in counters.items() if count >= threshold]
        return regimes or ["mixed"]
