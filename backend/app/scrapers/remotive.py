from __future__ import annotations

from datetime import datetime, timezone
import httpx
import structlog

from app.schemas.jobs import RawJob
from app.scrapers.base import BaseJobScraper, ScrapeQuery

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
            async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
                resp = await client.get(f"{self.base_url}/api/remote-jobs", params=params)
                resp.raise_for_status()
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
