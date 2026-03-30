from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.config import Settings
from app.core.logging_safety import log_debug, log_exception
from app.models.job import Job
from app.schemas.jobs import RawJob, ScrapedJobPreview, ScrapeTestData
from app.scrapers.apify_linkedin import ApifyLinkedInScraper
from app.scrapers.base import BaseJobScraper, ScrapeQuery
from app.scrapers.deduplicator import JobDeduplicator
from app.scrapers.indeed import IndeedScraper
from app.scrapers.remotive import RemotiveScraper
from app.scrapers.serpapi_jobs import SerpApiJobsScraper
from app.scrapers.wellfound import WellfoundScraper
from app.services.embedding_service import EmbeddingService


logger = structlog.get_logger(__name__)


class ScrapeService:
    def __init__(
        self,
        *,
        embedding_service: EmbeddingService,
        deduplicator: JobDeduplicator,
        settings: Settings | None = None,
        scrapers: dict[str, BaseJobScraper] | None = None,
    ) -> None:
        self._embedding_service = embedding_service
        self._deduplicator = deduplicator
        self._scrapers = scrapers or {
            "linkedin": ApifyLinkedInScraper(settings=settings),
            "indeed": IndeedScraper(),
            "remotive": RemotiveScraper(settings=settings),
            "wellfound": WellfoundScraper(),
            "serpapi": SerpApiJobsScraper(settings=settings),
        }

    async def run_test_scrape(
        self,
        *,
        session: AsyncSession,
        query: ScrapeQuery,
        sources: list[str],
    ) -> ScrapeTestData:
        log_debug(
            logger,
            "scrape.run_test.start",
            sources=sources,
            query=query.model_dump() if hasattr(query, "model_dump") else str(query),
        )
        try:
            selected_scrapers = [self._scrapers[source] for source in sources]
            log_debug(logger, "scrape.run_test.selected_scrapers", count=len(selected_scrapers))

            scraped_batches = await asyncio.gather(
                *(scraper.fetch_jobs(query) for scraper in selected_scrapers),
                return_exceptions=True,
            )

            raw_jobs: list[RawJob] = []
            batch_sizes: list[int] = []
            failed_sources: list[str] = []
            for source, batch in zip(sources, scraped_batches, strict=False):
                if isinstance(batch, Exception):
                    failed_sources.append(source)
                    log_exception(logger, "scrape.run_test.scraper_failed", batch, source=source)
                    continue

                batch_sizes.append(len(batch))
                raw_jobs.extend(batch)

            log_debug(
                logger,
                "scrape.run_test.scraped",
                batch_sizes=batch_sizes,
                raw_jobs_count=len(raw_jobs),
                failed_sources=failed_sources,
            )

            deduplicated_jobs = self._deduplicator.deduplicate(raw_jobs)
            log_debug(
                logger,
                "scrape.run_test.deduplicated",
                deduplicated_jobs_count=len(deduplicated_jobs),
                dropped_count=len(raw_jobs) - len(deduplicated_jobs),
            )
            stored_jobs_count = await self._upsert_jobs(session=session, jobs=deduplicated_jobs)

            result = ScrapeTestData(
                sources_used=sources,
                failed_sources=failed_sources,
                raw_jobs_count=len(raw_jobs),
                deduplicated_jobs_count=len(deduplicated_jobs),
                stored_jobs_count=stored_jobs_count,
                jobs=[
                    ScrapedJobPreview(
                        title=job.title,
                        company_name=job.company_name,
                        source=job.source,
                        apply_url=job.apply_url,
                    )
                    for job in deduplicated_jobs[:5]
                ],
            )
            log_debug(logger, "scrape.run_test.complete", stored_jobs_count=stored_jobs_count)
            return result
        except Exception as error:
            log_exception(logger, "scrape.run_test.failed", error, sources=sources)
            raise

    async def _upsert_jobs(self, *, session: AsyncSession, jobs: list[RawJob]) -> int:
        log_debug(logger, "scrape.upsert_jobs.start", jobs_count=len(jobs))
        inserted_count = 0
        updated_count = 0
        for raw_job in jobs:
            existing = await session.scalar(select(Job).where(Job.apply_url == raw_job.apply_url))
            description_embedding = self._embedding_service.embed_text(
                f"{raw_job.title} {raw_job.company_name} {raw_job.description_text}"
            )

            if existing is None:
                existing = Job(
                    external_id=raw_job.external_id,
                    source=raw_job.source,
                    title=raw_job.title,
                    company_name=raw_job.company_name,
                    company_domain=raw_job.company_domain,
                    location=raw_job.location,
                    is_remote=raw_job.is_remote,
                    salary_min=raw_job.salary_min,
                    salary_max=raw_job.salary_max,
                    description_text=raw_job.description_text,
                    description_embedding=description_embedding,
                    apply_url=raw_job.apply_url,
                    posted_at=raw_job.posted_at,
                )
                session.add(existing)
                inserted_count += 1
                continue

            existing.external_id = raw_job.external_id
            existing.source = raw_job.source
            existing.title = raw_job.title
            existing.company_name = raw_job.company_name
            existing.company_domain = raw_job.company_domain
            existing.location = raw_job.location
            existing.is_remote = raw_job.is_remote
            existing.salary_min = raw_job.salary_min
            existing.salary_max = raw_job.salary_max
            existing.description_text = raw_job.description_text
            existing.description_embedding = description_embedding
            existing.posted_at = raw_job.posted_at
            existing.is_active = True
            updated_count += 1

        await session.commit()
        log_debug(
            logger,
            "scrape.upsert_jobs.complete",
            jobs_count=len(jobs),
            inserted_count=inserted_count,
            updated_count=updated_count,
        )
        return len(jobs)
