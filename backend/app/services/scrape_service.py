from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


class ScrapeService:
    def __init__(
        self,
        *,
        embedding_service: EmbeddingService,
        deduplicator: JobDeduplicator,
        scrapers: dict[str, BaseJobScraper] | None = None,
    ) -> None:
        self._embedding_service = embedding_service
        self._deduplicator = deduplicator
        self._scrapers = scrapers or {
            "linkedin": ApifyLinkedInScraper(),
            "indeed": IndeedScraper(),
            "remotive": RemotiveScraper(),
            "wellfound": WellfoundScraper(),
            "serpapi": SerpApiJobsScraper(),
        }

    async def run_test_scrape(
        self,
        *,
        session: AsyncSession,
        query: ScrapeQuery,
        sources: list[str],
    ) -> ScrapeTestData:
        selected_scrapers = [self._scrapers[source] for source in sources]
        scraped_batches = await asyncio.gather(*(scraper.fetch_jobs(query) for scraper in selected_scrapers))
        raw_jobs = [job for batch in scraped_batches for job in batch]
        deduplicated_jobs = self._deduplicator.deduplicate(raw_jobs)
        stored_jobs_count = await self._upsert_jobs(session=session, jobs=deduplicated_jobs)

        return ScrapeTestData(
            sources_used=sources,
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

    async def _upsert_jobs(self, *, session: AsyncSession, jobs: list[RawJob]) -> int:
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

        await session.commit()
        return len(jobs)
