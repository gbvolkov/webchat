from __future__ import annotations

import asyncio
import base64
import binascii
import contextlib
import inspect
import io
import json
import logging
import textwrap
from html import escape
import os
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import quote
from uuid import UUID

import markdown as md
import markdown2
from markdown_pdf import MarkdownPdf, Section
from html2docx import html2docx as html_to_docx
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session, func, select
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.api.deps import (
    ensure_agent_access,
    ensure_product_access,
    get_chat_service,
    get_current_user,
    get_optional_search_index_service,
    get_session,
)
from app.db.models import Message, MessageAttachment, MessageStatus, ProviderThreadState, SenderType, Thread, utcnow
from app.core.config import get_settings
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
BUNDLED_FONT_PATH = (
    Path(__file__).resolve().parent.parent / "static" / "fonts" / "DejaVuSans.ttf"
)
_DEFAULT_THREAD_PREFIX = "Product"
logger = logging.getLogger(__name__)

_FONTS_REGISTERED = False


def _fonts_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "static" / "fonts"


def _discover_font_path() -> Path | None:
    candidates: list[Path] = [
        _fonts_dir() / "DejaVuSans.ttf",
        _fonts_dir() / "DejaVuSans-Bold.ttf",
        #BUNDLED_FONT_PATH,
        #Path("C:/Windows/Fonts/arial.ttf"),
        #Path("C:/Windows/Fonts/arialuni.ttf"),
        #Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        #Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _sanitize_export_filename(title: str | None, thread_id: UUID) -> str:
    raw = _sanitize_title_fragment(title or "").replace(" ", "_")
    ascii_only = "".join(ch for ch in raw if ch.isascii() and (ch.isalnum() or ch in ("_", "-", ".")))
    if not ascii_only:
        ascii_only = str(thread_id)
    return ascii_only.strip("._") or str(thread_id)


def _build_content_disposition(filename_ascii: str, filename_utf8: str | None = None) -> str:
    parts = [f'attachment; filename="{filename_ascii}"']
    if filename_utf8:
        parts.append(f"filename*=UTF-8''{quote(filename_utf8)}")
    return "; ".join(parts)


def _render_markdown_export(
    thread: Thread,
    messages: Sequence[Message],
    attachments_map: dict[UUID, list[MessageAttachment]],
) -> str:
    lines: list[str] = []
    title = thread.title or f"Thread {thread.id}"
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"- Thread ID: {thread.id}")
    lines.append(f"- Created at: {thread.created_at.isoformat()}")
    lines.append(f"- Updated at: {thread.updated_at.isoformat()}")
    if thread.attributes:
        for key, value in thread.attributes.items():
            lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Messages")
    lines.append("")

    for msg in messages:
        sender = msg.sender_type.value if hasattr(msg.sender_type, "value") else str(msg.sender_type)
        lines.append(f"### {msg.created_at.isoformat()} — {sender}")
        lines.append("")
        text_lines = (msg.text or "").splitlines() or [""]
        lines.extend(text_lines)

        attachments = attachments_map.get(msg.id, [])
        if attachments:
            lines.append("")
            lines.append("Attachments:")
            for attachment in attachments:
                download_url = _build_attachment_download_url(attachment.storage_filename)
                suffix = f" ({attachment.content_type})"
                if download_url:
                    lines.append(f"- [{attachment.filename}]({download_url}){suffix}")
                else:
                    lines.append(f"- {attachment.filename}{suffix}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _register_reportlab_font(font_path: Path | None, alias: str = "ExportFont") -> str:
    if not font_path:
        return "Helvetica"
    try:
        pdfmetrics.registerFont(TTFont(alias, str(font_path)))
        pdfmetrics.registerFontFamily(alias, normal=alias, bold=alias, italic=alias, boldItalic=alias)
        return alias
    except Exception:
        logger.debug("Failed to register reportlab font at %s", font_path, exc_info=True)
        return "Helvetica"


def _register_local_fonts() -> str:
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return "DejaVuSans"

    fonts_dir = _fonts_dir()
    regular = fonts_dir / "DejaVuSans.ttf"
    bold = fonts_dir  / "DejaVuSans-Bold.ttf"
    italic = fonts_dir  / "DejaVuSans-Oblique.ttf"
    bold_italic = fonts_dir  / "DejaVuSans-BoldOblique.ttf"

    missing = [p for p in (regular, bold, italic, bold_italic) if not p.exists()]
    if missing:
        logger.error("Missing font files for PDF export: %s", missing)

    pdfmetrics.registerFont(TTFont("DejaVuSans", str(regular)))
    if bold.exists():
        pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(bold)))
    if italic.exists():
        pdfmetrics.registerFont(TTFont("DejaVuSans-Italic", str(italic)))
    if bold_italic.exists():
        pdfmetrics.registerFont(TTFont("DejaVuSans-BoldItalic", str(bold_italic)))

    pdfmetrics.registerFontFamily(
        "DejaVuSans",
        normal="DejaVuSans",
        bold="DejaVuSans-Bold" if bold.exists() else "DejaVuSans",
        italic="DejaVuSans-Italic" if italic.exists() else "DejaVuSans",
        boldItalic="DejaVuSans-BoldItalic" if bold_italic.exists() else "DejaVuSans",
    )
    _FONTS_REGISTERED = True
    return "DejaVuSans"


