from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import structlog
import httpx

from app.core.config import Settings, get_settings
from app.schemas.jobs import RawJob
from app.scrapers.base import BaseJobScraper, ScrapeQuery, build_fixture_jobs

logger = structlog.get_logger(__name__)

class ApifyLinkedInScraper(BaseJobScraper):
    source_name = "linkedin"
    _ACTOR_ID = "bebity/linkedin-jobs-scraper"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings

    async def fetch_jobs(self, query: ScrapeQuery) -> list[RawJob]:
        settings = self._settings or get_settings()
        if not settings.apify_api_token or settings.is_non_production:
            return build_fixture_jobs(self.source_name, query)

        try:
            return await self._execute_apify_run(query, settings.apify_api_token)
        except Exception as e:
            logger.error("scraper.apify.error", error=str(e), source=self.source_name)
            return []

    async def _execute_apify_run(self, query: ScrapeQuery, token: str) -> list[RawJob]:
        input_data = {
            "searchKeywords": query.target_role,
            "location": query.location or "Worldwide",
            "limit": query.limit_per_source,
            "sortBy": "recent",
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            run_resp = await client.post(
                f"https://api.apify.com/v2/acts/{self._ACTOR_ID}/runs",
                params={"token": token},
                json=input_data
            )
            run_resp.raise_for_status()
            run_data = run_resp.json()["data"]
            run_id = run_data["id"]
            
            while True:
                await asyncio.sleep(5)
                status_resp = await client.get(
                    f"https://api.apify.com/v2/actor-runs/{run_id}",
                    params={"token": token}
                )
                status_resp.raise_for_status()
                status_data = status_resp.json()["data"]
                if status_data["status"] in {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}:
                    break
                    
            if status_data["status"] != "SUCCEEDED":
                logger.warning("scraper.apify.failed", status=status_data["status"])
                return []
                
            dataset_id = status_data["defaultDatasetId"]
            dataset_resp = await client.get(
                f"https://api.apify.com/v2/datasets/{dataset_id}/items",
                params={"token": token}
            )
            dataset_resp.raise_for_status()
            items = dataset_resp.json()
            
            return self._normalize(items)

    def _normalize(self, items: list[dict]) -> list[RawJob]:
        jobs = []
        for index, item in enumerate(items):
            # Normalization into a single RawJob shape
            title = item.get("title", "Unknown Role")
            company_name = item.get("companyName", "Unknown Company")
            apply_url = item.get("jobUrl", "")
            
            jobs.append(
                RawJob(
                    external_id=f"apify-li-{item.get('id', index)}",
                    source=self.source_name,
                    title=title,
                    company_name=company_name,
                    company_domain=item.get("companyDomain", ""),
                    location=item.get("location", "Remote"),
                    is_remote="remote" in str(item.get("location", "")).lower(),
                    salary_min=item.get("salaryMin"),
                    salary_max=item.get("salaryMax"),
                    description_text=item.get("description", f"{title} at {company_name}"),
                    apply_url=apply_url,
                    posted_at=datetime.now(timezone.utc),
                )
            )
        return jobs
