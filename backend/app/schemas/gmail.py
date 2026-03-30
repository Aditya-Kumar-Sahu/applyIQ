from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class GmailAuthUrlData(BaseModel):
    auth_url: str


class GmailConnectData(BaseModel):
    connected: bool
    has_refresh_token: bool
    gmail_account_hint: str | None = None
    email: str | None = None


class GmailStatusData(BaseModel):
    connected: bool
    gmail_account_hint: str | None = None
    email: str | None = None
    last_checked_at: datetime | None = None


class GmailPollData(BaseModel):
    polled: bool
    processed_messages: int
    matched_notifications: int
