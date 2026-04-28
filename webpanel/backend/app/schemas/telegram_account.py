"""TelegramAccount request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TelegramAccountCreate(BaseModel):
    label: str = Field(min_length=1, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    is_shared: bool = False


class TelegramAccountUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=64)
    is_shared: bool | None = None


class TelegramAccountRead(BaseModel):
    id: int
    owner_id: int
    label: str
    phone: str | None
    session_path: str
    is_shared: bool
    is_authorized: bool
    created_at: datetime
    updated_at: datetime
    last_used_at: datetime | None
