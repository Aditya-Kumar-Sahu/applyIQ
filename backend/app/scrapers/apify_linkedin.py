from __future__ import annotations

from datetime import UTC, datetime

import httpx
import structlog

from app.core.config import Settings, get_settings
from app.core.resilience import circuit_breaker
from app.schemas.jobs import RawJob
from app.scrapers.base import BaseJobScraper, ScrapeQuery

logger = structlog.get_logger(__name__)


class ApifyLinkedInScraper(BaseJobScraper):
    source_name = "linkedin"
    _ACTOR_ID = "bebity~linkedin-jobs-scraper"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings

    @circuit_breaker(name="linkedin_scraper", failure_threshold=3, recovery_timeout=60.0, fallback=lambda *a, **kw: [])
    async def fetch_jobs(self, query: ScrapeQuery) -> list[RawJob]:
        settings = self._settings or get_settings()
        if not settings.apify_api_token:
            logger.warning("scraper.apify.unconfigured", source=self.source_name)
            return []

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
                f"https://api.apify.com/v2/acts/{self._ACTOR_ID}/run-sync-get-dataset-items",
                params={"token": token},
                json=input_data,
            )
            run_resp.raise_for_status()
            payload = run_resp.json()

        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            items = payload.get("items") or payload.get("data") or []
        else:
            items = []

        return self._normalize(items)

    def _build_input_data(self, query: ScrapeQuery) -> dict[str, object]:
        return {
            "title": query.target_role,
            "location": query.location or "Worldwide",
            "rows": max(1, query.limit_per_source),
        }

    def _normalize(self, items: list[dict]) -> list[RawJob]:
        jobs = []
        for index, item in enumerate(items):
            title = str(item.get("title") or "")
            if not title:
                self.log_missing_field("title", "Unknown Role", item)
                title = "Unknown Role"

            company_name = str(item.get("company") or item.get("companyName") or "")
            if not company_name:
                self.log_missing_field("company_name", "Unknown Company", item)
                company_name = "Unknown Company"

            apply_url = str(item.get("url") or item.get("jobUrl") or "")
            if not apply_url:
                self.log_missing_field("apply_url", "", item)

            posted_at = _parse_posted_at(item.get("datePosted"))

            location = str(item.get("location") or "")
            if not location:
                self.log_missing_field("location", "Remote", item)
                location = "Remote"

            jobs.append(
                RawJob(
                    external_id=f"apify-li-{item.get('jobId', item.get('id', index))}",
                    source=self.source_name,
                    title=title,
                    company_name=company_name,
                    company_domain=str(item.get("companyDomain") or ""),
                    location=location,
                    is_remote="remote" in location.lower(),
                    salary_min=item.get("salaryMin"),
                    salary_max=item.get("salaryMax"),
                    description_text=str(item.get("description") or f"{title} at {company_name}"),
                    apply_url=apply_url,
                    posted_at=posted_at,
                )
            )
        return jobs


def _parse_posted_at(value: object) -> datetime:
    if not value or (isinstance(value, str) and not value.strip()):
        logger.warning("scraper.apify.missing_date", value=value, message="Defaulting to current UTC time.")
        return datetime.now(UTC)

    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
        except ValueError as e:
            logger.warning(
                "scraper.apify.date_parse_error", value=value, error=str(e), message="Failed to parse date string."
            )

    return datetime.now(UTC)
