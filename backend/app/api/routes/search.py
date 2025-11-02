from __future__ import annotations

import re
from typing import Iterable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.deps import (
    get_current_user,
    get_search_index_service,
    get_session,
)
from app.db.models import Message, Thread
from app.schemas.auth import AuthenticatedUser
from app.schemas.search import ThreadSearchRequest, ThreadSearchResponse, ThreadSearchResult
from app.schemas.thread import ThreadRead
from app.services.search_index import SearchIndexService
from app.utils.pagination import build_pagination, clamp_limit

router = APIRouter(prefix="/search", tags=["search"])


def _extract_text_sources(thread: Thread) -> Iterable[str]:
    if thread.title:
        yield thread.title
    if thread.summary:
        yield thread.summary
    attributes = thread.attributes or {}
    for value in attributes.values():
        if isinstance(value, str):
            yield value
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, str):
                    yield item


@router.post("/threads", response_model=ThreadSearchResponse)
async def search_threads(
    payload: ThreadSearchRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
    search_index: SearchIndexService = Depends(get_search_index_service),
) -> ThreadSearchResponse:
    user_id = current_user.user_id
    phrase = payload.phrase.strip()
    if not phrase:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Search phrase cannot be empty")

    try:
        pattern = re.compile(phrase, re.IGNORECASE)
    except re.error as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid regex: {exc}") from exc

    limit = clamp_limit(payload.limit)
    model_filter = (payload.model_id or "").strip() or None

    # Primary: semantic search via Chroma
    vector_results = await search_index.search(
        user_id=user_id,
        phrase=phrase,
        model_id=model_filter,
        limit=limit,
    )
    vector_matches = vector_results.matches

    ordered_thread_ids: list[UUID] = []
    similarity_map: dict[str, float | None] = {
        match.thread_id: match.similarity for match in vector_matches
    }
    for match in vector_matches:
        try:
            thread_uuid = UUID(match.thread_id)
        except (TypeError, ValueError):
            continue
        if thread_uuid not in ordered_thread_ids:
            ordered_thread_ids.append(thread_uuid)
        if len(ordered_thread_ids) >= limit:
            break

    # Fallback to regex search when no semantic results are found
    if not ordered_thread_ids:
        ordered_thread_ids = _regex_fallback(
            session=session,
            user_id=user_id,
            pattern=pattern,
            model_filter=model_filter,
            limit=limit,
        )

    total = len(ordered_thread_ids)

    if not ordered_thread_ids:
        pagination = build_pagination(page=1, limit=limit, total=0)
        return ThreadSearchResponse(
            items=[],
            pagination=pagination,
            best_similarity=vector_results.best_similarity,
            similarity_threshold=vector_results.similarity_threshold,
            best_distance=vector_results.best_distance,
            distance_threshold=vector_results.distance_threshold,
            min_similarity=vector_results.min_similarity,
        )

    threads_stmt = select(Thread).where(Thread.id.in_(ordered_thread_ids))
    fetched_threads = session.exec(threads_stmt).all()
    thread_map = {thread.id: thread for thread in fetched_threads}
    ordered_threads = [thread_map[thread_id] for thread_id in ordered_thread_ids if thread_id in thread_map]

    pagination = build_pagination(page=1, limit=limit, total=total)
    items = [
        ThreadSearchResult(
            thread=ThreadRead.model_validate(thread),
            similarity=similarity_map.get(str(thread.id)),
        )
        for thread in ordered_threads
    ]

    return ThreadSearchResponse(
        items=items,
        pagination=pagination,
        best_similarity=vector_results.best_similarity,
        similarity_threshold=vector_results.similarity_threshold,
        best_distance=vector_results.best_distance,
        distance_threshold=vector_results.distance_threshold,
        min_similarity=vector_results.min_similarity,
    )


def _regex_fallback(
    *,
    session: Session,
    user_id: str,
    pattern: re.Pattern[str],
    model_filter: str | None,
    limit: int,
) -> list[UUID]:
    thread_query = (
        select(Thread)
        .where(
            Thread.owner_id == user_id,
            Thread.is_deleted.is_(False),
            Thread.title.is_not(None),
            Thread.title != "",
        )
        .order_by(Thread.updated_at.desc())
    )

    threads = session.exec(thread_query).all()
    matched_ids: list[UUID] = []

    for thread in threads:
        attributes = thread.attributes or {}
        if model_filter and attributes.get("model") != model_filter:
            continue

        if any(pattern.search(text) for text in _extract_text_sources(thread)):
            matched_ids.append(thread.id)
            if len(matched_ids) >= limit:
                break
            continue

        messages_stmt = select(Message.text).where(Message.thread_id == thread.id)
        for row in session.exec(messages_stmt):
            text = row[0] if isinstance(row, (tuple, list)) else row
            if text and pattern.search(text):
                matched_ids.append(thread.id)
                break
        if len(matched_ids) >= limit:
            break

    return matched_ids[:limit]
