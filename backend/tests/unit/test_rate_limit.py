from __future__ import annotations

import anyio
from redis.exceptions import RedisError

from app.core.rate_limit import RedisRateLimiter


class _FailingRedisClient:
    @property
    def client(self) -> "_FailingRedisClient":
        return self

    async def incr(self, key: str) -> int:
        raise RedisError("redis unavailable")

    async def expire(self, key: str, window_seconds: int) -> bool:
        return True


def test_rate_limiter_fails_closed_for_sensitive_paths_when_redis_is_down() -> None:
    limiter = RedisRateLimiter(_FailingRedisClient())

    async def _call() -> bool:
        return await limiter.allow(
            key="pipeline_start:user-123",
            limit=1,
            window_seconds=60,
            fail_open=False,
        )

    allowed = anyio.run(_call)

    assert allowed is False
