"""User management routes.

The panel is single-role: any authenticated user may create or deactivate other users.
The very first account is created either through ``POST /api/users/bootstrap``
(only accepted while the users table is empty) or via ``scripts/bootstrap_admin.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.config import get_settings
from app.deps import CurrentUser, SessionDep
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.security import hash_password
from app.services import parser_files
from app.services.browser_session import get_manager

router = APIRouter(prefix="/api/users", tags=["users"])


def _create_user(session: SessionDep, payload: UserCreate) -> User:
    existing = session.exec(select(User).where(User.username == payload.username)).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already taken",
        )
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.post(
    "/bootstrap",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create the first panel user",
)
def bootstrap_user(payload: UserCreate, session: SessionDep) -> User:
    """Create the very first user. Returns 409 if any user already exists."""
    if session.exec(select(User)).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Panel already has at least one user; use POST /api/users instead",
        )
    user = _create_user(session, payload)
    # First-ever user inherits the legacy global config.json / prompts.json /
    # channels.txt that may already live in the repo root from a pre-PR-#9
    # install. Subsequent users get fresh templates from _create_user above.
    if user.id is not None:
        parser_files.seed_user_dir(user.id, copy_legacy=True)
    return user


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a new user",
)
def create_user(
    payload: UserCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> User:
    """Create a new user. Requires an authenticated caller."""
    del current_user
    user = _create_user(session, payload)
    if user.id is not None:
        parser_files.seed_user_dir(user.id)
    return user


@router.get("", response_model=list[UserRead])
def list_users(session: SessionDep, current_user: CurrentUser) -> list[User]:
    """Return all users ordered by id."""
    del current_user
    return list(session.exec(select(User).order_by(User.id)))


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> User:
    """Update a user's password or active flag."""
    del current_user
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
    if payload.is_active is not None:
        user.is_active = payload.is_active
    user.updated_at = datetime.now(tz=UTC)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int, session: SessionDep, current_user: CurrentUser
) -> None:
    """Delete a user.

    Refuses to delete the currently authenticated user or the last remaining user, to
    keep the panel reachable. Also tears down any in-flight browser-auth session
    owned by the deleted user so the shared Chromium isn't held by an orphaned
    record.
    """
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the currently authenticated user",
        )

    total = len(list(session.exec(select(User))))
    if total <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the last remaining user",
        )

    # Free the shared Chromium *before* dropping the row so an orphaned
    # browser-auth session doesn't pin the slot for the full timeout.
    manager = get_manager(get_settings())
    await manager.cancel_sessions_for_user(user_id)

    session.delete(user)
    session.commit()
