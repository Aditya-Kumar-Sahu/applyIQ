from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class RankedJob(TypedDict):
    job_id: str
    title: str
    company_name: str
    match_score: float
    matched_skills: list[str]


class PendingApproval(TypedDict):
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


class ApprovedApplication(TypedDict):
    id: str
    status: str


class AppliedApplication(TypedDict):
    id: str
    status: str


class PipelineError(TypedDict):
    node: str
    message: str
    application_id: NotRequired[str]


class ApplyIQState(TypedDict):
    run_id: str
    user_id: str
    target_role: str
    location: str | None
    limit_per_source: int
    sources: list[str]
    raw_jobs_count: int
    deduplicated_jobs_count: int
    ranked_jobs: list[RankedJob]
    pending_approvals: list[PendingApproval]
    approved_applications: list[ApprovedApplication]
    applied_applications: list[AppliedApplication]
    current_node: str
    resume: NotRequired[dict[str, Any]]
    search_preferences: NotRequired[dict[str, Any]]
    raw_jobs: NotRequired[list[dict[str, Any]]]
    deduplicated_jobs: NotRequired[list[dict[str, Any]]]
    errors: NotRequired[list[PipelineError]]
