from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.schemas.jobs import RawJob
from app.core.observability import SCRAPER_REQUESTS_TOTAL, SCRAPER_DURATION_SECONDS
from app.core.cache import cached

log = logging.getLogger(__name__)


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

    def _log_field_fallback(self, field_name: str, job_id: str, fallback_value: str) -> None:
        log.warning(
            "scraper.%s.missing_field: Using fallback '%s' for field '%s' for job '%s'. Falling back to '%s'.", 
            self.source_name, field_name, job_id, fallback_value
        )
