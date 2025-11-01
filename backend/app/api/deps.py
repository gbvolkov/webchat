from __future__ import annotations

from collections.abc import Generator

from fastapi import Header, HTTPException, Request, status
from sqlmodel import Session

from app.db.session import get_session as _get_session
from app.services.llm import OpenAIChatService
from app.services.search_index import SearchIndexService


def get_current_user_id(x_user_id: str | None = Header(default=None)) -> str:
    """
    Temporary auth placeholder.

    Falls back to demo user `1` to stay compatible with the existing frontend stub.
    """
    return x_user_id or "1"


def get_session() -> Generator[Session, None, None]:
    yield from _get_session()


def get_chat_service(request: Request) -> OpenAIChatService:
    service = getattr(request.app.state, "llm_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM integration is currently unavailable",
        )
    return service


def _get_search_service(request: Request) -> SearchIndexService | None:
    return getattr(request.app.state, "search_index_service", None)


def get_search_index_service(request: Request) -> SearchIndexService:
    service = _get_search_service(request)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search integration is currently unavailable",
        )
    return service


def get_optional_search_index_service(request: Request) -> SearchIndexService | None:
    return _get_search_service(request)
