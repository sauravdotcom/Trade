from __future__ import annotations

import math

from app.core.config import get_settings
from app.schemas.signal import RiskPlan


class RiskManager:
    LOT_SIZES = {
        "NIFTY": 75,
        "BANKNIFTY": 35,
    }

    def __init__(self) -> None:
        self.settings = get_settings()

    def generate_plan(
        self,
        symbol: str,
        option_price: float,
        capital: float | None = None,
        risk_per_trade: float | None = None,
    ) -> RiskPlan:
        capital = capital or self.settings.capital
        risk_per_trade = risk_per_trade or self.settings.max_risk_per_trade

        entry = round(option_price, 2)
        stop_loss = round(entry * 0.8, 2)
        target_1 = round(entry * 1.3, 2)
        target_2 = round(entry * 1.6, 2)

        risk_per_unit = max(entry - stop_loss, 0.01)
        max_risk_amount = capital * risk_per_trade
        max_units = math.floor(max_risk_amount / risk_per_unit)

        lot_size = self.LOT_SIZES.get(symbol.upper(), 50)
        quantity = max(lot_size, (max_units // lot_size) * lot_size)

        risk_reward = round((target_1 - entry) / risk_per_unit, 2)

        return RiskPlan(
            entry=entry,
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2,
            quantity=quantity,
            risk_reward=risk_reward,
        )
