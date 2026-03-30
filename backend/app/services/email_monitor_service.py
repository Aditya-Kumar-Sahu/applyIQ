from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import AsyncIterator

import anyio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.logging_safety import log_debug, log_exception
from app.models.application import Application
from app.models.email_monitor import EmailMonitor
from app.models.job import Job
from app.models.user import User
from app.schemas.notifications import NotificationItem, NotificationsData


logger = structlog.get_logger(__name__)


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
            log_debug(logger, "email_monitor.classify_message", classification="offer")
            return "offer"
        if any(keyword in lowered for keyword in ("interview", "schedule", "availability", "next round")):
            log_debug(logger, "email_monitor.classify_message", classification="interview_request")
            return "interview_request"
        if any(keyword in lowered for keyword in ("regret", "not moving forward", "unfortunately", "declined")):
            log_debug(logger, "email_monitor.classify_message", classification="rejection")
            return "rejection"
        if any(keyword in lowered for keyword in ("follow up", "follow-up", "additional information", "question")):
            log_debug(logger, "email_monitor.classify_message", classification="follow_up_request")
            return "follow_up_request"
        log_debug(logger, "email_monitor.classify_message", classification="no_action")
        return "no_action"

    async def process_messages(
        self,
        *,
        session: AsyncSession,
        user: User,
        messages: list[EmailMessage],
    ) -> NotificationsData:
        log_debug(
            logger,
            "email_monitor.process_messages.start",
            user_id=user.id,
            messages_count=len(messages),
        )
        try:
            applications = list(await session.scalars(select(Application).where(Application.user_id == user.id)))
            jobs_by_id = {
                job.id: job
                for job in list(
                    await session.scalars(select(Job).where(Job.id.in_([application.job_id for application in applications])))
                )
            }
            notifications: list[NotificationItem] = []

            for index, message in enumerate(messages, start=1):
                classification = self.classify_message(subject=message.subject, body=message.body)
                log_debug(
                    logger,
                    "email_monitor.process_messages.message_classified",
                    user_id=user.id,
                    index=index,
                    classification=classification,
                )
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
                    log_debug(
                        logger,
                        "email_monitor.process_messages.unmatched",
                        user_id=user.id,
                        index=index,
                        classification=classification,
                    )
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
            log_debug(
                logger,
                "email_monitor.process_messages.complete",
                user_id=user.id,
                notifications_count=len(notifications),
            )
            return NotificationsData(items=notifications)
        except Exception as error:
            log_exception(logger, "email_monitor.process_messages.failed", error, user_id=user.id)
            raise

    async def get_notifications(self, *, session: AsyncSession, user: User) -> NotificationsData:
        log_debug(logger, "email_monitor.get_notifications.start", user_id=user.id)
        try:
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
            log_debug(logger, "email_monitor.get_notifications.complete", user_id=user.id, count=len(notifications))
            return NotificationsData(items=notifications)
        except Exception as error:
            log_exception(logger, "email_monitor.get_notifications.failed", error, user_id=user.id)
            raise

    async def get_notifications_event(self, *, session: AsyncSession, user: User) -> str:
        log_debug(logger, "email_monitor.get_notifications_event.start", user_id=user.id)
        data = await self.get_notifications(session=session, user=user)
        payload = f"event: notifications\ndata: {json.dumps(data.model_dump(mode='json'))}\n\n"
        log_debug(logger, "email_monitor.get_notifications_event.complete", user_id=user.id, payload_length=len(payload))
        return payload

    async def stream_notifications_events(
        self,
        *,
        session: AsyncSession,
        user: User,
        poll_interval_seconds: float = 5.0,
    ) -> AsyncIterator[str]:
        log_debug(
            logger,
            "email_monitor.stream_notifications.start",
            user_id=user.id,
            poll_interval_seconds=poll_interval_seconds,
        )
        last_payload: str | None = None
        while True:
            data = await self.get_notifications(session=session, user=user)
            serialized = json.dumps(data.model_dump(mode="json"))
            if serialized != last_payload:
                yield f"event: notifications\ndata: {serialized}\n\n"
                last_payload = serialized
            else:
                yield "event: heartbeat\ndata: {}\n\n"

            await anyio.sleep(poll_interval_seconds)


def _application_status_for_classification(classification: str, current_status: str) -> str:
    if classification == "interview_request":
        return "interview_requested"
    if classification == "rejection":
        return "rejected"
    if classification == "offer":
        return "offer"
    return current_status
