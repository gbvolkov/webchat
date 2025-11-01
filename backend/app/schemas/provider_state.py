from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic import ConfigDict


class ProviderThreadStateBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    provider: str = Field(default="openai-compatible", max_length=64)
    conversation_id: Optional[str] = Field(default=None, max_length=255)
    payload: dict = Field(default_factory=dict)


class ProviderThreadStateUpsert(ProviderThreadStateBase):
    pass


class ProviderThreadStateRead(ProviderThreadStateBase):
    id: UUID
    thread_id: UUID
    created_at: datetime
    updated_at: datetime
