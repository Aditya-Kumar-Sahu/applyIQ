from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UsageMetadata(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class GeminiResponse(BaseModel):
    data: dict[str, Any]
    usage: UsageMetadata
    model: str
    request_id: str | None = None
