"""Общие схемы."""
from __future__ import annotations

from typing import Generic, List, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

class Page(BaseModel, Generic[T]):
    items: List[T]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)

class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict = {}
    request_id: str

class ErrorResponse(BaseModel):
    error: ErrorBody
