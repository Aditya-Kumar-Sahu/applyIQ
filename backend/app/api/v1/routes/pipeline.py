from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.api.v1.deps import get_current_user, get_db_session, get_encryption_service
from app.core.rate_limit import RedisRateLimiter
from app.models.user import User
from app.pipeline.checkpointer import PipelineCheckpointer
from app.pipeline.graph import PipelineGraphRunner
from app.schemas.common import Envelope
from app.schemas.pipeline import (
    CoverLetterABTestData,
    CoverLetterEditData,
    CoverLetterEditPayload,
    CoverLetterVariantSelectData,
    CoverLetterVariantSelectPayload,
    PipelineDecisionPayload,
    PipelineResultsData,
    PipelineRunData,
    PipelineStartRequest,
    RejectData,
)
from app.scrapers.deduplicator import JobDeduplicator
from app.services.auto_apply_service import AutoApplyService
from app.services.cover_letter_service import CoverLetterService
from app.services.embedding_service import EmbeddingService
from app.services.match_rank_service import MatchRankService
from app.services.pipeline_service import PipelineService
from app.services.scrape_service import ScrapeService
from app.services.vault_service import VaultService


router = APIRouter(prefix="/pipeline", tags=["pipeline"])
logger = structlog.get_logger(__name__)


def _build_pipeline_service(request: Request, encryption_service) -> PipelineService:
    cover_letter_service = CoverLetterService()
    settings = request.app.state.settings
    graph_runner = PipelineGraphRunner(
        scrape_service=ScrapeService(
            embedding_service=EmbeddingService(),
            deduplicator=JobDeduplicator(),
        ),
        match_service=MatchRankService(embedding_service=EmbeddingService()),
        checkpointer=PipelineCheckpointer(
            request.app.state.redis,
            ttl_seconds=settings.pipeline_checkpoint_ttl_seconds,
        ),
        encryption_service=encryption_service,
        cover_letter_service=cover_letter_service,
        auto_apply_service=AutoApplyService(),
        vault_service=VaultService(),
    )
    return PipelineService(
        graph_runner=graph_runner,
        encryption_service=encryption_service,
        cover_letter_service=cover_letter_service,
        settings=settings,
    )


@router.post("/start", response_model=Envelope[PipelineRunData], status_code=status.HTTP_202_ACCEPTED)
async def start_pipeline(
    payload: PipelineStartRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    encryption_service=Depends(get_encryption_service),
) -> Envelope[PipelineRunData]:
    settings = request.app.state.settings
    limiter = RedisRateLimiter(request.app.state.redis)
    is_allowed = await limiter.allow(
        key=f"pipeline_start:{current_user.id}",
        limit=settings.pipeline_start_rate_limit,
        window_seconds=settings.pipeline_start_rate_window_seconds,
    )
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Pipeline start rate limit exceeded. Please retry later.",
        )

    logger.info(
        "pipeline.start.requested",
        user_id=current_user.id,
        sources=payload.sources,
        target_role=payload.target_role,
    )
    service = _build_pipeline_service(request, encryption_service)
    data = await service.start_run(session=session, user=current_user, payload=payload)
    logger.info(
        "pipeline.start.accepted",
        user_id=current_user.id,
        run_id=data.run_id,
        status=data.status,
        current_node=data.current_node,
    )
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
    logger.info(
        "pipeline.approve.requested",
        user_id=current_user.id,
        run_id=run_id,
        approvals_count=len(payload.application_ids),
    )
    data = await service.approve(session=session, user=current_user, run_id=run_id, application_ids=payload.application_ids)
    logger.info(
        "pipeline.approve.accepted",
        user_id=current_user.id,
        run_id=data.run_id,
        status=data.status,
        current_node=data.current_node,
    )
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


@router.post(
    "/{run_id}/application/{application_id}/cover-letter/regenerate",
    response_model=Envelope[CoverLetterEditData],
)
async def regenerate_cover_letter(
    run_id: str,
    application_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    encryption_service=Depends(get_encryption_service),
) -> Envelope[CoverLetterEditData]:
    service = _build_pipeline_service(request, encryption_service)
    data = await service.regenerate_cover_letter(
        session=session,
        user=current_user,
        run_id=run_id,
        application_id=application_id,
    )
    return Envelope(success=True, data=data, error=None)


@router.post(
    "/{run_id}/application/{application_id}/cover-letter/ab-test",
    response_model=Envelope[CoverLetterABTestData],
)
async def generate_cover_letter_ab_test(
    run_id: str,
    application_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    encryption_service=Depends(get_encryption_service),
) -> Envelope[CoverLetterABTestData]:
    service = _build_pipeline_service(request, encryption_service)
    data = await service.generate_cover_letter_ab_test(
        session=session,
        user=current_user,
        run_id=run_id,
        application_id=application_id,
    )
    return Envelope(success=True, data=data, error=None)


@router.post(
    "/{run_id}/application/{application_id}/cover-letter/select-variant",
    response_model=Envelope[CoverLetterVariantSelectData],
)
async def select_cover_letter_variant(
    run_id: str,
    application_id: str,
    payload: CoverLetterVariantSelectPayload,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    encryption_service=Depends(get_encryption_service),
) -> Envelope[CoverLetterVariantSelectData]:
    service = _build_pipeline_service(request, encryption_service)
    data = await service.select_cover_letter_variant(
        session=session,
        user=current_user,
        run_id=run_id,
        application_id=application_id,
        payload=payload,
    )
    return Envelope(success=True, data=data, error=None)
