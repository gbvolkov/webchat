from __future__ import annotations

import asyncio
import base64
import binascii
import contextlib
import json
import logging
from typing import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session, func, select

from app.api.deps import (
    ensure_agent_access,
    ensure_product_access,
    get_chat_service,
    get_current_user,
    get_optional_search_index_service,
    get_session,
)
from app.db.models import Message, MessageAttachment, MessageStatus, ProviderThreadState, SenderType, Thread, utcnow
from app.schemas.common import PaginatedResponse
from app.schemas.message import MessageAttachmentRead, MessageCreate, MessageRead, MessageUpdate
from app.schemas.thread import (
    ThreadCreate,
    ThreadDetail,
    ThreadListResponse,
    ThreadRead,
    ThreadUpdate,
)
from app.utils.pagination import build_pagination, clamp_limit
from app.services.llm import ChatPromptMessage, LLMServiceError, OpenAIChatService
from app.services.search_index import SearchIndexService
from app.schemas.auth import AuthenticatedUser

router = APIRouter(prefix="/threads", tags=["threads"])

_DEFAULT_PROVIDER = "openai-compatible"
_DEFAULT_THREAD_PREFIX = "Product"

logger = logging.getLogger(__name__)


def _get_message_attachments(session: Session, message_ids: Sequence[UUID]) -> dict[UUID, list[MessageAttachment]]:
    if not message_ids:
        return {}
    attachments = session.exec(
        select(MessageAttachment).where(MessageAttachment.message_id.in_(message_ids))
    ).all()
    by_message: dict[UUID, list[MessageAttachment]] = {}
    for attachment in attachments:
        by_message.setdefault(attachment.message_id, []).append(attachment)
    return by_message


def _attachment_to_read_model(attachment: MessageAttachment, include_data: bool = True) -> MessageAttachmentRead:
    data_base64 = base64.b64encode(attachment.data).decode("utf-8") if include_data else None
    return MessageAttachmentRead(
        id=attachment.id,
        filename=attachment.filename,
        content_type=attachment.content_type,
        data_base64=data_base64,
        created_at=attachment.created_at,
    )


def _build_prompt_parts(message: Message, attachments: Sequence[MessageAttachment]) -> list[dict[str, object]]:
    parts: list[dict[str, object]] = [{"type": "text", "text": message.text}]
    for attachment in attachments:
        data_base64 = base64.b64encode(attachment.data).decode("utf-8")
        if attachment.content_type.startswith("image/"):
            parts.append(
                {
                    "type": "input_image",
                    "image_base64": data_base64,
                    "media_type": attachment.content_type,
                }
            )
        else:
            parts.append(
                {
                    "type": "input_file",
                    "data": data_base64,
                    "media_type": attachment.content_type,
                    "filename": attachment.filename,
                }
            )
    return parts


def _truncate(text: str, length: int) -> str:
    return text if len(text) <= length else text[:length].rstrip()


def _sanitize_title_fragment(fragment: str) -> str:
    return fragment.replace("[", "").replace("]", "").strip()


def _should_assign_default_title(thread: Thread) -> bool:
    return thread.title is None or thread.title.strip() == ""


def _ensure_thread(
    session: Session,
    thread_id: UUID,
    owner_id: str,
    *,
    include_deleted: bool = False,
) -> Thread:
    stmt = select(Thread).where(Thread.id == thread_id, Thread.owner_id == owner_id)
    if not include_deleted:
        stmt = stmt.where(Thread.is_deleted.is_(False))
    thread = session.exec(stmt).one_or_none()
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    return thread


_METADATA_PRODUCT_KEYS = ("product_id", "productId", "product")
_METADATA_AGENT_KEYS = ("agent_id", "agentId", "agent")


def _normalize_metadata_value(value: object) -> str | None:
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    if isinstance(value, dict):
        candidate = value.get("id") or value.get("value")
        if isinstance(candidate, str):
            trimmed = candidate.strip()
            return trimmed or None
    return None


def _extract_metadata_value(metadata: dict | None, keys: tuple[str, ...]) -> str | None:
    if not metadata:
        return None
    for key in keys:
        if key not in metadata:
            continue
        candidate = _normalize_metadata_value(metadata[key])
        if candidate:
            return candidate
    return None


def _enforce_metadata_permissions(user: AuthenticatedUser, metadata: dict | None) -> None:
    ensure_product_access(user, _extract_metadata_value(metadata, _METADATA_PRODUCT_KEYS))
    ensure_agent_access(user, _extract_metadata_value(metadata, _METADATA_AGENT_KEYS))


