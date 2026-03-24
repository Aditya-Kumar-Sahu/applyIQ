from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.common import Envelope
from app.schemas.match import JobDetailData, JobsListData
from app.services.embedding_service import EmbeddingService
from app.services.match_rank_service import MatchRankService


router = APIRouter(prefix="/jobs", tags=["jobs"])


def _build_match_service() -> MatchRankService:
    return MatchRankService(embedding_service=EmbeddingService())


@router.get("/semantic-search", response_model=Envelope[JobsListData])
async def semantic_search_jobs(
    q: str = Query(..., min_length=2, max_length=200),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[JobsListData]:
    service = _build_match_service()
    data = await service.semantic_search(session=session, user=current_user, query=q)
    return Envelope(success=True, data=data, error=None)


@router.get("", response_model=Envelope[JobsListData])
async def list_jobs(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[JobsListData]:
    service = _build_match_service()
    data = await service.list_ranked_jobs(session=session, user=current_user)
    return Envelope(success=True, data=data, error=None)


@router.get("/{job_id}", response_model=Envelope[JobDetailData])
async def get_job_detail(
    job_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[JobDetailData]:
    service = _build_match_service()
    data = await service.get_job_detail(session=session, user=current_user, job_id=job_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return Envelope(success=True, data=data, error=None)
