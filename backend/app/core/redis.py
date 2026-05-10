from __future__ import annotations

import json
from typing import Any

from redis import Redis as SyncRedis
from redis.asyncio import Redis
from redis.exceptions import RedisError

_redis_manager: RedisManager | None = None


class RedisManager:
    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._client: Redis | None = None
        self._sync_client: SyncRedis | None = None

    @property
    def client(self) -> Redis:
        if self._client is None:
            self._client = Redis.from_url(self._redis_url, decode_responses=True)
        return self._client

    @property
    def sync_client(self) -> SyncRedis:
        if self._sync_client is None:
            self._sync_client = SyncRedis.from_url(self._redis_url, decode_responses=True)
        return self._sync_client

    async def ping(self) -> bool:
        try:
            return bool(await self.client.ping())
        except RedisError:
            return False

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_value(self, key: str) -> Any | None:
        try:
            value = await self.client.get(key)
            if value is None:
                return None
            return json.loads(value)
        except (RedisError, json.JSONDecodeError):
            return None

    async def set_value(self, key: str, value: Any, ttl: int | None = None) -> bool:
        try:
            serialized = json.dumps(value)
            await self.client.set(key, serialized, ex=ttl)
            return True
        except (RedisError, TypeError):
            return False

    async def delete_value(self, key: str) -> bool:
        try:
            await self.client.delete(key)
            return True
        except RedisError:
            return False

    async def delete_pattern(self, pattern: str) -> int:
        try:
            count = 0
            async for key in self.client.scan_iter(match=pattern):
                await self.client.delete(key)
                count += 1
            return count
        except RedisError:
            return 0

    def delete_pattern_sync(self, pattern: str) -> int:
        try:
            count = 0
            for key in self.sync_client.scan_iter(match=pattern):
                self.sync_client.delete(key)
                count += 1
            return count
        except RedisError:
            return 0

    def get_value_sync(self, key: str) -> Any | None:
        try:
            value = self.sync_client.get(key)
            if value is None:
                return None
            return json.loads(value)
        except (RedisError, json.JSONDecodeError):
            return None

    def set_value_sync(self, key: str, value: Any, ttl: int | None = None) -> bool:
        try:
            serialized = json.dumps(value)
            self.sync_client.set(key, serialized, ex=ttl)
            return True
        except (RedisError, TypeError):
            return False


def init_redis(redis_url: str) -> RedisManager:
    global _redis_manager
    _redis_manager = RedisManager(redis_url)
    return _redis_manager


def get_redis_manager() -> RedisManager:
    if _redis_manager is None:
        raise RuntimeError("RedisManager not initialized. Call init_redis() first.")
    return _redis_manager
