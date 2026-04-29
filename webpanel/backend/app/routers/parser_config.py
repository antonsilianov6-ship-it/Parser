"""CRUD endpoints for parser-side files: config.json, prompts.json, channels.txt.

Files are scoped per panel user — every endpoint resolves paths inside the
caller's own ``users/<uid>/`` directory so two panel users have completely
independent parser configurations.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.deps import CurrentUser
from app.services import parser_files

router = APIRouter(prefix="/api/parser", tags=["parser-config"])


class ConfigPayload(BaseModel):
    config: dict[str, Any] = Field(
        ...,
        description="Whole config.json contents. Use *** to keep an existing secret.",
    )


class PromptsPayload(BaseModel):
    prompts: dict[str, Any] = Field(..., description="Whole prompts.json contents.")


class ChannelAddPayload(BaseModel):
    url: str = Field(..., min_length=1, max_length=512)


class ChannelsReplacePayload(BaseModel):
    channels: list[str] = Field(..., description="Full replacement list of channel URLs.")


@router.get("/config")
def get_config(current_user: CurrentUser) -> dict[str, Any]:
    """Return masked config.json contents for the calling user."""
    try:
        return parser_files.read_config(current_user.id)
    except (OSError, ValueError) as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(err),
        ) from err


@router.put("/config")
def put_config(payload: ConfigPayload, current_user: CurrentUser) -> dict[str, Any]:
    try:
        return parser_files.write_config(current_user.id, payload.config)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err
    except OSError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(err),
        ) from err


@router.get("/prompts")
def get_prompts(current_user: CurrentUser) -> dict[str, Any]:
    try:
        return parser_files.read_prompts(current_user.id)
    except (OSError, ValueError) as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(err),
        ) from err


@router.put("/prompts")
def put_prompts(payload: PromptsPayload, current_user: CurrentUser) -> dict[str, Any]:
    try:
        return parser_files.write_prompts(current_user.id, payload.prompts)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err
    except OSError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(err),
        ) from err


@router.get("/channels", response_model=list[str])
def get_channels(current_user: CurrentUser) -> list[str]:
    return parser_files.read_channels(current_user.id)


@router.put("/channels", response_model=list[str])
def replace_channels(
    payload: ChannelsReplacePayload, current_user: CurrentUser
) -> list[str]:
    try:
        return parser_files.write_channels(current_user.id, payload.channels)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err


@router.post(
    "/channels",
    response_model=list[str],
    status_code=status.HTTP_201_CREATED,
)
def add_channel(payload: ChannelAddPayload, current_user: CurrentUser) -> list[str]:
    try:
        return parser_files.add_channel(current_user.id, payload.url)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err


@router.delete("/channels", response_model=list[str])
def delete_channel(url: str, current_user: CurrentUser) -> list[str]:
    """Remove ``url`` from the user's channels.txt (no-op if absent)."""
    return parser_files.remove_channel(current_user.id, url)
