from __future__ import annotations

from datetime import datetime, timezone
import structlog
import httpx

from app.core.config import Settings, get_settings
from app.schemas.jobs import RawJob
from app.scrapers.base import BaseJobScraper, ScrapeQuery, build_fixture_jobs

logger = structlog.get_logger(__name__)

class SerpApiJobsScraper(BaseJobScraper):
    source_name = "serpapi"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings

    async def fetch_jobs(self, query: ScrapeQuery) -> list[RawJob]:
        settings = self._settings or get_settings()
        if not settings.serpapi_api_key or settings.is_non_production:
            return build_fixture_jobs(self.source_name, query)

        try:
            return await self._execute_serpapi_run(query, settings.serpapi_api_key)
        except Exception as e:
            logger.error("scraper.serpapi.error", error=str(e), source=self.source_name)
            return []

    async def _execute_serpapi_run(self, query: ScrapeQuery, api_key: str) -> list[RawJob]:
        params = {
            "engine": "google_jobs",
            "q": query.target_role,
            "api_key": api_key,
        }
        if query.location:
            params["location"] = query.location
            
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get("https://serpapi.com/search", params=params)
            resp.raise_for_status()
            data = resp.json()
            
            jobs_results = data.get("jobs_results", [])
            # limit
            jobs_results = jobs_results[:query.limit_per_source]
            return self._normalize(jobs_results)

    def _normalize(self, items: list[dict]) -> list[RawJob]:
        jobs = []
        for index, item in enumerate(items):
            title = item.get("title", "Unknown Role")
            company_name = item.get("company_name", "Unknown Company")
            
            related_links = item.get("related_links", [])
            apply_url = ""
            if related_links:
                apply_url = related_links[0].get("link", "")
                
            job_id = item.get("job_id", f"serp-{index}")
                
            jobs.append(
                RawJob(
                    external_id=job_id,
                    source=self.source_name,
                    title=title,
                    company_name=company_name,
                    company_domain="",
                    location=item.get("location", "Remote"),
                    is_remote="remote" in str(item.get("location", "")).lower(),
                    salary_min=None,
                    salary_max=None,
                    description_text=item.get("description", f"{title} at {company_name}"),
                    apply_url=apply_url,
                    posted_at=datetime.now(timezone.utc),
                )
            )
        return jobs
