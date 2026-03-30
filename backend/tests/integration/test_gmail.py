from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import anyio
import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.core.security import EncryptionService
from app.main import create_app
from app.models.credential_vault import CredentialVault
from app.models.base import Base
from app.models.user import User
from app.services.gmail_service import GmailService


class _FakeRedisClient:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}

    @property
    def client(self) -> "_FakeRedisClient":
        return self

    async def incr(self, key: str) -> int:
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def expire(self, key: str, window_seconds: int) -> bool:
        return True

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None


def test_gmail_endpoints_report_status_and_poll(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'gmail.db'}",
        redis_url="redis://localhost:6390/0",
        jwt_secret_key="test-jwt-secret-key-with-32-characters",
        fernet_secret_key="wWKJg6WVKwwhFVWG2yt30YIOCwVDDDeWGPAHDLcGRID=",
        encryption_pepper="pepper-for-tests",
        google_client_id="test-client-id",
        google_client_secret="test-client-secret",
        google_redirect_uri="http://localhost:3000/oauth/callback",
    )

    async def healthy_reporter() -> dict[str, str]:
        return {"status": "ok", "db": "up", "redis": "up"}

    app = create_app(settings=settings, health_reporter=healthy_reporter)
    app.state.redis = _FakeRedisClient()

    with TestClient(app) as client:
        anyio.run(_create_all_tables, app.state.database.engine)

        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "alex@example.com",
                "password": "SuperSecret123!",
                "full_name": "Alex Candidate",
            },
        )
        assert register_response.status_code == 201

        auth_url_response = client.get("/api/v1/gmail/auth-url")
        assert auth_url_response.status_code == 200
        auth_url = auth_url_response.json()["data"]["auth_url"]
        assert "accounts.google.com" in auth_url
        assert "client_id=test-client-id" in auth_url

        status_response = client.get("/api/v1/gmail/status")
        assert status_response.status_code == 200
        status_payload = status_response.json()["data"]
        assert status_payload["connected"] is False
        assert status_payload["email"] is None

        poll_response = client.post("/api/v1/gmail/poll")
        assert poll_response.status_code == 200
        poll_payload = poll_response.json()["data"]
        assert poll_payload["polled"] is False
        assert poll_payload["processed_messages"] == 0


def test_gmail_callback_redirects_to_settings(tmp_path: Path, monkeypatch) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'gmail-callback.db'}",
        redis_url="redis://localhost:6390/0",
        jwt_secret_key="test-jwt-secret-key-with-32-characters",
        fernet_secret_key="wWKJg6WVKwwhFVWG2yt30YIOCwVDDDeWGPAHDLcGRID=",
        encryption_pepper="pepper-for-tests",
        google_client_id="test-client-id",
        google_client_secret="test-client-secret",
        google_redirect_uri="http://localhost:3000/oauth/callback",
    )

    async def healthy_reporter() -> dict[str, str]:
        return {"status": "ok", "db": "up", "redis": "up"}

    async def fake_exchange_code_for_credentials(self, *, code: str, settings: Settings) -> dict[str, str]:
        return {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_type": "Bearer",
            "scope": settings.gmail_oauth_scope,
            "expires_at": "2026-03-30T00:00:00+00:00",
        }

    async def fake_get_profile(self, *, access_token: str) -> dict[str, str]:
        return {"emailAddress": "alex@example.com"}

    monkeypatch.setattr(GmailService, "exchange_code_for_credentials", fake_exchange_code_for_credentials)
    monkeypatch.setattr(GmailService, "get_profile", fake_get_profile)

    app = create_app(settings=settings, health_reporter=healthy_reporter)
    app.state.redis = _FakeRedisClient()

    with TestClient(app) as client:
        anyio.run(_create_all_tables, app.state.database.engine)

        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "alex@example.com",
                "password": "SuperSecret123!",
                "full_name": "Alex Candidate",
            },
        )
        assert register_response.status_code == 201

        auth_url = client.get("/api/v1/gmail/auth-url").json()["data"]["auth_url"]
        state = parse_qs(urlparse(auth_url).query)["state"][0]

        callback_response = client.get(f"/api/v1/gmail/callback?code=test-code&state={state}", follow_redirects=False)
        assert callback_response.status_code == 303
        assert callback_response.headers["location"].endswith("/settings?gmail=connected")

        status_response = client.get("/api/v1/gmail/status")
        assert status_response.status_code == 200
        status_payload = status_response.json()["data"]
        assert status_payload["connected"] is True
        assert status_payload["gmail_account_hint"] == "alex@example.com"
        assert status_payload["email"] == "alex@example.com"


