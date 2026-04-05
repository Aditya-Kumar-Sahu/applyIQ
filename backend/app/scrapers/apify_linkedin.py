from __future__ import annotations

import asyncio
import math
from datetime import datetime, timezone
import structlog
import httpx

from app.core.config import Settings, get_settings
from app.schemas.jobs import RawJob
from app.scrapers.base import BaseJobScraper, ScrapeQuery

logger = structlog.get_logger(__name__)


class ApifyLinkedInScraper(BaseJobScraper):
    source_name = "linkedin"
    _ACTOR_ID = "practicaltools/linkedin-jobs"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings

    async def fetch_jobs(self, query: ScrapeQuery) -> list[RawJob]:
        settings = self._settings or get_settings()
        if not settings.apify_api_token:
            raise RuntimeError("Apify API token is required for LinkedIn scraping")

        try:
            jobs = await self._execute_apify_run(query, settings.apify_api_token)
            return jobs[: query.limit_per_source]
        except Exception as e:
            logger.error("scraper.apify.error", error=str(e), source=self.source_name)
            raise RuntimeError("linkedin scraping failed") from e

    async def _execute_apify_run(self, query: ScrapeQuery, token: str) -> list[RawJob]:
        input_data = self._build_input_data(query)
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            run_resp = await client.post(
                f"https://api.apify.com/v2/acts/{self._ACTOR_ID}/runs",
                params={"token": token},
                json=input_data,
            )
            run_resp.raise_for_status()
            run_data = run_resp.json()["data"]
            run_id = run_data["id"]

            while True:
                await asyncio.sleep(5)
                status_resp = await client.get(
                    f"https://api.apify.com/v2/actor-runs/{run_id}",
                    params={"token": token},
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
                params={"token": token},
            )
            dataset_resp.raise_for_status()
            items = dataset_resp.json()

            return self._normalize(items)

    def _build_input_data(self, query: ScrapeQuery) -> dict[str, object]:
        return {
            "keywords": query.target_role,
            "location": query.location or "Worldwide",
            "sortBy": "DD",
            "maxPages": max(1, math.ceil(query.limit_per_source / 10)),
            "fetchDescription": True,
        }

    def _normalize(self, items: list[dict]) -> list[RawJob]:
        jobs = []
        for index, item in enumerate(items):
            title = str(item.get("title") or "Unknown Role")
            company_name = str(item.get("company") or item.get("companyName") or "Unknown Company")
            apply_url = str(item.get("url") or item.get("jobUrl") or "")
            posted_at = _parse_posted_at(item.get("datePosted"))
            
            jobs.append(
                RawJob(
                    external_id=f"apify-li-{item.get('jobId', item.get('id', index))}",
                    source=self.source_name,
                    title=title,
                    company_name=company_name,
                    company_domain=str(item.get("companyDomain") or ""),
                    location=str(item.get("location") or "Remote"),
                    is_remote="remote" in str(item.get("location") or "").lower(),
                    salary_min=item.get("salaryMin"),
                    salary_max=item.get("salaryMax"),
                    description_text=str(item.get("description") or f"{title} at {company_name}"),
                    apply_url=apply_url,
                    posted_at=posted_at,
                )
            )
        return jobs


def _parse_posted_at(value: object) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

    if isinstance(value, str) and value.strip():
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    return datetime.now(timezone.utc)
