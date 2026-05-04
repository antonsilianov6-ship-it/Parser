"""Unit tests for ``jobs_runner._build_env`` — verifies that the panel pumps
the right per-user GOOGLE_* / NOTEBOOKLM_AUTH_JSON env vars into the parser
subprocess, and only when the corresponding job flag was set.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.models.job import Job, JobMode, JobStatus
from app.models.telegram_account import TelegramAccount
from app.models.user import User
from app.services import jobs_runner, parser_files
from tests.conftest import bootstrap_login


def _make_account() -> TelegramAccount:
    return TelegramAccount(
        owner_id=1,
        label="main",
        api_id=12345,
        api_hash="hashy",
        session_path="sessions/main.session",
        is_authorized=True,
    )


def _make_job(*, docs: bool = False, nlm: bool = False) -> Job:
    return Job(
        owner_id=1,
        telegram_account_id=1,
        mode=JobMode.parse,
        channel="@example",
        export_to_docs=docs,
        export_to_notebooklm=nlm,
        status=JobStatus.pending,
        log_path="",
    )


def test_build_env_skips_google_when_no_export(client: TestClient) -> None:
    """If neither flag is set, no GOOGLE_* / NOTEBOOKLM_AUTH_JSON env exists."""
    bootstrap_login(client)
    env = jobs_runner._build_env(
        _make_account(),
        owner_user_id=1,
        job=_make_job(docs=False, nlm=False),
        owner=None,
    )
    assert env["PARSER_EXPORT_TO_DOCS"] == "0"
    assert env["PARSER_EXPORT_TO_NOTEBOOKLM"] == "0"
    assert "GOOGLE_CREDS_PATH" not in env
    assert "GOOGLE_DOC_ID" not in env
    assert "NOTEBOOKLM_AUTH_JSON" not in env
    assert "PARSER_CLEAR_DB_AFTER_EXPORT" not in env


def test_build_env_injects_docs_paths(client: TestClient) -> None:
    bootstrap_login(client)
    owner = User(
        id=1,
        username="admin",
        password_hash="x",
        google_doc_id="DOC42",
        google_drive_folder_id="FOLDER7",
    )
    env = jobs_runner._build_env(
        _make_account(),
        owner_user_id=1,
        job=_make_job(docs=True, nlm=False),
        owner=owner,
    )
    assert env["PARSER_EXPORT_TO_DOCS"] == "1"
    assert env["PARSER_EXPORT_TO_NOTEBOOKLM"] == "0"
    assert env["GOOGLE_CREDS_PATH"] == str(parser_files.google_credentials_path(1))
    assert env["GOOGLE_DOC_ID"] == "DOC42"
    assert env["GOOGLE_DRIVE_FOLDER_ID"] == "FOLDER7"
    assert env["PARSER_CLEAR_DB_AFTER_EXPORT"] == "1"
    # Cache path is always set so the parser doesn't drop the entity cache.
    assert env["PARSER_CACHE_PATH"].endswith("/cache/cache.json") or env[
        "PARSER_CACHE_PATH"
    ].endswith("\\cache\\cache.json")


def test_build_env_injects_notebooklm_only(client: TestClient) -> None:
    bootstrap_login(client)
    env = jobs_runner._build_env(
        _make_account(),
        owner_user_id=1,
        job=_make_job(docs=False, nlm=True),
        owner=None,
    )
    assert env["PARSER_EXPORT_TO_DOCS"] == "0"
    assert env["PARSER_EXPORT_TO_NOTEBOOKLM"] == "1"
    assert "GOOGLE_CREDS_PATH" not in env
    assert env["NOTEBOOKLM_AUTH_JSON"] == str(
        parser_files.notebooklm_storage_path(1)
    )
    assert env["PARSER_CLEAR_DB_AFTER_EXPORT"] == "1"
