"""Browser-auth router tests.

Playwright is stubbed out — these tests verify the router contract,
the per-user session isolation invariant, and the storage harvest
flow without spawning a real browser.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.services import browser_session, parser_files

from .conftest import auth_header, bootstrap_login


@pytest.fixture(autouse=True)
def _reset_manager() -> None:
    browser_session.reset_manager_for_tests()
    yield
    browser_session.reset_manager_for_tests()


@pytest.fixture
def patched_browser(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Replace the Playwright bits with awaitable stubs.

    The stubs let us drive ``status`` transitions deterministically
    via ``state["url"]`` and ``state["fail_open"]``.
    """
    state: dict[str, Any] = {
        "url": "https://accounts.google.com/signin",
        "fail_open": False,
        "storage": {"cookies": [{"name": "demo", "value": "ok"}]},
    }

    class _FakePage:
        def __init__(self) -> None:
            self.url = state["url"]

        async def goto(self, *_: Any, **__: Any) -> None:
            self.url = state["url"]

        async def close(self) -> None:
            return None

    class _FakeContext:
        async def new_page(self) -> _FakePage:
            return _FakePage()

        async def close(self) -> None:
            return None

        async def storage_state(self) -> dict[str, Any]:
            return state["storage"]

    class _FakeBrowser:
        contexts: list[_FakeContext] = []

        async def new_context(self) -> _FakeContext:
            return _FakeContext()

        async def close(self) -> None:
            return None

    class _FakeChromium:
        async def connect_over_cdp(self, _: str) -> _FakeBrowser:
            if state["fail_open"]:
                raise RuntimeError("CDP unreachable")
            return _FakeBrowser()

    class _FakePlaywright:
        chromium = _FakeChromium()

        async def stop(self) -> None:
            return None

    class _FakePlaywrightContextManager:
        async def start(self) -> _FakePlaywright:
            return _FakePlaywright()

    def _async_playwright() -> _FakePlaywrightContextManager:
        return _FakePlaywrightContextManager()

    import playwright.async_api as pw_module

    monkeypatch.setattr(pw_module, "async_playwright", _async_playwright)

    # Page url is read once at __init__, but get_session reads
    # ``session._page.url`` so we monkeypatch the property too.
    def _set_url(new_url: str) -> None:
        state["url"] = new_url

    state["set_url"] = _set_url
    return state


