from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

import httpx
import redis.asyncio as redis

from app.core.config import get_settings
from app.schemas.signal import TradeSignal


class AlertService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.redis = redis.from_url(self.settings.redis_url, decode_responses=True)

    async def close(self) -> None:
        await self.redis.aclose()

    async def dispatch(self, signal: TradeSignal, reasoning: str) -> None:
        if signal.signal_type == "NO_TRADE" or not signal.risk_plan:
            return

        message = self._format_message(signal, reasoning)

        tasks = [self._publish_web_alert(message)]
        if self.settings.telegram_bot_token and self.settings.telegram_chat_id:
            tasks.append(self._send_telegram(message))
        if self.settings.smtp_host and self.settings.alert_email_to:
            tasks.append(asyncio.to_thread(self._send_email, message))

        await asyncio.gather(*tasks, return_exceptions=True)

    def _format_message(self, signal: TradeSignal, reasoning: str) -> str:
        rp = signal.risk_plan
        return (
            f"{signal.instrument} {signal.signal_type} [{signal.lifecycle_status}]\n"
            f"Entry: {rp.entry}\n"
            f"SL: {rp.stop_loss}\n"
            f"Target1: {rp.target_1}\n"
            f"Target2: {rp.target_2}\n"
            f"Confidence: {signal.confidence}%\n"
            f"Reason: {reasoning}\n"
            f"Guidance: {signal.guidance or '-'}\n"
            f"Exit: {signal.exit_guidance or '-'}"
        )

    async def _publish_web_alert(self, message: str) -> None:
        await self.redis.publish("trade_alerts", message)

    async def _send_telegram(self, message: str) -> None:
        token = self.settings.telegram_bot_token
        chat_id = self.settings.telegram_chat_id
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        async with httpx.AsyncClient(timeout=4.0) as client:
            await client.post(url, json={"chat_id": chat_id, "text": message})

    def _send_email(self, message: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = "Trade Signal Alert"
        msg["From"] = self.settings.smtp_username or "trade-bot@example.com"
        msg["To"] = self.settings.alert_email_to
        msg.set_content(message)

        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=5) as smtp:
            smtp.starttls()
            if self.settings.smtp_username and self.settings.smtp_password:
                smtp.login(self.settings.smtp_username, self.settings.smtp_password)
            smtp.send_message(msg)
