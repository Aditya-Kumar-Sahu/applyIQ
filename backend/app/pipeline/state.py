from __future__ import annotations

from typing import Any, TypedDict


class ApplyIQState(TypedDict):
    run_id: str
    user_id: str
    target_role: str
    location: str | None
    limit_per_source: int
    sources: list[str]
    raw_jobs_count: int
    deduplicated_jobs_count: int
    ranked_jobs: list[dict[str, Any]]
    pending_approvals: list[dict[str, Any]]
    approved_applications: list[dict[str, Any]]
    applied_applications: list[dict[str, Any]]
    current_node: str