def _build_plain_pdf(markdown_text: str, *, title: str, font_path: Path | None) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    font_name = _register_local_fonts()
    font_size = 11
    leading = 16

    c.setTitle(title)
    c.setAuthor("GWP Chat")
    c.setFont(font_name, font_size)

    def new_text_obj():
        obj = c.beginText()
        obj.setTextOrigin(40, 780)
        obj.setLeading(leading)
        return obj

    text_obj = new_text_obj()

    def flush_page(obj):
        c.drawText(obj)
        c.showPage()
        c.setFont(font_name, font_size)
        return new_text_obj()

    for paragraph in markdown_text.splitlines():
        if not paragraph:
            text_obj.textLine("")
        else:
            wrapped_lines = textwrap.wrap(paragraph, width=110) or [paragraph]
            for line in wrapped_lines:
                try:
                    text_obj.textLine(line)
                except Exception:
                    text_obj.textLine(line.encode("latin-1", errors="replace").decode("latin-1"))
        if text_obj.getY() <= 40:
            text_obj = flush_page(text_obj)

    text_obj = flush_page(text_obj)
    c.save()
    return buffer.getvalue()


def _quiet_markdown_logging() -> None:
    """Suppress verbose markdown-it debug logs during PDF generation."""
    for name in ("markdown_it", "markdown_it.rules_block"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.WARNING)


def _build_pdf_from_markdown(markdown_text: str, *, title: str) -> bytes:
    _quiet_markdown_logging()
    pdf = MarkdownPdf(toc_level=0)
    pdf.meta["title"] = title or "Thread export"

    fonts_dir = _fonts_dir()
    regular = fonts_dir / "DejaVuSans.ttf"
    bold = fonts_dir / "DejaVuSans-Bold.ttf"
    italic = fonts_dir / "DejaVuSans-Oblique.ttf"
    bold_italic = fonts_dir / "DejaVuSans-BoldOblique.ttf"

    font_face = ""
    try:
        if regular.exists():
            font_face += (
                "@font-face { font-family: 'DejaVuSans'; font-style: normal; font-weight: normal; "
                f"src: url('{regular.resolve().as_uri()}') format('truetype'); }} "
            )
        if bold.exists():
            font_face += (
                "@font-face { font-family: 'DejaVuSans'; font-style: normal; font-weight: bold; "
                f"src: url('{bold.resolve().as_uri()}') format('truetype'); }} "
            )
        if italic.exists():
            font_face += (
                "@font-face { font-family: 'DejaVuSans'; font-style: italic; font-weight: normal; "
                f"src: url('{italic.resolve().as_uri()}') format('truetype'); }} "
            )
        if bold_italic.exists():
            font_face += (
                "@font-face { font-family: 'DejaVuSans'; font-style: italic; font-weight: bold; "
                f"src: url('{bold_italic.resolve().as_uri()}') format('truetype'); }} "
            )
    except Exception:
        font_face = ""

    stylesheet = f"""
    {font_face}
    @page {{
        size: A4;
        margin: 20mm;
    }}
    body {{
        font-family: 'DejaVuSans';
        font-size: 11pt;
        line-height: 1.4;
        color: #111;
    }}
    h1, h2, h3, h4 {{
        font-family: 'DejaVuSans';
        font-weight: bold;
        margin-top: 12pt;
        margin-bottom: 6pt;
        color: #111;
    }}
    strong {{ font-weight: bold; }}
    em {{ font-style: italic; }}
    code, pre {{ font-family: 'DejaVuSans'; }}
    """

    section = Section(markdown_text, toc=False)
    pdf.add_section(section, user_css=stylesheet)

    buffer = io.BytesIO()
    pdf.save_bytes(buffer)
    return buffer.getvalue()


