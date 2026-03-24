from __future__ import annotations

from pathlib import Path

import anyio
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings
from app.main import create_app
from app.models.base import Base
from app.models.job import Job


def test_scrape_test_endpoint_persists_deduplicated_jobs_with_embeddings(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'scrape.db'}",
        redis_url="redis://localhost:6392/0",
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
                "email": "scraper@example.com",
                "password": "SuperSecret123!",
                "full_name": "Scrape User",
            },
        )

        assert register_response.status_code == 201

        scrape_response = client.post(
            "/api/v1/scrape/test",
            json={
                "target_role": "ML Engineer",
                "location": "Remote",
                "limit_per_source": 20,
                "sources": ["linkedin", "indeed", "remotive"],
            },
        )

        assert scrape_response.status_code == 200
        payload = scrape_response.json()["data"]
        assert payload["raw_jobs_count"] == 60
        assert payload["deduplicated_jobs_count"] == 53
        assert payload["stored_jobs_count"] == 53
        assert payload["sources_used"] == ["linkedin", "indeed", "remotive"]
        assert len(payload["jobs"]) == 5

        stored_jobs = anyio.run(_get_jobs, app.state.database.engine)

        assert len(stored_jobs) == 53
        assert all(job.description_embedding for job in stored_jobs)
        assert {job.source for job in stored_jobs} == {"linkedin", "indeed", "remotive"}


def test_scrape_test_endpoint_rejects_unsupported_sources(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'scrape-invalid.db'}",
        redis_url="redis://localhost:6393/0",
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
                "email": "invalid-source@example.com",
                "password": "SuperSecret123!",
                "full_name": "Invalid Source User",
            },
        )

        assert register_response.status_code == 201

        scrape_response = client.post(
            "/api/v1/scrape/test",
            json={
                "target_role": "ML Engineer",
                "location": "Remote",
                "limit_per_source": 5,
                "sources": ["linkedin", "monster"],
            },
        )

        assert scrape_response.status_code == 422


async def _create_all_tables(engine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def _get_jobs(engine) -> list[Job]:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        result = await session.scalars(select(Job).order_by(Job.title.asc()))
        return list(result)