def test_start_returns_session_and_public_url(
    client: TestClient, patched_browser: dict[str, Any]
) -> None:
    token = bootstrap_login(client)
    response = client.post(
        "/api/google/notebooklm/auth/start", headers=auth_header(token)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["purpose"] == "notebooklm"
    assert body["public_url"].startswith("http")
    assert body["target_url"].startswith("https://notebooklm.google.com")


def test_poll_flips_to_ready_when_url_matches(
    client: TestClient, patched_browser: dict[str, Any]
) -> None:
    token = bootstrap_login(client)
    start = client.post(
        "/api/google/notebooklm/auth/start", headers=auth_header(token)
    ).json()

    # Simulate the user finishing the login → page url moves to NLM.
    from app.config import get_settings
    from app.services.browser_session import get_manager

    mgr = get_manager(get_settings())
    assert mgr._session is not None
    mgr._session._page.url = "https://notebooklm.google.com/u/0/"

    response = client.get(
        f"/api/google/notebooklm/auth/{start['id']}", headers=auth_header(token)
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_google_login_redirect_does_not_trigger_ready(
    client: TestClient, patched_browser: dict[str, Any]
) -> None:
    """Regression: ``accounts.google.com`` URL must NOT flip status to ready.

    Google's sign-in page embeds the post-login destination as
    ``continue=https://notebooklm.google.com/...``. A naive substring
    match would think the user is already on NotebookLM the very first
    time we poll. Status MUST remain ``pending`` until the page url
    actually starts with the NotebookLM origin.
    """
    token = bootstrap_login(client)
    start = client.post(
        "/api/google/notebooklm/auth/start", headers=auth_header(token)
    ).json()

    from app.config import get_settings
    from app.services.browser_session import get_manager

    mgr = get_manager(get_settings())
    assert mgr._session is not None
    mgr._session._page.url = (
        "https://accounts.google.com/v3/signin/identifier?"
        "continue=https%3A%2F%2Fnotebooklm.google.com%2F"
    )

    response = client.get(
        f"/api/google/notebooklm/auth/{start['id']}", headers=auth_header(token)
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


def test_save_writes_storage_state_to_disk(
    client: TestClient, patched_browser: dict[str, Any]
) -> None:
    token = bootstrap_login(client)
    start = client.post(
        "/api/google/notebooklm/auth/start", headers=auth_header(token)
    ).json()

    from app.config import get_settings
    from app.services.browser_session import get_manager

    mgr = get_manager(get_settings())
    assert mgr._session is not None
    mgr._session._page.url = "https://notebooklm.google.com/u/0/"

    response = client.post(
        f"/api/google/notebooklm/auth/{start['id']}/save",
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"

    storage_path = parser_files.notebooklm_storage_path(1)
    assert storage_path.exists()
    saved = json.loads(storage_path.read_text())
    assert saved == {"cookies": [{"name": "demo", "value": "ok"}]}


def test_save_rejects_when_status_not_ready(
    client: TestClient, patched_browser: dict[str, Any]
) -> None:
    token = bootstrap_login(client)
    start = client.post(
        "/api/google/notebooklm/auth/start", headers=auth_header(token)
    ).json()

    response = client.post(
        f"/api/google/notebooklm/auth/{start['id']}/save",
        headers=auth_header(token),
    )
    assert response.status_code == 400
    # disk should still be empty.
    assert not parser_files.notebooklm_storage_path(1).exists()


def test_cancel_clears_session(
    client: TestClient, patched_browser: dict[str, Any]
) -> None:
    token = bootstrap_login(client)
    start = client.post(
        "/api/google/notebooklm/auth/start", headers=auth_header(token)
    ).json()

    response = client.post(
        f"/api/google/notebooklm/auth/{start['id']}/cancel",
        headers=auth_header(token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_other_user_cant_see_session(
    client: TestClient, patched_browser: dict[str, Any]
) -> None:
    """Session id is per-user — second user gets 404 on someone else's session."""
    admin_token = bootstrap_login(client)
    start = client.post(
        "/api/google/notebooklm/auth/start", headers=auth_header(admin_token)
    ).json()

    # Create a second user (admin can register others).
    create_resp = client.post(
        "/api/users",
        json={"username": "alice", "password": "alicepwd123"},
        headers=auth_header(admin_token),
    )
    assert create_resp.status_code == 201, create_resp.text

    alice_login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alicepwd123"},
    ).json()
    alice_token = alice_login["access_token"]

    # Alice can't poll admin's session.
    response = client.get(
        f"/api/google/notebooklm/auth/{start['id']}",
        headers=auth_header(alice_token),
    )
    assert response.status_code == 404

    # And starting a new session while admin's is still active errors with 409.
    response = client.post(
        "/api/google/notebooklm/auth/start", headers=auth_header(alice_token)
    )
    assert response.status_code == 409


def test_other_user_can_take_over_idle_session(
    client: TestClient, patched_browser: dict[str, Any]
) -> None:
    """A second user must be able to start a session once the first is idle.

    Without an idle-takeover threshold a single abandoned tab would
    pin the shared Chromium for the full ``SESSION_TIMEOUT_SECONDS``
    (10 minutes). We simulate the abandonment by rewinding
    ``last_polled_at`` past ``SESSION_IDLE_TAKEOVER_SECONDS`` and
    confirm Alice's start now succeeds.
    """
    from app.config import get_settings
    from app.services.browser_session import (
        SESSION_IDLE_TAKEOVER_SECONDS,
        get_manager,
    )

    admin_token = bootstrap_login(client)
    admin_start = client.post(
        "/api/google/notebooklm/auth/start", headers=auth_header(admin_token)
    ).json()

    create_resp = client.post(
        "/api/users",
        json={"username": "alice", "password": "alicepwd123"},
        headers=auth_header(admin_token),
    )
    assert create_resp.status_code == 201

    alice_login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alicepwd123"},
    ).json()
    alice_token = alice_login["access_token"]

    # Backdate the heartbeat so the manager treats the session as abandoned.
    mgr = get_manager(get_settings())
    assert mgr._session is not None
    mgr._session.last_polled_at -= SESSION_IDLE_TAKEOVER_SECONDS + 5

    response = client.post(
        "/api/google/notebooklm/auth/start", headers=auth_header(alice_token)
    )
    assert response.status_code == 200, response.text
    new_session = response.json()
    assert new_session["id"] != admin_start["id"]
    assert new_session["status"] in ("pending", "loading")


def test_deleting_user_cancels_their_browser_session(
    client: TestClient, patched_browser: dict[str, Any]
) -> None:
    """Regression: deleting a user mid-login must free the shared Chromium.

    Otherwise the orphaned session pins the slot until the 10-minute
    timeout, blocking every other user from authenticating in the
    meantime.
    """
    from app.config import get_settings
    from app.services.browser_session import get_manager

    admin_token = bootstrap_login(client)

    create_resp = client.post(
        "/api/users",
        json={"username": "bob", "password": "bobpwd123"},
        headers=auth_header(admin_token),
    )
    assert create_resp.status_code == 201
    bob_id = create_resp.json()["id"]

    bob_token = client.post(
        "/api/auth/login",
        json={"username": "bob", "password": "bobpwd123"},
    ).json()["access_token"]

    # Bob starts an auth session, then admin nukes Bob's account.
    bob_session = client.post(
        "/api/google/notebooklm/auth/start", headers=auth_header(bob_token)
    ).json()
    mgr = get_manager(get_settings())
    assert mgr._session is not None
    assert mgr._session.user_id == bob_id
    assert mgr._session.is_active

    delete_resp = client.delete(
        f"/api/users/{bob_id}", headers=auth_header(admin_token)
    )
    assert delete_resp.status_code == 204, delete_resp.text

    # Manager session is torn down — admin can immediately start a fresh one.
    assert mgr._session is None or not mgr._session.is_active

    admin_session = client.post(
        "/api/google/notebooklm/auth/start", headers=auth_header(admin_token)
    )
    assert admin_session.status_code == 200, admin_session.text
    assert admin_session.json()["id"] != bob_session["id"]
