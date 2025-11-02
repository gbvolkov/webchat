from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable
from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int


class TokenPayload(BaseModel):
    sub: str
    username: str
    type: str
    exp: int
    iat: int
    nbf: int
    iss: str | None = None
    aud: str | None = None
    token_version: int
    roles: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    agents: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    username: str
    roles: tuple[str, ...] = field(default_factory=tuple)
    allowed_products: frozenset[str] = field(default_factory=frozenset)
    allowed_agents: frozenset[str] = field(default_factory=frozenset)
    token_version: int = 1

    def __post_init__(self) -> None:  # type: ignore[override]
        object.__setattr__(self, "roles", tuple(self.roles))
        object.__setattr__(self, "allowed_products", frozenset(self.allowed_products))
        object.__setattr__(self, "allowed_agents", frozenset(self.allowed_agents))

    @property
    def user_id(self) -> str:
        return str(self.id)

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def can_access_product(self, product_id: str) -> bool:
        if not product_id:
            return True
        if not self.allowed_products:
            return True
        return product_id in self.allowed_products

    def can_access_agent(self, agent_id: str) -> bool:
        if not agent_id:
            return True
        if not self.allowed_agents:
            return True
        return agent_id in self.allowed_agents

    def can_access_products(self, product_ids: Iterable[str]) -> bool:
        return all(self.can_access_product(pid) for pid in product_ids if pid)

    def can_access_agents(self, agent_ids: Iterable[str]) -> bool:
        return all(self.can_access_agent(aid) for aid in agent_ids if aid)
