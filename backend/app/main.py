from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Awaitable, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.api.routes.health import router as health_router
from app.api.v1.router import router as api_v1_router
from app.core.config import Settings, get_settings
from app.core.constants import DEGRADED_STATUS, DOWN_STATUS, HEALTHY_STATUS, UP_STATUS
from app.core.database import DatabaseManager
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.observability import configure_observability
from app.core.redis import RedisManager

HealthReporter = Callable[[], Awaitable[dict[str, str]]]


def create_app(
    settings: Settings | None = None,
    health_reporter: HealthReporter | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
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
            db_ok = await app.state.database.ping()
            redis_ok = await app.state.redis.ping()
            return {
                "status": HEALTHY_STATUS if db_ok and redis_ok else DEGRADED_STATUS,
                "db": UP_STATUS if db_ok else DOWN_STATUS,
                "redis": UP_STATUS if redis_ok else DOWN_STATUS,
            }

        app.state.health_reporter = default_health_reporter
    else:
        app.state.health_reporter = health_reporter

    app.include_router(health_router)
    app.include_router(api_v1_router, prefix=resolved_settings.api_v1_prefix)
    return app


app = create_app()
