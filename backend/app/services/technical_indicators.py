from __future__ import annotations

from datetime import datetime

import pandas as pd
from pydantic import BaseModel

from app.schemas.signal import IndicatorSnapshot


class PriceBar(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class IndicatorEngine:
    def compute(self, bars: list[PriceBar]) -> IndicatorSnapshot:
        if not bars:
            return IndicatorSnapshot(
                vwap=0,
                ema_9=0,
                ema_21=0,
                rsi=50,
                macd=0,
                macd_signal=0,
                atr=0,
                bollinger_upper=0,
                bollinger_lower=0,
            )

        frame = pd.DataFrame([bar.model_dump() for bar in bars])

        close = frame["close"].astype(float)
        high = frame["high"].astype(float)
        low = frame["low"].astype(float)
        volume = frame["volume"].astype(float).replace(0, 1)

        typical = (high + low + close) / 3
        vwap_series = (typical * volume).cumsum() / volume.cumsum()

        ema_9 = close.ewm(span=9, adjust=False).mean()
        ema_21 = close.ewm(span=21, adjust=False).mean()

        delta = close.diff().fillna(0)
        gains = delta.clip(lower=0)
        losses = (-delta).clip(lower=0)
        avg_gain = gains.rolling(14).mean().fillna(0)
        avg_loss = losses.rolling(14).mean().fillna(0)
        rs = avg_gain / avg_loss.replace(0, 1)
        rsi = 100 - (100 / (1 + rs))

        macd_fast = close.ewm(span=12, adjust=False).mean()
        macd_slow = close.ewm(span=26, adjust=False).mean()
        macd = macd_fast - macd_slow
        macd_signal = macd.ewm(span=9, adjust=False).mean()

        prev_close = close.shift(1).fillna(close)
        tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().fillna(tr)

        rolling_mean = close.rolling(20).mean().fillna(close.expanding().mean())
        rolling_std = close.rolling(20).std().fillna(0)
        bb_upper = rolling_mean + (2 * rolling_std)
        bb_lower = rolling_mean - (2 * rolling_std)

        return IndicatorSnapshot(
            vwap=round(float(vwap_series.iloc[-1]), 2),
            ema_9=round(float(ema_9.iloc[-1]), 2),
            ema_21=round(float(ema_21.iloc[-1]), 2),
            rsi=round(float(rsi.iloc[-1]), 2),
            macd=round(float(macd.iloc[-1]), 2),
            macd_signal=round(float(macd_signal.iloc[-1]), 2),
            atr=round(float(atr.iloc[-1]), 2),
            bollinger_upper=round(float(bb_upper.iloc[-1]), 2),
            bollinger_lower=round(float(bb_lower.iloc[-1]), 2),
        )
