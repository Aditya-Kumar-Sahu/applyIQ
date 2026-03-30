from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EmailMonitorData(BaseModel):
    gmail_thread_id: str
    sender: str
    subject: str
    snippet: str
    latest_classification: str
    last_checked_at: datetime
    is_resolved: bool


class ApplicationListItem(BaseModel):
    id: str
    job_id: str
    title: str
    company_name: str
    status: str
    match_score: float
    applied_at: datetime | None
    is_demo: bool = False
    latest_email_classification: str | None = None


class ApplicationsListData(BaseModel):
    items: list[ApplicationListItem] = Field(default_factory=list)


class SourcePerformanceItem(BaseModel):
    source: str
    total_applications: int
    replied_count: int
    response_rate: float


class TitlePerformanceItem(BaseModel):
    title: str
    total_applications: int
    replied_count: int
    response_rate: float


class ApplicationsStatsData(BaseModel):
    total_applications: int
    total_applied: int
    total_replied: int
    response_rate: float
    avg_hours_to_first_reply: float | None = None
    source_breakdown: list[SourcePerformanceItem] = Field(default_factory=list)
    top_titles: list[TitlePerformanceItem] = Field(default_factory=list)


class ApplicationDetailData(BaseModel):
    id: str
    job_id: str
    title: str
    company_name: str
    status: str
    match_score: float
    cover_letter_text: str
    ats_provider: str | None = None
    confirmation_url: str | None = None
    confirmation_number: str | None = None
    is_demo: bool = False
    screenshot_urls: list[str] = Field(default_factory=list)
    email_monitor: EmailMonitorData | None = None


class ApplicationStatusUpdatePayload(BaseModel):
    status: Literal["interview_requested", "rejected", "offer", "withdrawn"]


class ApplicationStatusUpdateData(BaseModel):
    application_id: str
    status: str
