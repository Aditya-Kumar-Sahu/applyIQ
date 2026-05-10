from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import structlog

from app.core.cache import cached
from app.core.observability import SCRAPER_DURATION_SECONDS, SCRAPER_REQUESTS_TOTAL
from app.schemas.jobs import RawJob

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ScrapeQuery:
    target_role: str
    location: str | None = None
    limit_per_source: int = 10


class BaseJobScraper(ABC):
    source_name: str
    ttl: int = 43200

    @cached(namespace="scraper")
    async def fetch_jobs(self, query: ScrapeQuery) -> list[RawJob]:
        """
        Public template method that handles metrics and instrumentation.
        """
        start_time = time.perf_counter()
        status = "success"
        try:
            results = await self._fetch_jobs(query)
            return results
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.perf_counter() - start_time
            SCRAPER_REQUESTS_TOTAL.labels(source=self.source_name, status=status).inc()
            SCRAPER_DURATION_SECONDS.labels(source=self.source_name).observe(duration)

    @abstractmethod
    async def _fetch_jobs(self, query: ScrapeQuery) -> list[RawJob]:
        """
        Implementation-specific scraping logic.
        """
        raise NotImplementedError

    def log_missing_field(self, field_name: str, fallback_value: str, raw_item: dict) -> None:
        """
        Standardized logging for missing fields in scraped data.
        """
        log.warning(
            "scraper.%s.missing_field",
            self.source_name,
            field=field_name,
            fallback=fallback_value,
            item_summary={k: v for k, v in raw_item.items() if k in {"id", "jobId", "url", "title"}},
        )
