"""Read-only browser for the parser's per-user SQLite database."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.deps import CurrentUser
from app.services import parser_db

router = APIRouter(prefix="/api/parser", tags=["parser-db"])


def _ensure_db_present(user_id: int) -> None:
    if not parser_db.db_exists(user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Parser DB not found for this user. Run a parse job first to "
                "populate users/<id>/parser.db."
            ),
        )


@router.get("/messages")
def list_messages(
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    channel: str | None = None,
    query: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    _ensure_db_present(current_user.id)
    items, total = parser_db.list_messages(
        current_user.id,
        limit=limit,
        offset=offset,
        channel=channel,
        query=query,
        date_from=date_from,
        date_to=date_to,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/messages/channels")
def list_channels(current_user: CurrentUser) -> list[dict[str, Any]]:
    _ensure_db_present(current_user.id)
    return parser_db.list_channels_in_db(current_user.id)


@router.get("/stats")
def get_stats(
    current_user: CurrentUser, top: int = Query(default=10, ge=1, le=50)
) -> dict[str, Any]:
    if not parser_db.db_exists(current_user.id):
        return {
            "total_messages": 0,
            "channels_count": 0,
            "latest_message_at": None,
            "earliest_message_at": None,
            "top_channels": [],
            "db_present": False,
        }
    payload = parser_db.overview_stats(current_user.id, top=top)
    payload["db_present"] = True
    return payload
