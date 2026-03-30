from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from typing import AsyncIterator

import anyio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.config import Settings
from app.core.logging_safety import log_debug, log_exception, text_snapshot
from app.models.application import Application
from app.models.email_monitor import EmailMonitor
from app.models.job import Job
from app.models.user import User
from app.schemas.notifications import NotificationItem, NotificationsData
from app.services.gemini_client import GeminiApiError, GeminiClient
from app.services.gmail_service import GmailService


logger = structlog.get_logger(__name__)


_CLASSIFICATION_LABELS = ("interview_request", "rejection", "offer", "follow_up_request", "no_action")
_CLASSIFICATION_SCHEMA = {
    "type": "object",
    "required": ["classification"],
    "properties": {
        "classification": {
            "type": "string",
            "enum": list(_CLASSIFICATION_LABELS),
        }
    },
}
_CLASSIFICATION_SYSTEM_INSTRUCTION = (
    "You classify recruiter emails for a job application tracker. "
    "Return strict JSON with a single classification field. "
    "Use interview_request for interview or scheduling messages, rejection for rejection/regret messages, "
    "offer for compensation or offer messages, follow_up_request for follow-up or more-information requests, "
    "and no_action for anything else. "
    "Do not include explanations."
)


@dataclass
class EmailMessage:
    thread_id: str
    sender: str
    subject: str
    body: str
    snippet: str


@dataclass
class PollResult:
    polled: bool
    processed_messages: int
    notifications: NotificationsData


