from __future__ import annotations

from typing import Awaitable, Callable, cast

from fastapi import APIRouter, Request, Response, status

from app.core.constants import DEGRADED_STATUS, DOWN_STATUS, HEALTHY_STATUS
from app.schemas.health import HealthStatus


HealthReporter = Callable[[], Awaitable[dict[str, str]]]

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus, response_model_exclude_none=True)
async def healthcheck(request: Request, response: Response) -> HealthStatus:
    reporter = cast(HealthReporter, request.app.state.health_reporter)

    try:
        payload = await reporter()
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthStatus(status=DEGRADED_STATUS, db=DOWN_STATUS, redis=DOWN_STATUS)

    if payload["status"] != HEALTHY_STATUS:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthStatus.model_validate(payload)
