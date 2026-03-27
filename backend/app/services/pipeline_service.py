from __future__ import annotations

import json

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    CoverLetterEditData,
    CoverLetterEditPayload,
    PipelineApplicationItem,
    PipelineResultsData,
    PipelineRunData,
    PipelineStartRequest,
    RejectData,
)


class PipelineService:
    def __init__(self, *, graph_runner: PipelineGraphRunner, encryption_service, cover_letter_service: CoverLetterService) -> None:
        self._graph_runner = graph_runner
        self._encryption_service = encryption_service
        self._cover_letter_service = cover_letter_service

    async def start_run(self, *, session: AsyncSession, user: User, payload: PipelineStartRequest) -> PipelineRunData:
        pipeline_run = PipelineRun(user_id=user.id, status="running", current_node="pending")
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
        final_state = await self._graph_runner.run_until_approval(
            session=session,
            pipeline_run=pipeline_run,
            user=user,
            initial_state=state,
        )
        return PipelineRunData(
            run_id=pipeline_run.id,
            status=pipeline_run.status,
            current_node=pipeline_run.current_node,
            jobs_found=pipeline_run.jobs_found,
            jobs_matched=pipeline_run.jobs_matched,
            applications_submitted=pipeline_run.applications_submitted,
            pending_approvals_count=len(final_state["pending_approvals"]),
        )

    async def get_results(self, *, session: AsyncSession, user: User, run_id: str) -> PipelineResultsData:
        pipeline_run = await self._get_run(session=session, user=user, run_id=run_id)
        applications = list(await session.scalars(select(Application).where(Application.pipeline_run_id == run_id)))

        items: list[PipelineApplicationItem] = []
        for application in applications:
            job = await session.scalar(select(Job).where(Job.id == application.job_id))
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
                )
            )

        return PipelineResultsData(
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

    async def approve(self, *, session: AsyncSession, user: User, run_id: str, application_ids: list[str]) -> PipelineRunData:
        pipeline_run = await self._get_run(session=session, user=user, run_id=run_id)
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

        await session.commit()
        await self._graph_runner.resume_after_approval(session=session, pipeline_run=pipeline_run, run_id=run_id)
        await session.refresh(pipeline_run)

        pending_count = len([application for application in applications if application.status == "pending_approval"])
        return PipelineRunData(
            run_id=pipeline_run.id,
            status=pipeline_run.status,
            current_node=pipeline_run.current_node,
            jobs_found=pipeline_run.jobs_found,
            jobs_matched=pipeline_run.jobs_matched,
            applications_submitted=pipeline_run.applications_submitted,
            pending_approvals_count=pending_count,
        )

    async def reject(self, *, session: AsyncSession, user: User, run_id: str, application_ids: list[str]) -> RejectData:
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
        return RejectData(rejected_count=len(applications))

    async def edit_cover_letter(
        self,
        *,
        session: AsyncSession,
        user: User,
        run_id: str,
        application_id: str,
        payload: CoverLetterEditPayload,
    ) -> CoverLetterEditData:
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

        return CoverLetterEditData(
            application_id=application.id,
            cover_letter_text=application.cover_letter_text,
            tone=application.cover_letter_tone,
            word_count=application.cover_letter_word_count,
            cover_letter_version=application.cover_letter_version,
        )

    async def regenerate_cover_letter(
        self,
        *,
        session: AsyncSession,
        user: User,
        run_id: str,
        application_id: str,
    ) -> CoverLetterEditData:
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

        return CoverLetterEditData(
            application_id=application.id,
            cover_letter_text=application.cover_letter_text,
            tone=application.cover_letter_tone,
            word_count=application.cover_letter_word_count,
            cover_letter_version=application.cover_letter_version,
        )

    async def get_status_event(self, *, session: AsyncSession, user: User, run_id: str) -> str:
        data = await self.get_results(session=session, user=user, run_id=run_id)
        return f"event: status\ndata: {json.dumps(data.model_dump(mode='json'))}\n\n"

    async def _get_run(self, *, session: AsyncSession, user: User, run_id: str) -> PipelineRun:
        pipeline_run = await session.scalar(
            select(PipelineRun).where(PipelineRun.id == run_id, PipelineRun.user_id == user.id)
        )
        if pipeline_run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline run not found")
        return pipeline_run
