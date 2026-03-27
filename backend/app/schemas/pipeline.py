from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PipelineStartRequest(BaseModel):
    target_role: str = Field(min_length=2, max_length=120)
    location: str | None = Field(default=None, max_length=120)
    limit_per_source: int = Field(default=10, ge=1, le=25)
    sources: list[str] = Field(default_factory=lambda: ["linkedin", "indeed", "remotive"])


class PipelineApplicationItem(BaseModel):
    id: str
    job_id: str
    title: str
    company_name: str
    match_score: float
    cover_letter_text: str
    tone: str
    word_count: int
    cover_letter_version: int
    status: str


class PipelineRunData(BaseModel):
    run_id: str
    status: str
    current_node: str
    jobs_found: int
    jobs_matched: int
    applications_submitted: int
    pending_approvals_count: int


class PipelineResultsData(BaseModel):
    run_id: str
    status: str
    current_node: str
    jobs_found: int
    jobs_matched: int
    applications_submitted: int
    started_at: datetime
    completed_at: datetime | None
    applications: list[PipelineApplicationItem]


class PipelineDecisionPayload(BaseModel):
    application_ids: list[str] = Field(default_factory=list, min_length=1)


class CoverLetterEditPayload(BaseModel):
    cover_letter_text: str = Field(min_length=10, max_length=5000)


class CoverLetterEditData(BaseModel):
    application_id: str
    cover_letter_text: str
    tone: str
    word_count: int
    cover_letter_version: int


class RejectData(BaseModel):
    rejected_count: int
