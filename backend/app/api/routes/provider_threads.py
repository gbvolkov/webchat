from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.api.deps import get_current_user, get_session
from app.db.models import ProviderThreadState, Thread, utcnow
from app.schemas.auth import AuthenticatedUser
from app.schemas.provider_state import ProviderThreadStateRead, ProviderThreadStateUpsert

router = APIRouter(prefix="/provider-threads", tags=["provider-thread-store"])


def _ensure_thread_owner(session: Session, thread_id: UUID, user_id: str) -> Thread:
    stmt = select(Thread).where(Thread.id == thread_id, Thread.owner_id == user_id)
    thread = session.exec(stmt).one_or_none()
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    return thread


@router.get("/{thread_id}", response_model=ProviderThreadStateRead)
def get_provider_thread_state(
    thread_id: UUID,
    provider: str = Query(default="openai-compatible", max_length=64),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ProviderThreadStateRead:
    _ensure_thread_owner(session, thread_id, current_user.user_id)
    stmt = select(ProviderThreadState).where(
        ProviderThreadState.thread_id == thread_id,
        ProviderThreadState.provider == provider,
    )
    state = session.exec(stmt).one_or_none()
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider thread state not found")
    return ProviderThreadStateRead.model_validate(state)


@router.put("/{thread_id}", response_model=ProviderThreadStateRead)
def upsert_provider_thread_state(
    thread_id: UUID,
    payload: ProviderThreadStateUpsert,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ProviderThreadStateRead:
    _ensure_thread_owner(session, thread_id, current_user.user_id)
    stmt = select(ProviderThreadState).where(
        ProviderThreadState.thread_id == thread_id,
        ProviderThreadState.provider == payload.provider,
    )
    state = session.exec(stmt).one_or_none()
    if state is None:
        state = ProviderThreadState(
            thread_id=thread_id,
            provider=payload.provider,
            conversation_id=payload.conversation_id,
            payload=payload.payload or {},
        )
        session.add(state)
    else:
        state.conversation_id = payload.conversation_id
        state.payload = payload.payload or {}
        state.updated_at = utcnow()
        session.add(state)
    session.commit()
    session.refresh(state)
    return ProviderThreadStateRead.model_validate(state)
