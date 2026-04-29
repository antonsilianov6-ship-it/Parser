"""Job request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.job import JobMode, JobStatus


class JobCreate(BaseModel):
    telegram_account_id: int = Field(ge=1)
    mode: JobMode = JobMode.parse
    channel: str | None = Field(default=None, max_length=256)
    export_format: str | None = Field(default=None, max_length=8)

    @model_validator(mode="after")
    def _validate_export_format(self) -> JobCreate:
        if self.mode == JobMode.export:
            if self.export_format is None:
                self.export_format = "csv"
            if self.export_format not in {"csv", "json", "xml"}:
                raise ValueError("export_format must be one of csv/json/xml")
        return self


class JobRead(BaseModel):
    id: int
    owner_id: int
    telegram_account_id: int
    mode: JobMode
    channel: str | None
    export_format: str | None
    status: JobStatus
    pid: int | None
    exit_code: int | None
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
