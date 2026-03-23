from __future__ import annotations

from redis.asyncio import Redis
from redis.exceptions import RedisError


class RedisManager:
    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._client: Redis | None = None

    @property
    def client(self) -> Redis:
        if self._client is None:
            self._client = Redis.from_url(self._redis_url, decode_responses=True)
        return self._client

    async def ping(self) -> bool:
        try:
            return bool(await self.client.ping())
        except RedisError:
            return False

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
