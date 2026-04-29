"""Tests for the per-user read-only parser-DB browser."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services import parser_files
from tests.conftest import auth_header, bootstrap_login


def _create_messages_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            text TEXT,
            date TIMESTAMP NOT NULL,
            author TEXT,
            views INTEGER DEFAULT 0,
            forwards INTEGER DEFAULT 0,
            replies INTEGER DEFAULT 0,
            comments TEXT DEFAULT '',
            media_type TEXT DEFAULT '',
            media_url TEXT DEFAULT '',
            source_type TEXT DEFAULT 'channel',
            topic_id INTEGER DEFAULT NULL,
            topic_title TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(channel, message_id)
        )
        """
    )


def _seed_messages(conn: sqlite3.Connection, rows: list[tuple]) -> None:
    for ch, mid, text, date, author, views, fwd, rep in rows:
        conn.execute(
            "INSERT INTO messages (channel, message_id, text, date, author, views,"
            " forwards, replies) VALUES (?,?,?,?,?,?,?,?)",
            (ch, mid, text, date, author, views, fwd, rep),
        )


@pytest.fixture
def seeded_db(client: TestClient) -> Path:
    """Build a tiny per-user parser SQLite DB for the bootstrapped admin (id=1)."""
    bootstrap_login(client)
    db_file = parser_files.parser_db_path(1)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_file)
    _create_messages_table(conn)
    _seed_messages(
        conn,
        [
            ("@foo", 1, "hello world", "2025-01-01 10:00:00", "alice", 5, 0, 1),
            ("@foo", 2, "second message", "2025-01-02 10:00:00", "alice", 6, 0, 0),
            ("@bar", 1, "another channel", "2025-01-03 10:00:00", "bob", 12, 1, 2),
            ("@bar", 2, "search me please", "2025-01-04 10:00:00", "bob", 4, 0, 0),
        ],
    )
    conn.commit()
    conn.close()
    return db_file


def _admin_token(client: TestClient) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "password123"},
    )
    return response.json()["access_token"]


def test_messages_list_paginates_and_orders(
    client: TestClient, seeded_db: Path
) -> None:
    token = _admin_token(client)
    body = client.get(
        "/api/parser/messages?limit=2",
        headers=auth_header(token),
    ).json()
    assert body["total"] == 4
    assert body["limit"] == 2
    assert len(body["items"]) == 2
    # Newest first.
    assert body["items"][0]["text"] == "search me please"
    assert body["items"][1]["text"] == "another channel"


def test_messages_filter_by_channel_and_query(
    client: TestClient, seeded_db: Path
) -> None:
    token = _admin_token(client)
    body = client.get(
        "/api/parser/messages?channel=@foo&query=second",
        headers=auth_header(token),
    ).json()
    assert body["total"] == 1
    assert body["items"][0]["channel"] == "@foo"


def test_messages_date_range(client: TestClient, seeded_db: Path) -> None:
    token = _admin_token(client)
    body = client.get(
        "/api/parser/messages?date_from=2025-01-03",
        headers=auth_header(token),
    ).json()
    assert body["total"] == 2
    body = client.get(
        "/api/parser/messages?date_to=2025-01-02 23:59:59",
        headers=auth_header(token),
    ).json()
    assert body["total"] == 2


def test_channels_in_db(client: TestClient, seeded_db: Path) -> None:
    token = _admin_token(client)
    body = client.get("/api/parser/messages/channels", headers=auth_header(token)).json()
    assert {row["channel"] for row in body} == {"@foo", "@bar"}
    assert body[0]["messages"] == 2  # both have 2 messages, order is by count desc


def test_stats_reports_totals(client: TestClient, seeded_db: Path) -> None:
    token = _admin_token(client)
    body = client.get("/api/parser/stats", headers=auth_header(token)).json()
    assert body["db_present"] is True
    assert body["total_messages"] == 4
    assert body["channels_count"] == 2
    assert body["latest_message_at"] == "2025-01-04 10:00:00"
    assert {row["channel"] for row in body["top_channels"]} == {"@foo", "@bar"}


def test_stats_when_db_missing_returns_empty(client: TestClient) -> None:
    # No per-user DB has been created → endpoint returns zeros instead of 404
    # so the dashboard still renders for fresh users.
    token = bootstrap_login(client)
    body = client.get("/api/parser/stats", headers=auth_header(token)).json()
    assert body == {
        "total_messages": 0,
        "channels_count": 0,
        "latest_message_at": None,
        "earliest_message_at": None,
        "top_channels": [],
        "db_present": False,
    }


def test_messages_endpoint_when_db_missing_returns_404(client: TestClient) -> None:
    token = bootstrap_login(client)
    response = client.get("/api/parser/messages", headers=auth_header(token))
    assert response.status_code == 404


def test_two_users_have_isolated_parser_dbs(client: TestClient) -> None:
    """A second user must not see the admin's parsed messages."""
    admin_token = bootstrap_login(client, username="admin", password="password123")
    create = client.post(
        "/api/users",
        json={"username": "second", "password": "password456"},
        headers=auth_header(admin_token),
    )
    assert create.status_code == 201, create.text

    # Seed only the admin's DB with one row.
    admin_db = parser_files.parser_db_path(1)
    admin_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(admin_db)
    _create_messages_table(conn)
    _seed_messages(
        conn,
        [("@admin-only", 1, "secret", "2025-01-01 10:00:00", "admin", 1, 0, 0)],
    )
    conn.commit()
    conn.close()

    second_token = client.post(
        "/api/auth/login",
        json={"username": "second", "password": "password456"},
    ).json()["access_token"]

    # Admin sees their row.
    admin_resp = client.get("/api/parser/stats", headers=auth_header(admin_token))
    assert admin_resp.json()["total_messages"] == 1

    # Second user has no DB at all → empty stats, not admin's data.
    second_resp = client.get("/api/parser/stats", headers=auth_header(second_token))
    body = second_resp.json()
    assert body["db_present"] is False
    assert body["total_messages"] == 0
    assert parser_files.parser_db_path(2) != parser_files.parser_db_path(1)
