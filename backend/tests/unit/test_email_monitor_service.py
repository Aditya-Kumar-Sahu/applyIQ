from __future__ import annotations

import anyio

from app.core.config import Settings
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
