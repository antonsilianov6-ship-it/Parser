"""Schedule model — a cron-style trigger that auto-creates parse jobs."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class Schedule(SQLModel, table=True):
    """A cron expression that the panel evaluates to spawn parse jobs.

    A schedule belongs to a single user (its ``owner_id``) and points
    at a single Telegram account slot. Each tick of the schedule
    creates a fresh ``Job`` row with the same flags as if the user
    had clicked "Запустить парсинг" manually.
    """

    __tablename__ = "schedules"

    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="users.id", index=True)
    telegram_account_id: int = Field(foreign_key="telegram_accounts.id", index=True)

    name: str = Field(max_length=128, description="Human-readable label.")

    # Five-field unix cron expression: ``min hour dom month dow``.
    # Validated against ``apscheduler.triggers.cron.CronTrigger.from_crontab``
    # before being stored.
    cron_expression: str = Field(max_length=64)

    # Optional ``--channel`` argument forwarded to the parser; ``None``
    # means "all channels in channels.txt".
    channel: str | None = Field(default=None, max_length=256)

    export_to_docs: bool = Field(default=False)
    export_to_notebooklm: bool = Field(default=False)

    is_active: bool = Field(default=True, index=True)

    last_run_at: datetime | None = Field(default=None)
    next_run_at: datetime | None = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
