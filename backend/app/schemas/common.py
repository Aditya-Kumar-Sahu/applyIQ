from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class ErrorDetail(BaseModel):
    code: str
    message: str


class Envelope[DataT](BaseModel):
    success: bool
    data: DataT | None
    error: ErrorDetail | None
