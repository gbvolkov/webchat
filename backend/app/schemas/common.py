from __future__ import annotations

from typing import Generic, Sequence, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class Pagination(BaseModel):
    total: int
    page: int = Field(ge=1)
    limit: int = Field(ge=1)
    has_more: bool


class PaginatedResponse(BaseModel, Generic[T]):
    items: Sequence[T]
    pagination: Pagination