def _build_docx_from_markdown(markdown_text: str, *, title: str) -> bytes:
    _quiet_markdown_logging()
    html_body = md.markdown(
        markdown_text,
        extensions=["extra", "sane_lists", "tables"],
        output_format="html",
    )
    html = f"<html><head><meta charset='utf-8'><title>{escape(title)}</title></head><body>{html_body}</body></html>"

    try:
        buf = html_to_docx(html, title=title or "Thread export")
        return buf.getvalue()
    except Exception:
        logger.exception("Failed to render DOCX export, falling back to plain text docx")

    try:
        from docx import Document

        buffer = io.BytesIO()
        doc = Document()
        doc.core_properties.title = title or "Thread export"
        for line in markdown_text.splitlines():
            doc.add_paragraph(line)
        doc.save(buffer)
        return buffer.getvalue()
    except Exception:
        logger.exception("Failed to render fallback DOCX export")
        return markdown_text.encode("utf-8", errors="replace")


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
    data_bytes = attachment.data if include_data and attachment.data is not None else None
    data_base64 = base64.b64encode(data_bytes).decode("utf-8") if data_bytes else None
    size_bytes = attachment.size_bytes
    if size_bytes is None and attachment.data is not None:
        size_bytes = len(attachment.data)
    return MessageAttachmentRead(
        id=attachment.id,
        filename=attachment.filename,
        content_type=attachment.content_type,
        data_base64=data_base64,
        created_at=attachment.created_at,
        size_bytes=size_bytes,
        download_url=_build_attachment_download_url(attachment.storage_filename),
    )


def _build_attachment_download_url(storage_filename: str | None) -> str | None:
    if not storage_filename:
        return None
    settings = get_settings()
    prefix = (settings.api_prefix or "").rstrip("/")
    base_path = f"{prefix}/attachments" if prefix else "/attachments"
    return f"{base_path}/{storage_filename}"


def _build_prompt_parts(message: Message, attachments: Sequence[MessageAttachment]) -> list[dict[str, object]]:
    parts: list[dict[str, object]] = [{"type": "text", "text": message.text}]
    for attachment in attachments:
        if attachment.data is None:
            continue
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


def _collect_provider_attachments(
    buffer: dict[str, dict[str, Any]],
    chunk: dict[str, Any],
) -> None:
    metadata = chunk.get("message_metadata")
    if not isinstance(metadata, dict):
        return
    attachments = metadata.get("attachments")
    if not isinstance(attachments, list):
        return
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        storage_name = attachment.get("storage_filename")
        key = storage_name or f"{attachment.get('filename')}:{len(buffer)}"
        buffer[key] = attachment


