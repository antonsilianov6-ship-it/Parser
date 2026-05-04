"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db as app_db
from app.config import Settings, get_settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Provide isolated Settings backed by a temp SQLite file and a throwaway secret."""
    monkeypatch.setenv(
        "PANEL_JWT_SECRET",
        "test-secret-that-is-at-least-32-bytes-long-abc",
    )
    monkeypatch.setenv("PANEL_DB_PATH", str(tmp_path / "panel.db"))
    monkeypatch.setenv("PANEL_ALLOW_REGISTRATION", "false")
    monkeypatch.setenv("PANEL_CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("PANEL_ENABLE_SCHEDULER", "false")

    get_settings.cache_clear()
    app_db.reset_engine()
    yield get_settings()
    get_settings.cache_clear()
    app_db.reset_engine()


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """FastAPI test client bound to the isolated settings."""
    del settings
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def bootstrap_login(
    client: TestClient,
    username: str = "admin",
    password: str = "password123",
) -> str:
    """Bootstrap the first user, log in and return the access token."""
    response = client.post(
        "/api/users/bootstrap",
        json={"username": username, "password": password},
    )
    assert response.status_code == 201, response.text
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]
