from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db_session
from app.models.user import User
from app.services.email_monitor_service import EmailMonitorService


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def notifications_stream(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    service = EmailMonitorService()

    async def event_stream():
        yield await service.get_notifications_event(session=session, user=current_user)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
