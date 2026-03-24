from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db_session, get_encryption_service
from app.models.user import User
from app.pipeline.checkpointer import PipelineCheckpointer
from app.pipeline.graph import PipelineGraphRunner
from app.schemas.common import Envelope
from app.schemas.pipeline import (
    CoverLetterEditData,
    CoverLetterEditPayload,
    PipelineDecisionPayload,
    PipelineResultsData,
    PipelineRunData,
    PipelineStartRequest,
    RejectData,
)
from app.scrapers.deduplicator import JobDeduplicator
from app.services.embedding_service import EmbeddingService
from app.services.match_rank_service import MatchRankService
from app.services.pipeline_service import PipelineService
from app.services.scrape_service import ScrapeService


router = APIRouter(prefix="/pipeline", tags=["pipeline"])


def _build_pipeline_service(request: Request, encryption_service) -> PipelineService:
    graph_runner = PipelineGraphRunner(
        scrape_service=ScrapeService(
            embedding_service=EmbeddingService(),
            deduplicator=JobDeduplicator(),
        ),
        match_service=MatchRankService(embedding_service=EmbeddingService()),
        checkpointer=PipelineCheckpointer(request.app.state.redis),
        encryption_service=encryption_service,
    )
    return PipelineService(graph_runner=graph_runner, encryption_service=encryption_service)


@router.post("/start", response_model=Envelope[PipelineRunData], status_code=status.HTTP_202_ACCEPTED)
async def start_pipeline(
    payload: PipelineStartRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    encryption_service=Depends(get_encryption_service),
) -> Envelope[PipelineRunData]:
    service = _build_pipeline_service(request, encryption_service)
    data = await service.start_run(session=session, user=current_user, payload=payload)
    return Envelope(success=True, data=data, error=None)


@router.get("/{run_id}/status")
async def pipeline_status(
    run_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    encryption_service=Depends(get_encryption_service),
):
    service = _build_pipeline_service(request, encryption_service)

    async def event_stream():
        yield await service.get_status_event(session=session, user=current_user, run_id=run_id)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/{run_id}/results", response_model=Envelope[PipelineResultsData])
async def pipeline_results(
    run_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    encryption_service=Depends(get_encryption_service),
) -> Envelope[PipelineResultsData]:
    service = _build_pipeline_service(request, encryption_service)
    data = await service.get_results(session=session, user=current_user, run_id=run_id)
    return Envelope(success=True, data=data, error=None)


@router.post("/{run_id}/approve", response_model=Envelope[PipelineRunData])
async def approve_pipeline(
    run_id: str,
    payload: PipelineDecisionPayload,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    encryption_service=Depends(get_encryption_service),
) -> Envelope[PipelineRunData]:
    service = _build_pipeline_service(request, encryption_service)
    data = await service.approve(session=session, user=current_user, run_id=run_id, application_ids=payload.application_ids)
    return Envelope(success=True, data=data, error=None)


@router.post("/{run_id}/reject", response_model=Envelope[RejectData])
async def reject_pipeline(
    run_id: str,
    payload: PipelineDecisionPayload,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    encryption_service=Depends(get_encryption_service),
) -> Envelope[RejectData]:
    service = _build_pipeline_service(request, encryption_service)
    data = await service.reject(session=session, user=current_user, run_id=run_id, application_ids=payload.application_ids)
    return Envelope(success=True, data=data, error=None)


@router.put("/{run_id}/application/{application_id}/cover-letter", response_model=Envelope[CoverLetterEditData])
async def edit_cover_letter(
    run_id: str,
    application_id: str,
    payload: CoverLetterEditPayload,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    encryption_service=Depends(get_encryption_service),
) -> Envelope[CoverLetterEditData]:
    service = _build_pipeline_service(request, encryption_service)
    data = await service.edit_cover_letter(
        session=session,
        user=current_user,
        run_id=run_id,
        application_id=application_id,
        payload=payload,
    )
    return Envelope(success=True, data=data, error=None)
