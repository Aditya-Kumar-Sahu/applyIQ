from __future__ import annotations

import time

from redis.exceptions import RedisError

from app.core.redis import RedisManager


class RedisRateLimiter:
    def __init__(self, redis_manager: RedisManager) -> None:
        self._redis_manager = redis_manager

    async def allow(self, *, key: str, limit: int, window_seconds: int) -> bool:
        bucket = int(time.time() // window_seconds)
        redis_key = f"rate_limit:{key}:{bucket}"
        try:
            current = await self._redis_manager.client.incr(redis_key)
            if current == 1:
                await self._redis_manager.client.expire(redis_key, window_seconds)
            return current <= limit
        except RedisError:
            # Degrade open when Redis is unavailable to avoid false negatives.
            return True