class EmailMonitorService:
    def __init__(self, *, gmail_service: GmailService | None = None) -> None:
        self._gmail_service = gmail_service or GmailService()

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

    def _classify_message_deterministic(self, *, subject: str, body: str) -> str:
        return self.classify_message(subject=subject, body=body)

    async def process_messages(
        self,
        *,
        session: AsyncSession,
        user: User,
        messages: list[EmailMessage],
        settings: Settings | None = None,
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
                classification = await self._classify_message(
                    subject=message.subject,
                    body=message.body,
                    settings=settings,
                )
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

    async def poll_inbox(
        self,
        *,
        session: AsyncSession,
        user: User,
        encryption_service,
        settings: Settings,
    ) -> NotificationsData:
        result = await self.poll_inbox_with_stats(
            session=session,
            user=user,
            encryption_service=encryption_service,
            settings=settings,
        )
        return result.notifications

    async def poll_inbox_with_stats(
        self,
        *,
        session: AsyncSession,
        user: User,
        encryption_service,
        settings: Settings,
    ) -> PollResult:
        log_debug(logger, "email_monitor.poll_inbox.start", user_id=user.id)
        credentials = await self._gmail_service.get_credentials(
            session=session,
            user_id=user.id,
            encryption_service=encryption_service,
        )
        if credentials is None:
            log_debug(logger, "email_monitor.poll_inbox.no_credentials", user_id=user.id)
            return PollResult(polled=False, processed_messages=0, notifications=NotificationsData(items=[]))

        refreshed_credentials, refreshed = await self._gmail_service.refresh_credentials_if_expired(
            credentials=credentials,
            settings=settings,
        )
        if refreshed:
            await self._gmail_service.store_credentials(
                session=session,
                user_id=user.id,
                credentials=refreshed_credentials,
                encryption_service=encryption_service,
            )
        access_token = str(refreshed_credentials.get("access_token") or "")
        if not access_token:
            log_debug(logger, "email_monitor.poll_inbox.missing_access_token", user_id=user.id)
            return PollResult(polled=False, processed_messages=0, notifications=NotificationsData(items=[]))

        await self._gmail_service.touch_credentials(
            session=session,
            user_id=user.id,
            encryption_service=encryption_service,
            account_hint=user.email,
        )

        applications = list(await session.scalars(select(Application).where(Application.user_id == user.id)))
        if not applications:
            return PollResult(polled=True, processed_messages=0, notifications=NotificationsData(items=[]))
        jobs = list(await session.scalars(select(Job).where(Job.id.in_([application.job_id for application in applications]))))
        domains = sorted(
            {
                job.company_domain.lower().strip()
                for job in jobs
                if job.company_domain and job.company_domain.strip()
            }
        )
        query = self._build_query(
            company_domains=domains,
            last_checked_at=await self._resolve_last_checked_at(session=session, user_id=user.id),
        )
        message_ids = await self._gmail_service.list_message_ids(
            access_token=access_token,
            query=query,
            max_results=max(settings.gmail_poll_max_messages, 1),
        )
        fetched_messages: list[EmailMessage] = []
        for message_id in message_ids:
            payload = await self._gmail_service.get_message(access_token=access_token, message_id=message_id)
            parsed = self._parse_gmail_message(payload)
            if parsed is None:
                continue
            fetched_messages.append(parsed)

        log_debug(
            logger,
            "email_monitor.poll_inbox.messages_loaded",
            user_id=user.id,
            fetched_count=len(fetched_messages),
        )
        notifications = await self.process_messages(
            session=session,
            user=user,
            messages=fetched_messages,
            settings=settings,
        )
        return PollResult(
            polled=True,
            processed_messages=len(fetched_messages),
            notifications=notifications,
        )

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

    async def _classify_message(self, *, subject: str, body: str, settings: Settings | None) -> str:
        if settings is None or not settings.gemini_api_key or settings.environment.lower() == "test":
            return self._classify_message_deterministic(subject=subject, body=body)

        return await anyio.to_thread.run_sync(
            self._classify_message_with_gemini,
            subject,
            body,
            settings,
        )

    def _classify_message_with_gemini(self, subject: str, body: str, settings: Settings) -> str:
        client = GeminiClient(
            api_key=settings.gemini_api_key,
            chat_model=settings.gemini_chat_model,
            embedding_model=settings.gemini_embedding_model,
        )
        try:
            payload = client.generate_json(
                prompt=(
                    "Classify the following recruiter email.\n"
                    f"Subject: {subject}\n"
                    f"Body: {body}\n"
                ),
                system_instruction=_CLASSIFICATION_SYSTEM_INSTRUCTION,
                schema=_CLASSIFICATION_SCHEMA,
                temperature=0.0,
                model=settings.gemini_chat_model,
            )
            classification = _normalize_classification(str(payload.get("classification") or ""))
            log_debug(
                logger,
                "email_monitor.classify_message.gemini_success",
                classification=classification,
                subject=text_snapshot(subject),
            )
            return classification
        except (GeminiApiError, ValueError) as error:
            log_debug(
                logger,
                "email_monitor.classify_message.gemini_failed",
                reason=str(error),
                subject=text_snapshot(subject),
            )
            return self._classify_message_deterministic(subject=subject, body=body)
        except Exception as error:
            log_exception(logger, "email_monitor.classify_message.gemini_unexpected_error", error)
            return self._classify_message_deterministic(subject=subject, body=body)
        finally:
            client.close()

    async def _resolve_last_checked_at(self, *, session: AsyncSession, user_id: str) -> datetime | None:
        rows = list(await session.scalars(select(EmailMonitor).where(EmailMonitor.user_id == user_id)))
        if not rows:
            return None
        return max(row.last_checked_at for row in rows)

    def _build_query(self, *, company_domains: list[str], last_checked_at: datetime | None) -> str:
        keyword_clause = "subject:(interview OR application OR opportunity OR offer OR rejected OR follow up)"
        domain_clause = ""
        if company_domains:
            joined = " OR ".join(f"*@{domain}" for domain in company_domains[:15])
            domain_clause = f"from:({joined}) "

        after_clause = ""
        if last_checked_at is not None:
            ts = int(last_checked_at.timestamp())
            after_clause = f" after:{ts}"

        return f"{domain_clause}{keyword_clause}{after_clause}".strip()

    def _parse_gmail_message(self, payload: dict[str, object]) -> EmailMessage | None:
        thread_id = str(payload.get("threadId") or "")
        if not thread_id:
            return None

        message_payload = payload.get("payload")
        if not isinstance(message_payload, dict):
            return None

        headers = message_payload.get("headers", [])
        sender = _header_value(headers, "From")
        subject = _header_value(headers, "Subject")
        snippet = str(payload.get("snippet") or "")
        body = _extract_body_text(message_payload) or snippet
        return EmailMessage(
            thread_id=thread_id,
            sender=sender,
            subject=subject,
            body=body,
            snippet=snippet[:280],
        )


def _normalize_classification(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized == "follow_up":
        normalized = "follow_up_request"
    if normalized not in _CLASSIFICATION_LABELS:
        return "no_action"
    return normalized


def _application_status_for_classification(classification: str, current_status: str) -> str:
    if classification == "interview_request":
        return "interview_requested"
    if classification == "rejection":
        return "rejected"
    if classification == "offer":
        return "offer"
    return current_status


def _header_value(headers: object, name: str) -> str:
    if not isinstance(headers, list):
        return ""
    needle = name.lower()
    for item in headers:
        if not isinstance(item, dict):
            continue
        key = str(item.get("name") or "").lower()
        if key != needle:
            continue
        return str(item.get("value") or "")
    return ""


def _extract_body_text(message_payload: dict[str, object]) -> str:
    body = message_payload.get("body")
    if isinstance(body, dict):
        body_data = body.get("data")
        if isinstance(body_data, str) and body_data:
            decoded = _decode_base64url(body_data)
            if decoded:
                return _clean_html(decoded)

    parts = message_payload.get("parts")
    if isinstance(parts, list):
        for part in parts:
            if not isinstance(part, dict):
                continue
            mime_type = str(part.get("mimeType") or "").lower()
            part_body = part.get("body")
            if not isinstance(part_body, dict):
                continue
            data = part_body.get("data")
            if not isinstance(data, str) or not data:
                continue
            decoded = _decode_base64url(data)
            if not decoded:
                continue
            if mime_type == "text/plain":
                return decoded
            if mime_type == "text/html":
                return _clean_html(decoded)
    return ""


def _decode_base64url(value: str) -> str:
    padded = value + "=" * ((4 - len(value) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("utf-8"))
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _clean_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
