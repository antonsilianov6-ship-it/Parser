"""Tests for the per-user Google credentials / NotebookLM router."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.services import parser_files
from tests.conftest import auth_header, bootstrap_login


def _service_account_json(email: str = "sa@example.iam.gserviceaccount.com") -> dict:
    return {
        "type": "service_account",
        "client_email": email,
        "private_key": "PRIV",
        "project_id": "proj",
    }


def _storage_state_json() -> dict:
    return {
        "cookies": [{"name": "session", "value": "abc", "domain": ".google.com"}],
        "origins": [],
    }


def test_status_default_empty(client: TestClient) -> None:
    token = bootstrap_login(client)
    response = client.get("/api/google/status", headers=auth_header(token))
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "has_credentials": False,
        "credentials_email": None,
        "has_notebooklm_storage": False,
        "google_doc_id": None,
        "google_drive_folder_id": None,
    }


def test_upload_credentials_validates_payload(client: TestClient) -> None:
    token = bootstrap_login(client)
    # Empty file → 400
    response = client.put(
        "/api/google/credentials",
        files={"file": ("creds.json", b"", "application/json")},
        headers=auth_header(token),
    )
    assert response.status_code == 400

    # Wrong type field → 400
    response = client.put(
        "/api/google/credentials",
        files={
            "file": (
                "creds.json",
                json.dumps({"type": "user", "client_email": "x", "private_key": "p"}).encode(),
                "application/json",
            )
        },
        headers=auth_header(token),
    )
    assert response.status_code == 400

    # Valid payload → 200, status flips to has_credentials
    payload = _service_account_json()
    response = client.put(
        "/api/google/credentials",
        files={"file": ("creds.json", json.dumps(payload).encode(), "application/json")},
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["has_credentials"] is True
    assert body["credentials_email"] == payload["client_email"]


def test_settings_normalises_urls_to_ids(client: TestClient) -> None:
    token = bootstrap_login(client)
    response = client.put(
        "/api/google/settings",
        json={
            "google_doc_id": "https://docs.google.com/document/d/DOC123/edit?usp=sharing",
            "google_drive_folder_id": (
                "https://drive.google.com/drive/folders/FOLDER456?usp=drive_link"
            ),
        },
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["google_doc_id"] == "DOC123"
    assert body["google_drive_folder_id"] == "FOLDER456"


def test_notebooklm_upload_and_delete(client: TestClient) -> None:
    token = bootstrap_login(client)
    payload = _storage_state_json()
    response = client.put(
        "/api/google/notebooklm",
        files={
            "file": ("storage_state.json", json.dumps(payload).encode(), "application/json")
        },
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["has_notebooklm_storage"] is True

    # File on disk should have the right shape.
    disk = parser_files.notebooklm_storage_path(1)
    assert disk.exists()
    assert json.loads(disk.read_text()) == payload

    response = client.delete("/api/google/notebooklm", headers=auth_header(token))
    assert response.status_code == 200
    assert response.json()["has_notebooklm_storage"] is False
    assert not disk.exists()


def test_credentials_isolation_between_users(client: TestClient) -> None:
    """Bob must not see / overwrite Alice's uploaded credentials."""
    admin_token = bootstrap_login(client)
    client.put(
        "/api/google/credentials",
        files={
            "file": (
                "creds.json",
                json.dumps(_service_account_json("alice@example.iam")).encode(),
                "application/json",
            )
        },
        headers=auth_header(admin_token),
    ).raise_for_status()

    # Create bob via admin endpoint
    client.post(
        "/api/users",
        json={"username": "bob", "password": "password123"},
        headers=auth_header(admin_token),
    ).raise_for_status()
    bob_token = client.post(
        "/api/auth/login",
        json={"username": "bob", "password": "password123"},
    ).json()["access_token"]

    bob_status = client.get("/api/google/status", headers=auth_header(bob_token)).json()
    assert bob_status["has_credentials"] is False
    assert bob_status["credentials_email"] is None

    # Alice's file still intact after bob deletes "his" creds (no-op).
    client.delete("/api/google/credentials", headers=auth_header(bob_token))
    alice_status = client.get(
        "/api/google/status", headers=auth_header(admin_token)
    ).json()
    assert alice_status["has_credentials"] is True
    assert alice_status["credentials_email"] == "alice@example.iam"


def test_test_endpoint_requires_creds_and_doc(client: TestClient) -> None:
    token = bootstrap_login(client)
    # No creds → 400
    response = client.post("/api/google/test", headers=auth_header(token))
    assert response.status_code == 400
    assert "service account" in response.json()["detail"].lower()

    # Creds present, no doc id → 400
    client.put(
        "/api/google/credentials",
        files={
            "file": (
                "creds.json",
                json.dumps(_service_account_json()).encode(),
                "application/json",
            )
        },
        headers=auth_header(token),
    ).raise_for_status()
    response = client.post("/api/google/test", headers=auth_header(token))
    assert response.status_code == 400
    assert "doc id" in response.json()["detail"].lower()
