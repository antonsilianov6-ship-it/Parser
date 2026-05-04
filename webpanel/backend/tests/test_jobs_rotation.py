"""Integration-ish tests for ``jobs_runner._maybe_rotate``.

We don't spawn the real parser subprocess; instead we craft a Job row,
write a synthetic log tail, and assert that ``_maybe_rotate`` either
schedules a relaunch via the (monkey-patched) ``launch`` or signals
the caller to mark the job failed by returning ``None``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import get_engine
from app.models.job import Job, JobMode, JobStatus
from app.models.telegram_account import TelegramAccount
from app.services import jobs_runner, rotation
from tests.conftest import bootstrap_login

# --- helpers -----------------------------------------------------------


def _seed_authorised(label: str = "main") -> int:
    with Session(get_engine()) as db:
        account = TelegramAccount(
            owner_id=1,
            label=label,
            session_path=f"data/users/1/{label}.session",
            api_id=12345,
            api_hash="deadbeefdead",
            phone="+79990001122",
            is_authorized=True,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        assert account.id is not None
        return account.id


def _seed_failed_parse_job(
    *,
    account_id: int,
    log_path: Path,
    log_text: str,
    allow_rotation: bool = True,
    retry_count: int = 0,
) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(log_text, encoding="utf-8")
    with Session(get_engine()) as db:
        job = Job(
            owner_id=1,
            telegram_account_id=account_id,
            mode=JobMode.parse,
            export_to_docs=True,
            allow_rotation=allow_rotation,
            retry_count=retry_count,
            status=JobStatus.running,
            log_path=str(log_path),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        assert job.id is not None
        return job.id


@pytest.fixture
def stub_launch(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Replace ``jobs_runner.launch`` with a no-op that records job ids."""
    relaunched: list[int] = []

    async def _stub(job_id: int) -> None:
        relaunched.append(job_id)

    monkeypatch.setattr(jobs_runner, "launch", _stub)
    return relaunched


@pytest.fixture
def fast_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Replace ``asyncio.sleep`` so FloodWait-short tests don't actually wait."""
    waited: list[float] = []

    async def _fast(seconds: float) -> None:
        waited.append(seconds)

    monkeypatch.setattr(jobs_runner.asyncio, "sleep", _fast)
    return waited


# --- tests -------------------------------------------------------------


@pytest.mark.asyncio
async def test_floodwait_short_retries_same_slot(
    client: TestClient,
    tmp_path: Path,
    stub_launch: list[int],
    fast_sleep: list[float],
) -> None:
    bootstrap_login(client)
    account_id = _seed_authorised()
    job_id = _seed_failed_parse_job(
        account_id=account_id,
        log_path=tmp_path / "job.log",
        log_text="FloodWaitError: A wait of 12 seconds is required",
    )

    decision = await jobs_runner._maybe_rotate(job_id)
    assert decision == "retry_same_slot"

    with Session(get_engine()) as db:
        job = db.get(Job, job_id)
        assert job is not None
        assert job.retry_count == 1
        assert job.status == JobStatus.pending
        assert job.telegram_account_id == account_id  # unchanged

    assert stub_launch == [job_id]
    assert fast_sleep == [12]  # rounded up from FloodWait seconds


@pytest.mark.asyncio
async def test_floodwait_long_swaps_to_next_slot(
    client: TestClient,
    tmp_path: Path,
    stub_launch: list[int],
    fast_sleep: list[float],
) -> None:
    bootstrap_login(client)
    primary = _seed_authorised("primary")
    fallback = _seed_authorised("fallback")
    job_id = _seed_failed_parse_job(
        account_id=primary,
        log_path=tmp_path / "job.log",
        log_text="FloodWaitError: A wait of 600 seconds is required",
    )

    decision = await jobs_runner._maybe_rotate(job_id)
    assert decision == "retry_next_slot"

    with Session(get_engine()) as db:
        job = db.get(Job, job_id)
        assert job is not None
        assert job.retry_count == 1
        assert job.telegram_account_id == fallback

    assert stub_launch == [job_id]
    assert fast_sleep == []  # slot swap doesn't sleep


