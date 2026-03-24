from __future__ import annotations

from app.schemas.jobs import RawJob
from app.scrapers.base import BaseJobScraper, ScrapeQuery, build_fixture_jobs


class IndeedScraper(BaseJobScraper):
    source_name = "indeed"

    async def fetch_jobs(self, query: ScrapeQuery) -> list[RawJob]:
        return build_fixture_jobs(self.source_name, query)
