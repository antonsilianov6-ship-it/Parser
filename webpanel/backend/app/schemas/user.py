"""User request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=256)


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=8, max_length=256)
    is_active: bool | None = None


class UserRead(BaseModel):
    id: int
    username: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
