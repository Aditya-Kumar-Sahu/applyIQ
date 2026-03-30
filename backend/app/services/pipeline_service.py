from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, AsyncIterator

import anyio
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.config import Settings
from app.core.logging_safety import log_debug, log_exception
from app.models.application import Application
from app.models.job import Job
from app.models.job_match import JobMatch
from app.models.pipeline_run import PipelineRun
from app.models.user import User
from app.pipeline.graph import PipelineGraphRunner
from app.pipeline.state import ApplyIQState
from app.schemas.resume import ParsedResumeProfile
from app.services.cover_letter_service import CoverLetterService
from app.schemas.pipeline import (
    CoverLetterABTestData,
    CoverLetterEditData,
    CoverLetterEditPayload,
    CoverLetterVariantItem,
    CoverLetterVariantSelectData,
    CoverLetterVariantSelectPayload,
    PipelineApplicationItem,
    PipelineResultsData,
    PipelineRunData,
    PipelineStartRequest,
    RejectData,
)


logger = structlog.get_logger(__name__)


_TERMINAL_RUN_STATES = {"paused_at_gate", "complete", "failed", "timed_out"}


class PipelineService:
    def __init__(
        self,
        *,
        graph_runner: PipelineGraphRunner,
        encryption_service,
        cover_letter_service: CoverLetterService,
        settings: Settings,
    ) -> None:
        self._graph_runner = graph_runner
        self._encryption_service = encryption_service
        self._cover_letter_service = cover_letter_service
        self._settings = settings

    async def start_run(self, *, session: AsyncSession, user: User, payload: PipelineStartRequest) -> PipelineRunData:
        log_debug(
            logger,
            "pipeline.start_run.start",
            user_id=user.id,
            target_role=payload.target_role,
            location=payload.location,
            sources=payload.sources,
            limit_per_source=payload.limit_per_source,
            execute_inline=self._settings.execute_pipeline_inline,
        )
        try:
            active_run = await session.scalar(
                select(PipelineRun)
                .where(
                    PipelineRun.user_id == user.id,
                    PipelineRun.status.in_(["queued", "running", "paused_at_gate", "resuming"])
                )
            )
            if active_run:
                log_debug(logger, "pipeline.start_run.active_run_conflict", user_id=user.id, run_id=active_run.id)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A pipeline run is already active across this user.",
                )

            pipeline_run = PipelineRun(
                user_id=user.id,
                status="running" if self._settings.execute_pipeline_inline else "queued",
                current_node="pending",
            )
            session.add(pipeline_run)
            await session.commit()
            await session.refresh(pipeline_run)

            state: ApplyIQState = {
                "run_id": pipeline_run.id,
                "user_id": user.id,
                "target_role": payload.target_role,
                "location": payload.location,
                "limit_per_source": payload.limit_per_source,
                "sources": payload.sources,
                "raw_jobs_count": 0,
                "deduplicated_jobs_count": 0,
                "ranked_jobs": [],
                "pending_approvals": [],
                "approved_applications": [],
                "applied_applications": [],
                "current_node": "pending",
            }
            pending_approvals_count = 0
            if self._settings.execute_pipeline_inline:
                log_debug(logger, "pipeline.start_run.inline_begin", run_id=pipeline_run.id, user_id=user.id)
                final_state = await self._graph_runner.run_until_approval(
                    session=session,
                    pipeline_run=pipeline_run,
                    user=user,
                    initial_state=state,
                )
                pending_approvals_count = len(final_state["pending_approvals"])
                log_debug(
                    logger,
                    "pipeline.start_run.inline_complete",
                    run_id=pipeline_run.id,
                    pending_approvals_count=pending_approvals_count,
                )
            else:
                from app.tasks.pipeline_task import run_pipeline_start_task

                task_payload = {
                    "run_id": pipeline_run.id,
                    "user_id": user.id,
                    "state": state,
                }
                try:
                    task = run_pipeline_start_task.delay(task_payload)
                    pipeline_run.celery_task_id = task.id
                    await session.commit()
                    await session.refresh(pipeline_run)
                    log_debug(
                        logger,
                        "pipeline.start_run.task_dispatched",
                        run_id=pipeline_run.id,
                        user_id=user.id,
                        celery_task_id=task.id,
                    )
                except Exception as error:
                    log_exception(
                        logger,
                        "pipeline.start.dispatch_failed",
                        error,
                        run_id=pipeline_run.id,
                        user_id=user.id,
                    )
                    final_state = await self._graph_runner.run_until_approval(
                        session=session,
                        pipeline_run=pipeline_run,
                        user=user,
                        initial_state=state,
                    )
                    pending_approvals_count = len(final_state["pending_approvals"])

            result = PipelineRunData(
                run_id=pipeline_run.id,
                status=pipeline_run.status,
                current_node=pipeline_run.current_node,
                jobs_found=pipeline_run.jobs_found,
                jobs_matched=pipeline_run.jobs_matched,
                applications_submitted=pipeline_run.applications_submitted,
                pending_approvals_count=pending_approvals_count,
            )
            log_debug(logger, "pipeline.start_run.complete", run_id=pipeline_run.id, user_id=user.id)
            return result
        except Exception as error:
            log_exception(logger, "pipeline.start_run.failed", error, user_id=user.id)
            raise

    async def get_results(self, *, session: AsyncSession, user: User, run_id: str) -> PipelineResultsData:
        log_debug(logger, "pipeline.get_results.start", user_id=user.id, run_id=run_id)
        pipeline_run = await self._get_run(session=session, user=user, run_id=run_id)
        applications = list(await session.scalars(select(Application).where(Application.pipeline_run_id == run_id)))

        items: list[PipelineApplicationItem] = []
        for application in applications:
            job = await session.scalar(select(Job).where(Job.id == application.job_id))
            notes = _load_notes(application.notes)
            selected_variant_id = _selected_variant_id(notes)
            items.append(
                PipelineApplicationItem(
                    id=application.id,
                    job_id=application.job_id,
                    title=job.title if job else "Unknown Job",
                    company_name=job.company_name if job else "Unknown Company",
                    match_score=application.match_score,
                    cover_letter_text=application.cover_letter_text,
                    tone=application.cover_letter_tone,
                    word_count=application.cover_letter_word_count,
                    cover_letter_version=application.cover_letter_version,
                    status=application.status,
                    ats_provider=application.ats_provider,
                    confirmation_url=application.confirmation_url,
                    confirmation_number=application.confirmation_number,
                    screenshot_urls=application.screenshot_urls,
                    failure_reason=application.failure_reason,
                    manual_required_reason=application.manual_required_reason,
                    selected_variant_id=selected_variant_id,
                )
            )

        result = PipelineResultsData(
            run_id=pipeline_run.id,
            status=pipeline_run.status,
            current_node=pipeline_run.current_node,
            jobs_found=pipeline_run.jobs_found,
            jobs_matched=pipeline_run.jobs_matched,
            applications_submitted=pipeline_run.applications_submitted,
            started_at=pipeline_run.started_at,
            completed_at=pipeline_run.completed_at,
            applications=items,
        )
        log_debug(logger, "pipeline.get_results.complete", user_id=user.id, run_id=run_id, applications=len(items))
        return result

    async def approve(self, *, session: AsyncSession, user: User, run_id: str, application_ids: list[str]) -> PipelineRunData:
        log_debug(
            logger,
            "pipeline.approve.start",
            user_id=user.id,
            run_id=run_id,
            requested_application_ids_count=len(application_ids),
        )
        pipeline_run = await self._get_run(session=session, user=user, run_id=run_id)
        
        # Idempotency guard: Ensure we are currently paused at gate
        if pipeline_run.status != "paused_at_gate":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot approve pipeline run in '{pipeline_run.status}' state",
            )
            
        applications = list(
            await session.scalars(
                select(Application).where(
                    Application.pipeline_run_id == run_id,
                    Application.user_id == user.id,
                )
            )
        )

        selected_ids = set(application_ids)
        for application in applications:
            if application.id in selected_ids:
                application.status = "approved"

        # Setup resume state atomically with the approval status change
        if not self._settings.execute_pipeline_inline:
            pipeline_run.status = "resuming"
            pipeline_run.current_node = "approval_gate_node"
            
        await session.commit()
        await session.refresh(pipeline_run)
        
        if self._settings.execute_pipeline_inline:
            await self._graph_runner.resume_after_approval(session=session, pipeline_run=pipeline_run, user=user, run_id=run_id)
            await session.refresh(pipeline_run)
            log_debug(logger, "pipeline.approve.inline_resume_complete", user_id=user.id, run_id=run_id)
        else:
            from app.tasks.pipeline_task import run_pipeline_resume_task
            try:
                task = run_pipeline_resume_task.delay({"run_id": run_id, "user_id": user.id})
                pipeline_run.celery_task_id = task.id
                await session.commit()
                await session.refresh(pipeline_run)
                log_debug(
                    logger,
                    "pipeline.approve.resume_task_dispatched",
                    run_id=run_id,
                    user_id=user.id,
                    celery_task_id=task.id,
                )
            except Exception as error:
                log_exception(
                    logger,
                    "pipeline.resume.dispatch_failed",
                    error,
                    run_id=run_id,
                    user_id=user.id,
                )
                await self._graph_runner.resume_after_approval(
                    session=session,
                    pipeline_run=pipeline_run,
                    user=user,
                    run_id=run_id,
                )
                await session.refresh(pipeline_run)

        pending_count = len([application for application in applications if application.status == "pending_approval"])
        result = PipelineRunData(
            run_id=pipeline_run.id,
            status=pipeline_run.status,
            current_node=pipeline_run.current_node,
            jobs_found=pipeline_run.jobs_found,
            jobs_matched=pipeline_run.jobs_matched,
            applications_submitted=pipeline_run.applications_submitted,
            pending_approvals_count=pending_count,
        )
        log_debug(
            logger,
            "pipeline.approve.complete",
            user_id=user.id,
            run_id=run_id,
            pending_approvals_count=pending_count,
        )
        return result

    async def reject(self, *, session: AsyncSession, user: User, run_id: str, application_ids: list[str]) -> RejectData:
        log_debug(
            logger,
            "pipeline.reject.start",
            user_id=user.id,
            run_id=run_id,
            requested_application_ids_count=len(application_ids),
        )
        try:
            await self._get_run(session=session, user=user, run_id=run_id)
            applications = list(
                await session.scalars(
                    select(Application).where(
                        Application.pipeline_run_id == run_id,
                        Application.user_id == user.id,
                        Application.id.in_(application_ids),
                    )
                )
            )

            for application in applications:
                application.status = "rejected"

            await session.commit()
            result = RejectData(rejected_count=len(applications))
            log_debug(logger, "pipeline.reject.complete", user_id=user.id, run_id=run_id, rejected_count=len(applications))
            return result
        except Exception as error:
            log_exception(logger, "pipeline.reject.failed", error, user_id=user.id, run_id=run_id)
            raise

    async def edit_cover_letter(
        self,
        *,
        session: AsyncSession,
        user: User,
        run_id: str,
        application_id: str,
        payload: CoverLetterEditPayload,
    ) -> CoverLetterEditData:
        log_debug(
            logger,
            "pipeline.edit_cover_letter.start",
            user_id=user.id,
            run_id=run_id,
            application_id=application_id,
            cover_letter_length=len(payload.cover_letter_text),
        )
        try:
            await self._get_run(session=session, user=user, run_id=run_id)
            application = await session.scalar(
                select(Application).where(
                    Application.pipeline_run_id == run_id,
                    Application.user_id == user.id,
                    Application.id == application_id,
                )
            )
            if application is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

            application.cover_letter_text = payload.cover_letter_text
            application.cover_letter_tone = "edited"
            application.cover_letter_word_count = self._cover_letter_service.word_count(payload.cover_letter_text)
            application.cover_letter_version += 1
            await session.commit()

            result = CoverLetterEditData(
                application_id=application.id,
                cover_letter_text=application.cover_letter_text,
                tone=application.cover_letter_tone,
                word_count=application.cover_letter_word_count,
                cover_letter_version=application.cover_letter_version,
            )
            log_debug(
                logger,
                "pipeline.edit_cover_letter.complete",
                user_id=user.id,
                run_id=run_id,
                application_id=application_id,
                cover_letter_version=application.cover_letter_version,
            )
            return result
        except Exception as error:
            log_exception(
                logger,
                "pipeline.edit_cover_letter.failed",
                error,
                user_id=user.id,
                run_id=run_id,
                application_id=application_id,
            )
            raise

    async def generate_cover_letter_ab_test(
        self,
        *,
        session: AsyncSession,
        user: User,
        run_id: str,
        application_id: str,
    ) -> CoverLetterABTestData:
        log_debug(
            logger,
            "pipeline.generate_cover_letter_ab_test.start",
            user_id=user.id,
            run_id=run_id,
            application_id=application_id,
        )
        try:
            await self._get_run(session=session, user=user, run_id=run_id)
            application = await session.scalar(
                select(Application).where(
                    Application.pipeline_run_id == run_id,
                    Application.user_id == user.id,
                    Application.id == application_id,
                )
            )
            if application is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
            if user.resume_profile is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resume profile not found")

            job = await session.scalar(select(Job).where(Job.id == application.job_id))
            if job is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

            job_match = await session.scalar(
                select(JobMatch).where(JobMatch.user_id == user.id, JobMatch.job_id == application.job_id)
            )
            resume = ParsedResumeProfile.model_validate(user.resume_profile.parsed_profile)
            matched_skills = job_match.matched_skills if job_match else []

            draft_a = self._cover_letter_service.generate(
                job=job,
                resume=resume,
                matched_skills=matched_skills,
                tone="formal",
                variant=application.cover_letter_version + 1,
            )
            draft_b = self._cover_letter_service.generate(
                job=job,
                resume=resume,
                matched_skills=matched_skills,
                tone="conversational",
                variant=application.cover_letter_version + 2,
            )

            variants = [
                CoverLetterVariantItem(
                    variant_id="A",
                    cover_letter_text=draft_a.cover_letter,
                    tone=draft_a.tone,
                    word_count=draft_a.word_count,
                ),
                CoverLetterVariantItem(
                    variant_id="B",
                    cover_letter_text=draft_b.cover_letter,
                    tone=draft_b.tone,
                    word_count=draft_b.word_count,
                ),
            ]

            notes = _load_notes(application.notes)
            notes["ab_test"] = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "selected_variant_id": _selected_variant_id(notes),
                "variants": [variant.model_dump() for variant in variants],
            }
            application.notes = _dump_notes(notes)
            await session.commit()

            result = CoverLetterABTestData(
                application_id=application.id,
                cover_letter_version=application.cover_letter_version,
                variants=variants,
            )
            log_debug(
                logger,
                "pipeline.generate_cover_letter_ab_test.complete",
                user_id=user.id,
                run_id=run_id,
                application_id=application_id,
                variants_count=len(variants),
            )
            return result
        except Exception as error:
            log_exception(
                logger,
                "pipeline.generate_cover_letter_ab_test.failed",
                error,
                user_id=user.id,
                run_id=run_id,
                application_id=application_id,
            )
            raise

    async def select_cover_letter_variant(
        self,
        *,
        session: AsyncSession,
        user: User,
        run_id: str,
        application_id: str,
        payload: CoverLetterVariantSelectPayload,
    ) -> CoverLetterVariantSelectData:
        log_debug(
            logger,
            "pipeline.select_cover_letter_variant.start",
            user_id=user.id,
            run_id=run_id,
            application_id=application_id,
            requested_variant=payload.variant_id,
        )
        try:
            await self._get_run(session=session, user=user, run_id=run_id)
            application = await session.scalar(
                select(Application).where(
                    Application.pipeline_run_id == run_id,
                    Application.user_id == user.id,
                    Application.id == application_id,
                )
            )
            if application is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

            notes = _load_notes(application.notes)
            variants = _ab_variants(notes)
            requested_variant = payload.variant_id.upper()
            variant = next((item for item in variants if str(item.get("variant_id", "")).upper() == requested_variant), None)
            if variant is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="A/B variant not found")

            application.cover_letter_text = str(variant["cover_letter_text"])
            application.cover_letter_tone = str(variant["tone"])
            application.cover_letter_word_count = int(variant["word_count"])
            application.cover_letter_version += 1

            notes.setdefault("ab_test", {})
            notes["ab_test"]["selected_variant_id"] = requested_variant
            application.notes = _dump_notes(notes)
            await session.commit()

            result = CoverLetterVariantSelectData(
                application_id=application.id,
                selected_variant_id=requested_variant,
                cover_letter_text=application.cover_letter_text,
                tone=application.cover_letter_tone,
                word_count=application.cover_letter_word_count,
                cover_letter_version=application.cover_letter_version,
            )
            log_debug(
                logger,
                "pipeline.select_cover_letter_variant.complete",
                user_id=user.id,
                run_id=run_id,
                application_id=application_id,
                selected_variant_id=requested_variant,
            )
            return result
        except Exception as error:
            log_exception(
                logger,
                "pipeline.select_cover_letter_variant.failed",
                error,
                user_id=user.id,
                run_id=run_id,
                application_id=application_id,
            )
            raise

    async def regenerate_cover_letter(
        self,
        *,
        session: AsyncSession,
        user: User,
        run_id: str,
        application_id: str,
    ) -> CoverLetterEditData:
        log_debug(
            logger,
            "pipeline.regenerate_cover_letter.start",
            user_id=user.id,
            run_id=run_id,
            application_id=application_id,
        )
        try:
            await self._get_run(session=session, user=user, run_id=run_id)
            application = await session.scalar(
                select(Application).where(
                    Application.pipeline_run_id == run_id,
                    Application.user_id == user.id,
                    Application.id == application_id,
                )
            )
            if application is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
            if user.resume_profile is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resume profile not found")

            job = await session.scalar(select(Job).where(Job.id == application.job_id))
            if job is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

            job_match = await session.scalar(
                select(JobMatch).where(JobMatch.user_id == user.id, JobMatch.job_id == application.job_id)
            )
            resume = ParsedResumeProfile.model_validate(user.resume_profile.parsed_profile)
            draft = self._cover_letter_service.generate(
                job=job,
                resume=resume,
                matched_skills=job_match.matched_skills if job_match else [],
                tone=self._cover_letter_service.next_tone(application.cover_letter_tone),
                variant=application.cover_letter_version + 1,
            )

            application.cover_letter_text = draft.cover_letter
            application.cover_letter_tone = draft.tone
            application.cover_letter_word_count = draft.word_count
            application.cover_letter_version += 1
            await session.commit()

            result = CoverLetterEditData(
                application_id=application.id,
                cover_letter_text=application.cover_letter_text,
                tone=application.cover_letter_tone,
                word_count=application.cover_letter_word_count,
                cover_letter_version=application.cover_letter_version,
            )
            log_debug(
                logger,
                "pipeline.regenerate_cover_letter.complete",
                user_id=user.id,
                run_id=run_id,
                application_id=application_id,
                cover_letter_version=application.cover_letter_version,
            )
            return result
        except Exception as error:
            log_exception(
                logger,
                "pipeline.regenerate_cover_letter.failed",
                error,
                user_id=user.id,
                run_id=run_id,
                application_id=application_id,
            )
            raise

    async def get_status_event(self, *, session: AsyncSession, user: User, run_id: str) -> str:
        log_debug(logger, "pipeline.get_status_event.start", user_id=user.id, run_id=run_id)
        data = await self.get_results(session=session, user=user, run_id=run_id)
        payload = f"event: status\ndata: {json.dumps(data.model_dump(mode='json'))}\n\n"
        log_debug(logger, "pipeline.get_status_event.complete", user_id=user.id, run_id=run_id, payload_length=len(payload))
        return payload

    async def stream_status_events(
        self,
        *,
        session: AsyncSession,
        user: User,
        run_id: str,
        poll_interval_seconds: float = 1.5,
    ) -> AsyncIterator[str]:
        log_debug(
            logger,
            "pipeline.stream_status.start",
            user_id=user.id,
            run_id=run_id,
            poll_interval_seconds=poll_interval_seconds,
        )
        last_payload: str | None = None
        while True:
            data = await self.get_results(session=session, user=user, run_id=run_id)
            serialized = json.dumps(data.model_dump(mode="json"))

            if serialized != last_payload:
                yield f"event: status\ndata: {serialized}\n\n"
                last_payload = serialized
            else:
                yield "event: heartbeat\ndata: {}\n\n"

            if data.status in _TERMINAL_RUN_STATES:
                break

            await anyio.sleep(poll_interval_seconds)

    async def _get_run(self, *, session: AsyncSession, user: User, run_id: str) -> PipelineRun:
        log_debug(logger, "pipeline.get_run.start", user_id=user.id, run_id=run_id)
        pipeline_run = await session.scalar(
            select(PipelineRun).where(PipelineRun.id == run_id, PipelineRun.user_id == user.id)
        )
        if pipeline_run is None:
            log_debug(logger, "pipeline.get_run.not_found", user_id=user.id, run_id=run_id)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline run not found")
        log_debug(logger, "pipeline.get_run.complete", user_id=user.id, run_id=run_id, status=pipeline_run.status)
        return pipeline_run


def _load_notes(raw_notes: str | None) -> dict[str, Any]:
    if raw_notes is None or raw_notes.strip() == "":
        return {}
    try:
        parsed = json.loads(raw_notes)
    except json.JSONDecodeError:
        return {"legacy_note": raw_notes}
    if isinstance(parsed, dict):
        return parsed
    return {"legacy_note": raw_notes}


def _dump_notes(notes: dict[str, Any]) -> str:
    return json.dumps(notes, ensure_ascii=True)


def _ab_variants(notes: dict[str, Any]) -> list[dict[str, Any]]:
    ab_test = notes.get("ab_test")
    if not isinstance(ab_test, dict):
        return []
    variants = ab_test.get("variants")
    if not isinstance(variants, list):
        return []
    normalized: list[dict[str, Any]] = []
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        if not {"variant_id", "cover_letter_text", "tone", "word_count"}.issubset(variant.keys()):
            continue
        normalized.append(variant)
    return normalized


def _selected_variant_id(notes: dict[str, Any]) -> str | None:
    ab_test = notes.get("ab_test")
    if not isinstance(ab_test, dict):
        return None
    selected = ab_test.get("selected_variant_id")
    if not isinstance(selected, str) or selected.strip() == "":
        return None
    return selected.upper()
