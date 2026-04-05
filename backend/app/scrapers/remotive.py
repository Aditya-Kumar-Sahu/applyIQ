from __future__ import annotations

from datetime import datetime, timezone
import structlog

from app.schemas.jobs import RawJob
from app.scrapers.base import BaseJobScraper, ScrapeQuery
from app.scrapers.etiquette import TolerantAsyncClient

logger = structlog.get_logger(__name__)

class RemotiveScraper(BaseJobScraper):
    source_name = "remotive"
    base_url = "https://remotive.com"

    def __init__(self, settings: object | None = None) -> None:
        self._settings = settings

    async def fetch_jobs(self, query: ScrapeQuery) -> list[RawJob]:
        params = {"search": query.target_role, "limit": query.limit_per_source}
        if query.location:
            params["location"] = query.location

        try:
            target_url = f"{self.base_url}/api/remote-jobs"
            async with TolerantAsyncClient(base_url=self.base_url, timeout=30.0) as client:
                resp = await client.get_with_etiquette(target_url, params=params)
            data = resp.json()
            jobs_results = data.get("jobs", [])
            jobs_results = jobs_results[:query.limit_per_source]
            return self._normalize(jobs_results)
        except Exception as e:
            logger.error("scraper.remotive.error", error=str(e), source=self.source_name)
            raise RuntimeError("remotive scraping failed") from e

    def _normalize(self, items: list[dict]) -> list[RawJob]:
        jobs = []
        for index, item in enumerate(items):
            title = item.get("title", "Unknown Role")
            company_name = item.get("company_name", "Unknown Company")
            apply_url = item.get("url", "")
            job_id = item.get("id", f"remotive-{index}")

            jobs.append(
                RawJob(
                    external_id=str(job_id),
                    source=self.source_name,
                    title=title,
                    company_name=company_name,
                    company_domain="",
                    location=item.get("candidate_required_location", "Remote"),
                    is_remote=True,
                    salary_min=None,
                    salary_max=None,
                    description_text=item.get("description", f"{title} at {company_name}"),
                    apply_url=apply_url,
                    posted_at=datetime.now(timezone.utc),
                )
            )
        return jobs
