from __future__ import annotations

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.schemas.market import OptionAnalysis
from app.schemas.signal import IndicatorSnapshot, TradeSignal


class AIReasoner:
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.openai_model
        self.client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    async def explain(self, signal: TradeSignal, analysis: OptionAnalysis, indicators: IndicatorSnapshot) -> str:
        if signal.signal_type == "NO_TRADE":
            if signal.exit_guidance:
                return signal.exit_guidance
            return signal.reason

        if not self.client:
            return (
                f"{signal.signal_type} validated: PCR={analysis.pcr}, support={analysis.support_strike}, "
                f"resistance={analysis.resistance_strike}, VWAP={indicators.vwap}, RSI={indicators.rsi}."
            )

        prompt = (
            "You are an options trading assistant. In <=40 words, explain why this signal is valid and mention "
            "PCR, OI zone, VWAP relation and one momentum confirmation. "
            f"Signal={signal.model_dump_json()} Analysis={analysis.model_dump_json()} "
            f"Indicators={indicators.model_dump_json()}"
        )

        try:
            response = await self.client.responses.create(
                model=self.model,
                input=prompt,
                temperature=0.1,
                max_output_tokens=120,
            )
            text = response.output_text.strip()
            return text or signal.reason
        except Exception:
            return signal.reason
