from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.schemas.health import CeleryStatus, HealthStatus

HealthReporter = Callable[[], Awaitable[dict[str, Any]]]

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus, response_model_exclude_none=True)
async def healthcheck(request: Request, response: Response) -> HealthStatus:
    reporter = cast(HealthReporter, request.app.state.health_reporter)

    try:
        payload = await reporter()

        if payload.get("is_hard_failure", False):
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        return HealthStatus.model_validate(payload)

    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthStatus(status="down", db="down", redis="down", celery=CeleryStatus(broker="down", workers="down"))


async def _verify_metrics_secret(request: Request):
    # Support both Bearer and custom header for flexibility
    expected = request.app.state.settings.project_slug + "-metrics-secret"
    provided_custom = request.headers.get("X-Metrics-Secret")
    provided_auth = request.headers.get("Authorization")

    is_valid = False
    if provided_custom == expected or provided_auth == f"Bearer {expected}":
        is_valid = True

    if not request.app.state.settings.is_non_production and not is_valid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized metrics access")


@router.get("/metrics", dependencies=[Depends(_verify_metrics_secret)])
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
