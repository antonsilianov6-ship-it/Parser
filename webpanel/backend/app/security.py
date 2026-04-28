"""Password hashing and JWT helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.config import get_settings


def hash_password(password: str) -> str:
    """Hash *password* with bcrypt and return an encoded UTF-8 string."""
    if not password:
        raise ValueError("password must not be empty")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Return True if *password* matches the stored bcrypt hash."""
    if not password or not hashed:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    """Create a signed JWT access token for *subject* (typically the user id)."""
    settings = get_settings()
    if not settings.jwt_secret:
        raise RuntimeError(
            "PANEL_JWT_SECRET is not configured; refusing to issue tokens with an empty secret"
        )
    now = datetime.now(tz=UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_access_ttl_minutes)).timestamp()),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT, returning its claims."""
    settings = get_settings()
    if not settings.jwt_secret:
        raise RuntimeError("PANEL_JWT_SECRET is not configured")
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