def test_gmail_callback_tolerates_profile_lookup_failure(tmp_path: Path, monkeypatch) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'gmail-profile-fallback.db'}",
        redis_url="redis://localhost:6390/0",
        jwt_secret_key="test-jwt-secret-key-with-32-characters",
        fernet_secret_key="wWKJg6WVKwwhFVWG2yt30YIOCwVDDDeWGPAHDLcGRID=",
        encryption_pepper="pepper-for-tests",
        google_client_id="test-client-id",
        google_client_secret="test-client-secret",
        google_redirect_uri="http://localhost:3000/oauth/callback",
    )

    async def healthy_reporter() -> dict[str, str]:
        return {"status": "ok", "db": "up", "redis": "up"}

    async def fake_exchange_code_for_credentials(self, *, code: str, settings: Settings) -> dict[str, str]:
        return {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_type": "Bearer",
            "scope": settings.gmail_oauth_scope,
            "expires_at": "2026-03-30T00:00:00+00:00",
        }

    async def failing_get_profile(self, *, access_token: str) -> dict[str, str]:
        request = httpx.Request("GET", "https://gmail.googleapis.com/gmail/v1/users/me/profile")
        response = httpx.Response(403, request=request)
        raise httpx.HTTPStatusError("Forbidden", request=request, response=response)

    monkeypatch.setattr(GmailService, "exchange_code_for_credentials", fake_exchange_code_for_credentials)
    monkeypatch.setattr(GmailService, "get_profile", failing_get_profile)

    app = create_app(settings=settings, health_reporter=healthy_reporter)
    app.state.redis = _FakeRedisClient()

    with TestClient(app) as client:
        anyio.run(_create_all_tables, app.state.database.engine)

        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "alex@example.com",
                "password": "SuperSecret123!",
                "full_name": "Alex Candidate",
            },
        )
        assert register_response.status_code == 201

        auth_url = client.get("/api/v1/gmail/auth-url").json()["data"]["auth_url"]
        state = parse_qs(urlparse(auth_url).query)["state"][0]

        callback_response = client.get(f"/api/v1/gmail/callback?code=test-code&state={state}", follow_redirects=False)
        assert callback_response.status_code == 303
        assert callback_response.headers["location"].endswith("/settings?gmail=connected")

        status_response = client.get("/api/v1/gmail/status")
        assert status_response.status_code == 200
        status_payload = status_response.json()["data"]
        assert status_payload["connected"] is True
        assert status_payload["gmail_account_hint"] == "alex@example.com"
        assert status_payload["email"] == "alex@example.com"


def test_gmail_poll_updates_last_checked_and_backfills_placeholder_hint(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'gmail-poll.db'}",
        redis_url="redis://localhost:6390/0",
        jwt_secret_key="test-jwt-secret-key-with-32-characters",
        fernet_secret_key="wWKJg6WVKwwhFVWG2yt30YIOCwVDDDeWGPAHDLcGRID=",
        encryption_pepper="pepper-for-tests",
        google_client_id="test-client-id",
        google_client_secret="test-client-secret",
        google_redirect_uri="http://localhost:3000/oauth/callback",
    )

    async def healthy_reporter() -> dict[str, str]:
        return {"status": "ok", "db": "up", "redis": "up"}

    app = create_app(settings=settings, health_reporter=healthy_reporter)
    app.state.redis = _FakeRedisClient()

    with TestClient(app) as client:
        anyio.run(_create_all_tables, app.state.database.engine)

        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "alex@example.com",
                "password": "SuperSecret123!",
                "full_name": "Alex Candidate",
            },
        )
        assert register_response.status_code == 201

        anyio.run(
            _insert_placeholder_gmail_credentials,
            app.state.database.engine,
            settings,
            "alex@example.com",
        )

        initial_status = client.get("/api/v1/gmail/status")
        assert initial_status.status_code == 200
        initial_payload = initial_status.json()["data"]
        assert initial_payload["connected"] is True
        assert initial_payload["gmail_account_hint"] == "alex@example.com"
        assert initial_payload["email"] == "alex@example.com"
        assert initial_payload["last_checked_at"] is None

        poll_response = client.post("/api/v1/gmail/poll")
        assert poll_response.status_code == 200
        poll_payload = poll_response.json()["data"]
        assert poll_payload["polled"] is True
        assert poll_payload["processed_messages"] == 0

        refreshed_status = client.get("/api/v1/gmail/status")
        assert refreshed_status.status_code == 200
        refreshed_payload = refreshed_status.json()["data"]
        assert refreshed_payload["connected"] is True
        assert refreshed_payload["gmail_account_hint"] == "alex@example.com"
        assert refreshed_payload["email"] == "alex@example.com"
        assert refreshed_payload["last_checked_at"] is not None


async def _create_all_tables(engine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def _insert_placeholder_gmail_credentials(engine, settings: Settings, email: str) -> None:
    encryption_service = EncryptionService(
        fernet_secret_key=settings.fernet_secret_key or "",
        encryption_pepper=settings.encryption_pepper or "",
    )
    async with app_session_from_engine(engine) as session:
        user = await session.scalar(select(User).where(User.email == email))
        assert user is not None
        credential = CredentialVault(
            user_id=user.id,
            site_name="gmail_oauth",
            site_url="https://mail.google.com",
            encrypted_username=encryption_service.encrypt_for_user(user.id, "gmail-oauth"),
            encrypted_password=encryption_service.encrypt_for_user(
                user.id,
                json.dumps(
                    {
                        "access_token": "access-token",
                        "refresh_token": "refresh-token",
                        "token_type": "Bearer",
                        "scope": settings.gmail_oauth_scope,
                        "expires_at": "2026-04-30T00:00:00+00:00",
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            ),
        )
        session.add(credential)
        await session.commit()


def app_session_from_engine(engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return session_factory()
