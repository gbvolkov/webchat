from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    email: EmailStr | None = None
    full_name: Optional[str] = None
    roles: list[str] = Field(default_factory=list)
    allowed_products: list[str] = Field(default_factory=list)
    allowed_agents: list[str] = Field(default_factory=list)
    is_active: bool = True


class UserRead(UserBase):
    id: UUID
    token_version: int
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None


class UserCreate(BaseModel):
    username: str
    password: str
    email: EmailStr | None = None
    full_name: Optional[str] = None
    roles: list[str] = Field(default_factory=list)
    allowed_products: list[str] = Field(default_factory=list)
    allowed_agents: list[str] = Field(default_factory=list)
    is_active: bool = True


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: Optional[str] = None
    password: str | None = None
    roles: list[str] | None = None
    allowed_products: list[str] | None = None
    allowed_agents: list[str] | None = None
    is_active: bool | None = None
