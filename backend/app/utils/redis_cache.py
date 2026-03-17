from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis

from app.core.config import get_settings


class RedisCache:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = redis.from_url(settings.redis_url, decode_responses=True)

    async def close(self) -> None:
        await self.client.aclose()

    async def get_json(self, key: str) -> dict[str, Any] | None:
        raw = await self.client.get(key)
        if not raw:
            return None
        return json.loads(raw)

    async def set_json(self, key: str, value: dict[str, Any], ttl: int = 180) -> None:
        await self.client.set(key, json.dumps(value), ex=ttl)
