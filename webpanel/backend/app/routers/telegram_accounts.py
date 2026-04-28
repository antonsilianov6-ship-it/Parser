"""Telegram account CRUD (metadata only; actual Telethon auth lands in a later PR)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlmodel import or_, select

from app.deps import CurrentUser, SessionDep
from app.models.telegram_account import TelegramAccount
from app.schemas.telegram_account import (
    TelegramAccountCreate,
    TelegramAccountRead,
    TelegramAccountUpdate,
)

router = APIRouter(prefix="/api/telegram/accounts", tags=["telegram"])


def _default_session_path(owner_id: int, label: str) -> str:
    """Return the default on-disk location for a new Telethon session file."""
    safe_label = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in label)
    return f"sessions/user_{owner_id}_{safe_label}.session"


@router.post(
    "",
    response_model=TelegramAccountRead,
    status_code=status.HTTP_201_CREATED,
)
def create_account(
    payload: TelegramAccountCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> TelegramAccount:
    """Register a new Telegram account slot for the caller.

    This only creates metadata; the Telethon send-code / sign-in flow is added in a
    follow-up PR and will flip ``is_authorized`` once completed.
    """
    assert current_user.id is not None
    existing = session.exec(
        select(TelegramAccount).where(
            TelegramAccount.owner_id == current_user.id,
            TelegramAccount.label == payload.label,
        )
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a Telegram account with this label",
        )

    account = TelegramAccount(
        owner_id=current_user.id,
        label=payload.label,
        phone=payload.phone,
        session_path=_default_session_path(current_user.id, payload.label),
        is_shared=payload.is_shared,
        is_authorized=False,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


@router.get("", response_model=list[TelegramAccountRead])
def list_accounts(session: SessionDep, current_user: CurrentUser) -> list[TelegramAccount]:
    """Return accounts the caller owns plus all accounts marked as shared."""
    assert current_user.id is not None
    statement = (
        select(TelegramAccount)
        .where(
            or_(
                TelegramAccount.owner_id == current_user.id,
                TelegramAccount.is_shared.is_(True),  # type: ignore[attr-defined]
            )
        )
        .order_by(TelegramAccount.id)
    )
    return list(session.exec(statement))


@router.patch("/{account_id}", response_model=TelegramAccountRead)
def update_account(
    account_id: int,
    payload: TelegramAccountUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> TelegramAccount:
    """Rename an account or toggle its shared flag. Only the owner can edit."""
    account = session.get(TelegramAccount, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    if account.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner may modify this Telegram account",
        )

    if payload.label is not None and payload.label != account.label:
        collision = session.exec(
            select(TelegramAccount).where(
                TelegramAccount.owner_id == account.owner_id,
                TelegramAccount.label == payload.label,
                TelegramAccount.id != account.id,
            )
        ).first()
        if collision is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have a Telegram account with this label",
            )
        account.label = payload.label
    if payload.is_shared is not None:
        account.is_shared = payload.is_shared
    account.updated_at = datetime.now(tz=UTC)
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    account_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> None:
    """Delete an account slot. Only the owner can delete."""
    account = session.get(TelegramAccount, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    if account.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner may delete this Telegram account",
        )
    session.delete(account)
    session.commit()
