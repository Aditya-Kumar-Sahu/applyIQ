from __future__ import annotations

import anyio
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import DatabaseManager
from app.core.redis import RedisManager
from app.core.security import EncryptionService
from app.models.pipeline_run import PipelineRun
from app.models.user import User
from app.pipeline.checkpointer import PipelineCheckpointer
from app.pipeline.graph import PipelineGraphRunner
from app.scrapers.deduplicator import JobDeduplicator
from app.services.auto_apply_service import AutoApplyService
from app.services.cover_letter_service import CoverLetterService
from app.services.embedding_service import EmbeddingService
from app.services.match_rank_service import MatchRankService
from app.services.scrape_service import ScrapeService
from app.services.vault_service import VaultService
from app.worker import celery_app


async def _run_start(payload: dict) -> dict:
    settings = get_settings()
    database = DatabaseManager(settings.database_url)
    redis_manager = RedisManager(settings.redis_url)
    encryption_service = EncryptionService(
        fernet_secret_key=settings.fernet_secret_key,
        encryption_pepper=settings.encryption_pepper,
    )
    cover_letter_service = CoverLetterService()
    graph_runner = PipelineGraphRunner(
        scrape_service=ScrapeService(
            embedding_service=EmbeddingService(),
            deduplicator=JobDeduplicator(),
            settings=settings,
        ),
        match_service=MatchRankService(embedding_service=EmbeddingService()),
        checkpointer=PipelineCheckpointer(redis_manager, ttl_seconds=settings.pipeline_checkpoint_ttl_seconds),
        encryption_service=encryption_service,
        cover_letter_service=cover_letter_service,
        auto_apply_service=AutoApplyService(),
        vault_service=VaultService(),
    )

    try:
        async with database.session() as session:
            pipeline_run = await session.scalar(select(PipelineRun).where(PipelineRun.id == str(payload["run_id"])))
            user = await session.scalar(
                select(User)
                .where(User.id == str(payload["user_id"]))
                .options(
                    selectinload(User.resume_profile),
                    selectinload(User.search_preferences),
                )
            )
            if pipeline_run is None or user is None:
                return {"processed": False, "reason": "run_or_user_missing"}

            pipeline_run.status = "running"
            pipeline_run.current_node = "fetch_jobs_node"
            await session.commit()

            await graph_runner.run_until_approval(
                session=session,
                pipeline_run=pipeline_run,
                user=user,
                initial_state=payload["state"],
            )
            return {"processed": True, "run_id": pipeline_run.id}
    except Exception:
        async with database.session() as session:
            pipeline_run = await session.scalar(select(PipelineRun).where(PipelineRun.id == str(payload["run_id"])))
            if pipeline_run is not None:
                pipeline_run.status = "failed"
                pipeline_run.current_node = "pipeline_task_start"
                await session.commit()
        raise
    finally:
        await database.dispose()
        await redis_manager.close()


async def _run_resume(payload: dict) -> dict:
    settings = get_settings()
    database = DatabaseManager(settings.database_url)
    redis_manager = RedisManager(settings.redis_url)
    encryption_service = EncryptionService(
        fernet_secret_key=settings.fernet_secret_key,
        encryption_pepper=settings.encryption_pepper,
    )
    cover_letter_service = CoverLetterService()
    graph_runner = PipelineGraphRunner(
        scrape_service=ScrapeService(
            embedding_service=EmbeddingService(),
            deduplicator=JobDeduplicator(),
            settings=settings,
        ),
        match_service=MatchRankService(embedding_service=EmbeddingService()),
        checkpointer=PipelineCheckpointer(redis_manager, ttl_seconds=settings.pipeline_checkpoint_ttl_seconds),
        encryption_service=encryption_service,
        cover_letter_service=cover_letter_service,
        auto_apply_service=AutoApplyService(),
        vault_service=VaultService(),
    )

    try:
        async with database.session() as session:
            pipeline_run = await session.scalar(select(PipelineRun).where(PipelineRun.id == str(payload["run_id"])))
            user = await session.scalar(
                select(User)
                .where(User.id == str(payload["user_id"]))
                .options(
                    selectinload(User.resume_profile),
                    selectinload(User.search_preferences),
                )
            )
            if pipeline_run is None or user is None:
                return {"processed": False, "reason": "run_or_user_missing"}

            pipeline_run.status = "resuming"
            pipeline_run.current_node = "approval_gate_node"
            await session.commit()

            await graph_runner.resume_after_approval(
                session=session,
                pipeline_run=pipeline_run,
                user=user,
                run_id=pipeline_run.id,
            )
            return {"processed": True, "run_id": pipeline_run.id}
    except Exception:
        async with database.session() as session:
            pipeline_run = await session.scalar(select(PipelineRun).where(PipelineRun.id == str(payload["run_id"])))
            if pipeline_run is not None:
                pipeline_run.status = "failed"
                pipeline_run.current_node = "pipeline_task_resume"
                await session.commit()
        raise
    finally:
        await database.dispose()
        await redis_manager.close()


@celery_app.task(name="applyiq.pipeline.start")
def run_pipeline_start_task(payload: dict) -> dict:
    return anyio.run(_run_start, payload)


@celery_app.task(name="applyiq.pipeline.resume")
def run_pipeline_resume_task(payload: dict) -> dict:
    return anyio.run(_run_resume, payload)


async def _sweep_stale():
    settings = get_settings()
    database = DatabaseManager(settings.database_url)
    
    try:
        from datetime import datetime, timezone, timedelta
        stale_threshold = datetime.now(timezone.utc) - timedelta(days=7) # Assume 7 days timeout for a paused run
        
        async with database.session() as session:
            stale_runs = await session.scalars(
                select(PipelineRun).where(
                    PipelineRun.status == "paused_at_gate",
                    PipelineRun.updated_at < stale_threshold
                )
            )
            count = 0
            for run_row in stale_runs:
                run_row.status = "timed_out"
                count += 1
            if count > 0:
                await session.commit()
            return {"timed_out_count": count}
    finally:
        await database.dispose()

@celery_app.task(name="applyiq.pipeline.sweep_stale")
def run_pipeline_sweep_stale_task():
    return anyio.run(_sweep_stale)

