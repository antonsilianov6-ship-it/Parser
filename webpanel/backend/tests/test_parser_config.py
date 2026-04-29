"""Tests for the parser-config CRUD router (per-user file isolation)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services import parser_files
from tests.conftest import auth_header, bootstrap_login


@pytest.fixture
def admin_dir(client: TestClient) -> Path:
    """Bootstrap the admin and pre-seed their per-user dir with sane fixtures.

    Uses the ``client`` fixture to trigger ``init_db`` and ``bootstrap`` so
    the user_dir for id=1 is created, then writes deterministic files into
    ``users/1/`` so each test has a known starting point.
    """
    bootstrap_login(client)
    udir = parser_files.user_dir(1)

    udir.mkdir(parents=True, exist_ok=True)
    (udir / "prompts.json").write_text(
        json.dumps(
            {
                "prompts": {"negative": {"template": "neg", "variables": []}},
                "defaults": {"timeout": 120},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (udir / "channels.txt").write_text(
        "https://t.me/foo\nhttps://t.me/bar\n", encoding="utf-8"
    )
    (udir / "config.json").write_text(
        json.dumps(
            {
                "TELEGRAM": {"API_ID": 12345, "API_HASH": "deadbeef"},
                "PARSER": {"DAYS_FOR_EXPORT": 3},
                "NOTEBOOKLM": {"email": "x@y", "password": "supersecret"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return udir


def _login(client: TestClient) -> str:
    """Log in as the admin user that was already bootstrapped by ``admin_dir``."""
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "password123"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_config_get_masks_secrets(client: TestClient, admin_dir: Path) -> None:
    token = _login(client)
    response = client.get("/api/parser/config", headers=auth_header(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["TELEGRAM"]["API_ID"] == 12345
    assert body["TELEGRAM"]["API_HASH"] == parser_files.SECRET_SENTINEL
    assert body["NOTEBOOKLM"]["password"] == parser_files.SECRET_SENTINEL
    assert body["NOTEBOOKLM"]["email"] == "x@y"


def test_config_put_preserves_masked_secret(
    client: TestClient, admin_dir: Path
) -> None:
    token = _login(client)
    incoming = client.get("/api/parser/config", headers=auth_header(token)).json()
    incoming["PARSER"]["DAYS_FOR_EXPORT"] = 7  # change something innocuous
    # API_HASH stays as ***  → server must keep the previous value.
    response = client.put(
        "/api/parser/config",
        json={"config": incoming},
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text

    raw = json.loads((admin_dir / "config.json").read_text(encoding="utf-8"))
    assert raw["TELEGRAM"]["API_HASH"] == "deadbeef"  # untouched on disk
    assert raw["NOTEBOOKLM"]["password"] == "supersecret"
    assert raw["PARSER"]["DAYS_FOR_EXPORT"] == 7


def test_config_put_can_replace_secret_with_real_value(
    client: TestClient, admin_dir: Path
) -> None:
    token = _login(client)
    incoming = client.get("/api/parser/config", headers=auth_header(token)).json()
    incoming["TELEGRAM"]["API_HASH"] = "newhash123"
    response = client.put(
        "/api/parser/config",
        json={"config": incoming},
        headers=auth_header(token),
    )
    assert response.status_code == 200
    raw = json.loads((admin_dir / "config.json").read_text(encoding="utf-8"))
    assert raw["TELEGRAM"]["API_HASH"] == "newhash123"


def test_config_rejects_non_object(client: TestClient, admin_dir: Path) -> None:
    token = _login(client)
    response = client.put(
        "/api/parser/config",
        json={"config": {"TELEGRAM": "not-an-object"}},
        headers=auth_header(token),
    )
    assert response.status_code == 400


def test_prompts_get_and_put(client: TestClient, admin_dir: Path) -> None:
    token = _login(client)
    body = client.get("/api/parser/prompts", headers=auth_header(token)).json()
    assert "prompts" in body and "negative" in body["prompts"]

    body["prompts"]["positive"] = {"template": "pos", "variables": []}
    response = client.put(
        "/api/parser/prompts",
        json={"prompts": body},
        headers=auth_header(token),
    )
    assert response.status_code == 200
    saved = json.loads((admin_dir / "prompts.json").read_text(encoding="utf-8"))
    assert "positive" in saved["prompts"]


def test_prompts_put_rejects_missing_prompts_key(
    client: TestClient, admin_dir: Path
) -> None:
    token = _login(client)
    response = client.put(
        "/api/parser/prompts",
        json={"prompts": {"defaults": {}}},
        headers=auth_header(token),
    )
    assert response.status_code == 400


def test_channels_list(client: TestClient, admin_dir: Path) -> None:
    token = _login(client)
    response = client.get("/api/parser/channels", headers=auth_header(token))
    assert response.status_code == 200
    assert response.json() == ["https://t.me/foo", "https://t.me/bar"]


def test_channels_add_dedup_and_persist(
    client: TestClient, admin_dir: Path
) -> None:
    token = _login(client)
    response = client.post(
        "/api/parser/channels",
        json={"url": "https://t.me/baz"},
        headers=auth_header(token),
    )
    assert response.status_code == 201
    assert response.json()[-1] == "https://t.me/baz"

    # Adding the same URL again is a no-op.
    again = client.post(
        "/api/parser/channels",
        json={"url": "https://t.me/baz"},
        headers=auth_header(token),
    )
    assert again.status_code == 201
    assert again.json().count("https://t.me/baz") == 1


def test_channels_delete(client: TestClient, admin_dir: Path) -> None:
    token = _login(client)
    response = client.delete(
        "/api/parser/channels",
        params={"url": "https://t.me/foo"},
        headers=auth_header(token),
    )
    assert response.status_code == 200
    assert "https://t.me/foo" not in response.json()


def test_channels_replace_full(client: TestClient, admin_dir: Path) -> None:
    token = _login(client)
    response = client.put(
        "/api/parser/channels",
        json={"channels": ["https://t.me/x", "  ", "https://t.me/x", "https://t.me/y"]},
        headers=auth_header(token),
    )
    assert response.status_code == 200
    assert response.json() == ["https://t.me/x", "https://t.me/y"]
    written = (admin_dir / "channels.txt").read_text(encoding="utf-8").splitlines()
    assert written == ["https://t.me/x", "https://t.me/y"]


def test_unauthorized_requests_rejected(client: TestClient) -> None:
    response = client.get("/api/parser/config")
    assert response.status_code == 401


def test_two_users_have_isolated_configs(client: TestClient) -> None:
    """Two panel users must never see each other's parser config files."""
    admin_token = bootstrap_login(client, username="admin", password="password123")
    create = client.post(
        "/api/users",
        json={"username": "second", "password": "password456"},
        headers=auth_header(admin_token),
    )
    assert create.status_code == 201, create.text

    # Admin writes a unique channels.txt + config.
    client.put(
        "/api/parser/channels",
        json={"channels": ["https://t.me/admin-only"]},
        headers=auth_header(admin_token),
    )
    client.put(
        "/api/parser/config",
        json={"config": {"PARSER": {"DAYS_FOR_EXPORT": 99}}},
        headers=auth_header(admin_token),
    )

    second_login = client.post(
        "/api/auth/login",
        json={"username": "second", "password": "password456"},
    )
    assert second_login.status_code == 200, second_login.text
    second_token = second_login.json()["access_token"]

    # Second user starts with an empty channel list, not admin's.
    second_channels = client.get(
        "/api/parser/channels", headers=auth_header(second_token)
    )
    assert second_channels.status_code == 200
    assert "https://t.me/admin-only" not in second_channels.json()

    # And admin's PARSER.DAYS_FOR_EXPORT does not leak across.
    second_cfg = client.get("/api/parser/config", headers=auth_header(second_token))
    assert second_cfg.status_code == 200
    assert second_cfg.json().get("PARSER", {}).get("DAYS_FOR_EXPORT") != 99

    # Files on disk live in different directories.
    admin_path = parser_files.config_json_path(1)
    second_path = parser_files.config_json_path(2)
    assert admin_path != second_path
    assert admin_path.exists()
    assert second_path.exists()
