from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

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


def build_fixture_jobs(source: str, query: ScrapeQuery) -> list[RawJob]:
    if source == "linkedin":
        return _build_linkedin_jobs(query)
    if source == "indeed":
        return _build_indeed_jobs(query)
    if source == "remotive":
        return _build_remotive_jobs(query)
    if source == "wellfound":
        return _build_generic_jobs(query, source, offset=300)
    if source == "serpapi":
        return _build_generic_jobs(query, source, offset=400)
    raise ValueError(f"Unsupported source: {source}")


def _build_linkedin_jobs(query: ScrapeQuery) -> list[RawJob]:
    jobs: list[RawJob] = []
    for index in range(query.limit_per_source):
        jobs.append(_make_job(source="linkedin", query=query, index=index, global_index=index))
    return jobs


def _build_indeed_jobs(query: ScrapeQuery) -> list[RawJob]:
    jobs: list[RawJob] = []
    for index in range(query.limit_per_source):
        if index < 4:
            jobs.append(_make_job(source="indeed", query=query, index=index, global_index=index, duplicate_url_of=index))
            continue
        jobs.append(_make_job(source="indeed", query=query, index=index, global_index=100 + index))
    return jobs


def _build_remotive_jobs(query: ScrapeQuery) -> list[RawJob]:
    jobs: list[RawJob] = []
    for index in range(query.limit_per_source):
        if index < 3:
            jobs.append(
                _make_job(
                    source="remotive",
                    query=query,
                    index=index,
                    global_index=200 + index,
                    duplicate_title_of=4 + index,
                )
            )
            continue
        jobs.append(_make_job(source="remotive", query=query, index=index, global_index=200 + index))
    return jobs


def _build_generic_jobs(query: ScrapeQuery, source: str, *, offset: int) -> list[RawJob]:
    return [_make_job(source=source, query=query, index=index, global_index=offset + index) for index in range(query.limit_per_source)]


def _make_job(
    *,
    source: str,
    query: ScrapeQuery,
    index: int,
    global_index: int,
    duplicate_url_of: int | None = None,
    duplicate_title_of: int | None = None,
) -> RawJob:
    base_title = f"{query.target_role} Platform {global_index}"
    company_name = f"Company {global_index}"
    company_domain = f"company{global_index}.example"
    apply_url = f"https://jobs.applyiq.dev/{source}/{global_index}"

    if duplicate_url_of is not None:
        base_title = f"{query.target_role} Platform {duplicate_url_of}"
        company_name = f"Company {duplicate_url_of}"
        company_domain = f"company{duplicate_url_of}.example"
        apply_url = f"https://jobs.applyiq.dev/linkedin/{duplicate_url_of}"

    if duplicate_title_of is not None:
        base_title = f"{query.target_role} Platfrm {duplicate_title_of}"
        company_name = f"Company {duplicate_title_of}"
        company_domain = f"company{duplicate_title_of}.example"

    return RawJob(
        external_id=f"{source}-{index}",
        source=source,
        title=base_title,
        company_name=company_name,
        company_domain=company_domain,
        location=query.location or "Remote",
        is_remote=(query.location or "Remote").lower() == "remote",
        salary_min=1800000 + (index * 10000),
        salary_max=2600000 + (index * 10000),
        description_text=(
            f"{base_title} role at {company_name} focused on Python, FastAPI, PostgreSQL, Docker, "
            f"and production ML systems."
        ),
        apply_url=apply_url,
        posted_at=datetime.now(timezone.utc) - timedelta(hours=index),
    )
