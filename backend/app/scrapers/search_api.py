from __future__ import annotations

from datetime import datetime, timezone
import re

import httpx
import structlog

from app.core.config import Settings, get_settings
from app.schemas.jobs import RawJob
from app.scrapers.base import BaseJobScraper, ScrapeQuery


logger = structlog.get_logger(__name__)


class SerpApiGoogleJobsScraper(BaseJobScraper):
    source_name: str
    _source_domains: tuple[str, ...] = ()

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings

    async def fetch_jobs(self, query: ScrapeQuery) -> list[RawJob]:
        settings = self._settings or get_settings()
        if not settings.serpapi_api_key:
            raise RuntimeError(f"SerpApi API key is required for {self.source_name} scraping")

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
        if query.location:
            params["location"] = query.location

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
        if self._source_domains:
            parts.append("(" + " OR ".join(f"site:{domain}" for domain in self._source_domains) + ")")
        return " ".join(parts)

    def _normalize(self, items: list[dict]) -> list[RawJob]:
        jobs: list[RawJob] = []
        for index, item in enumerate(items):
            title = str(item.get("title") or "Unknown Role")
            company_name = str(item.get("company_name") or item.get("company") or "Unknown Company")
            apply_url = self._extract_apply_url(item)
            posted_at = _parse_posted_at(
                item.get("detected_extensions", {}).get("posted_at")
                if isinstance(item.get("detected_extensions"), dict)
                else item.get("date_posted")
            )
            location = str(item.get("location") or "Remote")

            jobs.append(
                RawJob(
                    external_id=str(item.get("job_id") or item.get("jobId") or f"serp-{index}"),
                    source=self.source_name,
                    title=title,
                    company_name=company_name,
                    company_domain=str(item.get("company_domain") or item.get("company_url") or ""),
                    location=location,
                    is_remote="remote" in location.lower(),
                    salary_min=_coerce_int(item.get("salary_min") or item.get("salary_minimum") or item.get("min_salary")),
                    salary_max=_coerce_int(item.get("salary_max") or item.get("salary_maximum") or item.get("max_salary")),
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