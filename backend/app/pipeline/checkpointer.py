from __future__ import annotations

import json

from redis.exceptions import RedisError

from app.core.redis import RedisManager
from app.pipeline.state import ApplyIQState


_FALLBACK_CHECKPOINTS: dict[str, str] = {}


class PipelineCheckpointer:
    def __init__(self, redis_manager: RedisManager) -> None:
        self._redis_manager = redis_manager

    async def save(self, run_id: str, state: ApplyIQState) -> None:
        payload = json.dumps(state)
        try:
            await self._redis_manager.client.set(self._redis_key(run_id), payload)
        except RedisError:
            _FALLBACK_CHECKPOINTS[run_id] = payload

    async def load(self, run_id: str) -> ApplyIQState | None:
        try:
            payload = await self._redis_manager.client.get(self._redis_key(run_id))
        except RedisError:
            payload = _FALLBACK_CHECKPOINTS.get(run_id)

        if not payload:
            return None
        return json.loads(payload)

    async def delete(self, run_id: str) -> None:
        try:
            await self._redis_manager.client.delete(self._redis_key(run_id))
        except RedisError:
            _FALLBACK_CHECKPOINTS.pop(run_id, None)

    def _redis_key(self, run_id: str) -> str:
        return f"applyiq:pipeline:{run_id}"
