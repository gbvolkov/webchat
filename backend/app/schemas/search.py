from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import Pagination
from app.schemas.thread import ThreadRead


class ThreadSearchRequest(BaseModel):
    phrase: str = Field(min_length=1)
    model_id: str | None = None
    limit: int | None = Field(default=None, ge=1)


class ThreadSearchResult(BaseModel):
    thread: ThreadRead
    similarity: float | None = None


class ThreadSearchResponse(BaseModel):
    items: list[ThreadSearchResult]
    pagination: Pagination
    best_similarity: float | None = None
    similarity_threshold: float | None = None
    best_distance: float | None = None
    distance_threshold: float | None = None
    min_similarity: float | None = None
