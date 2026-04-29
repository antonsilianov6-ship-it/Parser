"""Read-only access to each user's parser SQLite database.

Each panel user has an isolated ``parser.db`` under their per-user directory
(see :mod:`app.services.parser_files`). The web panel never writes to these
DBs — that's the parser's job. We just open the file in read-only mode
(``mode=ro``) per request, which is safe even if the parser is mid-write
because SQLite uses WAL by default in the parser.

Schema is documented in ``src/database/models.py``: at minimum we rely on
``messages(channel, message_id, text, date, author, views, forwards, replies,
comments, media_type, source_type, topic_title)``.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.services import parser_files


def db_path(user_id: int) -> Path:
    return parser_files.parser_db_path(user_id)


def db_exists(user_id: int) -> bool:
    return db_path(user_id).exists()


@contextmanager
def _connect(user_id: int):
    path = db_path(user_id)
    if not path.exists():
        raise FileNotFoundError(
            f"Parser database not found at {path}. Run a parse job first."
        )
    uri = f"file:{path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def list_messages(
    user_id: int,
    *,
    limit: int = 50,
    offset: int = 0,
    channel: str | None = None,
    query: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Return a page of messages and the total row count for the filter."""
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    where_parts: list[str] = []
    params: list[Any] = []
    if channel:
        where_parts.append("channel = ?")
        params.append(channel)
    if query:
        where_parts.append("text LIKE ?")
        params.append(f"%{query}%")
    if date_from:
        where_parts.append("date >= ?")
        params.append(date_from)
    if date_to:
        where_parts.append("date <= ?")
        params.append(date_to)

    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    with _connect(user_id) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM messages {where_sql}", params
        ).fetchone()["c"]
        rows = conn.execute(
            f"""
            SELECT id, channel, message_id, text, date, author, views, forwards,
                   replies, comments, media_type, source_type, topic_title
            FROM messages
            {where_sql}
            ORDER BY date DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
    items = [dict(row) for row in rows]
    return items, int(total)


def list_channels_in_db(user_id: int) -> list[dict[str, Any]]:
    """Return distinct channels that have at least one message stored."""
    with _connect(user_id) as conn:
        rows = conn.execute(
            """
            SELECT channel,
                   COUNT(*) AS messages,
                   MAX(date) AS latest
            FROM messages
            GROUP BY channel
            ORDER BY messages DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def overview_stats(user_id: int, top: int = 10) -> dict[str, Any]:
    """High-level counters used on the dashboard."""
    top = max(1, min(top, 50))
    with _connect(user_id) as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM messages").fetchone()["c"]
        channels_count = conn.execute(
            "SELECT COUNT(DISTINCT channel) AS c FROM messages"
        ).fetchone()["c"]
        latest_row = conn.execute(
            "SELECT MAX(date) AS d, MIN(date) AS m FROM messages"
        ).fetchone()
        top_rows = conn.execute(
            """
            SELECT channel, COUNT(*) AS messages
            FROM messages
            GROUP BY channel
            ORDER BY messages DESC
            LIMIT ?
            """,
            (top,),
        ).fetchall()
    return {
        "total_messages": int(total or 0),
        "channels_count": int(channels_count or 0),
        "latest_message_at": latest_row["d"] if latest_row else None,
        "earliest_message_at": latest_row["m"] if latest_row else None,
        "top_channels": [dict(r) for r in top_rows],
    }
