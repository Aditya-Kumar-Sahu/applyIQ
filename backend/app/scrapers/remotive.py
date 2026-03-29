from __future__ import annotations

from datetime import datetime, timezone
import structlog

from app.schemas.jobs import RawJob
from app.scrapers.base import BaseJobScraper, ScrapeQuery
from app.scrapers.etiquette import TolerantAyncClient

logger = structlog.get_logger(__name__)

class RemotiveScraper(BaseJobScraper):
    source_name = "remotive"
    base_url = "https://remotive.com"

    async def fetch_jobs(self, query: ScrapeQuery) -> list[RawJob]:
        from app.core.config import get_settings
        
        settings = get_settings()
        if settings.is_non_production:
            # Import locally to avoid circular import issues if base uses this
            from app.scrapers.base import build_fixture_jobs
            return build_fixture_jobs(self.source_name, query)
            
        params = {"search": query.target_role, "limit": query.limit_per_source}
        if query.location:
            params["location"] = query.location
            
        try:
            # We enforce scraping etiquette policy internally
            client = TolerantAyncClient(base_url=self.base_url, timeout=30.0)
            target_url = f"{self.base_url}/api/remote-jobs"
            resp = await client.get_with_etiquette(target_url, params=params)
            data = resp.json()
            jobs_results = data.get("jobs", [])
            # Limiting to per source
            jobs_results = jobs_results[:query.limit_per_source]
            return self._normalize(jobs_results)
        except Exception as e:
            logger.error("scraper.remotive.error", error=str(e), source=self.source_name)
            return []

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
