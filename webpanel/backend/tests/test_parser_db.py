"""Tests for the read-only parser-DB browser."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services import parser_db as parser_db_svc
from tests.conftest import auth_header, bootstrap_login


@pytest.fixture
def seeded_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a tiny parser SQLite DB with two channels of messages."""
    monkeypatch.setattr(parser_db_svc, "project_root", lambda: tmp_path)
    db_dir = tmp_path / "data"
    db_dir.mkdir()
    db_file = db_dir / "parser.db"
    conn = sqlite3.connect(db_file)
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
    rows = [
        ("@foo", 1, "hello world", "2025-01-01 10:00:00", "alice", 5, 0, 1),
        ("@foo", 2, "second message", "2025-01-02 10:00:00", "alice", 6, 0, 0),
        ("@bar", 1, "another channel", "2025-01-03 10:00:00", "bob", 12, 1, 2),
        ("@bar", 2, "search me please", "2025-01-04 10:00:00", "bob", 4, 0, 0),
    ]
    for ch, mid, text, date, author, views, fwd, rep in rows:
        conn.execute(
            "INSERT INTO messages (channel, message_id, text, date, author, views,"
            " forwards, replies) VALUES (?,?,?,?,?,?,?,?)",
            (ch, mid, text, date, author, views, fwd, rep),
        )
    conn.commit()
    conn.close()
    return db_file


def test_messages_list_paginates_and_orders(
    client: TestClient, seeded_db: Path
) -> None:
    token = bootstrap_login(client)
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
    token = bootstrap_login(client)
    body = client.get(
        "/api/parser/messages?channel=@foo&query=second",
        headers=auth_header(token),
    ).json()
    assert body["total"] == 1
    assert body["items"][0]["channel"] == "@foo"


def test_messages_date_range(client: TestClient, seeded_db: Path) -> None:
    token = bootstrap_login(client)
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
    token = bootstrap_login(client)
    body = client.get("/api/parser/messages/channels", headers=auth_header(token)).json()
    assert {row["channel"] for row in body} == {"@foo", "@bar"}
    assert body[0]["messages"] == 2  # both have 2 messages, order is by count desc


def test_stats_reports_totals(client: TestClient, seeded_db: Path) -> None:
    token = bootstrap_login(client)
    body = client.get("/api/parser/stats", headers=auth_header(token)).json()
    assert body["db_present"] is True
    assert body["total_messages"] == 4
    assert body["channels_count"] == 2
    assert body["latest_message_at"] == "2025-01-04 10:00:00"
    assert {row["channel"] for row in body["top_channels"]} == {"@foo", "@bar"}


def test_stats_when_db_missing_returns_empty(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No DB at all → endpoint returns zeros instead of 404 so dashboard renders.
    monkeypatch.setattr(parser_db_svc, "project_root", lambda: tmp_path)
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


def test_messages_endpoint_when_db_missing_returns_404(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(parser_db_svc, "project_root", lambda: tmp_path)
    token = bootstrap_login(client)
    response = client.get("/api/parser/messages", headers=auth_header(token))
    assert response.status_code == 404


def test_unauthorized(client: TestClient, seeded_db: Path) -> None:
    response = client.get("/api/parser/messages")
    assert response.status_code == 401