@pytest.mark.asyncio
async def test_session_revoked_swaps_slot(
    client: TestClient,
    tmp_path: Path,
    stub_launch: list[int],
) -> None:
    bootstrap_login(client)
    primary = _seed_authorised("primary")
    fallback = _seed_authorised("fallback")
    job_id = _seed_failed_parse_job(
        account_id=primary,
        log_path=tmp_path / "job.log",
        log_text="telethon.errors.rpcerrorlist.AuthKeyUnregisteredError",
    )

    decision = await jobs_runner._maybe_rotate(job_id)
    assert decision == "retry_next_slot"
    with Session(get_engine()) as db:
        job = db.get(Job, job_id)
        assert job is not None and job.telegram_account_id == fallback


@pytest.mark.asyncio
async def test_no_other_slot_gives_up(
    client: TestClient,
    tmp_path: Path,
    stub_launch: list[int],
) -> None:
    bootstrap_login(client)
    only_slot = _seed_authorised("solo")
    job_id = _seed_failed_parse_job(
        account_id=only_slot,
        log_path=tmp_path / "job.log",
        log_text="SessionRevokedError: ...",
    )

    decision = await jobs_runner._maybe_rotate(job_id)
    assert decision is None  # caller will mark the job failed
    assert stub_launch == []
    with Session(get_engine()) as db:
        job = db.get(Job, job_id)
        assert job is not None and job.retry_count == 0


@pytest.mark.asyncio
async def test_unknown_failure_is_not_retried(
    client: TestClient,
    tmp_path: Path,
    stub_launch: list[int],
) -> None:
    bootstrap_login(client)
    account_id = _seed_authorised()
    job_id = _seed_failed_parse_job(
        account_id=account_id,
        log_path=tmp_path / "job.log",
        log_text="ConnectionResetError: ...",
    )

    decision = await jobs_runner._maybe_rotate(job_id)
    assert decision is None
    assert stub_launch == []


@pytest.mark.asyncio
async def test_rotation_disabled_is_not_retried(
    client: TestClient,
    tmp_path: Path,
    stub_launch: list[int],
) -> None:
    bootstrap_login(client)
    primary = _seed_authorised("primary")
    _seed_authorised("fallback")
    job_id = _seed_failed_parse_job(
        account_id=primary,
        log_path=tmp_path / "job.log",
        log_text="FloodWaitError: A wait of 5 seconds is required",
        allow_rotation=False,
    )

    decision = await jobs_runner._maybe_rotate(job_id)
    assert decision is None
    assert stub_launch == []


@pytest.mark.asyncio
async def test_max_retries_caps_relaunches(
    client: TestClient,
    tmp_path: Path,
    stub_launch: list[int],
    fast_sleep: list[float],
) -> None:
    bootstrap_login(client)
    account_id = _seed_authorised()
    job_id = _seed_failed_parse_job(
        account_id=account_id,
        log_path=tmp_path / "job.log",
        log_text="FloodWaitError: A wait of 5 seconds is required",
        retry_count=rotation.MAX_RETRIES,
    )

    decision = await jobs_runner._maybe_rotate(job_id)
    assert decision is None
    assert stub_launch == []


@pytest.mark.asyncio
async def test_cancelled_job_is_not_retried(
    client: TestClient,
    tmp_path: Path,
    stub_launch: list[int],
) -> None:
    bootstrap_login(client)
    account_id = _seed_authorised()
    job_id = _seed_failed_parse_job(
        account_id=account_id,
        log_path=tmp_path / "job.log",
        log_text="FloodWaitError: A wait of 5 seconds is required",
    )
    with Session(get_engine()) as db:
        job = db.get(Job, job_id)
        assert job is not None
        job.status = JobStatus.cancelled
        db.add(job)
        db.commit()

    decision = await jobs_runner._maybe_rotate(job_id)
    assert decision is None
    assert stub_launch == []
