from __future__ import annotations

import anyio

from app.core.config import get_settings
from app.core.database import DatabaseManager
from app.schemas.jobs import ScrapeTestData, ScrapeTestRequest
from app.scrapers.base import ScrapeQuery
from app.scrapers.deduplicator import JobDeduplicator
from app.services.embedding_service import EmbeddingService
from app.services.scrape_service import ScrapeService
from app.worker import celery_app


async def _run_scrape(payload: dict) -> dict:
    request = ScrapeTestRequest.model_validate(payload)
    settings = get_settings()
    database = DatabaseManager(settings.database_url)
    service = ScrapeService(
        embedding_service=EmbeddingService(),
        deduplicator=JobDeduplicator(),
        settings=settings,
    )

    try:
        async with database.session() as session:
            result = await service.run_test_scrape(
                session=session,
                query=ScrapeQuery(
                    target_role=request.target_role,
                    location=request.location,
                    limit_per_source=request.limit_per_source,
                ),
                sources=request.sources,
            )
    finally:
        await database.dispose()

    return ScrapeTestData.model_validate(result).model_dump(mode="json")


@celery_app.task(name="applyiq.scrape.test")
def run_scrape_test_task(payload: dict) -> dict:
    return anyio.run(_run_scrape, payload)
