from __future__ import annotations

import abc
import random
from datetime import UTC, date, datetime, timedelta

import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

from app.core.config import get_settings
from app.schemas.market import MarketSnapshot, OptionRow


class BaseBrokerAdapter(abc.ABC):
    name = "base"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = httpx.AsyncClient(timeout=2.0)

    async def close(self) -> None:
        await self.client.aclose()

    @abc.abstractmethod
    async def fetch_spot(self, symbol: str) -> float:
        raise NotImplementedError

    @abc.abstractmethod
    async def fetch_options_chain(self, symbol: str, spot: float) -> list[OptionRow]:
        raise NotImplementedError


class MockBrokerAdapter(BaseBrokerAdapter):
    name = "mock"

    async def fetch_spot(self, symbol: str) -> float:
        base = 23500 if symbol.upper() == "NIFTY" else 51200
        return round(base + random.uniform(-35, 35), 2)

    async def fetch_options_chain(self, symbol: str, spot: float) -> list[OptionRow]:
        step = 50 if symbol.upper() == "NIFTY" else 100
        atm = round(spot / step) * step
        chain: list[OptionRow] = []

        for strike in range(int(atm - 10 * step), int(atm + 10 * step) + step, step):
            distance = abs(strike - spot)
            base_oi = max(12000 - int(distance * 9), 1200)
            call_oi = max(base_oi + random.randint(-1500, 1500), 200)
            put_oi = max(base_oi + random.randint(-1500, 1500), 200)
            call_price = max(20, (spot - strike) * 0.48 + 118 + random.uniform(-7, 7))
            put_price = max(20, (strike - spot) * 0.48 + 118 + random.uniform(-7, 7))
            chain.append(
                OptionRow(
                    strike=float(strike),
                    call_oi=int(call_oi),
                    put_oi=int(put_oi),
                    call_oi_change=random.randint(-900, 900),
                    put_oi_change=random.randint(-900, 900),
                    call_ltp=round(call_price, 2),
                    put_ltp=round(put_price, 2),
                    call_ltp_change=round(random.uniform(-5.0, 5.0), 2),
                    put_ltp_change=round(random.uniform(-5.0, 5.0), 2),
                    iv=round(random.uniform(10, 22), 2),
                    volume=random.randint(3000, 40000),
                    gamma=round(random.uniform(-0.02, 0.02), 5),
                )
            )
        return chain


class NsePublicAdapter(BaseBrokerAdapter):
    name = "nse"
    OPTION_CHAIN_URL = "https://www.nseindia.com/api/option-chain-indices"
    ALL_INDICES_URL = "https://www.nseindia.com/api/allIndices"
    BOOTSTRAP_URL = "https://www.nseindia.com/option-chain"

    def __init__(self) -> None:
        super().__init__()
        self.client = httpx.AsyncClient(timeout=4.0, headers=self._headers())
        self._bootstrapped_until: datetime | None = None
        self._payload_cache: dict[str, tuple[datetime, dict]] = {}
        self._indices_cache: tuple[datetime, dict] | None = None

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/option-chain",
        }

    async def _ensure_bootstrap(self) -> None:
        now = datetime.now(UTC)
        if self._bootstrapped_until and now < self._bootstrapped_until:
            return
        await self.client.get(self.BOOTSTRAP_URL)
        self._bootstrapped_until = now + timedelta(minutes=10)

    async def _fetch_payload(self, symbol: str) -> dict:
        now = datetime.now(UTC)
        cached = self._payload_cache.get(symbol)
        if cached and (now - cached[0]).total_seconds() <= 2.0:
            return cached[1]

        await self._ensure_bootstrap()
        response = await self.client.get(self.OPTION_CHAIN_URL, params={"symbol": symbol})
        response.raise_for_status()
        payload = response.json()
        self._payload_cache[symbol] = (now, payload)
        return payload

    async def _fetch_indices_payload(self) -> dict:
        now = datetime.now(UTC)
        if self._indices_cache and (now - self._indices_cache[0]).total_seconds() <= 2.0:
            return self._indices_cache[1]

        await self._ensure_bootstrap()
        response = await self.client.get(self.ALL_INDICES_URL)
        response.raise_for_status()
        payload = response.json()
        self._indices_cache = (now, payload)
        return payload

    @retry(wait=wait_fixed(0.4), stop=stop_after_attempt(2))
    async def fetch_spot(self, symbol: str) -> float:
        payload = await self._fetch_indices_payload()
        rows = payload.get("data", [])
        target = "NIFTY 50" if symbol.upper() == "NIFTY" else "NIFTY BANK"
        for row in rows:
            if row.get("index") == target:
                last = row.get("last")
                if last is not None:
                    return float(last)
        raise ValueError(f"NSE spot unavailable for {symbol}")

    @retry(wait=wait_fixed(0.4), stop=stop_after_attempt(2))
    async def fetch_options_chain(self, symbol: str, spot: float) -> list[OptionRow]:
        payload = await self._fetch_payload(symbol.upper())
        records = payload.get("records", {})
        rows = records.get("data", [])
        parsed: list[OptionRow] = []

        for row in rows:
            strike = row.get("strikePrice")
            if strike is None:
                continue

            ce = row.get("CE") or {}
            pe = row.get("PE") or {}

            call_oi = int(ce.get("openInterest") or 0)
            put_oi = int(pe.get("openInterest") or 0)
            if call_oi == 0 and put_oi == 0:
                continue

            call_iv = float(ce.get("impliedVolatility") or 0.0)
            put_iv = float(pe.get("impliedVolatility") or 0.0)
            iv_values = [value for value in (call_iv, put_iv) if value > 0]
            avg_iv = sum(iv_values) / len(iv_values) if iv_values else 0.0

            parsed.append(
                OptionRow(
                    strike=float(strike),
                    call_oi=call_oi,
                    put_oi=put_oi,
                    call_oi_change=int(ce.get("changeinOpenInterest") or 0),
                    put_oi_change=int(pe.get("changeinOpenInterest") or 0),
                    call_ltp=float(ce.get("lastPrice") or 0.0),
                    put_ltp=float(pe.get("lastPrice") or 0.0),
                    call_ltp_change=float(ce.get("change") or 0.0),
                    put_ltp_change=float(pe.get("change") or 0.0),
                    iv=round(avg_iv, 2),
                    volume=int(ce.get("totalTradedVolume") or 0) + int(pe.get("totalTradedVolume") or 0),
                    gamma=0.0,
                )
            )

        return sorted(parsed, key=lambda item: item.strike)


