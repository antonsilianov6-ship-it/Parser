"""Authentication routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.config import get_settings
from app.deps import CurrentUser, SessionDep
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserRead
from app.security import create_access_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: SessionDep) -> TokenResponse:
    """Authenticate with username + password and return a JWT access token."""
    user = session.exec(select(User).where(User.username == payload.username)).first()
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    settings = get_settings()
    token = create_access_token(subject=str(user.id))
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_access_ttl_minutes * 60,
    )


@router.get("/me", response_model=UserRead)
def me(current_user: CurrentUser) -> User:
    """Return the currently authenticated user."""
    return current_user
