from __future__ import annotations

from pathlib import Path

import anyio
from fastapi.testclient import TestClient
from sqlalchemy import select, func

from app.core.config import Settings
from app.main import create_app
from app.models.refresh_token_session import RefreshTokenSession
from app.models.base import Base


class _FakeRedisClient:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}
        self.deleted_keys: list[str] = []

    @property
    def client(self) -> "_FakeRedisClient":
        return self

    async def incr(self, key: str) -> int:
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def expire(self, key: str, window_seconds: int) -> bool:
        return True

    async def delete(self, *keys: str) -> int:
        self.deleted_keys.extend(keys)
        return len(keys)

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None


def test_auth_register_login_refresh_and_delete_flow(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}",
        redis_url="redis://localhost:6390/0",
        jwt_secret_key="test-jwt-secret-key-with-32-characters",
        fernet_secret_key="wWKJg6WVKwwhFVWG2yt30YIOCwVDDDeWGPAHDLcGRID=",
        encryption_pepper="pepper-for-tests",
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
        assert register_response.json()["data"]["user"]["email"] == "alex@example.com"
        assert "applyiq_access_token" in register_response.cookies
        assert "applyiq_refresh_token" in register_response.cookies

        me_response = client.get("/api/v1/auth/me")

        assert me_response.status_code == 200
        assert me_response.json()["data"]["user"]["email"] == "alex@example.com"

        client.cookies.clear()
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "alex@example.com", "password": "SuperSecret123!"},
        )

        assert login_response.status_code == 200
        assert "applyiq_access_token" in login_response.cookies
        assert "applyiq_refresh_token" in login_response.cookies

        refresh_response = client.post("/api/v1/auth/refresh")

        assert refresh_response.status_code == 200
        assert refresh_response.json()["data"]["token_type"] == "bearer"

        delete_response = client.request(
            "DELETE",
            "/api/v1/auth/account",
            json={"password_confirmation": "SuperSecret123!"},
        )

        assert delete_response.status_code == 200
        assert delete_response.json()["data"]["deleted"] is True

        failed_login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "alex@example.com", "password": "SuperSecret123!"},
        )

        assert failed_login_response.status_code == 401


def test_auth_rate_limits_and_refresh_reuse_detection(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'auth_limits.db'}",
        redis_url="redis://localhost:6390/0",
        jwt_secret_key="test-jwt-secret-key-with-32-characters",
        fernet_secret_key="wWKJg6WVKwwhFVWG2yt30YIOCwVDDDeWGPAHDLcGRID=",
        encryption_pepper="pepper-for-tests",
        auth_register_rate_limit=1,
        auth_login_rate_limit=1,
        auth_rate_window_seconds=60,
    )

    async def healthy_reporter() -> dict[str, str]:
        return {"status": "ok", "db": "up", "redis": "up"}

    app = create_app(settings=settings, health_reporter=healthy_reporter)
    app.state.redis = _FakeRedisClient()

    with TestClient(app) as client:
        anyio.run(_create_all_tables, app.state.database.engine)

        first_register_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "alex@example.com",
                "password": "SuperSecret123!",
                "full_name": "Alex Candidate",
            },
        )

        assert first_register_response.status_code == 201

        second_register_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "alex@example.com",
                "password": "SuperSecret123!",
                "full_name": "Alex Candidate",
            },
        )

        assert second_register_response.status_code == 429

        client.cookies.clear()
        first_login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "alex@example.com", "password": "SuperSecret123!"},
        )

        assert first_login_response.status_code == 200

        second_login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "alex@example.com", "password": "SuperSecret123!"},
        )

        assert second_login_response.status_code == 429

        first_refresh_token = first_login_response.cookies.get(settings.refresh_cookie_name)
        assert first_refresh_token is not None

        client.cookies.set(settings.refresh_cookie_name, first_refresh_token)
        rotation_response = client.post("/api/v1/auth/refresh")

        assert rotation_response.status_code == 200

        rotated_refresh_token = rotation_response.cookies.get(settings.refresh_cookie_name)
        assert rotated_refresh_token is not None

        client.cookies.set(settings.refresh_cookie_name, first_refresh_token)
        reuse_response = client.post("/api/v1/auth/refresh")

        assert reuse_response.status_code == 401
        assert reuse_response.json()["error"]["message"] == "Refresh token reuse detected"

        client.cookies.set(settings.refresh_cookie_name, rotated_refresh_token)
        revoked_session_response = client.post("/api/v1/auth/refresh")

        assert revoked_session_response.status_code == 401

        async def _count_refresh_sessions(engine) -> int:
            from sqlalchemy.ext.asyncio import async_sessionmaker

            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                result = await session.scalar(
                    select(func.count()).select_from(RefreshTokenSession).where(RefreshTokenSession.revoked_at.is_(None))
                )
                return int(result or 0)

        active_refresh_session_count = anyio.run(_count_refresh_sessions, app.state.database.engine)
        assert active_refresh_session_count == 0


async def _create_all_tables(engine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
