from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import httpx
import structlog

from app.core.config import Settings, get_settings
from app.core.resilience import circuit_breaker
from app.schemas.jobs import RawJob
from app.scrapers.base import BaseJobScraper, ScrapeQuery

logger = structlog.get_logger(__name__)


class SerpApiGoogleJobsScraper(BaseJobScraper):
    source_name: str
    _source_domains: tuple[str, ...] = ()

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings

    @circuit_breaker(name="serpapi_scraper", failure_threshold=3, recovery_timeout=60.0, fallback=lambda *a, **kw: [])
    async def fetch_jobs(self, query: ScrapeQuery) -> list[RawJob]:
        settings = self._settings or get_settings()
        if not settings.serpapi_api_key:
            logger.warning("scraper.serpapi.unconfigured", source=self.source_name)
            return []

        try:
            return await self._execute_serpapi_run(query, settings.serpapi_api_key)
        except Exception as error:
            logger.error("scraper.serpapi.error", error=str(error), source=self.source_name)
            raise RuntimeError(f"{self.source_name} scraping failed") from error

    async def _execute_serpapi_run(self, query: ScrapeQuery, api_key: str) -> list[RawJob]:
        params = {
            "engine": "google_jobs",
            "q": self._build_query(query),
            "api_key": api_key,
            "num": query.limit_per_source,
        }
        # Do not use the specific location parameter to avoid 400 Bad Request errors.
        # Instead, the location is appended to the text query inside _build_query()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get("https://serpapi.com/search", params=params)
            response.raise_for_status()
            data = response.json()

        jobs = self._normalize(data.get("jobs_results", []))
        return jobs[: query.limit_per_source]

    def _build_query(self, query: ScrapeQuery) -> str:
        parts = [query.target_role]
        if query.location:
            parts.append(query.location)
        # Fix: Using site: operator with google_jobs engine often returns 0 results
        # Removing domain filters to ensure we actually get jobs back from SerpApi
        # if self._source_domains:
        #    parts.append("(" + " OR ".join(f"site:{domain}" for domain in self._source_domains) + ")")
        return " ".join(parts)

    def _normalize(self, items: list[dict]) -> list[RawJob]:
        jobs: list[RawJob] = []
        for index, item in enumerate(items):
            title = str(item.get("title") or "")
            if not title:
                self.log_missing_field("title", "Unknown Role", item)
                title = "Unknown Role"

            company_name = str(item.get("company_name") or item.get("company") or "")
            if not company_name:
                self.log_missing_field("company_name", "Unknown Company", item)
                company_name = "Unknown Company"

            apply_url = self._extract_apply_url(item)
            if not apply_url:
                self.log_missing_field("apply_url", "", item)

            posted_at = _parse_posted_at(
                item.get("detected_extensions", {}).get("posted_at")
                if isinstance(item.get("detected_extensions"), dict)
                else item.get("date_posted")
            )
            location = str(item.get("location") or "")
            if not location:
                self.log_missing_field("location", "Remote", item)
                location = "Remote"

            jobs.append(
                RawJob(
                    external_id=str(item.get("job_id") or item.get("jobId") or f"serp-{index}"),
                    source=self.source_name,
                    title=title,
                    company_name=company_name,
                    company_domain=str(item.get("company_domain") or item.get("company_url") or ""),
                    location=location,
                    is_remote="remote" in location.lower(),
                    salary_min=_coerce_int(
                        item.get("salary_min") or item.get("salary_minimum") or item.get("min_salary")
                    ),
                    salary_max=_coerce_int(
                        item.get("salary_max") or item.get("salary_maximum") or item.get("max_salary")
                    ),
                    description_text=str(item.get("description") or f"{title} at {company_name}"),
                    apply_url=apply_url,
                    posted_at=posted_at,
                )
            )
        return jobs

    def _extract_apply_url(self, item: dict) -> str:
        for key in ("apply_options", "related_links"):
            links = item.get(key)
            if not isinstance(links, list):
                continue
            for link in links:
                if isinstance(link, dict):
                    candidate = link.get("link") or link.get("url")
                    if candidate:
                        return str(candidate)

        for key in ("share_link", "job_url", "url", "link"):
            candidate = item.get(key)
            if candidate:
                return str(candidate)

        return ""


def _coerce_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        match = re.search(r"\d{4,}", value.replace(",", ""))
        if match:
            return int(match.group(0))
    return None


def _parse_posted_at(value: object) -> datetime:
    if not value or (isinstance(value, str) and not value.strip()):
        logger.warning("scraper.search_api.missing_date", value=value, message="Defaulting to current UTC time.")
        return datetime.now(UTC)

    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

    if isinstance(value, str):
        val_lower = value.strip().lower()
        # Parse relative dates like "2 days ago", "19 hours ago"
        match = re.match(r"(\d+)\s+(minute|hour|day|week|month)s?\s+ago", val_lower)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            now = datetime.now(UTC)
            if unit == "minute":
                return now - timedelta(minutes=amount)
            if unit == "hour":
                return now - timedelta(hours=amount)
            if unit == "day":
                return now - timedelta(days=amount)
            if unit == "week":
                return now - timedelta(weeks=amount)
            if unit == "month":
                return now - timedelta(days=amount * 30)

        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
        except ValueError as e:
            logger.warning(
                "scraper.search_api.date_parse_error", value=value, error=str(e), message="Failed to parse date string."
            )

    return datetime.now(UTC)
