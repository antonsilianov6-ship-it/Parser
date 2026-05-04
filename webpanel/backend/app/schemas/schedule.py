"""Schedule request/response schemas."""

from __future__ import annotations

from datetime import datetime

from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel, Field, field_validator, model_validator


def _validate_cron(expression: str) -> str:
    """Round-trip through APScheduler so we error on bad expressions early."""
    try:
        CronTrigger.from_crontab(expression)
    except (ValueError, KeyError) as exc:
        raise ValueError(f"Невалидное cron-выражение: {exc}") from exc
    return expression


class ScheduleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    telegram_account_id: int = Field(ge=1)
    cron_expression: str = Field(min_length=1, max_length=64)
    channel: str | None = Field(default=None, max_length=256)
    export_to_docs: bool = False
    export_to_notebooklm: bool = False
    is_active: bool = True

    @field_validator("cron_expression")
    @classmethod
    def _validate_cron_expression(cls, value: str) -> str:
        return _validate_cron(value.strip())

    @model_validator(mode="after")
    def _at_least_one_export(self) -> ScheduleCreate:
        if not (self.export_to_docs or self.export_to_notebooklm):
            raise ValueError(
                "Для расписания нужно выбрать хотя бы один вариант "
                "выгрузки: Google Docs или NotebookLM"
            )
        return self


class ScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    telegram_account_id: int | None = Field(default=None, ge=1)
    cron_expression: str | None = Field(default=None, min_length=1, max_length=64)
    channel: str | None = Field(default=None, max_length=256)
    export_to_docs: bool | None = None
    export_to_notebooklm: bool | None = None
    is_active: bool | None = None

    @field_validator("cron_expression")
    @classmethod
    def _validate_cron_expression(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_cron(value.strip())


class ScheduleRead(BaseModel):
    id: int
    owner_id: int
    telegram_account_id: int
    name: str
    cron_expression: str
    channel: str | None
    export_to_docs: bool
    export_to_notebooklm: bool
    is_active: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime
