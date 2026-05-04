"""Interactive browser-based login flow for NotebookLM.

The panel cannot complete a Google login on the user's behalf — but
we *can* run a headed Chromium in a separate ``browser`` docker
service and let the user drive it through a noVNC iframe embedded in
the panel UI. Once the user reaches NotebookLM successfully the
panel grabs the Playwright ``storage_state`` and writes it to disk
just like the manual upload flow.

Endpoints (all under ``/api/google/notebooklm/auth``):

- ``POST /start``     create a session, navigate to NotebookLM, return iframe URL
- ``GET  /{id}``      poll status (``loading`` / ``pending`` / ``ready`` / ...)
- ``POST /{id}/save`` capture ``storage_state`` and persist to disk
- ``POST /{id}/cancel`` close the browser session without saving
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.config import get_settings
from app.deps import CurrentUser
from app.services import parser_files
from app.services.browser_session import BrowserSession, get_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/google/notebooklm/auth", tags=["google"])


# NotebookLM lives at this origin. We compare the full origin prefix
# (not just the host) because Google's accounts.google.com login page
# embeds ``continue=https://notebooklm.google.com/...`` in the query
# string — a naive substring match would flip status to ``ready``
# before the user has actually signed in.
NOTEBOOKLM_HOME_URL = "https://notebooklm.google.com/"
NOTEBOOKLM_SUCCESS_PREFIX = "https://notebooklm.google.com"


class BrowserSessionPublic(BaseModel):
    """Subset of :class:`BrowserSession` that's safe to return to the SPA."""

    id: str
    purpose: str
    status: str
    error: str | None = None
    started_at: float
    finished_at: float | None = None
    target_url: str
    public_url: str


def _to_public(session: BrowserSession, public_url: str) -> BrowserSessionPublic:
    return BrowserSessionPublic(
        id=session.id,
        purpose=session.purpose,
        status=session.status,
        error=session.error,
        started_at=session.started_at,
        finished_at=session.finished_at,
        target_url=session.target_url,
        public_url=public_url,
    )


@router.post("/start", response_model=BrowserSessionPublic)
async def start_auth(current_user: CurrentUser) -> BrowserSessionPublic:
    settings = get_settings()
    manager = get_manager(settings)
    assert current_user.id is not None
    try:
        session = await manager.start_session(
            user_id=current_user.id,
            purpose="notebooklm",
            target_url=NOTEBOOKLM_HOME_URL,
            success_url_substring=NOTEBOOKLM_SUCCESS_PREFIX,
        )
    except RuntimeError as exc:
        # Either the browser service is unreachable, or another user
        # already has an active session.
        message = str(exc)
        code = (
            status.HTTP_409_CONFLICT
            if message.startswith("browser_busy")
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        raise HTTPException(status_code=code, detail=message) from exc
    return _to_public(session, manager.public_url)


@router.get("/{session_id}", response_model=BrowserSessionPublic)
async def poll_auth(session_id: str, current_user: CurrentUser) -> BrowserSessionPublic:
    settings = get_settings()
    manager = get_manager(settings)
    session = await manager.get_session(session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена"
        )
    return _to_public(session, manager.public_url)


@router.post("/{session_id}/save", response_model=BrowserSessionPublic)
async def save_auth(session_id: str, current_user: CurrentUser) -> BrowserSessionPublic:
    settings = get_settings()
    manager = get_manager(settings)
    session = await manager.get_session(session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена"
        )
    if session.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дождитесь, пока в браузере появится главная страница NotebookLM",
        )
    try:
        state = await manager.harvest_storage_state(session_id)
    except Exception as exc:  # noqa: BLE001 — surface to user
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось извлечь storage_state: {exc}",
        ) from exc
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Сессия больше не активна"
        )
    assert current_user.id is not None
    try:
        parser_files.write_notebooklm_storage(current_user.id, json.dumps(state))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Полученный storage_state невалиден: {exc}",
        ) from exc
    refreshed = await manager.get_session(session_id)
    return _to_public(refreshed or session, manager.public_url)


@router.post("/{session_id}/cancel", response_model=BrowserSessionPublic)
async def cancel_auth(session_id: str, current_user: CurrentUser) -> BrowserSessionPublic:
    settings = get_settings()
    manager = get_manager(settings)
    session = await manager.get_session(session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена"
        )
    await manager.cancel_session(session_id)
    refreshed = await manager.get_session(session_id) or session
    return _to_public(refreshed, manager.public_url)
