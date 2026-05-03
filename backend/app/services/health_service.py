from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import structlog
from celery import Celery

from app.core.config import Settings
from app.core.constants import (
    DEGRADED_STATUS,
    DOWN_STATUS,
    HEALTHY_STATUS,
    NOT_CONFIGURED_STATUS,
    UP_STATUS,
)
from app.core.database import DatabaseManager
from app.core.logging_safety import log_debug
from app.core.redis import RedisManager

logger = structlog.get_logger(__name__)


class HealthService:
    def __init__(
        self,
        *,
        settings: Settings,
        database: DatabaseManager,
        redis: RedisManager,
        celery: Celery,
    ) -> None:
        self._settings = settings
        self._db = database
        self._redis = redis
        self._celery = celery
        self._cache_prefix = "health_check:"
        self._cache_ttl = 300  # 5 minutes

    async def get_report(self) -> dict[str, Any]:
        # Perform critical checks first
        db_ok, redis_ok = await asyncio.gather(
            self._db.ping(),
            self._redis.ping(),
        )

        # Non-blocking Celery checks
        broker_ok, workers_ok = await asyncio.gather(
            self._check_celery_broker(),
            self._check_celery_workers(),
        )

        # Determine core status (Hard Dependencies)
        is_hard_failure = not (db_ok and redis_ok and broker_ok and workers_ok)

        # Perform soft checks (External APIs) with caching
        api_statuses = {}
        if not self._settings.is_non_production:
            api_statuses = await self._check_external_apis()

        # Determine overall status
        any_soft_failure = any(s == DOWN_STATUS for s in api_statuses.values())
        
        status = HEALTHY_STATUS
        if is_hard_failure:
            status = DOWN_STATUS
        elif any_soft_failure:
            status = DEGRADED_STATUS

        payload = {
            "status": status,
            "db": UP_STATUS if db_ok else DOWN_STATUS,
            "redis": UP_STATUS if redis_ok else DOWN_STATUS,
            "celery": {
                "broker": UP_STATUS if broker_ok else DOWN_STATUS,
                "workers": UP_STATUS if workers_ok else DOWN_STATUS,
            },
            "is_hard_failure": is_hard_failure,
        }
        payload.update(api_statuses)
        return payload

    async def _check_celery_broker(self) -> bool:
        try:
            # check if we can connect to the broker
            def _check():
                with self._celery.connection_for_write() as conn:
                    conn.ensure_connection(max_retries=1)
                return True

            return await asyncio.to_thread(_check)
        except Exception:
            logger.warning("health_service.celery_broker_down")
            return False

    async def _check_celery_workers(self) -> bool:
        try:
            # ping workers with 1s timeout
            def _ping():
                # broadcast ping
                responses = self._celery.control.ping(timeout=1.0)
                return len(responses) > 0

            return await asyncio.wait_for(asyncio.to_thread(_ping), timeout=1.2)
        except Exception:
            logger.warning("health_service.celery_workers_unreachable")
            return False

    async def _check_external_apis(self) -> dict[str, str]:
        tasks = [
            self._probe_with_cache("apify", self._probe_apify),
            self._probe_with_cache("serpapi", self._probe_serpapi),
            self._probe_with_cache("remotive", self._probe_remotive),
            self._probe_with_cache("ai_provider", self._probe_gemini),
        ]
        results = await asyncio.gather(*tasks)
        return {name: status for name, status in results}

    async def _probe_with_cache(self, name: str, probe_func: callable) -> tuple[str, str]:
        cache_key = f"{self._cache_prefix}{name}"
        
        # Check cache
        cached_status = await self._redis.get(cache_key)
        if cached_status:
            return name, cached_status.decode("utf-8") if isinstance(cached_status, bytes) else cached_status

        # Perform probe
        status = await probe_func()
        
        # Cache result
        await self._redis.set(cache_key, status, ex=self._cache_ttl)
        return name, status

    async def _probe_url(self, url: str, params: dict = None, headers: dict = None) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                return True
        except Exception:
            return False

    async def _probe_apify(self) -> str:
        if not self._settings.apify_api_token:
            return NOT_CONFIGURED_STATUS
        is_up = await self._probe_url(
            "https://api.apify.com/v2/acts",
            headers={"Authorization": f"Bearer {self._settings.apify_api_token}"},
        )
        return UP_STATUS if is_up else DOWN_STATUS

    async def _probe_serpapi(self) -> str:
        if not self._settings.serpapi_api_key:
            return NOT_CONFIGURED_STATUS
        is_up = await self._probe_url(
            "https://serpapi.com/search",
            params={"engine": "google_jobs", "q": "ping", "api_key": self._settings.serpapi_api_key, "num": 1},
        )
        return UP_STATUS if is_up else DOWN_STATUS

    async def _probe_remotive(self) -> str:
        is_up = await self._probe_url(
            "https://remotive.com/api/remote-jobs",
            params={"limit": 1},
        )
        return UP_STATUS if is_up else DOWN_STATUS

    async def _probe_gemini(self) -> str:
        if not self._settings.gemini_api_key:
            return NOT_CONFIGURED_STATUS
        is_up = await self._probe_url(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": self._settings.gemini_api_key, "pageSize": 1},
        )
        return UP_STATUS if is_up else DOWN_STATUS
