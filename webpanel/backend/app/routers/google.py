"""Google Drive / Docs / NotebookLM credential management (per-user).

Each panel user uploads:
- a Google service-account JSON (used by ``GoogleDocsExporter``);
- a NotebookLM Playwright ``storage_state.json`` (used by ``notebooklm-py``);
- the target Google Doc id and optional Drive folder id.

Files live under the user's data dir on disk (see ``parser_files.py``); the
DB only stores the doc / folder ids and a couple of "has X" flags surface
through ``GET /api/google/status``.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.deps import CurrentUser, SessionDep
from app.models.user import User
from app.services import parser_files

router = APIRouter(prefix="/api/google", tags=["google"])


class GoogleStatus(BaseModel):
    has_credentials: bool
    credentials_email: str | None = None
    has_notebooklm_storage: bool
    google_doc_id: str | None = None
    google_drive_folder_id: str | None = None


class GoogleSettingsUpdate(BaseModel):
    """Doc and folder IDs accept either a raw id or a full URL — we normalise."""

    google_doc_id: str | None = Field(default=None, max_length=512)
    google_drive_folder_id: str | None = Field(default=None, max_length=512)


def _extract_id(value: str | None, kind: str) -> str | None:
    """Return the bare id from either a raw id or a Drive URL.

    - ``https://docs.google.com/document/d/<ID>/edit?usp=sharing`` → ``<ID>``
    - ``https://drive.google.com/drive/folders/<ID>?usp=drive_link`` → ``<ID>``
    - ``<ID>`` → ``<ID>``
    """
    if not value:
        return None
    value = value.strip()
    if not value:
        return None

    def _clean(seg: str) -> str:
        # Strip any ``?query`` / ``#fragment`` from the captured segment.
        return seg.split("?", 1)[0].split("#", 1)[0]

    if "/" not in value:
        return _clean(value)
    parts = [p for p in value.split("/") if p]
    if kind == "doc" and "d" in parts:
        idx = parts.index("d")
        if idx + 1 < len(parts):
            return _clean(parts[idx + 1])
    if kind == "folder" and "folders" in parts:
        idx = parts.index("folders")
        if idx + 1 < len(parts):
            return _clean(parts[idx + 1])
    # Last segment is a reasonable best-effort fallback (handles URLs we
    # don't explicitly recognise).
    return _clean(parts[-1])


def _build_status(session: SessionDep, user: User) -> GoogleStatus:
    assert user.id is not None
    return GoogleStatus(
        has_credentials=parser_files.has_google_credentials(user.id),
        credentials_email=parser_files.google_credentials_email(user.id),
        has_notebooklm_storage=parser_files.has_notebooklm_storage(user.id),
        google_doc_id=user.google_doc_id,
        google_drive_folder_id=user.google_drive_folder_id,
    )


@router.get("/status", response_model=GoogleStatus)
def get_status(session: SessionDep, current_user: CurrentUser) -> GoogleStatus:
    return _build_status(session, current_user)


@router.put("/credentials", response_model=GoogleStatus)
async def upload_credentials(
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),  # noqa: B008 — FastAPI dependency injection idiom
) -> GoogleStatus:
    raw = await file.read()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Получен пустой файл",
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл должен быть UTF-8 JSON",
        ) from exc

    assert current_user.id is not None
    try:
        parser_files.write_google_credentials(current_user.id, text)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return _build_status(session, current_user)


@router.delete("/credentials", response_model=GoogleStatus)
def delete_credentials(
    session: SessionDep, current_user: CurrentUser
) -> GoogleStatus:
    assert current_user.id is not None
    parser_files.delete_google_credentials(current_user.id)
    return _build_status(session, current_user)


@router.put("/notebooklm", response_model=GoogleStatus)
async def upload_notebooklm_storage(
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),  # noqa: B008 — FastAPI dependency injection idiom
) -> GoogleStatus:
    raw = await file.read()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Получен пустой файл",
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл должен быть UTF-8 JSON",
        ) from exc

    assert current_user.id is not None
    try:
        parser_files.write_notebooklm_storage(current_user.id, text)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return _build_status(session, current_user)


@router.delete("/notebooklm", response_model=GoogleStatus)
def delete_notebooklm_storage(
    session: SessionDep, current_user: CurrentUser
) -> GoogleStatus:
    assert current_user.id is not None
    parser_files.delete_notebooklm_storage(current_user.id)
    return _build_status(session, current_user)


@router.put("/settings", response_model=GoogleStatus)
def update_settings(
    payload: GoogleSettingsUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> GoogleStatus:
    user = session.get(User, current_user.id)
    if user is None:  # pragma: no cover — auth dep guarantees presence
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.google_doc_id = _extract_id(payload.google_doc_id, "doc")
    user.google_drive_folder_id = _extract_id(payload.google_drive_folder_id, "folder")
    session.add(user)
    session.commit()
    session.refresh(user)
    return _build_status(session, user)


@router.post("/test")
def test_credentials(session: SessionDep, current_user: CurrentUser) -> dict[str, str]:
    """Smoke-test that the uploaded service account can talk to Google APIs.

    Tries to build a Drive client and ``files().get`` the configured doc id.
    Surfaces a friendly error message instead of a 500 if anything is off.
    """
    assert current_user.id is not None
    if not parser_files.has_google_credentials(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Сначала загрузите Service Account JSON",
        )

    user = session.get(User, current_user.id)
    if user is None or not user.google_doc_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите Google Doc ID или ссылку в настройках",
        )

    try:
        from google.oauth2.service_account import Credentials  # type: ignore[import-untyped]
        from googleapiclient.discovery import build  # type: ignore[import-untyped]
        from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover — deps in requirements.runtime.txt
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google API libraries are not installed: {exc}",
        ) from exc

    creds_path = parser_files.google_credentials_path(current_user.id)
    try:
        creds = Credentials.from_service_account_file(
            str(creds_path),
            scopes=[
                "https://www.googleapis.com/auth/documents",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        service = build("docs", "v1", credentials=creds, cache_discovery=False)
        service.documents().get(documentId=user.google_doc_id).execute()
    except HttpError as exc:
        # Google's HttpError carries a JSON-encoded reason; surface the
        # human-readable message so the user can act on it (e.g. "the
        # service account doesn't have access — share the doc with X").
        try:
            payload = json.loads(exc.content)
            message = payload.get("error", {}).get("message", str(exc))
        except (ValueError, AttributeError):
            message = str(exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google API ответил ошибкой: {message}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Не удалось подключиться к Google API: {exc}",
        ) from exc

    return {"detail": "Доступ подтверждён"}