class KiteAdapter(BaseBrokerAdapter):
    name = "kite"

    @property
    def headers(self) -> dict[str, str]:
        settings = self.settings
        return {
            "X-Kite-Version": "3",
            "Authorization": f"token {settings.kite_api_key}:{settings.kite_access_token}",
        }

    @retry(wait=wait_fixed(0.2), stop=stop_after_attempt(2))
    async def fetch_spot(self, symbol: str) -> float:
        mapped = "NIFTY 50" if symbol.upper() == "NIFTY" else "NIFTY BANK"
        url = f"https://api.kite.trade/quote/ltp?i=NSE:{mapped}"
        response = await self.client.get(url, headers=self.headers)
        response.raise_for_status()
        payload = response.json()
        return float(payload["data"][f"NSE:{mapped}"]["last_price"])

    async def fetch_options_chain(self, symbol: str, spot: float) -> list[OptionRow]:
        # Kite does not expose a direct options-chain endpoint. In production,
        # map option trading symbols and batch-quote them here.
        return []


class AngelAdapter(BaseBrokerAdapter):
    name = "angel"

    @retry(wait=wait_fixed(0.2), stop=stop_after_attempt(2))
    async def fetch_spot(self, symbol: str) -> float:
        token = "99926000" if symbol.upper() == "NIFTY" else "99926009"
        url = "https://apiconnect.angelone.in/rest/secure/angelbroking/market/v1/quote"
        headers = {
            "X-PrivateKey": self.settings.angel_api_key or "",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        body = {"mode": "LTP", "exchangeTokens": {"NSE": [token]}}
        response = await self.client.post(url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()
        fetched = data.get("data", {}).get("fetched", [])
        if not fetched:
            raise ValueError("Angel spot response missing data")
        return float(fetched[0]["ltp"])

    async def fetch_options_chain(self, symbol: str, spot: float) -> list[OptionRow]:
        return []


class UpstoxAdapter(BaseBrokerAdapter):
    name = "upstox"
    CHAIN_ENDPOINTS = [
        "https://api.upstox.com/v2/option/chain",
        "https://api.upstox.com/v2/option-chain",
    ]
    CONTRACT_ENDPOINTS = [
        "https://api.upstox.com/v2/option/contract",
        "https://api.upstox.com/v2/option/contracts",
    ]

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.upstox_access_token}",
            "Accept": "application/json",
        }

    @retry(wait=wait_fixed(0.2), stop=stop_after_attempt(2))
    async def fetch_spot(self, symbol: str) -> float:
        instrument = self._instrument_key(symbol)
        url = "https://api.upstox.com/v2/market-quote/ltp"
        response = await self.client.get(url, headers=self.headers, params={"instrument_key": instrument})
        response.raise_for_status()
        data = response.json()["data"]
        return float(data[instrument]["last_price"])

    async def fetch_options_chain(self, symbol: str, spot: float) -> list[OptionRow]:
        instrument = self._instrument_key(symbol)
        expiry = await self._resolve_nearest_expiry(instrument)
        if not expiry:
            return []

        rows = await self._fetch_chain_rows(instrument, expiry)
        parsed: list[OptionRow] = []

        for row in rows:
            strike = row.get("strike_price") or row.get("strike")
            if strike is None:
                continue

            call_node = row.get("call_options") or row.get("ce") or {}
            put_node = row.get("put_options") or row.get("pe") or {}

            call_market = call_node.get("market_data") or call_node
            put_market = put_node.get("market_data") or put_node
            call_greeks = call_node.get("option_greeks") or {}
            put_greeks = put_node.get("option_greeks") or {}

            call_oi = int(call_market.get("oi") or call_market.get("open_interest") or 0)
            put_oi = int(put_market.get("oi") or put_market.get("open_interest") or 0)
            if call_oi == 0 and put_oi == 0:
                continue

            call_iv = float(call_greeks.get("iv") or call_market.get("iv") or 0.0)
            put_iv = float(put_greeks.get("iv") or put_market.get("iv") or 0.0)
            iv_values = [value for value in (call_iv, put_iv) if value > 0]
            avg_iv = sum(iv_values) / len(iv_values) if iv_values else 0.0

            gamma_values = [value for value in (call_greeks.get("gamma"), put_greeks.get("gamma")) if value is not None]
            avg_gamma = float(sum(gamma_values) / len(gamma_values)) if gamma_values else 0.0

            parsed.append(
                OptionRow(
                    strike=float(strike),
                    call_oi=call_oi,
                    put_oi=put_oi,
                    call_oi_change=int(call_market.get("oi_day_change") or call_market.get("change_oi") or 0),
                    put_oi_change=int(put_market.get("oi_day_change") or put_market.get("change_oi") or 0),
                    call_ltp=float(call_market.get("ltp") or call_market.get("last_price") or 0.0),
                    put_ltp=float(put_market.get("ltp") or put_market.get("last_price") or 0.0),
                    call_ltp_change=float(call_market.get("net_change") or call_market.get("change") or 0.0),
                    put_ltp_change=float(put_market.get("net_change") or put_market.get("change") or 0.0),
                    iv=round(avg_iv, 2),
                    volume=int(call_market.get("volume") or 0) + int(put_market.get("volume") or 0),
                    gamma=round(avg_gamma, 6),
                )
            )

        return sorted(parsed, key=lambda item: item.strike)

    def _instrument_key(self, symbol: str) -> str:
        return "NSE_INDEX|Nifty 50" if symbol.upper() == "NIFTY" else "NSE_INDEX|Nifty Bank"

    async def _resolve_nearest_expiry(self, instrument_key: str) -> str | None:
        today = date.today()

        for endpoint in self.CONTRACT_ENDPOINTS:
            try:
                response = await self.client.get(
                    endpoint,
                    headers=self.headers,
                    params={"instrument_key": instrument_key},
                )
                if response.status_code >= 400:
                    continue
                payload = response.json()
                rows = payload.get("data", [])
                expiries: list[date] = []
                for row in rows:
                    expiry_str = row.get("expiry") or row.get("expiry_date")
                    if not expiry_str:
                        continue
                    try:
                        parsed = datetime.fromisoformat(expiry_str.replace("Z", "")).date()
                    except ValueError:
                        continue
                    if parsed >= today:
                        expiries.append(parsed)
                if expiries:
                    return min(expiries).isoformat()
            except Exception:
                continue

        return None

    async def _fetch_chain_rows(self, instrument_key: str, expiry: str) -> list[dict]:
        for endpoint in self.CHAIN_ENDPOINTS:
            try:
                response = await self.client.get(
                    endpoint,
                    headers=self.headers,
                    params={"instrument_key": instrument_key, "expiry_date": expiry},
                )
                if response.status_code >= 400:
                    continue
                payload = response.json()
                rows = payload.get("data", [])
                if rows:
                    return rows
            except Exception:
                continue
        return []


