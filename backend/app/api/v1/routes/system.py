from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.common import Envelope
from app.schemas.meta import MetaPayload


router = APIRouter(tags=["system"])


@router.get("/meta", response_model=Envelope[MetaPayload])
async def meta() -> Envelope[MetaPayload]:
    settings = get_settings()
    return Envelope(
        success=True,
        data=MetaPayload(service=settings.project_slug, environment=settings.environment),
        error=None,
    )
