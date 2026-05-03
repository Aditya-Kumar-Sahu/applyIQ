from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast

from fastapi import APIRouter, Request, Response, status

from app.core.constants import HEALTHY_STATUS
from app.schemas.health import HealthStatus

HealthReporter = Callable[[], Awaitable[dict[str, Any]]]

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus, response_model_exclude_none=True)
async def healthcheck(request: Request, response: Response) -> HealthStatus:
    reporter = cast(HealthReporter, request.app.state.health_reporter)

    try:
        payload = await reporter()
        
        # If any hard dependency is down, return 503
        if payload.get("is_hard_failure", False):
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        
        # We still return the payload so monitoring can see WHAT is down
        return HealthStatus.model_validate(payload)
        
    except Exception:
        # Fallback for catastrophic service failure
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthStatus(
            status="down",
            db="down",
            redis="down",
            celery={"broker": "down", "workers": "down"}
        )
