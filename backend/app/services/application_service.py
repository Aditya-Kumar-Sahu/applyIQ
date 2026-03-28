from __future__ import annotations

from collections import defaultdict

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.email_monitor import EmailMonitor
from app.models.job import Job
from app.models.user import User
from app.schemas.applications import (
    ApplicationDetailData,
    ApplicationListItem,
    ApplicationsListData,
    ApplicationsStatsData,
    EmailMonitorData,
    SourcePerformanceItem,
    TitlePerformanceItem,
)


class ApplicationService:
    async def list_applications(self, *, session: AsyncSession, user: User) -> ApplicationsListData:
        applications = list(await session.scalars(select(Application).where(Application.user_id == user.id)))
        items: list[ApplicationListItem] = []
        for application in applications:
            job = await session.scalar(select(Job).where(Job.id == application.job_id))
            monitor = await session.scalar(
                select(EmailMonitor).where(
                    EmailMonitor.user_id == user.id,
                    EmailMonitor.application_id == application.id,
                )
            )
            items.append(
                ApplicationListItem(
                    id=application.id,
                    job_id=application.job_id,
                    title=job.title if job else "Unknown Job",
                    company_name=job.company_name if job else "Unknown Company",
                    status=application.status,
                    match_score=application.match_score,
                    applied_at=application.applied_at,
                    latest_email_classification=monitor.latest_classification if monitor else None,
                )
            )

        items.sort(key=lambda item: (item.applied_at is None, item.applied_at), reverse=True)
        return ApplicationsListData(items=items)

    async def get_application_detail(self, *, session: AsyncSession, user: User, application_id: str) -> ApplicationDetailData:
        application = await session.scalar(
            select(Application).where(Application.user_id == user.id, Application.id == application_id)
        )
        if application is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

        job = await session.scalar(select(Job).where(Job.id == application.job_id))
        monitor = await session.scalar(
            select(EmailMonitor).where(
                EmailMonitor.user_id == user.id,
                EmailMonitor.application_id == application.id,
            )
        )

        return ApplicationDetailData(
            id=application.id,
            job_id=application.job_id,
            title=job.title if job else "Unknown Job",
            company_name=job.company_name if job else "Unknown Company",
            status=application.status,
            match_score=application.match_score,
            cover_letter_text=application.cover_letter_text,
            ats_provider=application.ats_provider,
            confirmation_url=application.confirmation_url,
            screenshot_urls=application.screenshot_urls,
            email_monitor=(
                EmailMonitorData(
                    gmail_thread_id=monitor.gmail_thread_id,
                    sender=monitor.sender,
                    subject=monitor.subject,
                    snippet=monitor.snippet,
                    latest_classification=monitor.latest_classification,
                    last_checked_at=monitor.last_checked_at,
                    is_resolved=monitor.is_resolved,
                )
                if monitor
                else None
            ),
        )

    async def get_stats(self, *, session: AsyncSession, user: User) -> ApplicationsStatsData:
        applications = list(await session.scalars(select(Application).where(Application.user_id == user.id)))
        if len(applications) == 0:
            return ApplicationsStatsData(
                total_applications=0,
                total_applied=0,
                total_replied=0,
                response_rate=0.0,
                avg_hours_to_first_reply=None,
                source_breakdown=[],
                top_titles=[],
            )

        application_ids = [application.id for application in applications]
        job_ids = [application.job_id for application in applications]
        jobs = list(await session.scalars(select(Job).where(Job.id.in_(job_ids))))
        monitors = list(
            await session.scalars(
                select(EmailMonitor).where(
                    EmailMonitor.user_id == user.id,
                    EmailMonitor.application_id.in_(application_ids),
                )
            )
        )
        jobs_by_id = {job.id: job for job in jobs}
        monitors_by_application_id = {monitor.application_id: monitor for monitor in monitors}

        total_applications = len(applications)
        total_applied = len([application for application in applications if application.applied_at is not None])
        replied_applications = {
            monitor.application_id
            for monitor in monitors
            if monitor.latest_classification != "no_action"
        }
        total_replied = len(replied_applications)
        response_rate = (total_replied / total_applied) if total_applied > 0 else 0.0

        reply_deltas: list[float] = []
        for application in applications:
            monitor = monitors_by_application_id.get(application.id)
            if monitor is None:
                continue
            if monitor.latest_classification == "no_action":
                continue
            if application.applied_at is None:
                continue
            delta_hours = (monitor.created_at - application.applied_at).total_seconds() / 3600
            reply_deltas.append(max(delta_hours, 0.0))
        avg_hours_to_first_reply = (
            sum(reply_deltas) / len(reply_deltas)
            if len(reply_deltas) > 0
            else None
        )

        source_totals: dict[str, int] = defaultdict(int)
        source_replies: dict[str, int] = defaultdict(int)
        title_totals: dict[str, int] = defaultdict(int)
        title_replies: dict[str, int] = defaultdict(int)
        for application in applications:
            job = jobs_by_id.get(application.job_id)
            if job is None:
                continue

            source_totals[job.source] += 1
            title_totals[job.title] += 1
            if application.id in replied_applications:
                source_replies[job.source] += 1
                title_replies[job.title] += 1

        source_breakdown = sorted(
            [
                SourcePerformanceItem(
                    source=source,
                    total_applications=total,
                    replied_count=source_replies.get(source, 0),
                    response_rate=(source_replies.get(source, 0) / total) if total > 0 else 0.0,
                )
                for source, total in source_totals.items()
            ],
            key=lambda item: (item.response_rate, item.total_applications),
            reverse=True,
        )

        top_titles = sorted(
            [
                TitlePerformanceItem(
                    title=title,
                    total_applications=total,
                    replied_count=title_replies.get(title, 0),
                    response_rate=(title_replies.get(title, 0) / total) if total > 0 else 0.0,
                )
                for title, total in title_totals.items()
            ],
            key=lambda item: (item.response_rate, item.total_applications),
            reverse=True,
        )[:5]

        return ApplicationsStatsData(
            total_applications=total_applications,
            total_applied=total_applied,
            total_replied=total_replied,
            response_rate=response_rate,
            avg_hours_to_first_reply=avg_hours_to_first_reply,
            source_breakdown=source_breakdown,
            top_titles=top_titles,
        )
