from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from jwt import InvalidTokenError

from app.core.config import Settings, get_settings
from app.db.models import User
from app.schemas.auth import TokenPayload


class AuthenticationError(Exception):
    """Raised when authentication data cannot be validated."""


class AuthService:
    """Encapsulates password hashing and JWT token management."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        rounds = int(self._settings.bcrypt_rounds)
        self._bcrypt_rounds = max(4, min(rounds, 31))

    @property
    def access_token_expires_seconds(self) -> int:
        return int(self._settings.access_token_expire_minutes * 60)

    @property
    def refresh_token_expires_seconds(self) -> int:
        return int(self._settings.refresh_token_expire_minutes * 60)

    def hash_password(self, password: str) -> str:
        password_bytes = password.encode("utf-8")
        if len(password_bytes) > 72:
            raise AuthenticationError("Password must be 72 bytes or fewer when encoded as UTF-8")
        salt = bcrypt.gensalt(rounds=self._bcrypt_rounds)
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode("utf-8")

    def verify_password(self, plain_password: str, password_hash: str) -> bool:
        try:
            password_bytes = plain_password.encode("utf-8")
            if len(password_bytes) > 72:
                return False
            return bcrypt.checkpw(password_bytes, (password_hash or "").encode("utf-8"))
        except ValueError:
            return False

    def issue_access_token(self, user: User) -> str:
        return self._create_token(user=user, token_type="access", expires_seconds=self.access_token_expires_seconds)

    def issue_refresh_token(self, user: User) -> str:
        return self._create_token(user=user, token_type="refresh", expires_seconds=self.refresh_token_expires_seconds)

    def issue_token_pair(self, user: User) -> tuple[str, str]:
        return self.issue_access_token(user), self.issue_refresh_token(user)

    def decode_access_token(self, token: str) -> TokenPayload:
        return self._decode_token(token, expected_type="access")

    def decode_refresh_token(self, token: str) -> TokenPayload:
        return self._decode_token(token, expected_type="refresh")

    def _create_token(self, *, user: User, token_type: str, expires_seconds: int) -> str:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=expires_seconds)
        payload: dict[str, Any] = {
            "sub": str(user.id),
            "username": user.username,
            "type": token_type,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "iss": self._settings.jwt_issuer,
            "token_version": user.token_version,
            "roles": user.roles or [],
            "products": user.allowed_products or [],
            "agents": user.allowed_agents or [],
        }
        if self._settings.jwt_audience:
            payload["aud"] = self._settings.jwt_audience
        return jwt.encode(
            payload,
            self._settings.jwt_secret_key,
            algorithm=self._settings.jwt_algorithm,
        )

    def _decode_token(self, token: str, *, expected_type: str) -> TokenPayload:
        options = {"require": ["exp", "iat", "nbf", "sub", "type", "token_version"]}
        decode_kwargs: dict[str, Any] = {
            "key": self._settings.jwt_secret_key,
            "algorithms": [self._settings.jwt_algorithm],
            "options": options,
        }
        if self._settings.jwt_audience:
            decode_kwargs["audience"] = self._settings.jwt_audience
        if self._settings.jwt_issuer:
            decode_kwargs["issuer"] = self._settings.jwt_issuer
        try:
            raw_payload = jwt.decode(token, **decode_kwargs)
        except InvalidTokenError as exc:
            raise AuthenticationError("Failed to validate token") from exc

        payload = TokenPayload.model_validate(raw_payload)
        if payload.type != expected_type:
            raise AuthenticationError("Unexpected token type")
        return payload
