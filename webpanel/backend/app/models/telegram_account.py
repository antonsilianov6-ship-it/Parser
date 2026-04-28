"""TelegramAccount model — one Telethon session belonging to a panel user."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class TelegramAccount(SQLModel, table=True):
    """A Telegram account authorised from the panel.

    The actual Telethon ``.session`` file lives on disk at :attr:`session_path`; this row
    only stores metadata so the panel can list, rename or share accounts.

    ``is_shared`` is a simple global flag: when true, any active panel user can run jobs
    using this account. When false, only the owner can use it.
    """

    __tablename__ = "telegram_accounts"

    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="users.id", index=True)

    label: str = Field(
        min_length=1,
        max_length=64,
        description="Human-friendly name shown in the UI (e.g. 'main', 'scraper-2').",
    )
    phone: str | None = Field(
        default=None,
        max_length=32,
        description="Phone number used to log in; nullable until authorisation completes.",
    )
    session_path: str = Field(
        max_length=512,
        description="Absolute or repo-relative path to the Telethon .session file.",
    )

    is_shared: bool = Field(
        default=False,
        description="When true, all panel users may select this account when launching jobs.",
    )
    is_authorized: bool = Field(
        default=False,
        description="Set to true once Telethon sign-in has succeeded (set by a later PR).",
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    last_used_at: datetime | None = Field(default=None)
