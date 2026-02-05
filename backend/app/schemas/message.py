from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic import ConfigDict, field_validator, model_validator

from app.db.models import MessageStatus, SenderType


ERROR_CODE_MAX_LENGTH = 128


def _truncate_error_code(value: str) -> str:
    if len(value) <= ERROR_CODE_MAX_LENGTH:
        return value
    return value[:ERROR_CODE_MAX_LENGTH].rstrip()


class MessageBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    text: str = Field(min_length=1)
    sender_type: SenderType = Field(default=SenderType.USER)
    status: MessageStatus = Field(default=MessageStatus.QUEUED)
    correlation_id: Optional[str] = Field(default=None, max_length=255)
    error_code: Optional[str] = Field(default=None, max_length=ERROR_CODE_MAX_LENGTH)
    tokens_count: Optional[int] = Field(default=None, ge=0)
    metadata: dict = Field(default_factory=dict, validation_alias="meta")

    @field_validator("error_code", mode="before")
    @classmethod
    def _normalize_error_code(cls, value):
        if isinstance(value, str):
            return _truncate_error_code(value)
        return value


class MessageCreate(MessageBase):
    sender_id: str = Field(min_length=1, max_length=128)
    model: Optional[str] = Field(default=None, min_length=1, max_length=255)
    attachments: list["MessageAttachmentCreate"] = Field(default_factory=list)
    model_label: Optional[str] = Field(default=None, min_length=1, max_length=255)

    @model_validator(mode="before")
    @classmethod
    def apply_sender_aliases(cls, values):
        if isinstance(values, dict):
            data = dict(values)
            if "sender_id" not in data and "user_id" in data:
                data["sender_id"] = data["user_id"]
            return data
        return values


class MessageUpdate(BaseModel):
    status: Optional[MessageStatus] = None
    error_code: Optional[str] = Field(default=None, max_length=ERROR_CODE_MAX_LENGTH)
    text: Optional[str] = None
    tokens_count: Optional[int] = Field(default=None, ge=0)

    @field_validator("error_code", mode="before")
    @classmethod
    def _normalize_error_code(cls, value):
        if isinstance(value, str):
            return _truncate_error_code(value)
        return value


class MessageRead(MessageBase):
    id: UUID
    thread_id: UUID
    sender_id: str
    created_at: datetime
    updated_at: datetime
    attachments: list["MessageAttachmentRead"] = Field(default_factory=list)


class MessageAttachmentBase(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(default="application/octet-stream", max_length=255)


class MessageAttachmentCreate(MessageAttachmentBase):
    data_base64: str = Field(min_length=1)


class MessageAttachmentRead(MessageAttachmentBase):
    id: UUID
    created_at: datetime
    data_base64: Optional[str] = None
    size_bytes: Optional[int] = None
    download_url: Optional[str] = None


MessageCreate.model_rebuild()
MessageRead.model_rebuild()
