from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic import ConfigDict, model_validator

from app.schemas.common import PaginatedResponse
from app.schemas.message import MessageRead


class ThreadBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    title: Optional[str] = Field(default=None, max_length=255)
    summary: Optional[str] = Field(default=None, max_length=1024)
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def apply_metadata_aliases(cls, values):
        if isinstance(values, dict):
            data = dict(values)
        else:
            data = {}
            if hasattr(values, "__dict__"):
                data.update(values.__dict__)
            if hasattr(values, "model_dump"):
                data.update(values.model_dump())
        if "metadata" not in data:
            if "attributes" in data:
                data["metadata"] = data["attributes"]
            elif hasattr(values, "attributes"):
                data["metadata"] = getattr(values, "attributes")
        return data or values


class ThreadCreate(ThreadBase):
    pass


class ThreadUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: Optional[str] = Field(default=None, max_length=255)
    summary: Optional[str] = Field(default=None, max_length=1024)
    metadata: Optional[dict] = Field(default=None)
    is_deleted: Optional[bool] = None

    @model_validator(mode="before")
    @classmethod
    def apply_metadata_aliases(cls, values):
        if isinstance(values, dict):
            data = dict(values)
        else:
            data = {}
            if hasattr(values, "__dict__"):
                data.update(values.__dict__)
            if hasattr(values, "model_dump"):
                data.update(values.model_dump())
        if "metadata" not in data and "attributes" in data:
            data["metadata"] = data["attributes"]
        return data or values


class ThreadRead(ThreadBase):
    id: UUID
    owner_id: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class ThreadDetail(ThreadRead):
    last_messages: list[MessageRead] = Field(default_factory=list)


ThreadListResponse = PaginatedResponse[ThreadRead]
