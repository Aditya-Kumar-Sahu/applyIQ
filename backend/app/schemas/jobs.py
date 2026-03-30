from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


SUPPORTED_SCRAPE_SOURCES = {"linkedin", "indeed", "remotive", "wellfound", "serpapi"}


class RawJob(BaseModel):
    external_id: str
    source: str
    title: str
    company_name: str
    company_domain: str | None = None
    location: str
    is_remote: bool
    salary_min: int | None = None
    salary_max: int | None = None
    description_text: str
    apply_url: str
    posted_at: datetime | None = None


class ScrapeTestRequest(BaseModel):
    target_role: str = Field(min_length=2, max_length=120)
    location: str | None = Field(default=None, max_length=120)
    limit_per_source: int = Field(default=20, ge=1, le=25)
    sources: list[str] = Field(default_factory=lambda: ["linkedin", "indeed", "remotive"])

    @field_validator("sources")
    @classmethod
    def validate_sources(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("At least one source is required")

        invalid_sources = [source for source in value if source not in SUPPORTED_SCRAPE_SOURCES]
        if invalid_sources:
            raise ValueError(f"Unsupported sources: {', '.join(invalid_sources)}")

        return value


class ScrapedJobPreview(BaseModel):
    title: str
    company_name: str
    source: str
    apply_url: str


class ScrapeTestData(BaseModel):
    sources_used: list[str]
    failed_sources: list[str] = Field(default_factory=list)
    raw_jobs_count: int
    deduplicated_jobs_count: int
    stored_jobs_count: int
    jobs: list[ScrapedJobPreview]
