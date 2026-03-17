from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import httpx

from app.core.config import get_settings


class NseMarketClock:
    HOLIDAY_URL = "https://www.nseindia.com/api/holiday-master?type=trading"
    BOOTSTRAP_URL = "https://www.nseindia.com/"

    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.timezone = ZoneInfo(settings.nse_timezone)
        self.market_open = self._parse_time(settings.nse_market_open)
        self.market_close = self._parse_time(settings.nse_market_close)

        self._holiday_dates: set[date] = set()
        self._last_refresh_utc: datetime | None = None
        self._client = httpx.AsyncClient(timeout=4.0, headers=self._headers())

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/",
        }

    def _parse_time(self, value: str) -> time:
        hour, minute = value.split(":")
        return time(hour=int(hour), minute=int(minute))

    async def close(self) -> None:
        await self._client.aclose()

    async def refresh_holidays(self, force: bool = False) -> None:
        now_utc = datetime.now(UTC)
        if not force and self._last_refresh_utc and (now_utc - self._last_refresh_utc).total_seconds() < 6 * 3600:
            return

        try:
            await self._client.get(self.BOOTSTRAP_URL)
            response = await self._client.get(self.HOLIDAY_URL)
            response.raise_for_status()
            payload = response.json()
            self._holiday_dates = self._extract_holidays(payload)
            self._last_refresh_utc = now_utc
        except Exception:
            if self._last_refresh_utc is None:
                self._holiday_dates = set()

    def is_market_open(self, now: datetime | None = None) -> bool:
        current = (now or datetime.now(UTC)).astimezone(self.timezone)

        if current.weekday() >= 5:
            return False

        if current.date() in self._holiday_dates:
            return False

        current_time = current.time()
        return self.market_open <= current_time < self.market_close

    def status_message(self, now: datetime | None = None) -> str:
        current = (now or datetime.now(UTC)).astimezone(self.timezone)
        is_open = self.is_market_open(now)
        state = "OPEN" if is_open else "CLOSED"
        return f"NSE market is {state} ({current.strftime('%Y-%m-%d %H:%M:%S %Z')})."

    def _extract_holidays(self, payload: dict) -> set[date]:
        parsed: set[date] = set()

        def add_from_rows(rows: list[dict]) -> None:
            for row in rows:
                value = row.get("tradingDate") or row.get("date")
                if not value:
                    continue
                parsed_date = self._parse_holiday_date(value)
                if parsed_date:
                    parsed.add(parsed_date)

        if isinstance(payload, dict):
            if "FO" in payload and isinstance(payload["FO"], list):
                add_from_rows(payload["FO"])
            if "CM" in payload and isinstance(payload["CM"], list):
                add_from_rows(payload["CM"])
            if "data" in payload and isinstance(payload["data"], list):
                add_from_rows(payload["data"])

        return parsed

    def _parse_holiday_date(self, value: str) -> date | None:
        for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return None
