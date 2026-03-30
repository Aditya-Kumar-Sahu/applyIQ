from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.job import Job
from app.models.pipeline_run import PipelineRun
from app.models.user import User
from app.pipeline.checkpointer import PipelineCheckpointer
from app.pipeline.state import ApplyIQState
from app.schemas.resume import ParsedResumeProfile
from app.services.cover_letter_service import CoverLetterService
from app.scrapers.base import ScrapeQuery
from app.services.match_rank_service import MatchRankService
from app.services.scrape_service import ScrapeService


async def fetch_jobs_node(
    state: ApplyIQState,
    *,
    session: AsyncSession,
    scrape_service: ScrapeService,
    pipeline_run: PipelineRun,
) -> ApplyIQState:
    summary = await scrape_service.run_test_scrape(
        session=session,
        query=ScrapeQuery(
            target_role=state["target_role"],
            location=state["location"],
            limit_per_source=state["limit_per_source"],
        ),
        sources=state["sources"],
    )
    pipeline_run.jobs_found = summary.deduplicated_jobs_count
    pipeline_run.current_node = "fetch_jobs_node"
    pipeline_run.status = "running"
    await session.commit()

    state["raw_jobs_count"] = summary.raw_jobs_count
    state["deduplicated_jobs_count"] = summary.deduplicated_jobs_count
    state["raw_jobs"] = [job.model_dump(mode="json") for job in summary.jobs]
    state["deduplicated_jobs"] = [job.model_dump(mode="json") for job in summary.jobs]
    if summary.failed_sources:
        errors = state.setdefault("errors", [])
        for source in summary.failed_sources:
            errors.append(
                {
                    "node": "fetch_jobs_node",
                    "message": f"Source '{source}' failed during scrape",
                }
            )
    state["current_node"] = "fetch_jobs_node"
    return state


async def rank_jobs_node(
    state: ApplyIQState,
    *,
    session: AsyncSession,
    match_service: MatchRankService,
    pipeline_run: PipelineRun,
    user: User,
) -> ApplyIQState:
    ranked_jobs = await match_service.list_ranked_jobs(session=session, user=user)
    pipeline_run.jobs_matched = ranked_jobs.total
    pipeline_run.current_node = "rank_jobs_node"
    await session.commit()

    state["ranked_jobs"] = [item.model_dump(mode="json") for item in ranked_jobs.items[:5]]
    state["current_node"] = "rank_jobs_node"
    return state


async def approval_gate_node(
    state: ApplyIQState,
    *,
    session: AsyncSession,
    pipeline_run: PipelineRun,
    user: User,
    checkpointer: PipelineCheckpointer,
    encryption_service,
    cover_letter_service: CoverLetterService,
) -> ApplyIQState:
    if user.resume_profile is None:
        raise ValueError("Resume profile is required before generating cover letters")

    if len(state["ranked_jobs"]) == 0:
        state["pending_approvals"] = []
        state["approved_applications"] = []
        state["applied_applications"] = []
        state["current_node"] = "track_applications_node"
        pipeline_run.status = "complete"
        pipeline_run.current_node = "track_applications_node"
        pipeline_run.completed_at = datetime.now(timezone.utc)
        pipeline_run.state_snapshot = encryption_service.encrypt_for_user(user.id, _serialize_state(state))
        await session.commit()
        await checkpointer.delete(pipeline_run.id)
        return state

    resume = ParsedResumeProfile.model_validate(user.resume_profile.parsed_profile)
    pending_approvals: list[dict[str, str | int | float]] = []
    for index, ranked_job in enumerate(state["ranked_jobs"], start=1):
        job = await session.scalar(select(Job).where(Job.id == str(ranked_job["job_id"])))
        if job is None:
            continue

        draft = cover_letter_service.generate(
            job=job,
            resume=resume,
            matched_skills=[str(skill) for skill in ranked_job.get("matched_skills", [])],
            tone="formal" if index % 2 else "conversational",
            variant=index,
        )
        application = Application(
            user_id=user.id,
            job_id=str(ranked_job["job_id"]),
            pipeline_run_id=pipeline_run.id,
            status="pending_approval",
            match_score=float(ranked_job["match_score"]),
            cover_letter_text=draft.cover_letter,
            cover_letter_tone=draft.tone,
            cover_letter_word_count=draft.word_count,
        )
        session.add(application)
        await session.flush()
        pending_approvals.append(
            {
                "id": application.id,
                "job_id": application.job_id,
                "title": str(ranked_job["title"]),
                "company_name": str(ranked_job["company_name"]),
                "match_score": float(ranked_job["match_score"]),
                "cover_letter_text": application.cover_letter_text,
                "tone": application.cover_letter_tone,
                "word_count": application.cover_letter_word_count,
                "cover_letter_version": application.cover_letter_version,
                "status": application.status,
            }
        )

    state["pending_approvals"] = pending_approvals
    state["current_node"] = "approval_gate_node"
    pipeline_run.status = "paused_at_gate"
    pipeline_run.current_node = "approval_gate_node"
    pipeline_run.state_snapshot = encryption_service.encrypt_for_user(user.id, _serialize_state(state))
    await session.commit()
    await checkpointer.save(pipeline_run.id, state)
    return state


