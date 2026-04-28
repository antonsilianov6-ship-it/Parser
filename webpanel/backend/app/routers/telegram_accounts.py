"""Telegram account CRUD + Telethon-backed authorisation flow."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlmodel import or_, select

from app.deps import CurrentUser, SessionDep
from app.models.telegram_account import TelegramAccount
from app.schemas.telegram_account import (
    SendCodeRequest,
    SendCodeResponse,
    TelegramAccountCreate,
    TelegramAccountRead,
    TelegramAccountUpdate,
    VerifyRequest,
    VerifyResponse,
)
from app.services import telegram_auth as tg_auth

router = APIRouter(prefix="/api/telegram/accounts", tags=["telegram"])


def _default_session_path(owner_id: int, label: str) -> str:
    safe_label = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in label)
    return f"sessions/user_{owner_id}_{safe_label}.session"


def _to_read(account: TelegramAccount) -> TelegramAccountRead:
    """Serialise a row to the public response (never leaks ``api_hash``)."""
    assert account.id is not None
    return TelegramAccountRead(
        id=account.id,
        owner_id=account.owner_id,
        label=account.label,
        phone=account.phone,
        session_path=account.session_path,
        api_id=account.api_id,
        has_api_hash=bool(account.api_hash),
        is_shared=account.is_shared,
        is_authorized=account.is_authorized,
        created_at=account.created_at,
        updated_at=account.updated_at,
        last_used_at=account.last_used_at,
    )


def _ensure_owner(account: TelegramAccount, user_id: int | None, verb: str) -> None:
    if account.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only the owner may {verb} this Telegram account",
        )


@router.post(
    "",
    response_model=TelegramAccountRead,
    status_code=status.HTTP_201_CREATED,
)
def create_account(
    payload: TelegramAccountCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> TelegramAccountRead:
    """Register a new Telegram account slot for the caller."""
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
    return _to_read(account)


@router.get("", response_model=list[TelegramAccountRead])
def list_accounts(
    session: SessionDep, current_user: CurrentUser
) -> list[TelegramAccountRead]:
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
    return [_to_read(a) for a in session.exec(statement)]


@router.patch("/{account_id}", response_model=TelegramAccountRead)
def update_account(
    account_id: int,
    payload: TelegramAccountUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> TelegramAccountRead:
    """Rename an account or toggle its shared flag. Only the owner can edit."""
    account = session.get(TelegramAccount, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    _ensure_owner(account, current_user.id, "modify")

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
    return _to_read(account)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> None:
    """Delete an account slot. Only the owner can delete."""
    account = session.get(TelegramAccount, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    _ensure_owner(account, current_user.id, "delete")
    await tg_auth.cancel_pending(account_id)
    session.delete(account)
    session.commit()


# -- Telethon authorisation flow --------------------------------------------


@router.post(
    "/{account_id}/send-code",
    response_model=SendCodeResponse,
)
async def send_code(
    account_id: int,
    payload: SendCodeRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> SendCodeResponse:
    """Step 1: cache API credentials and ask Telegram to send the login code."""
    account = session.get(TelegramAccount, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    _ensure_owner(account, current_user.id, "authorize")

    try:
        expires_in = await tg_auth.send_code(
            account_id,
            session_path=account.session_path,
            api_id=payload.api_id,
            api_hash=payload.api_hash,
            phone=payload.phone,
        )
    except tg_auth.TelegramAuthError as err:
        raise HTTPException(status_code=err.status_code, detail=str(err)) from err

    account.api_id = payload.api_id
    account.api_hash = payload.api_hash
    account.phone = payload.phone
    account.updated_at = datetime.now(tz=UTC)
    session.add(account)
    session.commit()

    return SendCodeResponse(pending=True, expires_in=expires_in)


@router.post(
    "/{account_id}/verify",
    response_model=VerifyResponse,
)
async def verify(
    account_id: int,
    payload: VerifyRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> VerifyResponse:
    """Step 2: submit the received code (and optionally a 2FA password)."""
    account = session.get(TelegramAccount, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    _ensure_owner(account, current_user.id, "authorize")

    try:
        authorized, needs_password = await tg_auth.verify(
            account_id,
            code=payload.code,
            password=payload.password,
        )
    except tg_auth.TelegramAuthError as err:
        raise HTTPException(status_code=err.status_code, detail=str(err)) from err

    if authorized:
        account.is_authorized = True
        account.last_used_at = datetime.now(tz=UTC)
        account.updated_at = datetime.now(tz=UTC)
        session.add(account)
        session.commit()

    return VerifyResponse(is_authorized=authorized, needs_password=needs_password)


@router.post(
    "/{account_id}/logout",
    response_model=TelegramAccountRead,
)
async def logout(
    account_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> TelegramAccountRead:
    """Revoke the Telethon session and clear the stored ``.session`` file."""
    account = session.get(TelegramAccount, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    _ensure_owner(account, current_user.id, "log out of")

    await tg_auth.cancel_pending(account_id)
    if account.api_id is not None and account.api_hash is not None:
        try:
            await tg_auth.logout(
                session_path=account.session_path,
                api_id=account.api_id,
                api_hash=account.api_hash,
            )
        except tg_auth.TelegramAuthError as err:
            raise HTTPException(status_code=err.status_code, detail=str(err)) from err

    account.is_authorized = False
    account.updated_at = datetime.now(tz=UTC)
    session.add(account)
    session.commit()
    session.refresh(account)
    return _to_read(account)
