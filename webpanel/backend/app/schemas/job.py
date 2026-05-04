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

    # For ``mode=parse`` jobs the panel requires the user to pick at least one
    # downstream destination, otherwise parsed messages would just sit in the
    # local SQLite and waste disk. The actual export is run as the final step
    # of the parser subprocess (see ``jobs_runner._build_env``).
    export_to_docs: bool = False
    export_to_notebooklm: bool = False

    @model_validator(mode="after")
    def _validate(self) -> JobCreate:
        if self.mode == JobMode.export:
            if self.export_format is None:
                self.export_format = "csv"
            if self.export_format not in {"csv", "json", "xml"}:
                raise ValueError("export_format must be one of csv/json/xml")
        if self.mode == JobMode.parse and not (
            self.export_to_docs or self.export_to_notebooklm
        ):
            raise ValueError(
                "Для parse-задачи нужно выбрать хотя бы один вариант "
                "выгрузки: Google Docs или NotebookLM"
            )
        return self


class JobRead(BaseModel):
    id: int
    owner_id: int
    telegram_account_id: int
    mode: JobMode
    channel: str | None
    export_format: str | None
    export_to_docs: bool
    export_to_notebooklm: bool
    status: JobStatus
    pid: int | None
    exit_code: int | None
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