def _persist_provider_attachments(
    session: Session,
    message: Message,
    attachments: Sequence[dict[str, Any]],
) -> list[MessageAttachment]:
    persisted: list[MessageAttachment] = []
    for attachment in attachments:
        storage_filename = attachment.get("storage_filename")
        if not isinstance(storage_filename, str) or not storage_filename:
            continue
        filename = str(attachment.get("filename") or storage_filename)
        raw_content_type = (
            attachment.get("content_type")
            or attachment.get("media_type")
            or attachment.get("mime_type")
        )
        content_type = str(raw_content_type) if isinstance(raw_content_type, str) else "application/octet-stream"
        size_bytes = _coerce_int(attachment.get("bytes"))
        record = MessageAttachment(
            message_id=message.id,
            filename=filename,
            content_type=content_type,
            data=None,
            storage_filename=storage_filename,
            size_bytes=size_bytes,
        )
        persisted.append(record)
        session.add(record)
    return persisted


def _coerce_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            try:
                return int(stripped)
            except ValueError:
                return None
    return None


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


def _extract_chunk_text(chunk: dict[str, Any]) -> str:
    choices = chunk.get("choices")
    if not isinstance(choices, list):
        return ""
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        for key in ("delta", "message"):
            candidate = choice.get(key)
            text = _extract_text_from_candidate(candidate)
            if text:
                return text
    return ""


def _extract_text_from_candidate(candidate: Any) -> str:
    if not isinstance(candidate, dict):
        return ""
    direct = candidate.get("text")
    if isinstance(direct, str) and direct.strip():
        return direct
    content = candidate.get("content")
    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                return text
    return ""


def _enrich_interrupt_chunk_content(chunk: dict[str, Any]) -> dict[str, Any]:
    status = chunk.get("agent_status")
    if not isinstance(status, str) or status.lower() != "interrupted":
        return chunk
    metadata = chunk.get("message_metadata")
    if not isinstance(metadata, dict):
        return chunk
    payload = metadata.get("interrupt_payload")
    content: str | None = None
    if isinstance(payload, dict):
        for key in ("content", "question"):
            candidate = payload.get(key)
            if isinstance(candidate, str) and candidate.strip():
                content = candidate.strip()
                break
    if content is None:
        for key in ("content", "question"):
            candidate = metadata.get(key)
            if isinstance(candidate, str) and candidate.strip():
                content = candidate.strip()
                break
    if not content:
        return chunk
    choices = chunk.get("choices")
    if not isinstance(choices, list) or not choices:
        chunk["choices"] = [{"delta": {"content": content}, "finish_reason": None}]
        return chunk
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        delta = choice.get("delta")
        if isinstance(delta, dict):
            delta["content"] = content
        else:
            choice["delta"] = {"content": content}
        message = choice.get("message")
        if isinstance(message, dict):
            message["content"] = content
    return chunk


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


@router.get("/{thread_id}/export")
def export_thread(
    thread_id: UUID,
    format: str = Query(default="markdown", pattern="^(pdf|markdown|docx)$"),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    user_id = current_user.user_id
    thread = _ensure_thread(session, thread_id, user_id)
    _enforce_metadata_permissions(current_user, thread.attributes)

    messages: list[Message] = session.exec(
        select(Message).where(Message.thread_id == thread_id).order_by(Message.created_at.asc())
    ).all()
    attachments_map = _get_message_attachments(session, [msg.id for msg in messages])

    markdown_text = _render_markdown_export(thread, messages, attachments_map)
    filename_base = _sanitize_export_filename(thread.title, thread.id)

    ext = "md" if format == "markdown" else "pdf" if format == "pdf" else "docx"
    utf8_filename = f"{thread.title or thread.id}.{ext}"
    if format == "markdown":
        disposition = _build_content_disposition(f"{filename_base}.md", utf8_filename)
        return Response(
            content=markdown_text,
            media_type="text/markdown",
            headers={"Content-Disposition": disposition},
        )

    if format == "pdf":
        pdf_bytes = _build_pdf_from_markdown(markdown_text, title=thread.title or str(thread.id))
        disposition = _build_content_disposition(f"{filename_base}.pdf", utf8_filename)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": disposition},
        )

    docx_bytes = _build_docx_from_markdown(markdown_text, title=thread.title or str(thread.id))
    disposition = _build_content_disposition(f"{filename_base}.docx", utf8_filename)
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": disposition},
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
    provider_attachments_buffer: dict[str, dict[str, Any]] = {}
    conversation_state = session.exec(conversation_state_stmt).one_or_none()
    active_conversation_id = conversation_state.conversation_id if conversation_state else None

    user_message = Message(
        thread_id=thread.id,
        sender_id=payload.sender_id,
        sender_type=payload.sender_type,
        status=MessageStatus.QUEUED,
        text=payload.text,
        meta=payload.metadata or {},
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
                size_bytes=len(binary),
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
                metadata=msg.meta or None,
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

        async def handle_stream_chunk(chunk: dict[str, Any]) -> None:
            chunk = _enrich_interrupt_chunk_content(chunk)
            _collect_provider_attachments(provider_attachments_buffer, chunk)
            if chunk_callback is None:
                return
            result = chunk_callback(chunk)
            if inspect.isawaitable(result):
                await result

        completion = await chat_service.create_completion(
            model=model_name,
            messages=prompt_messages,
            user=user_id,
            conversation_id=active_conversation_id,
            stream=True,
            on_status=handle_agent_status,
            on_chunk=handle_stream_chunk,
        )
        if completion.agent_status and completion.agent_status.lower() == "interrupted":
            completion.content = OpenAIChatService._extract_interrupt_text(
                completion.metadata if isinstance(completion.metadata, dict) else None,
                completion.content,
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
    assistant_text = completion.content or ""
    if not assistant_text.strip():
        assistant_text = "(no text content)"
    assistant_message = Message(
        thread_id=thread.id,
        sender_id="assistant",
        sender_type=SenderType.ASSISTANT,
        status=MessageStatus.READY,
        text=assistant_text,
        meta=completion.metadata or {},
        tokens_count=assistant_tokens,
        correlation_id=completion.response_id or None,
    )

    if isinstance(completion.metadata, dict):
        attachments_meta = completion.metadata.get("attachments")
        if isinstance(attachments_meta, list):
            for attachment in attachments_meta:
                if not isinstance(attachment, dict):
                    continue
                key = attachment.get("storage_filename") or f"{attachment.get('filename')}:{len(provider_attachments_buffer)}"
                provider_attachments_buffer.setdefault(key, attachment)

    provider_attachment_payloads = list(provider_attachments_buffer.values())
    if provider_attachment_payloads:
        _persist_provider_attachments(
            session=session,
            message=assistant_message,
            attachments=provider_attachment_payloads,
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
        metadata = chunk.get("message_metadata")
        attachments_preview: list[dict[str, Any]] = []
        if isinstance(metadata, dict):
            attachments = metadata.get("attachments")
            if isinstance(attachments, list):
                for attachment in attachments:
                    if isinstance(attachment, dict):
                        attachments_preview.append(
                            {
                                "filename": attachment.get("filename"),
                                "bytes": attachment.get("bytes"),
                                "download_url": attachment.get("download_url"),
                            }
                        )
        text_preview = _truncate(_extract_chunk_text(chunk), 160)
        logger.info(
            "Forwarded agent chunk to client: thread_id=%s status=%s text_preview=%s attachments=%s",
            thread.id,
            status or last_status["value"] or "n/a",
            text_preview,
            attachments_preview,
        )

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
            if last_status["value"] not in {"completed", "interrupted"}:
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
    if payload.text is not None and not payload.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text must not be empty",
        )
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
def _pisa_link_callback(uri: str, rel: str) -> str:
    if not isinstance(uri, str):
        return uri
    if uri.startswith("file:"):
        path = uri[5:]
        if path.startswith("//"):
            path = path[2:]
        if path.startswith("/"):
            path = path[1:]
        if os.name == "nt" and path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]
        return path
    return uri
