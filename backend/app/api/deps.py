from __future__ import annotations

from collections.abc import Generator
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlmodel import Session

from app.db.session import get_session as _get_session
from app.db.models import User
from app.schemas.auth import AuthenticatedUser
from app.services.auth import AuthService, AuthenticationError
from app.services.llm import OpenAIChatService
from app.services.search_index import SearchIndexService

_auth_service: AuthService | None = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


def get_session() -> Generator[Session, None, None]:
    yield from _get_session()


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization scheme",
        )
    return token.strip()


def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: Session = Depends(get_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthenticatedUser:
    token = _extract_bearer_token(authorization)
    try:
        payload = auth_service.decode_access_token(token)
    except AuthenticationError as exc:  # pragma: no cover - defensive logging can be added later
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from exc

    try:
        user_id = UUID(payload.sub)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
        ) from exc

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive or missing user",
        )
    if user.token_version != payload.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    return AuthenticatedUser(
        id=user.id,
        username=user.username,
        roles=tuple(user.roles or []),
        allowed_products=frozenset(user.allowed_products or []),
        allowed_agents=frozenset(user.allowed_agents or []),
        token_version=user.token_version,
    )


def get_current_user_id(current_user: AuthenticatedUser = Depends(get_current_user)) -> str:
    return current_user.user_id


def get_optional_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: Session = Depends(get_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthenticatedUser | None:
    if not authorization:
        return None
    return get_current_user(authorization=authorization, session=session, auth_service=auth_service)


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


def ensure_product_access(user: AuthenticatedUser, product_id: str) -> None:
    if product_id and not user.can_access_product(product_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User lacks access to the requested product",
        )


def ensure_agent_access(user: AuthenticatedUser, agent_id: str) -> None:
    if agent_id and not user.can_access_agent(agent_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User lacks access to the requested agent",
        )
