"""User model for the web panel."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """A single web panel account.

    The panel currently has exactly one role; ``is_active`` controls whether the account
    can authenticate. Multi-role support can be added later by introducing a ``role`` column.
    """

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, min_length=3, max_length=64)
    password_hash: str = Field(max_length=255)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    # Google integration (per-user). The actual credentials JSON files live on
    # disk under the user's data directory (see ``parser_files.py``); the DB
    # only stores the metadata that's safe to expose through the API.
    google_doc_id: str | None = Field(default=None, max_length=128)
    google_drive_folder_id: str | None = Field(default=None, max_length=128)
