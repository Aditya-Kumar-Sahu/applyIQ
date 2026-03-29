from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Awaitable, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
import structlog

from app.api.routes.health import router as health_router
from app.api.v1.router import router as api_v1_router
from app.core.config import Settings, get_settings
from app.core.constants import (
    DEGRADED_STATUS,
    DOWN_STATUS,
    FIXTURE_STATUS,
    HEALTHY_STATUS,
    NOT_CONFIGURED_STATUS,
    UP_STATUS,
)
from app.core.database import DatabaseManager
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.observability import configure_observability
from app.core.redis import RedisManager

HealthReporter = Callable[[], Awaitable[dict[str, str]]]
logger = structlog.get_logger(__name__)


async def _probe_url(
    *,
    url: str,
    params: dict[str, str | int] | None = None,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 5.0,
) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
    except Exception:
        logger.warning("probe_url_failed", url=url, params=params, headers=headers)
        return False
    return True


async def _probe_apify(token: str) -> str:
    is_up = await _probe_url(
        url=f"https://api.apify.com/v2/acts",
        headers={"Authorization": f"Bearer {token}"},
    )
    return UP_STATUS if is_up else DOWN_STATUS


async def _probe_serpapi(api_key: str) -> str:
    is_up = await _probe_url(
        url="https://serpapi.com/search",
        params={"engine": "google_jobs", "q": "software engineer", "api_key": api_key, "num": 1},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    return UP_STATUS if is_up else DOWN_STATUS


async def _probe_remotive() -> str:
    is_up = await _probe_url(
        url="https://remotive.com/api/remote-jobs",
        params={"search": "software engineer", "limit": 1},
    )
    return UP_STATUS if is_up else DOWN_STATUS


async def _probe_gemini(api_key: str) -> str:
    is_up = await _probe_url(
        url="https://generativelanguage.googleapis.com/v1beta/models",
        params={"key": api_key, "pageSize": 1},
    )
    return UP_STATUS if is_up else DOWN_STATUS


async def _build_external_api_statuses(settings: Settings) -> dict[str, str]:
    async def apify_status() -> str:
        if not settings.apify_api_token:
            return NOT_CONFIGURED_STATUS
        return await _probe_apify(settings.apify_api_token)

    async def serpapi_status() -> str:
        if not settings.serpapi_api_key:
            return NOT_CONFIGURED_STATUS
        return await _probe_serpapi(settings.serpapi_api_key)

    async def ai_provider_status() -> str:
        if not settings.gemini_api_key:
            return NOT_CONFIGURED_STATUS
        return await _probe_gemini(settings.gemini_api_key)

    apify, serpapi, remotive, ai_provider = await asyncio.gather(
        apify_status(),
        serpapi_status(),
        _probe_remotive(),
        ai_provider_status(),
    )
    return {
        "apify": apify,
        "serpapi": serpapi,
        "remotive": remotive,
        "indeed": FIXTURE_STATUS,
        "wellfound": FIXTURE_STATUS,
        "ai_provider": ai_provider,
    }


def _is_degraded(*, db_ok: bool, redis_ok: bool, api_statuses: dict[str, str] | None) -> bool:
    if not db_ok or not redis_ok:
        return True

    if api_statuses is None:
        return False

    required_api_fields = ("apify", "serpapi", "remotive")
    if any(api_statuses[field] != UP_STATUS for field in required_api_fields):
        return True

    ai_provider_status = api_statuses.get("ai_provider")
    if ai_provider_status not in {None, NOT_CONFIGURED_STATUS, UP_STATUS}:
        return True

    return False


def create_app(
    settings: Settings | None = None,
    health_reporter: HealthReporter | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_settings.validate_security_contract()
    configure_logging(
        log_level=resolved_settings.log_level,
        log_to_file=resolved_settings.log_to_file,
        log_dir=resolved_settings.log_dir,
        log_file_name=resolved_settings.log_file_name,
        log_file_max_bytes=resolved_settings.log_file_max_bytes,
        log_file_backup_count=resolved_settings.log_file_backup_count,
    )
    configure_observability(resolved_settings)
    logger = structlog.get_logger(__name__)
    database = DatabaseManager(resolved_settings.database_url)
    redis = RedisManager(resolved_settings.redis_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("app.startup", environment=resolved_settings.environment)
        yield
        await app.state.database.dispose()
        await app.state.redis.close()
        logger.info("app.shutdown")

    app = FastAPI(title=resolved_settings.app_name, lifespan=lifespan)
    app.state.settings = resolved_settings
    app.state.database = database
    app.state.redis = redis
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)

    if health_reporter is None:

        async def default_health_reporter() -> dict[str, str]:
            db_ok, redis_ok = await asyncio.gather(
                app.state.database.ping(),
                app.state.redis.ping(),
            )

            api_statuses: dict[str, str] | None = None
            if not resolved_settings.is_non_production:
                api_statuses = await _build_external_api_statuses(resolved_settings)

            payload = {
                "status": HEALTHY_STATUS
                if not _is_degraded(db_ok=db_ok, redis_ok=redis_ok, api_statuses=api_statuses)
                else DEGRADED_STATUS,
                "db": UP_STATUS if db_ok else DOWN_STATUS,
                "redis": UP_STATUS if redis_ok else DOWN_STATUS,
            }
            if api_statuses is not None:
                payload.update(api_statuses)
            return payload

        app.state.health_reporter = default_health_reporter
    else:
        app.state.health_reporter = health_reporter

    app.include_router(health_router)
    app.include_router(api_v1_router, prefix=resolved_settings.api_v1_prefix)
    return app


app = create_app()
