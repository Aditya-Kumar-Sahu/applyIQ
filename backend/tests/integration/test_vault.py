from __future__ import annotations

from pathlib import Path

import anyio
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.main import create_app
from app.models.base import Base
from app.models.credential_vault import CredentialVault


def test_credential_vault_store_list_and_delete(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'vault.db'}",
        redis_url="redis://localhost:6396/0",
        jwt_secret_key="test-jwt-secret-key-with-32-characters",
        fernet_secret_key="wWKJg6WVKwwhFVWG2yt30YIOCwVDDDeWGPAHDLcGRID=",
        encryption_pepper="pepper-for-tests",
    )

    async def healthy_reporter() -> dict[str, str]:
        return {"status": "ok", "db": "up", "redis": "up"}

    app = create_app(settings=settings, health_reporter=healthy_reporter)

    with TestClient(app) as client:
        anyio.run(_create_all_tables, app.state.database.engine)
        _register(client)

        store_response = client.post(
            "/api/v1/vault/credentials",
            json={
                "site_name": "linkedin",
                "site_url": "https://www.linkedin.com/jobs",
                "username": "candidate@example.com",
                "password": "SuperSecret123!",
            },
        )

        assert store_response.status_code == 201
        vault_item = store_response.json()["data"]
        assert vault_item["site_name"] == "linkedin"
        assert vault_item["masked_username"].startswith("c")

        async def fetch_saved_credential() -> CredentialVault | None:
            async with app.state.database.session() as session:
                return await session.scalar(select(CredentialVault).where(CredentialVault.site_name == "linkedin"))

        saved = anyio.run(fetch_saved_credential)
        assert saved is not None
        assert saved.encrypted_username != "candidate@example.com"
        assert saved.encrypted_password != "SuperSecret123!"

        list_response = client.get("/api/v1/vault/credentials")

        assert list_response.status_code == 200
        listed = list_response.json()["data"]["items"]
        assert len(listed) == 1
        assert listed[0]["site_name"] == "linkedin"

        delete_response = client.delete(f"/api/v1/vault/credentials/{vault_item['id']}")

        assert delete_response.status_code == 200
        assert delete_response.json()["data"]["deleted"] is True


async def _create_all_tables(engine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


def _register(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "vault-user@example.com",
            "password": "SuperSecret123!",
            "full_name": "Vault User",
        },
    )

    assert response.status_code == 201
