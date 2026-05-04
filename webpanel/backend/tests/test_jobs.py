"""Tests for the jobs router.

The actual ``main.py`` invocation is replaced by a mocked
:func:`app.services.jobs_runner.launch` so we can exercise the router without
spawning real Python processes.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import get_engine
from app.models.job import Job, JobStatus
from app.models.telegram_account import TelegramAccount
from app.models.user import User
from app.services import jobs_runner, parser_files
from tests.conftest import auth_header, bootstrap_login


def _seed_docs_creds(user_id: int, doc_id: str = "doc-stub-1") -> None:
    """Pre-populate per-user Google creds so parse-mode jobs can be created."""
    parser_files.write_google_credentials(
        user_id,
        {
            "type": "service_account",
            "client_email": "sa@example.iam.gserviceaccount.com",
            "private_key": "PRIV",
            "project_id": "proj",
        },
    )
    with Session(get_engine()) as db:
        user = db.get(User, user_id)
        assert user is not None
        user.google_doc_id = doc_id
        db.add(user)
        db.commit()


@pytest.fixture
def authorised_account(client: TestClient) -> tuple[str, dict]:
    """Bootstrap the admin and create an *authorised* TG slot directly in DB."""
    token = bootstrap_login(client)
    account_payload = client.post(
        "/api/telegram/accounts",
        json={"label": "main"},
        headers=auth_header(token),
    ).json()
    # Skip the real Telethon auth flow — flip the row to authorised + creds.
    with Session(get_engine()) as db:
        account = db.get(TelegramAccount, account_payload["id"])
        assert account is not None
        account.is_authorized = True
        account.api_id = 12345
        account.api_hash = "deadbeefdead"
        account.phone = "+79990001122"
        db.add(account)
        db.commit()
        db.refresh(account)
    return token, account_payload


@pytest.fixture
def stub_launch(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Replace jobs_runner.launch with a stub that just records the call."""
    launched: list[int] = []

    async def _fake_launch(job_id: int) -> None:
        launched.append(job_id)

    monkeypatch.setattr(jobs_runner, "launch", _fake_launch)
    return launched


