from __future__ import annotations

from pydantic import BaseModel


class MetaPayload(BaseModel):
    service: str
    environment: str
