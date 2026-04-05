from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.schemas.jobs import RawJob


@dataclass(frozen=True)
class ScrapeQuery:
    target_role: str
    location: str | None
    limit_per_source: int


class BaseJobScraper(ABC):
    source_name: str

    @abstractmethod
    async def fetch_jobs(self, query: ScrapeQuery) -> list[RawJob]:
        raise NotImplementedError
