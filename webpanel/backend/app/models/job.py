"""Job model — a single parser subprocess invocation tracked by the panel."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class JobMode(str, Enum):
    """Subset of ``main.py --mode`` values exposed via the panel."""

    parse = "parse"
    export = "export"
    stats = "stats"


class JobStatus(str, Enum):
    """Lifecycle states of a panel-launched parser subprocess."""

    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class Job(SQLModel, table=True):
    """A single parser run launched from the panel.

    The actual stdout/stderr lines stream into the on-disk file at
    :attr:`log_path`; the ``logs`` SSE endpoint tails that file.
    """

    __tablename__ = "jobs"

    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="users.id", index=True)
    telegram_account_id: int = Field(foreign_key="telegram_accounts.id", index=True)

    mode: JobMode = Field(default=JobMode.parse, description="Parser mode (parse/export/stats).")
    channel: str | None = Field(
        default=None,
        max_length=256,
        description="Optional --channel argument; when null all channels.txt entries run.",
    )
    export_format: str | None = Field(
        default=None,
        max_length=8,
        description="Optional --format for export mode (csv/json/xml).",
    )

    status: JobStatus = Field(default=JobStatus.pending)
    pid: int | None = Field(default=None)
    exit_code: int | None = Field(default=None)
    log_path: str = Field(max_length=512)

    # Post-parse export flags. At least one must be true for parse-mode jobs;
    # this is enforced by the API schema, not at the DB layer.
    export_to_docs: bool = Field(default=False)
    export_to_notebooklm: bool = Field(default=False)

    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    started_at: datetime | None = Field(default=None)
    ended_at: datetime | None = Field(default=None)
