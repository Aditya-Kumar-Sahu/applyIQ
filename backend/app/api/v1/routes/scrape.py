from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.common import Envelope
from app.schemas.jobs import ScrapeTestData, ScrapeTestRequest
from app.scrapers.base import ScrapeQuery
from app.scrapers.deduplicator import JobDeduplicator
from app.services.embedding_service import EmbeddingService
from app.services.scrape_service import ScrapeService


router = APIRouter(prefix="/scrape", tags=["scrape"])


def _build_scrape_service() -> ScrapeService:
    return ScrapeService(
        embedding_service=EmbeddingService(),
        deduplicator=JobDeduplicator(),
    )


@router.post("/test", response_model=Envelope[ScrapeTestData])
async def scrape_test(
    payload: ScrapeTestRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[ScrapeTestData]:
    _ = current_user
    service = _build_scrape_service()
    result = await service.run_test_scrape(
        session=session,
        query=ScrapeQuery(
            target_role=payload.target_role,
            location=payload.location,
            limit_per_source=payload.limit_per_source,
        ),
        sources=payload.sources,
    )
    return Envelope(success=True, data=result, error=None)