@router.post("", response_model=ThreadRead, status_code=status.HTTP_201_CREATED)
def create_thread(
    payload: ThreadCreate,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ThreadRead:
    metadata = payload.metadata or {}
    _enforce_metadata_permissions(current_user, metadata)
    user_id = current_user.user_id
    thread = Thread(
        owner_id=user_id,
        title=payload.title,
        summary=payload.summary,
        attributes=metadata,
    )
    session.add(thread)
    session.commit()
    session.refresh(thread)
    return ThreadRead.model_validate(thread)


@router.get("", response_model=ThreadListResponse)
def list_threads(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=None, ge=1),
    include_deleted: bool = Query(default=False),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ThreadListResponse:
    user_id = current_user.user_id
    limit = clamp_limit(limit)
    filters = [Thread.owner_id == user_id]
    if not include_deleted:
        filters.append(Thread.is_deleted.is_(False))
        filters.append(Thread.title.is_not(None))
        filters.append(Thread.title != "")
        message_thread_ids = select(Message.thread_id)
        filters.append(Thread.id.in_(message_thread_ids))

    total = session.exec(
        select(func.count()).select_from(Thread).where(*filters)
    ).one()
    query = (
        select(Thread)
        .where(*filters)
        .order_by(Thread.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    items = session.exec(query).all()
    pagination = build_pagination(page=page, limit=limit, total=total)
    return ThreadListResponse(
        items=[ThreadRead.model_validate(item) for item in items],
        pagination=pagination,
    )


@router.get("/{thread_id}", response_model=ThreadDetail)
def get_thread(
    thread_id: UUID,
    messages_limit: int = Query(default=5, ge=1, le=50),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ThreadDetail:
    user_id = current_user.user_id
    thread = _ensure_thread(session, thread_id, user_id)
    _enforce_metadata_permissions(current_user, thread.attributes)
    message_stmt = (
        select(Message)
        .where(Message.thread_id == thread_id)
        .order_by(Message.created_at.desc())
        .limit(messages_limit)
    )
    messages: Sequence[Message] = session.exec(message_stmt).all()
    thread_detail = ThreadDetail.model_validate(thread)
    attachments_map = _get_message_attachments(session, [msg.id for msg in messages])
    thread_detail.last_messages = []
    for msg in messages:
        msg_read = MessageRead.model_validate(msg)
        msg_read.attachments = [
            _attachment_to_read_model(att, include_data=False)
            for att in attachments_map.get(msg.id, [])
        ]
        thread_detail.last_messages.append(msg_read)
    return thread_detail


@router.patch("/{thread_id}", response_model=ThreadRead)
def update_thread(
    thread_id: UUID,
    payload: ThreadUpdate,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ThreadRead:
    user_id = current_user.user_id
    thread = _ensure_thread(session, thread_id, user_id)
    _enforce_metadata_permissions(current_user, thread.attributes)
    updated = False

    if payload.title is not None:
        thread.title = payload.title
        updated = True
    if payload.summary is not None:
        thread.summary = payload.summary
        updated = True
    if payload.metadata is not None:
        _enforce_metadata_permissions(current_user, payload.metadata)
        thread.attributes = payload.metadata
        updated = True
    if payload.is_deleted is not None:
        thread.is_deleted = payload.is_deleted
        thread.deleted_at = utcnow() if payload.is_deleted else None
        updated = True

    if updated:
        thread.updated_at = utcnow()
        session.add(thread)
        session.commit()
        session.refresh(thread)

    return ThreadRead.model_validate(thread)


@router.delete(
    "/{thread_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_thread(
    thread_id: UUID,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
    search_index: SearchIndexService | None = Depends(get_optional_search_index_service),
) -> Response:
    user_id = current_user.user_id
    thread = _ensure_thread(session, thread_id, user_id, include_deleted=True)
    _enforce_metadata_permissions(current_user, thread.attributes)
    if thread.is_deleted:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    thread.is_deleted = True
    thread.deleted_at = utcnow()
    thread.updated_at = utcnow()
    session.add(thread)
    session.commit()
    session.refresh(thread)

    if search_index is not None:
        try:
            await search_index.delete_thread(str(thread.id))
        except Exception:  # pragma: no cover - best effort logging
            logger.exception("Failed to delete thread %s from semantic index", thread.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{thread_id}/messages", response_model=PaginatedResponse[MessageRead])
def list_messages(
    thread_id: UUID,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=None, ge=1),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> PaginatedResponse[MessageRead]:
    user_id = current_user.user_id
    thread = _ensure_thread(session, thread_id, user_id)
    _enforce_metadata_permissions(current_user, thread.attributes)
    limit = clamp_limit(limit)

    base_filters = [Message.thread_id == thread_id]
    total = session.exec(
        select(func.count()).select_from(Message).where(*base_filters)
    ).one()

    messages = session.exec(
        select(Message)
        .where(*base_filters)
        .order_by(Message.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()

    attachments_map = _get_message_attachments(session, [msg.id for msg in messages])
    message_items: list[MessageRead] = []
    for msg in messages:
        item = MessageRead.model_validate(msg)
        item.attachments = [
            _attachment_to_read_model(att, include_data=False)
            for att in attachments_map.get(msg.id, [])
        ]
        message_items.append(item)

    pagination = build_pagination(page=page, limit=limit, total=total)
    return PaginatedResponse[MessageRead](
        items=message_items,
        pagination=pagination,
    )


_ROLE_BY_SENDER: dict[SenderType, str] = {
    SenderType.USER: "user",
    SenderType.ASSISTANT: "assistant",
    SenderType.SYSTEM: "system",
}


async def _process_message_creation(
    *,
    thread: Thread,
    payload: MessageCreate,
    session: Session,
    user_id: str,
    chat_service: OpenAIChatService,
    search_index: SearchIndexService | None,
    chunk_callback: OpenAIChatService.ChunkCallback | None = None,
) -> MessageRead:
    model_from_payload = payload.model.strip() if payload.model else None
    thread_attributes = dict(thread.attributes or {})
    model_name = model_from_payload or thread_attributes.get("model")
    if model_name is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Model is required")

    if model_from_payload and thread_attributes.get("model") != model_from_payload:
        thread_attributes["model"] = model_from_payload
    elif "model" not in thread_attributes:
        thread_attributes["model"] = model_name

    model_label_raw = (payload.model_label or thread_attributes.get("model_label") or model_name or "").strip()
    if model_label_raw:
        thread_attributes["model_label"] = model_label_raw
    else:
        thread_attributes.pop("model_label", None)

    existing_message_count = session.exec(
        select(func.count()).select_from(Message).where(Message.thread_id == thread.id)
    ).one()
    user_text = (payload.text or "").strip()
    if not user_text:
        default_text = "Process as expected."
        payload = payload.model_copy(update={"text": default_text})
        user_text = default_text

    if user_text and (existing_message_count == 0 or _should_assign_default_title(thread)):
        product_label = _sanitize_title_fragment(model_label_raw or model_name) or _DEFAULT_THREAD_PREFIX
        preview = _sanitize_title_fragment(_truncate(user_text, 32))
        thread.title = f"{product_label}: {preview}"
        thread.updated_at = utcnow()

    provider_key = thread_attributes.get("provider") or _DEFAULT_PROVIDER
    thread_attributes["provider"] = provider_key

    if thread_attributes != thread.attributes:
        thread.attributes = thread_attributes

    conversation_state_stmt = select(ProviderThreadState).where(
        ProviderThreadState.thread_id == thread.id,
        ProviderThreadState.provider == provider_key,
    )
    conversation_state = session.exec(conversation_state_stmt).one_or_none()
    active_conversation_id = conversation_state.conversation_id if conversation_state else None

    user_message = Message(
        thread_id=thread.id,
        sender_id=payload.sender_id,
        sender_type=payload.sender_type,
        status=MessageStatus.QUEUED,
        text=payload.text,
        tokens_count=payload.tokens_count,
        correlation_id=payload.correlation_id,
        error_code=payload.error_code,
    )
    session.add(user_message)
    thread.updated_at = utcnow()
    session.add(thread)
    session.commit()
    session.refresh(user_message)

    new_attachments: list[MessageAttachment] = []
    if payload.attachments:
        for attachment_payload in payload.attachments:
            try:
                binary = base64.b64decode(attachment_payload.data_base64)
            except (binascii.Error, ValueError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid attachment encoding",
                ) from exc
            attachment = MessageAttachment(
                message_id=user_message.id,
                filename=attachment_payload.filename,
                content_type=attachment_payload.content_type or "application/octet-stream",
                data=binary,
            )
            session.add(attachment)
            new_attachments.append(attachment)
        session.commit()
        for attachment in new_attachments:
            session.refresh(attachment)

    attachments_map: dict[UUID, list[MessageAttachment]] = {}

    try:
        history_stmt = (
            select(Message)
            .where(Message.thread_id == thread.id)
            .order_by(Message.created_at)
        )
        history = session.exec(history_stmt).all()
        attachments_map = _get_message_attachments(session, [msg.id for msg in history])
        prompt_messages = [
            ChatPromptMessage(
                role=_ROLE_BY_SENDER.get(msg.sender_type, "user"),
                parts=_build_prompt_parts(msg, attachments_map.get(msg.id, [])),
            )
            for msg in history
        ]

        total_prompt_attachments = sum(
            1
            for message in prompt_messages
            for part in message.parts
            if part.get("type") != "text"
        )
        logger.info(
            "Dispatching OpenAI-compatible completion: thread_id=%s model=%s user_id=%s messages=%s attachments=%s conversation_id=%s",
            thread.id,
            model_name,
            user_id,
            len(prompt_messages),
            total_prompt_attachments,
            active_conversation_id,
        )
        if logger.isEnabledFor(logging.DEBUG):
            prompt_preview: list[dict[str, object]] = []
            for idx, prompt_message in enumerate(prompt_messages):
                text_part = next(
                    (
                        part.get("text")
                        for part in prompt_message.parts
                        if part.get("type") == "text"
                    ),
                    "",
                )
                prompt_preview.append(
                    {
                        "idx": idx,
                        "role": prompt_message.role,
                        "text_preview": _truncate(text_part, 120),
                        "attachments": [
                            part.get("type")
                            for part in prompt_message.parts
                            if part.get("type") != "text"
                        ],
                    }
                )
            logger.debug(
                "OpenAI-compatible completion payload summary: thread_id=%s payload=%s",
                thread.id,
                prompt_preview,
            )

        async def handle_agent_status(agent_status: str) -> None:
            normalized = (agent_status or "").lower()
            if normalized == "queued":
                target_status = MessageStatus.QUEUED
            elif normalized in {"running", "streaming"}:
                target_status = MessageStatus.PROCESSING
            elif normalized == "completed":
                target_status = MessageStatus.PROCESSING
            else:
                return
            if user_message.status == target_status:
                return
            user_message.status = target_status
            user_message.updated_at = utcnow()
            thread.updated_at = utcnow()
            session.add(user_message)
            session.add(thread)
            session.commit()
            session.refresh(user_message)
            session.refresh(thread)
            logger.info(
                "Updated message status from agent stream: message_id=%s agent_status=%s mapped_status=%s",
                user_message.id,
                agent_status,
                target_status.value,
            )

        completion = await chat_service.create_completion(
            model=model_name,
            messages=prompt_messages,
            user=user_id,
            conversation_id=active_conversation_id,
            stream=True,
            on_status=handle_agent_status,
            on_chunk=chunk_callback,
        )
        logger.info(
            "OpenAI-compatible completion succeeded: thread_id=%s model=%s response_id=%s conversation_id=%s",
            thread.id,
            model_name,
            completion.response_id,
            completion.conversation_id,
        )
    except LLMServiceError as exc:
        raw_detail = str(exc).strip()
        cause_detail = ""
        if exc.__cause__ is not None:
            cause_detail = str(exc.__cause__).strip()
        error_detail = raw_detail
        if cause_detail:
            if not error_detail:
                error_detail = cause_detail
            elif cause_detail not in error_detail:
                separator = "" if error_detail.endswith(":") else ":"
                error_detail = f"{error_detail}{separator} {cause_detail}".strip()
        if error_detail.endswith(":"):
            error_detail = error_detail[:-1].rstrip()
        if not error_detail:
            error_detail = "Agent invocation failed"
        provider_code = getattr(exc, "error_code", None)
        if provider_code and provider_code not in error_detail:
            error_detail = f"{error_detail} (code: {provider_code})".strip()
        provider_status = getattr(exc, "status_code", None)
        provider_type = getattr(exc, "error_type", None)
        provider_request_id = getattr(exc, "request_id", None)
        logger.warning(
            (
                "OpenAI-compatible completion failed: thread_id=%s model=%s user_id=%s "
                "conversation_id=%s status_code=%s error_type=%s error_code=%s request_id=%s detail=%s"
            ),
            thread.id,
            model_name,
            user_id,
            active_conversation_id,
            provider_status if provider_status is not None else "n/a",
            provider_type or "n/a",
            provider_code or "n/a",
            provider_request_id or "n/a",
            error_detail,
        )
        if getattr(exc, "extra", None):
            logger.debug(
                "LLM provider error context: thread_id=%s extra=%s",
                thread.id,
                exc.extra,
            )
        user_message.status = MessageStatus.ERROR
        user_message.error_code = error_detail
        user_message.updated_at = utcnow()
        session.add(user_message)
        thread.updated_at = utcnow()
        session.add(thread)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_detail,
        ) from exc

    user_message.status = MessageStatus.READY
    user_message.error_code = None
    usage_prompt = completion.usage.get("prompt_tokens")
    if usage_prompt is not None:
        user_message.tokens_count = usage_prompt
    if completion.response_id:
        user_message.correlation_id = completion.response_id
    user_message.updated_at = utcnow()

    assistant_tokens = completion.usage.get("completion_tokens")
    assistant_message = Message(
        thread_id=thread.id,
        sender_id="assistant",
        sender_type=SenderType.ASSISTANT,
        status=MessageStatus.READY,
        text=completion.content,
        tokens_count=assistant_tokens,
        correlation_id=completion.response_id or None,
    )

    if completion.conversation_id:
        if conversation_state is None:
            conversation_state = ProviderThreadState(
                thread_id=thread.id,
                provider=provider_key,
                conversation_id=completion.conversation_id,
                payload={
                    "model": completion.model,
                    "model_label": thread_attributes.get("model_label"),
                },
            )
        else:
            conversation_state.conversation_id = completion.conversation_id
            current_payload = conversation_state.payload or {}
            current_payload["model"] = completion.model
            if thread_attributes.get("model_label"):
                current_payload["model_label"] = thread_attributes.get("model_label")
            conversation_state.payload = current_payload
            conversation_state.updated_at = utcnow()
        session.add(conversation_state)

    session.add(user_message)
    session.add(assistant_message)
    thread.updated_at = utcnow()
    session.add(thread)
    session.commit()
    session.refresh(user_message)
    session.refresh(assistant_message)
    session.refresh(thread)

    if user_message.id not in attachments_map:
        attachments_map[user_message.id] = new_attachments

    if search_index is not None:
        try:
            await search_index.index_message(
                message=user_message,
                thread=thread,
                model_label=thread_attributes.get("model_label"),
            )
            await search_index.index_message(
                message=assistant_message,
                thread=thread,
                model_label=thread_attributes.get("model_label"),
            )
        except Exception:  # pragma: no cover - best effort logging
            logger.exception("Failed to index message %s for semantic search", user_message.id)

    user_message_read = MessageRead.model_validate(user_message)
    user_message_read.attachments = [
        _attachment_to_read_model(attachment)
        for attachment in attachments_map.get(user_message.id, [])
    ]
    return user_message_read


@router.post(
    "/{thread_id}/messages",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_message(
    thread_id: UUID,
    payload: MessageCreate,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
    chat_service: OpenAIChatService = Depends(get_chat_service),
    search_index: SearchIndexService | None = Depends(get_optional_search_index_service),
) -> MessageRead:
    user_id = current_user.user_id
    thread = _ensure_thread(session, thread_id, user_id)
    _enforce_metadata_permissions(current_user, thread.attributes)
    payload = payload.model_copy(update={"sender_id": user_id})
    return await _process_message_creation(
        thread=thread,
        payload=payload,
        session=session,
        user_id=user_id,
        chat_service=chat_service,
        search_index=search_index,
    )


@router.post(
    "/{thread_id}/messages/stream",
    response_class=StreamingResponse,
)
async def stream_message(
    thread_id: UUID,
    payload: MessageCreate,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
    chat_service: OpenAIChatService = Depends(get_chat_service),
    search_index: SearchIndexService | None = Depends(get_optional_search_index_service),
) -> StreamingResponse:
    user_id = current_user.user_id
    thread = _ensure_thread(session, thread_id, user_id)
    _enforce_metadata_permissions(current_user, thread.attributes)
    payload = payload.model_copy(update={"sender_id": user_id})
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    last_status: dict[str, str | None] = {"value": None}

    async def forward_chunk(chunk: dict[str, object]) -> None:
        status = chunk.get("agent_status")
        if isinstance(status, str):
            last_status["value"] = status.lower()
        await queue.put(json.dumps(chunk, separators=(",", ":")))

    initial_chunk = {
        "id": str(thread_id),
        "object": "chat.completion.chunk",
        "agent_status": "queued",
        "choices": [
            {
                "delta": {},
                "finish_reason": None,
            }
        ],
    }
    await queue.put(json.dumps(initial_chunk, separators=(",", ":")))
    last_status["value"] = "queued"

    async def worker() -> None:
        heartbeat_interval_seconds = 10.0
        stop_heartbeat = asyncio.Event()
        running_chunk_json = json.dumps(
            {
                "id": str(thread_id),
                "object": "chat.completion.chunk",
                "agent_status": "running",
                "choices": [
                    {
                        "delta": {},
                        "finish_reason": None,
                    }
                ],
            },
            separators=(",", ":"),
        )

        async def heartbeat_loop() -> None:
            try:
                while True:
                    await asyncio.sleep(heartbeat_interval_seconds)
                    if stop_heartbeat.is_set():
                        break
                    await queue.put(running_chunk_json)
            except asyncio.CancelledError:
                raise

        heartbeat_task: asyncio.Task | None = None
        try:
            await queue.put(running_chunk_json)
            last_status["value"] = "running"
            heartbeat_task = asyncio.create_task(heartbeat_loop())
            await _process_message_creation(
                thread=thread,
                payload=payload,
                session=session,
                user_id=user_id,
                chat_service=chat_service,
                search_index=search_index,
                chunk_callback=forward_chunk,
            )
            if last_status["value"] != "completed":
                completion_chunk = {
                    "id": str(thread_id),
                    "object": "chat.completion.chunk",
                    "agent_status": "completed",
                    "choices": [
                        {
                            "delta": {},
                            "finish_reason": "stop",
                        }
                    ],
                }
                await queue.put(json.dumps(completion_chunk, separators=(",", ":")))
        except HTTPException as exc:
            failure_chunk = {
                "id": str(thread_id),
                "object": "chat.completion.chunk",
                "agent_status": "failed",
                "choices": [
                    {
                        "delta": {},
                        "finish_reason": "error",
                    }
                ],
            }
            await queue.put(json.dumps(failure_chunk, separators=(",", ":")))
            await queue.put(
                json.dumps(
                    {"error": {"message": exc.detail, "type": "agent_error"}},
                    separators=(",", ":"),
                )
            )
            last_status["value"] = "failed"
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover - defensive logging
            logger.exception(
                "Unexpected error while streaming completion: thread_id=%s user_id=%s",
                thread.id,
                user_id,
            )
            failure_chunk = {
                "id": str(thread_id),
                "object": "chat.completion.chunk",
                "agent_status": "failed",
                "choices": [
                    {
                        "delta": {},
                        "finish_reason": "error",
                    }
                ],
            }
            await queue.put(json.dumps(failure_chunk, separators=(",", ":")))
            await queue.put(
                json.dumps(
                    {"error": {"message": "Internal server error", "type": "internal_error"}},
                    separators=(",", ":"),
                )
            )
            last_status["value"] = "failed"
        finally:
            stop_heartbeat.set()
            if heartbeat_task is not None:
                heartbeat_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await heartbeat_task
            await queue.put(None)

    task = asyncio.create_task(worker())

    async def event_generator():
        try:
            while True:
                item = await queue.get()
                if item is None:
                    yield "data: [DONE]\n\n"
                    break
                yield f"data: {item}\n\n"
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.patch(
    "/{thread_id}/messages/{message_id}",
    response_model=MessageRead,
)
def update_message(
    thread_id: UUID,
    message_id: UUID,
    payload: MessageUpdate,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> MessageRead:
    user_id = current_user.user_id
    thread = _ensure_thread(session, thread_id, user_id)
    _enforce_metadata_permissions(current_user, thread.attributes)
    stmt = select(Message).where(Message.id == message_id, Message.thread_id == thread_id)
    message = session.exec(stmt).one_or_none()
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    updated = False
    if payload.status is not None:
        message.status = payload.status
        updated = True
    if payload.error_code is not None:
        message.error_code = payload.error_code
        updated = True
    if payload.text is not None:
        message.text = payload.text
        updated = True
    if payload.tokens_count is not None:
        message.tokens_count = payload.tokens_count
        updated = True

    if updated:
        message.updated_at = utcnow()
        session.add(message)
        session.commit()
        session.refresh(message)

    return MessageRead.model_validate(message)
