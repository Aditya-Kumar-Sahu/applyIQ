from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CredentialStorePayload(BaseModel):
    site_name: str = Field(min_length=2, max_length=100)
    site_url: str = Field(min_length=8, max_length=255)
    username: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=255)


class VaultCredentialItem(BaseModel):
    id: str
    site_name: str
    site_url: str
    masked_username: str
    created_at: datetime
    last_used_at: datetime | None


class VaultCredentialListData(BaseModel):
    items: list[VaultCredentialItem]


class DeleteCredentialData(BaseModel):
    deleted: bool
