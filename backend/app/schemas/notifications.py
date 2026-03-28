from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NotificationItem(BaseModel):
    application_id: str
    company_name: str
    title: str
    classification: str
    snippet: str
    created_at: datetime


class NotificationsData(BaseModel):
    items: list[NotificationItem] = Field(default_factory=list)
