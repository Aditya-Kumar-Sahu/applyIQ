from __future__ import annotations

from types import SimpleNamespace

import anyio

from app.core.config import Settings
from app.schemas.notifications import NotificationsData
from app.services.email_monitor_service import EmailMonitorService


def test_email_classifier_maps_recruiter_messages_to_statuses() -> None:
    service = EmailMonitorService()

    assert (
        service.classify_message(
            subject="Interview availability for Company 1",
            body="We would love to schedule an interview next week.",
        )
        == "interview_request"
    )
    assert (
        service.classify_message(
            subject="Update on your application",
            body="We regret to inform you that we will not be moving forward.",
        )
        == "rejection"
    )
    assert (
        service.classify_message(
            subject="Offer details",
            body="We are excited to extend an offer for the role.",
        )
        == "offer"
    )


def test_email_classifier_uses_gemini_when_configured(monkeypatch) -> None:
    settings = Settings(
        environment="development",
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost:6390/0",
        jwt_secret_key="test-jwt-secret-key-with-32-characters",
        fernet_secret_key="wWKJg6WVKwwhFVWG2yt30YIOCwVDDDeWGPAHDLcGRID=",
        encryption_pepper="pepper-for-tests",
        gemini_api_key="test-gemini-key",
        gemini_chat_model="gemini-2.0-flash",
        gemini_embedding_model="text-embedding-004",
    )

    class _FakeGeminiClient:
        def __init__(self, **kwargs) -> None:
            self.closed = False

        def generate_json(self, **kwargs):
            return {"classification": "offer"}

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr("app.services.email_monitor_service.GeminiClient", _FakeGeminiClient)

    service = EmailMonitorService()

    async def classify() -> str:
        return await service._classify_message(
            subject="Offer details",
            body="We are excited to extend an offer for the role.",
            settings=settings,
        )

    assert anyio.run(classify) == "offer"


class _FakeDatabase:
    def __init__(self) -> None:
        self.sessions: list[object] = []

    def session(self):
        database = self

        class _SessionContext:
            async def __aenter__(self):
                session = object()
                database.sessions.append(session)
                return session

            async def __aexit__(self, exc_type, exc, tb):
                return None

        return _SessionContext()


def test_notifications_stream_opens_a_fresh_session_per_poll(monkeypatch) -> None:
    service = EmailMonitorService()
    database = _FakeDatabase()
    user = SimpleNamespace(id="user-1")

    async def fake_get_notifications(*, session, user):
        return NotificationsData(items=[])

    monkeypatch.setattr(service, "get_notifications", fake_get_notifications)

    async def exercise() -> tuple[list[str], list[object]]:
        events: list[str] = []
        stream = service.stream_notifications_events(database=database, user=user, poll_interval_seconds=0)
        try:
            events.append(await anext(stream))
            events.append(await anext(stream))
        finally:
            await stream.aclose()
        return events, database.sessions

    events, sessions = anyio.run(exercise)

    assert len(events) == 2
    assert len(sessions) == 2
    assert sessions[0] != sessions[1]
