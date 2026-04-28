"""In-memory state machine for the multi-step Telegram sign-in flow.

Each :class:`TelegramAccount` is authorised through three endpoints:

1. ``POST /send-code`` — stores API credentials on the row, creates a
   :class:`TelegramClient`, asks Telegram to send the SMS/app code and keeps the
   connected client (and the returned ``phone_code_hash``) in :data:`_pending`
   so ``verify`` can finish the sign-in on the same session.
2. ``POST /verify`` — with the code (and optionally a 2FA password) completes
   ``sign_in``. On success the client is disconnected — Telethon has already
   persisted the session file on disk — and the pending entry is dropped.
3. ``POST /logout`` — opens a short-lived client, calls ``log_out`` and removes
   the ``.session`` file so the next authorisation starts clean.

Pending entries expire after :data:`PENDING_TTL_SECONDS`; stale clients are
disconnected on the next call.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import (
    ApiIdInvalidError,
    FloodWaitError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberBannedError,
    PhoneNumberInvalidError,
    PhoneNumberUnoccupiedError,
    SessionPasswordNeededError,
)

logger = logging.getLogger(__name__)

PENDING_TTL_SECONDS = 600


class TelegramAuthError(Exception):
    """Raised for mapped, user-facing Telethon failures."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class PendingAuth:
    client: TelegramClient
    phone: str
    phone_code_hash: str
    expires_at: float
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_pending: dict[int, PendingAuth] = {}
_gc_lock = asyncio.Lock()


async def _disconnect_quiet(client: TelegramClient) -> None:
    try:
        result = client.disconnect()
        if asyncio.iscoroutine(result):
            await result
    except Exception:  # pragma: no cover — best-effort cleanup
        logger.debug("disconnect failed", exc_info=True)


async def _gc_expired() -> None:
    async with _gc_lock:
        now = time.monotonic()
        for account_id, pending in list(_pending.items()):
            if pending.expires_at < now:
                await _disconnect_quiet(pending.client)
                _pending.pop(account_id, None)


async def _drop_pending(account_id: int) -> None:
    pending = _pending.pop(account_id, None)
    if pending is not None:
        await _disconnect_quiet(pending.client)


async def send_code(
    account_id: int,
    *,
    session_path: str,
    api_id: int,
    api_hash: str,
    phone: str,
) -> int:
    """Ask Telegram to send the login code and cache the pending client."""
    await _gc_expired()
    await _drop_pending(account_id)

    Path(session_path).parent.mkdir(parents=True, exist_ok=True)
    client = TelegramClient(session_path, api_id, api_hash)
    try:
        await client.connect()
        sent = await client.send_code_request(phone)
    except ApiIdInvalidError as err:
        await _disconnect_quiet(client)
        raise TelegramAuthError("Неверные API_ID / API_HASH") from err
    except PhoneNumberInvalidError as err:
        await _disconnect_quiet(client)
        raise TelegramAuthError("Неверный формат номера телефона") from err
    except PhoneNumberBannedError as err:
        await _disconnect_quiet(client)
        raise TelegramAuthError("Этот номер заблокирован в Telegram") from err
    except FloodWaitError as err:
        await _disconnect_quiet(client)
        raise TelegramAuthError(
            f"Telegram временно ограничил авторизацию. Подождите {err.seconds} сек.",
            status_code=429,
        ) from err
    except Exception as err:
        await _disconnect_quiet(client)
        raise TelegramAuthError(f"Telethon: {err}", status_code=502) from err

    _pending[account_id] = PendingAuth(
        client=client,
        phone=phone,
        phone_code_hash=sent.phone_code_hash,
        expires_at=time.monotonic() + PENDING_TTL_SECONDS,
    )
    return PENDING_TTL_SECONDS


async def verify(
    account_id: int,
    *,
    code: str | None,
    password: str | None,
) -> tuple[bool, bool]:
    """Complete the sign-in. Returns ``(authorized, needs_password)``."""
    await _gc_expired()
    pending = _pending.get(account_id)
    if pending is None:
        raise TelegramAuthError(
            "Сессия авторизации не найдена или истекла. Повторите запрос кода.",
            status_code=409,
        )

    async with pending.lock:
        try:
            if password:
                await pending.client.sign_in(password=password)
            else:
                if not code:
                    raise TelegramAuthError("Введите код из Telegram")
                await pending.client.sign_in(
                    phone=pending.phone,
                    code=code,
                    phone_code_hash=pending.phone_code_hash,
                )
        except SessionPasswordNeededError:
            # Keep the pending session alive so the user can retry with password.
            return False, True
        except PhoneCodeInvalidError as err:
            raise TelegramAuthError("Неверный код подтверждения") from err
        except PhoneCodeExpiredError as err:
            await _drop_pending(account_id)
            raise TelegramAuthError(
                "Код истёк. Запросите новый.", status_code=410
            ) from err
        except PhoneNumberUnoccupiedError as err:
            await _drop_pending(account_id)
            raise TelegramAuthError(
                "У этого номера нет аккаунта Telegram"
            ) from err
        except FloodWaitError as err:
            raise TelegramAuthError(
                f"Flood wait: подождите {err.seconds} сек.", status_code=429
            ) from err
        except TelegramAuthError:
            raise
        except Exception as err:
            raise TelegramAuthError(f"Telethon: {err}", status_code=502) from err

        # Success — disconnect to flush session, then drop pending.
        await _disconnect_quiet(pending.client)
        _pending.pop(account_id, None)
        return True, False


async def logout(
    *,
    session_path: str,
    api_id: int,
    api_hash: str,
) -> None:
    """Revoke the session with Telegram and remove the local ``.session`` file."""
    Path(session_path).parent.mkdir(parents=True, exist_ok=True)
    client = TelegramClient(session_path, api_id, api_hash)
    try:
        await client.connect()
        if await client.is_user_authorized():
            await client.log_out()
    except Exception as err:
        logger.warning("log_out failed: %s", err)
    finally:
        await _disconnect_quiet(client)

    for suffix in ("", "-journal"):
        path = Path(session_path + suffix)
        if path.exists():
            try:
                path.unlink()
            except OSError:
                logger.debug("could not remove %s", path, exc_info=True)


async def cancel_pending(account_id: int) -> None:
    """Explicit cleanup of a dangling pending sign-in (used on DELETE)."""
    await _drop_pending(account_id)