class MarketDataService:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.mock = MockBrokerAdapter()
        self.adapters: list[BaseBrokerAdapter] = []

        if settings.use_nse_public_feed:
            self.adapters.append(NsePublicAdapter())
        if settings.kite_api_key and settings.kite_access_token:
            self.adapters.append(KiteAdapter())
        if settings.angel_api_key and settings.angel_client_code:
            self.adapters.append(AngelAdapter())
        if settings.upstox_api_key and settings.upstox_access_token:
            self.adapters.append(UpstoxAdapter())

        if not self.adapters and settings.allow_mock_fallback:
            self.adapters = [self.mock]

    async def close(self) -> None:
        for adapter in self.adapters:
            await adapter.close()

    async def _fetch_from_adapter(self, adapter: BaseBrokerAdapter, symbol: str) -> tuple[float, list[OptionRow]] | None:
        try:
            spot = await adapter.fetch_spot(symbol)
            chain = await adapter.fetch_options_chain(symbol, spot)
            if not chain and self.settings.allow_mock_fallback:
                chain = await self.mock.fetch_options_chain(symbol, spot)
            if not chain:
                return None
            return spot, chain
        except Exception:
            return None

    async def get_snapshot(self, symbol: str) -> MarketSnapshot:
        normalized = symbol.upper().strip()
        for adapter in self.adapters:
            result = await self._fetch_from_adapter(adapter, normalized)
            if result:
                spot, chain = result
                return MarketSnapshot(symbol=normalized, spot_price=spot, chain=chain, timestamp=datetime.now(UTC))

        if self.settings.allow_mock_fallback:
            spot = await self.mock.fetch_spot(normalized)
            chain = await self.mock.fetch_options_chain(normalized, spot)
            return MarketSnapshot(symbol=normalized, spot_price=spot, chain=chain, timestamp=datetime.now(UTC))

        raise RuntimeError(f"Live market data unavailable for {normalized}.")
