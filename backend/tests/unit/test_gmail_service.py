from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from app.core.config import Settings
from app.services.gmail_service import GmailService


def test_gmail_auth_url_builds_and_state_round_trips() -> None:
    settings = Settings(
        environment="test",
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost:6390/0",
        jwt_secret_key="test-jwt-secret-key-with-32-characters",
        fernet_secret_key="wWKJg6WVKwwhFVWG2yt30YIOCwVDDDeWGPAHDLcGRID=",
        encryption_pepper="pepper-for-tests",
        google_client_id="test-client-id",
        google_client_secret="test-client-secret",
        google_redirect_uri="http://localhost:3000/oauth/callback",
    )
    service = GmailService()
    auth_url = service.build_auth_url(user_id="user-123", settings=settings)

    parsed = urlparse(auth_url)
    assert parsed.netloc == "accounts.google.com"
    query = parse_qs(parsed.query)
    assert query["client_id"][0] == "test-client-id"
    assert query["redirect_uri"][0] == "http://localhost:3000/oauth/callback"
    state = query["state"][0]
    assert service.validate_state(state=state, settings=settings) == "user-123"
