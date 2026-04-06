from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.v1.deps import get_current_user_stream
from app.models.user import User
from app.services.email_monitor_service import EmailMonitorService


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def notifications_stream(
    request: Request,
    current_user: User = Depends(get_current_user_stream),
):
    service = EmailMonitorService()

    async with request.app.state.database.session() as session:
        payload = await service.get_notifications_event(session=session, user=current_user)

    async def event_stream():
        yield payload

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/stream")
async def notifications_live_stream(
    request: Request,
    poll_interval_seconds: float = 5.0,
    current_user: User = Depends(get_current_user_stream),
):
    service = EmailMonitorService()

    async def event_stream():
        async for event in service.stream_notifications_events(
            database=request.app.state.database,
            user=current_user,
            poll_interval_seconds=poll_interval_seconds,
        ):
            if await request.is_disconnected():
                break
            yield event

    return StreamingResponse(event_stream(), media_type="text/event-stream")
