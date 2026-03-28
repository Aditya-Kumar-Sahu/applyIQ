from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.email_monitor import EmailMonitor
from app.models.job import Job
from app.models.user import User
from app.schemas.notifications import NotificationItem, NotificationsData


@dataclass
class EmailMessage:
    thread_id: str
    sender: str
    subject: str
    body: str
    snippet: str


class EmailMonitorService:
    def classify_message(self, *, subject: str, body: str) -> str:
        lowered = f"{subject} {body}".lower()
        if any(keyword in lowered for keyword in ("offer", "compensation package", "joining bonus")):
            return "offer"
        if any(keyword in lowered for keyword in ("interview", "schedule", "availability", "next round")):
            return "interview_request"
        if any(keyword in lowered for keyword in ("regret", "not moving forward", "unfortunately", "declined")):
            return "rejection"
        if any(keyword in lowered for keyword in ("follow up", "follow-up", "additional information", "question")):
            return "follow_up_request"
        return "no_action"

    async def process_messages(
        self,
        *,
        session: AsyncSession,
        user: User,
        messages: list[EmailMessage],
    ) -> NotificationsData:
        applications = list(await session.scalars(select(Application).where(Application.user_id == user.id)))
        jobs_by_id = {
            job.id: job
            for job in list(await session.scalars(select(Job).where(Job.id.in_([application.job_id for application in applications]))))
        }
        notifications: list[NotificationItem] = []

        for message in messages:
            classification = self.classify_message(subject=message.subject, body=message.body)
            if classification == "no_action":
                continue

            matched_application: Application | None = None
            matched_job: Job | None = None
            sender_lower = message.sender.lower()
            message_text = f"{message.subject} {message.body}".lower()

            for application in applications:
                job = jobs_by_id.get(application.job_id)
                if job is None:
                    continue
                domain_match = job.company_domain and job.company_domain.lower() in sender_lower
                company_match = job.company_name.lower() in message_text
                if domain_match or company_match:
                    matched_application = application
                    matched_job = job
                    break

            if matched_application is None or matched_job is None:
                continue

            monitor = await session.scalar(
                select(EmailMonitor).where(
                    EmailMonitor.user_id == user.id,
                    EmailMonitor.application_id == matched_application.id,
                )
            )
            if monitor is None:
                monitor = EmailMonitor(
                    user_id=user.id,
                    application_id=matched_application.id,
                    gmail_thread_id=message.thread_id,
                    sender=message.sender,
                    subject=message.subject,
                )
                session.add(monitor)

            monitor.gmail_thread_id = message.thread_id
            monitor.sender = message.sender
            monitor.subject = message.subject
            monitor.snippet = message.snippet
            monitor.latest_classification = classification
            monitor.last_checked_at = datetime.now(timezone.utc)
            monitor.is_resolved = classification in {"rejection", "offer"}

            matched_application.status = _application_status_for_classification(classification, matched_application.status)

            notifications.append(
                NotificationItem(
                    application_id=matched_application.id,
                    company_name=matched_job.company_name,
                    title=matched_job.title,
                    classification=classification,
                    snippet=message.snippet,
                    created_at=monitor.last_checked_at,
                )
            )

        await session.commit()
        return NotificationsData(items=notifications)

    async def get_notifications(self, *, session: AsyncSession, user: User) -> NotificationsData:
        monitors = list(
            await session.scalars(
                select(EmailMonitor).where(
                    EmailMonitor.user_id == user.id,
                    EmailMonitor.latest_classification != "no_action",
                )
            )
        )

        notifications: list[NotificationItem] = []
        for monitor in monitors:
            application = await session.scalar(select(Application).where(Application.id == monitor.application_id))
            job = await session.scalar(select(Job).where(Job.id == application.job_id)) if application else None
            if application is None or job is None:
                continue
            notifications.append(
                NotificationItem(
                    application_id=application.id,
                    company_name=job.company_name,
                    title=job.title,
                    classification=monitor.latest_classification,
                    snippet=monitor.snippet,
                    created_at=monitor.last_checked_at,
                )
            )

        notifications.sort(key=lambda item: item.created_at, reverse=True)
        return NotificationsData(items=notifications)

    async def get_notifications_event(self, *, session: AsyncSession, user: User) -> str:
        data = await self.get_notifications(session=session, user=user)
        return f"event: notifications\ndata: {json.dumps(data.model_dump(mode='json'))}\n\n"


def _application_status_for_classification(classification: str, current_status: str) -> str:
    if classification == "interview_request":
        return "interview_requested"
    if classification == "rejection":
        return "rejected"
    if classification == "offer":
        return "offer"
    return current_status
