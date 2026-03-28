from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.applications import ApplicationDetailData, ApplicationsListData
from app.schemas.common import Envelope
from app.services.application_service import ApplicationService


router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=Envelope[ApplicationsListData])
async def list_applications(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[ApplicationsListData]:
    service = ApplicationService()
    data = await service.list_applications(session=session, user=current_user)
    return Envelope(success=True, data=data, error=None)


@router.get("/{application_id}", response_model=Envelope[ApplicationDetailData])
async def get_application_detail(
    application_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[ApplicationDetailData]:
    service = ApplicationService()
    data = await service.get_application_detail(session=session, user=current_user, application_id=application_id)
    return Envelope(success=True, data=data, error=None)
