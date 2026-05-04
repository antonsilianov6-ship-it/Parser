"""Tests for the auto-rotation logic in :mod:`app.services.rotation`.

Covers the failure classifier (FloodWait short/long, SessionRevoked,
unknown) and the slot picker (visibility rules + deterministic order).
The integration with ``jobs_runner._maybe_rotate`` is covered in
``test_jobs_rotation.py`` to keep the unit-test surface here small.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import Session

from app.db import get_engine
from app.models.telegram_account import TelegramAccount
from app.services import rotation
from tests.conftest import auth_header, bootstrap_login

# --- classify_text -----------------------------------------------------


def test_classify_floodwait_short() -> None:
    text = "telethon.errors.rpcerrorlist.FloodWaitError: A wait of 30 seconds is required"
    result = rotation.classify_text(text)
    assert result.kind == "floodwait_short"
    assert result.floodwait_seconds == 30


def test_classify_floodwait_long() -> None:
    text = "FloodWaitError: A wait of 600 seconds is required (caused by ResolveUsername)"
    result = rotation.classify_text(text)
    assert result.kind == "floodwait_long"
    assert result.floodwait_seconds == 600


def test_classify_floodwait_at_threshold_is_short() -> None:
    """Boundary case: ``MAX_FLOODWAIT_SHORT_SECONDS`` itself is still short."""
    text = f"FloodWaitError: A wait of {rotation.MAX_FLOODWAIT_SHORT_SECONDS} seconds is required"
    assert rotation.classify_text(text).kind == "floodwait_short"


def test_classify_session_revoked() -> None:
    samples = [
        "telethon.errors.rpcerrorlist.AuthKeyUnregisteredError: ...",
        "Some traceback then SessionRevokedError: The authorization has been invalidated",
        "AuthKeyDuplicatedError: ...",
        "UserDeactivatedError: ...",
    ]
    for text in samples:
        assert rotation.classify_text(text).kind == "session_revoked", text


def test_classify_unknown() -> None:
    assert rotation.classify_text("ConnectionError: cannot reach server").kind == "unknown"
    assert rotation.classify_text("").kind == "unknown"


def test_classify_failure_reads_log_tail(tmp_path: Path) -> None:
    """Only the last LOG_TAIL_BYTES bytes are inspected, so noise above
    a real Telethon error doesn't drown it out."""
    log = tmp_path / "job.log"
    junk = "x" * (rotation.LOG_TAIL_BYTES * 2)
    log.write_text(
        junk + "\nFloodWaitError: A wait of 5 seconds is required\n",
        encoding="utf-8",
    )
    failure = rotation.classify_failure(log)
    assert failure.kind == "floodwait_short"
    assert failure.floodwait_seconds == 5


def test_classify_failure_missing_file_is_unknown(tmp_path: Path) -> None:
    failure = rotation.classify_failure(tmp_path / "nope.log")
    assert failure.kind == "unknown"


# --- pick_next_slot ----------------------------------------------------


def _seed_account(
    *,
    owner_id: int,
    label: str,
    is_authorized: bool = True,
    is_shared: bool = False,
) -> int:
    with Session(get_engine()) as db:
        account = TelegramAccount(
            owner_id=owner_id,
            label=label,
            session_path=f"data/users/{owner_id}/{label}.session",
            api_id=12345,
            api_hash="deadbeefdead",
            phone="+79990001122",
            is_shared=is_shared,
            is_authorized=is_authorized,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        assert account.id is not None
        return account.id


def test_pick_next_slot_skips_current_and_picks_owner_slot(client: pytest.FixtureRequest) -> None:
    bootstrap_login(client)  # owner = user 1
    a1 = _seed_account(owner_id=1, label="a1")
    a2 = _seed_account(owner_id=1, label="a2")
    with Session(get_engine()) as db:
        chosen = rotation.pick_next_slot(db, owner_id=1, current_account_id=a1)
        assert chosen is not None and chosen.id == a2


def test_pick_next_slot_skips_other_owners_private_slots(
    client: pytest.FixtureRequest,
) -> None:
    """Other users' non-shared slots must NOT be picked even if authorised."""
    token = bootstrap_login(client)
    a1 = _seed_account(owner_id=1, label="a1")

    # Create a second user via API so password hashing is real.
    client.post(
        "/api/users",
        json={"username": "alice", "password": "alicepwd123"},
        headers=auth_header(token),
    )
    _seed_account(owner_id=2, label="alice-private", is_shared=False)

    with Session(get_engine()) as db:
        chosen = rotation.pick_next_slot(db, owner_id=1, current_account_id=a1)
        assert chosen is None


def test_pick_next_slot_picks_shared_slot_from_other_owner(
    client: pytest.FixtureRequest,
) -> None:
    token = bootstrap_login(client)
    a1 = _seed_account(owner_id=1, label="a1")

    client.post(
        "/api/users",
        json={"username": "alice", "password": "alicepwd123"},
        headers=auth_header(token),
    )
    shared_id = _seed_account(owner_id=2, label="alice-shared", is_shared=True)

    with Session(get_engine()) as db:
        chosen = rotation.pick_next_slot(db, owner_id=1, current_account_id=a1)
        assert chosen is not None and chosen.id == shared_id


def test_pick_next_slot_wraps_past_current(client: pytest.FixtureRequest) -> None:
    """With slots [1, 2, 3] starting on slot 2 we should try 3, then 1.

    Regression: previously the picker just returned the lowest-id slot
    that wasn't the current one, so consecutive rotations from slot 2
    would alternate 2→1→2→1 and slot 3 would never be tried.
    """
    bootstrap_login(client)
    a1 = _seed_account(owner_id=1, label="a1")  # id=1
    a2 = _seed_account(owner_id=1, label="a2")  # id=2
    a3 = _seed_account(owner_id=1, label="a3")  # id=3

    with Session(get_engine()) as db:
        # First rotation: from 2 → 3 (id > current)
        first = rotation.pick_next_slot(db, owner_id=1, current_account_id=a2)
        assert first is not None and first.id == a3
        # Second rotation: from 3 → 1 (wrap, smallest id)
        second = rotation.pick_next_slot(db, owner_id=1, current_account_id=a3)
        assert second is not None and second.id == a1
        # Third rotation: from 1 → 2 (next id > 1)
        third = rotation.pick_next_slot(db, owner_id=1, current_account_id=a1)
        assert third is not None and third.id == a2


def test_pick_next_slot_skips_unauthorised_slots(client: pytest.FixtureRequest) -> None:
    bootstrap_login(client)
    a1 = _seed_account(owner_id=1, label="a1")
    _seed_account(owner_id=1, label="a2-not-yet-signed-in", is_authorized=False)

    with Session(get_engine()) as db:
        chosen = rotation.pick_next_slot(db, owner_id=1, current_account_id=a1)
        assert chosen is None
