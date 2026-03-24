from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.pipeline_run import PipelineRun
from app.models.user import User
from app.pipeline.checkpointer import PipelineCheckpointer
from app.pipeline.state import ApplyIQState
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
) -> ApplyIQState:
    pending_approvals: list[dict[str, str | int | float]] = []
    for ranked_job in state["ranked_jobs"]:
        application = Application(
            user_id=user.id,
            job_id=str(ranked_job["job_id"]),
            pipeline_run_id=pipeline_run.id,
            status="pending_approval",
            match_score=float(ranked_job["match_score"]),
            cover_letter_text=_generate_cover_letter(str(ranked_job["company_name"]), str(ranked_job["title"])),
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
    for application in applications:
        application.approved_at = application.approved_at or datetime.now(timezone.utc)
        approved_items.append({"id": application.id, "status": application.status})

    pipeline_run.current_node = "auto_apply_node"
    pipeline_run.applications_submitted = len(applications)
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
    pipeline_run.status = "complete"
    pipeline_run.current_node = "track_applications_node"
    pipeline_run.completed_at = datetime.now(timezone.utc)
    await session.commit()

    state["current_node"] = "track_applications_node"
    state["applied_applications"] = state["approved_applications"]
    return state


def _generate_cover_letter(company_name: str, title: str) -> str:
    return (
        f"{company_name} stands out for the way it is building in this market. "
        f"My recent work shipping ML and backend systems maps well to the {title} role, "
        "and I would be excited to bring that execution focus here."
    )


def _serialize_state(state: ApplyIQState) -> str:
    import json

    return json.dumps(state)
