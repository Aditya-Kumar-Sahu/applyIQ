from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.email_monitor import EmailMonitor
from app.models.job import Job
from app.models.user import User
from app.schemas.applications import ApplicationDetailData, ApplicationListItem, ApplicationsListData, EmailMonitorData


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
