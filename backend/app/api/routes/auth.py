from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select, func

from app.api.deps import (
    get_auth_service,
    get_current_user,
    get_optional_current_user,
    get_session,
)
from app.db.models import User, utcnow
from app.schemas.auth import AuthenticatedUser, LoginRequest, RefreshRequest, TokenResponse
from app.schemas.user import UserCreate, UserRead
from app.services.auth import AuthService, AuthenticationError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    session: Session = Depends(get_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    stmt = select(User).where(User.username == payload.username)
    user = session.exec(stmt).one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not auth_service.verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    access_token, refresh_token = auth_service.issue_token_pair(user)
    user.last_login_at = utcnow()
    user.updated_at = utcnow()
    session.add(user)
    session.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=auth_service.access_token_expires_seconds,
        refresh_expires_in=auth_service.refresh_token_expires_seconds,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(
    payload: RefreshRequest,
    session: Session = Depends(get_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    try:
        refresh_payload = auth_service.decode_refresh_token(payload.refresh_token)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc

    try:
        user_id = UUID(refresh_payload.sub)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    if user.token_version != refresh_payload.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    access_token, refresh_token = auth_service.issue_token_pair(user)
    user.updated_at = utcnow()
    session.add(user)
    session.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=auth_service.access_token_expires_seconds,
        refresh_expires_in=auth_service.refresh_token_expires_seconds,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def logout(
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    user = session.get(User, current_user.id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    user.token_version += 1
    user.updated_at = utcnow()
    session.add(user)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserRead)
def read_current_user(
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> UserRead:
    user = session.get(User, current_user.id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserRead.model_validate(user)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(
    payload: UserCreate,
    session: Session = Depends(get_session),
    auth_service: AuthService = Depends(get_auth_service),
    current_user: AuthenticatedUser | None = Depends(get_optional_current_user),
) -> UserRead:
    total_users = session.exec(select(func.count()).select_from(User)).one()
    if total_users > 0:
        if current_user is None or not current_user.has_role("admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator privileges required to create users",
            )

    username_exists = session.exec(select(User).where(User.username == payload.username)).one_or_none()
    if username_exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )
    if payload.email:
        email_exists = session.exec(select(User).where(User.email == payload.email)).one_or_none()
        if email_exists is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already exists",
            )

    try:
        password_hash = auth_service.hash_password(payload.password)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    user = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        password_hash=password_hash,
        roles=payload.roles,
        allowed_products=payload.allowed_products,
        allowed_agents=payload.allowed_agents,
        is_active=payload.is_active,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserRead.model_validate(user)
