"""Tests for the schedules CRUD router.

APScheduler is disabled in the test fixture (`PANEL_ENABLE_SCHEDULER=false`)
so the cron strings are validated and stored, but no real ticks fire — we
test the persistence + validation behaviour, plus directly exercise
``scheduler._fire_schedule`` to verify a tick spawns a Job.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import get_engine
from app.models.job import Job, JobMode, JobStatus
from app.models.telegram_account import TelegramAccount
from app.models.user import User
from app.services import jobs_runner, parser_files, scheduler

from .conftest import auth_header, bootstrap_login


def _seed_docs_creds(user_id: int, doc_id: str = "doc-stub-1") -> None:
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
    token = bootstrap_login(client)
    account_payload = client.post(
        "/api/telegram/accounts",
        json={"label": "main"},
        headers=auth_header(token),
    ).json()
    with Session(get_engine()) as db:
        account = db.get(TelegramAccount, account_payload["id"])
        assert account is not None
        account.is_authorized = True
        account.api_id = 12345
        account.api_hash = "deadbeefdead"
        account.phone = "+79990001122"
        db.add(account)
        db.commit()
    _seed_docs_creds(1)
    return token, account_payload


def test_create_schedule_validates_cron_and_stores(
    client: TestClient, authorised_account: tuple[str, dict]
) -> None:
    token, account = authorised_account
    response = client.post(
        "/api/schedules",
        json={
            "name": "Каждый час",
            "telegram_account_id": account["id"],
            "cron_expression": "0 * * * *",
            "export_to_docs": True,
        },
        headers=auth_header(token),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["cron_expression"] == "0 * * * *"
    assert body["export_to_docs"] is True
    assert body["is_active"] is True


def test_create_schedule_rejects_invalid_cron(
    client: TestClient, authorised_account: tuple[str, dict]
) -> None:
    token, account = authorised_account
    response = client.post(
        "/api/schedules",
        json={
            "name": "Bad",
            "telegram_account_id": account["id"],
            "cron_expression": "not a cron",
            "export_to_docs": True,
        },
        headers=auth_header(token),
    )
    assert response.status_code == 422


def test_create_schedule_requires_export_target(
    client: TestClient, authorised_account: tuple[str, dict]
) -> None:
    token, account = authorised_account
    response = client.post(
        "/api/schedules",
        json={
            "name": "No targets",
            "telegram_account_id": account["id"],
            "cron_expression": "*/30 * * * *",
        },
        headers=auth_header(token),
    )
    assert response.status_code == 422


def test_list_schedules_only_returns_owned_or_shared(
    client: TestClient, authorised_account: tuple[str, dict]
) -> None:
    token, account = authorised_account
    client.post(
        "/api/schedules",
        json={
            "name": "Mine",
            "telegram_account_id": account["id"],
            "cron_expression": "0 9 * * *",
            "export_to_docs": True,
        },
        headers=auth_header(token),
    )

    # Create a second user; they should see no schedules.
    client.post(
        "/api/users",
        json={"username": "alice", "password": "alicepwd123"},
        headers=auth_header(token),
    )
    alice_token = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alicepwd123"},
    ).json()["access_token"]

    mine = client.get("/api/schedules", headers=auth_header(token)).json()
    alice = client.get("/api/schedules", headers=auth_header(alice_token)).json()
    assert len(mine) == 1
    assert alice == []


def test_update_and_delete_schedule(
    client: TestClient, authorised_account: tuple[str, dict]
) -> None:
    token, account = authorised_account
    created = client.post(
        "/api/schedules",
        json={
            "name": "Mine",
            "telegram_account_id": account["id"],
            "cron_expression": "0 9 * * *",
            "export_to_docs": True,
        },
        headers=auth_header(token),
    ).json()
    sid = created["id"]

    patched = client.patch(
        f"/api/schedules/{sid}",
        json={"is_active": False, "name": "Renamed"},
        headers=auth_header(token),
    ).json()
    assert patched["is_active"] is False
    assert patched["name"] == "Renamed"

    response = client.delete(f"/api/schedules/{sid}", headers=auth_header(token))
    assert response.status_code == 204
    assert client.get("/api/schedules", headers=auth_header(token)).json() == []


def test_deactivate_does_not_revalidate_creds(
    client: TestClient, authorised_account: tuple[str, dict]
) -> None:
    """Regression: pausing a schedule must work even after creds are gone.

    Previously ``update_schedule`` always called the credential check,
    so a user who deleted their Google Service Account JSON could not
    flip ``is_active=False`` on an existing Docs-export schedule and
    was stuck with a cron that spawned failing jobs every tick.
    """
    token, account = authorised_account
    created = client.post(
        "/api/schedules",
        json={
            "name": "Was active",
            "telegram_account_id": account["id"],
            "cron_expression": "0 * * * *",
            "export_to_docs": True,
        },
        headers=auth_header(token),
    ).json()

    # Wipe the per-user Google credential file so the cred check would fail.
    parser_files.google_credentials_path(1).unlink()

    response = client.patch(
        f"/api/schedules/{created['id']}",
        json={"is_active": False},
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_active"] is False
    # Stale next_run_at must also be wiped on deactivation.
    assert body["next_run_at"] is None


def test_rename_does_not_revalidate_creds_when_inactive(
    client: TestClient, authorised_account: tuple[str, dict]
) -> None:
    token, account = authorised_account
    created = client.post(
        "/api/schedules",
        json={
            "name": "Old",
            "telegram_account_id": account["id"],
            "cron_expression": "0 * * * *",
            "export_to_docs": True,
        },
        headers=auth_header(token),
    ).json()
    client.patch(
        f"/api/schedules/{created['id']}",
        json={"is_active": False},
        headers=auth_header(token),
    )
    parser_files.google_credentials_path(1).unlink()

    response = client.patch(
        f"/api/schedules/{created['id']}",
        json={"name": "Renamed while paused"},
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Renamed while paused"


def test_reactivating_without_creds_still_blocks(
    client: TestClient, authorised_account: tuple[str, dict]
) -> None:
    """Re-enabling a paused schedule must still require the creds it needs."""
    token, account = authorised_account
    created = client.post(
        "/api/schedules",
        json={
            "name": "Paused",
            "telegram_account_id": account["id"],
            "cron_expression": "0 * * * *",
            "export_to_docs": True,
            "is_active": False,
        },
        headers=auth_header(token),
    ).json()
    parser_files.google_credentials_path(1).unlink()

    response = client.patch(
        f"/api/schedules/{created['id']}",
        json={"is_active": True},
        headers=auth_header(token),
    )
    assert response.status_code == 400


def test_create_schedule_rejects_unauthorised_tg_account(
    client: TestClient,
) -> None:
    """A schedule cannot point at a TG account that hasn't completed sign-in.

    Otherwise every cron tick would spawn a Job that ``jobs_runner.launch``
    immediately marks failed (the runner refuses unauthorised slots),
    producing a stream of useless failed-job rows.
    """
    token = bootstrap_login(client)
    account_payload = client.post(
        "/api/telegram/accounts",
        json={"label": "not-yet-signed-in"},
        headers=auth_header(token),
    ).json()
    _seed_docs_creds(1)

    response = client.post(
        "/api/schedules",
        json={
            "name": "Useless",
            "telegram_account_id": account_payload["id"],
            "cron_expression": "0 * * * *",
            "export_to_docs": True,
        },
        headers=auth_header(token),
    )
    assert response.status_code == 400
    assert "authorised" in response.json()["detail"].lower()


def test_patch_can_clear_channel_to_null(
    client: TestClient, authorised_account: tuple[str, dict]
) -> None:
    """PATCH must distinguish 'channel field omitted' from 'set channel=null'.

    Setting ``channel`` back to ``None`` is the way to switch a schedule
    from a single channel to "all channels in channels.txt".
    """
    token, account = authorised_account
    created = client.post(
        "/api/schedules",
        json={
            "name": "with channel",
            "telegram_account_id": account["id"],
            "cron_expression": "0 * * * *",
            "channel": "@example",
            "export_to_docs": True,
        },
        headers=auth_header(token),
    ).json()
    assert created["channel"] == "@example"

    response = client.patch(
        f"/api/schedules/{created['id']}",
        json={"channel": None},
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["channel"] is None


def test_patch_without_channel_field_keeps_existing_value(
    client: TestClient, authorised_account: tuple[str, dict]
) -> None:
    """Sanity check: omitting channel from PATCH must NOT wipe it."""
    token, account = authorised_account
    created = client.post(
        "/api/schedules",
        json={
            "name": "with channel",
            "telegram_account_id": account["id"],
            "cron_expression": "0 * * * *",
            "channel": "@example",
            "export_to_docs": True,
        },
        headers=auth_header(token),
    ).json()
    response = client.patch(
        f"/api/schedules/{created['id']}",
        json={"name": "renamed only"},
        headers=auth_header(token),
    )
    assert response.status_code == 200
    assert response.json()["channel"] == "@example"


def test_other_user_cant_modify_schedule(
    client: TestClient, authorised_account: tuple[str, dict]
) -> None:
    token, account = authorised_account
    created = client.post(
        "/api/schedules",
        json={
            "name": "Mine",
            "telegram_account_id": account["id"],
            "cron_expression": "0 9 * * *",
            "export_to_docs": True,
        },
        headers=auth_header(token),
    ).json()
    sid = created["id"]

    client.post(
        "/api/users",
        json={"username": "alice", "password": "alicepwd123"},
        headers=auth_header(token),
    )
    alice_token = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alicepwd123"},
    ).json()["access_token"]

    response = client.patch(
        f"/api/schedules/{sid}",
        json={"name": "Hacked"},
        headers=auth_header(alice_token),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_fire_schedule_spawns_job(
    client: TestClient,
    authorised_account: tuple[str, dict],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A scheduler tick must persist a Job row and call jobs_runner.launch."""
    token, account = authorised_account
    created = client.post(
        "/api/schedules",
        json={
            "name": "Fires",
            "telegram_account_id": account["id"],
            "cron_expression": "0 * * * *",
            "export_to_docs": True,
            "export_to_notebooklm": False,
        },
        headers=auth_header(token),
    ).json()

    launched: list[int] = []

    async def _fake_launch(job_id: int) -> None:
        launched.append(job_id)

    monkeypatch.setattr(jobs_runner, "launch", _fake_launch)

    await scheduler._fire_schedule(created["id"])
    # Wait one event loop turn so the create_task fires.
    import asyncio

    await asyncio.sleep(0)

    with Session(get_engine()) as db:
        jobs = db.exec(  # type: ignore[call-arg]
            __import__("sqlmodel").select(Job)
        ).all()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.owner_id == 1
    assert job.mode == JobMode.parse
    assert job.export_to_docs is True
    assert job.status == JobStatus.pending
    assert launched == [job.id]


@pytest.mark.asyncio
async def test_fire_schedule_skips_when_inactive(
    client: TestClient,
    authorised_account: tuple[str, dict],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token, account = authorised_account
    created = client.post(
        "/api/schedules",
        json={
            "name": "Will be disabled",
            "telegram_account_id": account["id"],
            "cron_expression": "0 * * * *",
            "export_to_docs": True,
        },
        headers=auth_header(token),
    ).json()
    # Disable.
    client.patch(
        f"/api/schedules/{created['id']}",
        json={"is_active": False},
        headers=auth_header(token),
    )

    launched: list[int] = []

    async def _fake_launch(job_id: int) -> None:  # noqa: ARG001
        launched.append(job_id)

    monkeypatch.setattr(jobs_runner, "launch", _fake_launch)

    await scheduler._fire_schedule(created["id"])
    import asyncio

    await asyncio.sleep(0)
    assert launched == []
