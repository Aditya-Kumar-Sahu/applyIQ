from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import anyio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.base import Base
from app.schemas.jobs import RawJob
from app.scrapers.base import ScrapeQuery
from app.scrapers.deduplicator import JobDeduplicator
from app.services.embedding_service import EmbeddingService
from app.services.scrape_service import ScrapeService


class _FixtureScraper:
    def __init__(self, jobs: list[RawJob]) -> None:
        self._jobs = jobs

    async def fetch_jobs(self, query: ScrapeQuery) -> list[RawJob]:
        return self._jobs[: query.limit_per_source]


class _FailingScraper:
    def __init__(self, source_name: str) -> None:
        self.source_name = source_name

    async def fetch_jobs(self, query: ScrapeQuery) -> list[RawJob]:
        raise RuntimeError(f"{self.source_name} scraper unavailable")


def test_run_test_scrape_keeps_successful_sources_when_one_fails(tmp_path: Path) -> None:
    async def run_test() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'scrape-service.db'}")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        service = ScrapeService(
            embedding_service=EmbeddingService(),
            deduplicator=JobDeduplicator(),
            scrapers={
                "linkedin": _FixtureScraper(
                    [
                        RawJob(
                            external_id="linkedin-1",
                            source="linkedin",
                            title="Senior ML Engineer",
                            company_name="Acme AI",
                            company_domain="acme.ai",
                            location="Remote",
                            is_remote=True,
                            salary_min=2500000,
                            salary_max=3500000,
                            description_text="Build ML systems with Python and FastAPI.",
                            apply_url="https://jobs.acme.ai/ml-engineer",
                            posted_at=datetime(2026, 3, 20, 10, 0, tzinfo=UTC),
                        ),
                        RawJob(
                            external_id="linkedin-2",
                            source="linkedin",
                            title="Lead Data Engineer",
                            company_name="Northstar Labs",
                            company_domain="northstar.dev",
                            location="Remote",
                            is_remote=True,
                            salary_min=3000000,
                            salary_max=3900000,
                            description_text="Pipeline role with strong data tooling.",
                            apply_url="https://northstar.dev/jobs/data-engineer",
                            posted_at=datetime(2026, 3, 20, 11, 0, tzinfo=UTC),
                        ),
                        RawJob(
                            external_id="linkedin-3",
                            source="linkedin",
                            title="MLOps Engineer",
                            company_name="City AI",
                            company_domain="cityai.example",
                            location="Remote",
                            is_remote=True,
                            salary_min=2800000,
                            salary_max=3600000,
                            description_text="MLOps and platform reliability.",
                            apply_url="https://cityai.example/jobs/mlops",
                            posted_at=datetime(2026, 3, 20, 12, 0, tzinfo=UTC),
                        ),
                        RawJob(
                            external_id="linkedin-4",
                            source="linkedin",
                            title="Platform Engineer",
                            company_name="Budget AI",
                            company_domain="budget.example",
                            location="Remote",
                            is_remote=True,
                            salary_min=1200000,
                            salary_max=1800000,
                            description_text="Below-preference sample role.",
                            apply_url="https://budget.example/jobs/platform",
                            posted_at=datetime(2026, 3, 20, 13, 0, tzinfo=UTC),
                        ),
                    ]
                ),
                "indeed": _FailingScraper("indeed"),
            },
        )

        async with session_factory() as session:
            result = await service.run_test_scrape(
                session=session,
                query=ScrapeQuery(target_role="ML Engineer", location="Remote", limit_per_source=4),
                sources=["linkedin", "indeed"],
            )

        assert result.sources_used == ["linkedin", "indeed"]
        assert result.failed_sources == ["indeed"]
        assert result.raw_jobs_count == 4
        assert result.deduplicated_jobs_count == 4
        assert result.stored_jobs_count == 4
        assert len(result.jobs) == 4

        await engine.dispose()

    anyio.run(run_test)