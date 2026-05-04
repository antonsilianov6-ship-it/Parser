"""Auto-rotation of Telegram sessions on transient parse failures.

When a parse Job's subprocess exits with a non-zero code we look at the
last bytes of its log file and try to classify the failure into one of:

- ``floodwait`` — Telethon raised ``FloodWaitError`` with an explicit
  wait length. Short waits (< ``MAX_FLOODWAIT_SHORT_SECONDS``) retry
  the same slot after sleeping; longer ones are treated as
  ``floodwait_long`` and trigger a slot swap.
- ``session_revoked`` — Telethon raised ``SessionRevokedError`` /
  ``AuthKeyUnregisteredError`` / ``UserDeactivatedError``: the slot
  is no longer usable, swap to the next authorised slot.
- ``unknown`` — anything else, no automatic retry.

Slot swap rule: pick the next authorised :class:`TelegramAccount`
visible to the job owner (own slot or shared) by ascending id, skipping
the slot that just failed. If no other authorised slot is available the
runner gives up and marks the job failed.

The scanner is deliberately conservative: it only matches well-known
Telethon error class names + a numeric duration when applicable. False
positives just mean "no auto-retry", which is safe.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session, select

from app.models.telegram_account import TelegramAccount

logger = logging.getLogger(__name__)


# Configurable, but rarely needed at runtime.
MAX_RETRIES = 3
MAX_FLOODWAIT_SHORT_SECONDS = 60
LOG_TAIL_BYTES = 16_384


@dataclass(frozen=True)
class FailureClass:
    kind: str  # "floodwait_short" | "floodwait_long" | "session_revoked" | "unknown"
    floodwait_seconds: int = 0


# Telethon prints e.g.
#   "telethon.errors.rpcerrorlist.FloodWaitError: A wait of 42 seconds is required"
# but we also accept the bare exception name without the module prefix.
_FLOODWAIT_RE = re.compile(
    r"FloodWaitError[^\n]*?(?:wait of\s+|seconds=|for\s+)?(\d+)\s*seconds?",
    re.IGNORECASE,
)
_REVOKED_TOKENS = (
    "SessionRevokedError",
    "AuthKeyUnregisteredError",
    "AuthKeyDuplicatedError",
    "UserDeactivatedError",
    "SessionPasswordNeededError",
)


def classify_failure(log_path: Path) -> FailureClass:
    """Inspect the tail of ``log_path`` and classify the failure."""
    try:
        with log_path.open("rb") as fh:
            fh.seek(0, 2)  # SEEK_END
            size = fh.tell()
            fh.seek(max(0, size - LOG_TAIL_BYTES))
            tail = fh.read().decode("utf-8", errors="replace")
    except FileNotFoundError:
        return FailureClass(kind="unknown")

    return classify_text(tail)


def classify_text(text: str) -> FailureClass:
    """Pure-text variant of :func:`classify_failure` — handy for unit tests."""
    flood_match = _FLOODWAIT_RE.search(text)
    if flood_match:
        seconds = int(flood_match.group(1))
        if seconds <= MAX_FLOODWAIT_SHORT_SECONDS:
            return FailureClass(kind="floodwait_short", floodwait_seconds=seconds)
        return FailureClass(kind="floodwait_long", floodwait_seconds=seconds)

    for token in _REVOKED_TOKENS:
        if token in text:
            return FailureClass(kind="session_revoked")

    return FailureClass(kind="unknown")


def pick_next_slot(
    session: Session,
    *,
    owner_id: int,
    current_account_id: int,
) -> TelegramAccount | None:
    """Return the next authorised TG slot the owner can use, or None.

    Visibility rule mirrors ``_account_visible_to`` in the jobs router:
    a user can use slots they own plus any slot marked ``is_shared``.
    Selection is deterministic and **wraps past the current slot**: with
    slots ``[1, 2, 3]`` starting on slot 2 we try 3 first, then 1, then
    give up — never bouncing back to slot 2 itself. This matters for
    ``session_revoked`` failures where the runner cumulatively retries
    different slots and we don't want to ping-pong between two of them
    while a third never gets tried.
    """
    statement = (
        select(TelegramAccount)
        .where(TelegramAccount.is_authorized.is_(True))  # type: ignore[attr-defined]
        .where(TelegramAccount.id != current_account_id)
        .order_by(TelegramAccount.id)  # type: ignore[arg-type]
    )
    candidates = [
        c
        for c in session.exec(statement)
        if c.id is not None and (c.owner_id == owner_id or c.is_shared)
    ]
    # Slots with id > current first (the "next" wrap segment), then
    # slots with smaller id (the "wrap-around" segment).
    after = [c for c in candidates if c.id > current_account_id]  # type: ignore[operator]
    before = [c for c in candidates if c.id < current_account_id]  # type: ignore[operator]
    ordered = after + before
    return ordered[0] if ordered else None
