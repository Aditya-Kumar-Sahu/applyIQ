from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from redis.exceptions import RedisError
import structlog

from app.core.redis import RedisManager
from app.pipeline.state import ApplyIQState


logger = structlog.get_logger(__name__)


class PipelineCheckpointer:
    def __init__(self, redis_manager: RedisManager, *, ttl_seconds: int) -> None:
        self._redis_manager = redis_manager
        self._ttl_seconds = ttl_seconds

    async def save(self, run_id: str, state: ApplyIQState) -> None:
        payload = json.dumps(
            {
                "version": 1,
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "state": state,
            },
            default=_json_default,
        )
        try:
            await self._redis_manager.client.set(self._redis_key(run_id), payload, ex=self._ttl_seconds)
        except RedisError as e:
            logger.warning("pipeline.checkpoint.redis_save_failed", run_id=run_id, error=str(e))

    async def load(self, run_id: str) -> ApplyIQState | None:
        try:
            if payload := await self._redis_manager.client.get(self._redis_key(run_id)):
                parsed = json.loads(payload)
                if isinstance(parsed, dict) and "state" in parsed:
                    return parsed["state"]
                return parsed
        except RedisError as e:
            logger.warning("pipeline.checkpoint.redis_load_failed", run_id=run_id, error=str(e))
        return None

    async def delete(self, run_id: str) -> None:
        try:
            await self._redis_manager.client.delete(self._redis_key(run_id))
        except RedisError as e:
            logger.warning("pipeline.checkpoint.redis_delete_failed", run_id=run_id, error=str(e))

    def _redis_key(self, run_id: str) -> str:
        return f"pipeline_run:{run_id}"


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(f"Type {type(value)!r} is not JSON serializable")