async def auto_apply_node(
    state: ApplyIQState,
    *,
    session: AsyncSession,
    pipeline_run: PipelineRun,
    user: User,
    auto_apply_service,
    vault_service,
    encryption_service,
) -> ApplyIQState:
    applications = list(
        await session.scalars(
            select(Application).where(
                Application.pipeline_run_id == pipeline_run.id,
                Application.status == "approved",
            )
        )
    )
    approved_items: list[dict[str, str]] = []
    errors = state.setdefault("errors", [])
    for application in applications:
        try:
            application.approved_at = application.approved_at or datetime.now(timezone.utc)
            job = await session.scalar(select(Job).where(Job.id == application.job_id))
            if job is None:
                application.status = "failed"
                application.is_demo = False
                application.failure_reason = "Job record not found for auto-apply"
                errors.append(
                    {
                        "node": "auto_apply_node",
                        "application_id": application.id,
                        "message": "Job record not found for auto-apply",
                    }
                )
                approved_items.append({"id": application.id, "status": application.status})
                await session.commit()
                continue

            credential = await vault_service.resolve_credential(
                session=session,
                user_id=user.id,
                site_names=[job.source, auto_apply_service.detect_ats(job)],
                encryption_service=encryption_service,
            )
            result = auto_apply_service.apply(
                application=application,
                job=job,
                has_credentials=credential is not None,
            )

            application.ats_provider = result.ats_provider
            application.confirmation_url = result.confirmation_url
            application.confirmation_number = result.confirmation_number
            application.is_demo = result.is_demo
            application.screenshot_urls = result.screenshot_urls
            application.failure_reason = result.failure_reason
            application.manual_required_reason = result.manual_required_reason

            if result.status == "success":
                application.status = "applied"
                application.applied_at = datetime.now(timezone.utc)
            elif result.status == "manual_required":
                application.status = "manual_required"
            else:
                application.status = "failed"

            approved_items.append({"id": application.id, "status": application.status})
            await session.commit()
        except Exception as error:
            await session.rollback()
            failed_application = await session.scalar(select(Application).where(Application.id == application.id))
            if failed_application is not None:
                failed_application.status = "failed"
                failed_application.is_demo = False
                failed_application.failure_reason = f"Auto-apply node failed: {error}"
                await session.commit()
            errors.append(
                {
                    "node": "auto_apply_node",
                    "application_id": application.id,
                    "message": str(error),
                }
            )
            approved_items.append({"id": application.id, "status": "failed"})

    pipeline_run.current_node = "auto_apply_node"
    pipeline_run.applications_submitted = len([item for item in approved_items if item["status"] == "applied"])
    await session.commit()

    state["approved_applications"] = approved_items
    state["current_node"] = "auto_apply_node"
    return state


async def track_applications_node(
    state: ApplyIQState,
    *,
    session: AsyncSession,
    pipeline_run: PipelineRun,
) -> ApplyIQState:
    applications = list(
        await session.scalars(
            select(Application).where(
                Application.pipeline_run_id == pipeline_run.id,
            )
        )
    )
    applied_applications = [
        {"id": application.id, "status": application.status}
        for application in applications
        if application.status == "applied"
    ]
    pipeline_run.status = "complete"
    pipeline_run.current_node = "track_applications_node"
    pipeline_run.completed_at = datetime.now(timezone.utc)
    await session.commit()

    state["current_node"] = "track_applications_node"
    state["applied_applications"] = applied_applications
    return state


def _serialize_state(state: ApplyIQState) -> str:
    import json

    return json.dumps(state)
