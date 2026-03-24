from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RankedJobScoreBreakdown(BaseModel):
    semantic_similarity: float
    skills_coverage: float
    seniority_alignment: float
    location_match: float
    salary_alignment: float


class RankedJobItem(BaseModel):
    job_id: str
    title: str
    company_name: str
    source: str
    location: str
    is_remote: bool
    salary_min: int | None
    salary_max: int | None
    apply_url: str
    match_score: float
    score_breakdown: RankedJobScoreBreakdown
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    recommendation: str
    one_line_reason: str


class JobsListData(BaseModel):
    total: int
    items: list[RankedJobItem]


class JobDetailData(RankedJobItem):
    company_domain: str | None = None
    description_text: str
    posted_at: datetime | None = None

