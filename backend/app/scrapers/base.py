from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.schemas.jobs import RawJob

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScrapeQuery:
    target_role: str
    location: str | None
    limit_per_source: int


class BaseJobScraper(ABC):
    source_name: str

    def log_missing_field(self, field_name: str, fallback_value: str, context: dict | None = None) -> None:
        """Standardized warning for missing mandatory job data."""
        job_id = context.get("job_id", context.get("id", "Unknown ID")) if context else "Unknown ID"
        log.warning(
            "Scraper [%s] missing field '%s' for job '%s'. Falling back to '%s'.",
            self.source_name,
            field_name,
            job_id,
            fallback_value,
        )

    @abstractmethod
    async def fetch_jobs(self, query: ScrapeQuery) -> list[RawJob]:
        raise NotImplementedError
