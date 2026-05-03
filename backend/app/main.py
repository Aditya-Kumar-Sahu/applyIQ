from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.v1.router import router as api_v1_router
from app.core.config import Settings, get_settings
from app.core.database import DatabaseManager
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.observability import configure_observability
from app.core.redis import RedisManager
from app.services.health_service import HealthService
from app.worker import celery_app

HealthReporter = Callable[[], Awaitable[dict[str, Any]]]
logger = structlog.get_logger(__name__)


def create_app(
    settings: Settings | None = None,
    health_reporter: HealthReporter | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
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
    database = DatabaseManager(resolved_settings.database_url.get_secret_value())
    redis = RedisManager(resolved_settings.redis_url.get_secret_value())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        resolved_settings.validate_security_contract()
        logger.info("app.startup", environment=resolved_settings.environment)
        yield
        await app.state.database.dispose()
        await app.state.redis.close()
        logger.info("app.shutdown")

    app = FastAPI(title=resolved_settings.app_name, lifespan=lifespan)
    app.state.settings = resolved_settings
    app.state.database = database
    app.state.redis = redis
    app.state.health_service = HealthService(
        settings=resolved_settings,
        database=database,
        redis=redis,
        celery=celery_app,
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)

    if health_reporter is None:
        app.state.health_reporter = app.state.health_service.get_report
    else:
        app.state.health_reporter = health_reporter

    app.include_router(health_router)
    app.include_router(api_v1_router, prefix=resolved_settings.api_v1_prefix)
    return app


app = create_app()
