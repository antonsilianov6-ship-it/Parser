"""Tests for the parser-config CRUD router."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services import parser_files
from tests.conftest import auth_header, bootstrap_login


@pytest.fixture
def parser_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect parser_files at a temp directory and seed sane fixtures."""
    monkeypatch.setattr(parser_files, "project_root", lambda: tmp_path)
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config" / "prompts.json").write_text(
        json.dumps(
            {
                "prompts": {"negative": {"template": "neg", "variables": []}},
                "defaults": {"timeout": 120},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "channels.txt").write_text(
        "https://t.me/foo\nhttps://t.me/bar\n", encoding="utf-8"
    )
    (tmp_path / "config.json").write_text(
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
    return tmp_path


def _login(client: TestClient) -> str:
    return bootstrap_login(client)


def test_config_get_masks_secrets(client: TestClient, parser_dir: Path) -> None:
    token = _login(client)
    response = client.get("/api/parser/config", headers=auth_header(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["TELEGRAM"]["API_ID"] == 12345
    assert body["TELEGRAM"]["API_HASH"] == parser_files.SECRET_SENTINEL
    assert body["NOTEBOOKLM"]["password"] == parser_files.SECRET_SENTINEL
    assert body["NOTEBOOKLM"]["email"] == "x@y"


def test_config_put_preserves_masked_secret(
    client: TestClient, parser_dir: Path
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

    raw = json.loads((parser_dir / "config.json").read_text(encoding="utf-8"))
    assert raw["TELEGRAM"]["API_HASH"] == "deadbeef"  # untouched on disk
    assert raw["NOTEBOOKLM"]["password"] == "supersecret"
    assert raw["PARSER"]["DAYS_FOR_EXPORT"] == 7


def test_config_put_can_replace_secret_with_real_value(
    client: TestClient, parser_dir: Path
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
    raw = json.loads((parser_dir / "config.json").read_text(encoding="utf-8"))
    assert raw["TELEGRAM"]["API_HASH"] == "newhash123"


def test_config_rejects_non_object(client: TestClient, parser_dir: Path) -> None:
    token = _login(client)
    response = client.put(
        "/api/parser/config",
        json={"config": {"TELEGRAM": "not-an-object"}},
        headers=auth_header(token),
    )
    assert response.status_code == 400


def test_prompts_get_and_put(client: TestClient, parser_dir: Path) -> None:
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
    saved = json.loads((parser_dir / "config" / "prompts.json").read_text(encoding="utf-8"))
    assert "positive" in saved["prompts"]


def test_prompts_put_rejects_missing_prompts_key(
    client: TestClient, parser_dir: Path
) -> None:
    token = _login(client)
    response = client.put(
        "/api/parser/prompts",
        json={"prompts": {"defaults": {}}},
        headers=auth_header(token),
    )
    assert response.status_code == 400


def test_channels_list(client: TestClient, parser_dir: Path) -> None:
    token = _login(client)
    response = client.get("/api/parser/channels", headers=auth_header(token))
    assert response.status_code == 200
    assert response.json() == ["https://t.me/foo", "https://t.me/bar"]


def test_channels_add_dedup_and_persist(
    client: TestClient, parser_dir: Path
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


def test_channels_delete(client: TestClient, parser_dir: Path) -> None:
    token = _login(client)
    response = client.delete(
        "/api/parser/channels",
        params={"url": "https://t.me/foo"},
        headers=auth_header(token),
    )
    assert response.status_code == 200
    assert "https://t.me/foo" not in response.json()


def test_channels_replace_full(client: TestClient, parser_dir: Path) -> None:
    token = _login(client)
    response = client.put(
        "/api/parser/channels",
        json={"channels": ["https://t.me/x", "  ", "https://t.me/x", "https://t.me/y"]},
        headers=auth_header(token),
    )
    assert response.status_code == 200
    assert response.json() == ["https://t.me/x", "https://t.me/y"]
    written = (parser_dir / "channels.txt").read_text(encoding="utf-8").splitlines()
    assert written == ["https://t.me/x", "https://t.me/y"]


def test_unauthorized_requests_rejected(client: TestClient, parser_dir: Path) -> None:
    response = client.get("/api/parser/config")
    assert response.status_code == 401
