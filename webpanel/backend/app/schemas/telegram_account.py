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
    api_id: int | None
    has_api_hash: bool = False
    is_shared: bool
    is_authorized: bool
    created_at: datetime
    updated_at: datetime
    last_used_at: datetime | None


class SendCodeRequest(BaseModel):
    api_id: int = Field(ge=1, description="Telegram application API_ID")
    api_hash: str = Field(min_length=8, max_length=64, description="Telegram application API_HASH")
    phone: str = Field(min_length=5, max_length=32, description="Phone in international format")


class SendCodeResponse(BaseModel):
    pending: bool = True
    expires_in: int = Field(description="Seconds until the code expires")


class VerifyRequest(BaseModel):
    code: str | None = Field(default=None, min_length=3, max_length=16)
    password: str | None = Field(default=None, max_length=256)


class VerifyResponse(BaseModel):
    is_authorized: bool
    needs_password: bool = False
