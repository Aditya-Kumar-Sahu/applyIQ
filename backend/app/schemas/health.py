from __future__ import annotations

from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: str
    db: str
    redis: str
    apify: str | None = None
    serpapi: str | None = None
    remotive: str | None = None
    indeed: str | None = None
    wellfound: str | None = None
    ai_provider: str | None = None
