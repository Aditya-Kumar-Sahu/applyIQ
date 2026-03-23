from __future__ import annotations

from pathlib import Path

import anyio
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.base import Base


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


async def _create_all_tables(engine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