def test_create_job_records_pending_state(
    client: TestClient,
    authorised_account: tuple[str, dict],
    stub_launch: list[int],
) -> None:
    token, account = authorised_account
    _seed_docs_creds(1)
    response = client.post(
        "/api/jobs",
        json={
            "telegram_account_id": account["id"],
            "mode": "parse",
            "channel": "@example",
            "export_to_docs": True,
        },
        headers=auth_header(token),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["channel"] == "@example"
    assert body["mode"] == "parse"
    assert body["export_to_docs"] is True
    assert body["export_to_notebooklm"] is False
    assert stub_launch == [body["id"]]


def test_create_parse_job_requires_at_least_one_export(
    client: TestClient,
    authorised_account: tuple[str, dict],
    stub_launch: list[int],
) -> None:
    """Parse jobs without any export target must be rejected by Pydantic."""
    token, account = authorised_account
    response = client.post(
        "/api/jobs",
        json={
            "telegram_account_id": account["id"],
            "mode": "parse",
            "channel": "@example",
        },
        headers=auth_header(token),
    )
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    msg = " ".join(item.get("msg", "") for item in detail).lower()
    assert "выгрузки" in msg or "google docs" in msg
    assert stub_launch == []


def test_create_parse_job_requires_uploaded_creds(
    client: TestClient,
    authorised_account: tuple[str, dict],
    stub_launch: list[int],
) -> None:
    """Even with the box ticked, parse rejects until creds are uploaded."""
    token, account = authorised_account
    response = client.post(
        "/api/jobs",
        json={
            "telegram_account_id": account["id"],
            "mode": "parse",
            "export_to_docs": True,
        },
        headers=auth_header(token),
    )
    assert response.status_code == 400, response.text
    assert "service account" in response.json()["detail"].lower()
    assert stub_launch == []


def test_create_job_rejects_unauthorised_slot(
    client: TestClient,
    stub_launch: list[int],
) -> None:
    token = bootstrap_login(client)
    account = client.post(
        "/api/telegram/accounts",
        json={"label": "main"},
        headers=auth_header(token),
    ).json()
    response = client.post(
        "/api/jobs",
        json={
            "telegram_account_id": account["id"],
            "mode": "parse",
            "export_to_docs": True,
        },
        headers=auth_header(token),
    )
    assert response.status_code == 400
    detail = response.json()["detail"].lower()
    assert "не авторизован" in detail or "not authorised" in detail
    assert stub_launch == []


def test_create_job_rejects_other_users_private_slot(
    client: TestClient,
    authorised_account: tuple[str, dict],
    stub_launch: list[int],
) -> None:
    admin_token, account = authorised_account
    client.post(
        "/api/users",
        json={"username": "bob", "password": "password123"},
        headers=auth_header(admin_token),
    )
    bob_token = client.post(
        "/api/auth/login",
        json={"username": "bob", "password": "password123"},
    ).json()["access_token"]

    response = client.post(
        "/api/jobs",
        json={
            "telegram_account_id": account["id"],
            "mode": "parse",
            "export_to_docs": True,
        },
        headers=auth_header(bob_token),
    )
    assert response.status_code == 403
    assert stub_launch == []


def test_list_jobs_filters_by_visibility(
    client: TestClient,
    authorised_account: tuple[str, dict],
    stub_launch: list[int],
) -> None:
    admin_token, account = authorised_account
    client.post(
        "/api/jobs",
        json={"telegram_account_id": account["id"], "mode": "stats"},
        headers=auth_header(admin_token),
    ).raise_for_status()

    # Bob should not see admin's private-slot job.
    client.post(
        "/api/users",
        json={"username": "bob", "password": "password123"},
        headers=auth_header(admin_token),
    )
    bob_token = client.post(
        "/api/auth/login",
        json={"username": "bob", "password": "password123"},
    ).json()["access_token"]

    bob_view = client.get("/api/jobs", headers=auth_header(bob_token)).json()
    assert bob_view == []

    admin_view = client.get("/api/jobs", headers=auth_header(admin_token)).json()
    assert len(admin_view) == 1
    assert admin_view[0]["mode"] == "stats"


def test_cancel_only_for_owner(
    client: TestClient,
    authorised_account: tuple[str, dict],
    stub_launch: list[int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token, account = authorised_account
    _seed_docs_creds(1)
    job = client.post(
        "/api/jobs",
        json={
            "telegram_account_id": account["id"],
            "mode": "parse",
            "export_to_docs": True,
        },
        headers=auth_header(token),
    ).json()

    cancel_calls: list[int] = []

    async def _fake_cancel(job_id: int) -> bool:
        cancel_calls.append(job_id)
        with Session(get_engine()) as db:
            j = db.get(Job, job_id)
            if j is not None:
                j.status = JobStatus.cancelled
                db.add(j)
                db.commit()
        return True

    monkeypatch.setattr(jobs_runner, "cancel", _fake_cancel)

    response = client.post(
        f"/api/jobs/{job['id']}/cancel",
        headers=auth_header(token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert cancel_calls == [job["id"]]


def test_export_mode_default_format(
    client: TestClient,
    authorised_account: tuple[str, dict],
    stub_launch: list[int],
) -> None:
    token, account = authorised_account
    response = client.post(
        "/api/jobs",
        json={"telegram_account_id": account["id"], "mode": "export"},
        headers=auth_header(token),
    )
    assert response.status_code == 201, response.text
    assert response.json()["export_format"] == "csv"


def test_logs_endpoint_streams_existing_then_end(
    client: TestClient,
    authorised_account: tuple[str, dict],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    token, account = authorised_account

    # Stub launch to write a small canned log and mark the job as finished.
    async def _writing_launch(job_id: int) -> None:
        with Session(get_engine()) as db:
            job = db.get(Job, job_id)
            assert job is not None
            log_file = tmp_path / f"job-{job_id}.log"
            log_file.write_text("line one\nline two\n", encoding="utf-8")
            job.log_path = str(log_file)
            job.status = JobStatus.succeeded
            job.exit_code = 0
            db.add(job)
            db.commit()

    monkeypatch.setattr(jobs_runner, "launch", _writing_launch)

    job = client.post(
        "/api/jobs",
        json={"telegram_account_id": account["id"], "mode": "stats"},
        headers=auth_header(token),
    ).json()

    # is_running should be False since we stubbed launch and never registered.
    assert not jobs_runner.is_running(job["id"])

    response = client.get(
        f"/api/jobs/{job['id']}/logs",
        headers=auth_header(token),
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "data: line one" in body
    assert "data: line two" in body
    assert "event: end" in body
