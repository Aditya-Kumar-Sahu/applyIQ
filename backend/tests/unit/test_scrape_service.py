from __future__ import annotations

from pathlib import Path

import anyio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.base import Base
from app.schemas.jobs import RawJob
from app.scrapers.base import ScrapeQuery, build_fixture_jobs
from app.scrapers.deduplicator import JobDeduplicator
from app.services.embedding_service import EmbeddingService
from app.services.scrape_service import ScrapeService


class _FixtureScraper:
    def __init__(self, source_name: str) -> None:
        self.source_name = source_name

    async def fetch_jobs(self, query: ScrapeQuery) -> list[RawJob]:
        return build_fixture_jobs(self.source_name, query)


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
                "linkedin": _FixtureScraper("linkedin"),
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