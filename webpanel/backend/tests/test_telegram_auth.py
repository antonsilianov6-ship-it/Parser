"""Tests for the Telethon-backed authorisation flow.

Telethon itself is replaced with an in-memory fake that records the calls the
service makes, so we can exercise the full router → service wiring without
hitting real Telegram.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from app.services import telegram_auth as tg_auth
from tests.conftest import auth_header, bootstrap_login


@dataclass
class _SentCode:
    phone_code_hash: str = "hash-" + "x" * 24


class _FakeClient:
    """Minimal stand-in for :class:`telethon.TelegramClient`.

    Each instance records its constructor args and the calls made on it; the
    module-level :data:`FAKE_STATE` holds programmable outcomes.
    """

    def __init__(self, session_path: str, api_id: int, api_hash: str) -> None:
        self.session_path = session_path
        self.api_id = api_id
        self.api_hash = api_hash
        FAKE_STATE.instances.append(self)
        self._connected = False
        self._authorized = False

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def send_code_request(self, phone: str) -> _SentCode:
        FAKE_STATE.phones_sent.append(phone)
        if FAKE_STATE.send_code_exc is not None:
            raise FAKE_STATE.send_code_exc
        return _SentCode()

    async def sign_in(
        self,
        phone: str | None = None,
        code: str | None = None,
        phone_code_hash: str | None = None,
        password: str | None = None,
    ) -> None:
        FAKE_STATE.sign_in_calls.append(
            {
                "phone": phone,
                "code": code,
                "phone_code_hash": phone_code_hash,
                "password": password,
            }
        )
        if FAKE_STATE.sign_in_exc is not None:
            exc = FAKE_STATE.sign_in_exc
            FAKE_STATE.sign_in_exc = None
            raise exc
        self._authorized = True

    async def is_user_authorized(self) -> bool:
        return self._authorized

    async def log_out(self) -> bool:
        FAKE_STATE.logout_calls += 1
        self._authorized = False
        return True


@dataclass
class _FakeState:
    instances: list[_FakeClient] = field(default_factory=list)
    phones_sent: list[str] = field(default_factory=list)
    sign_in_calls: list[dict[str, str | None]] = field(default_factory=list)
    send_code_exc: Exception | None = None
    sign_in_exc: Exception | None = None
    logout_calls: int = 0


FAKE_STATE: _FakeState = _FakeState()


@pytest.fixture(autouse=True)
def _patch_telethon(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace Telethon's ``TelegramClient`` everywhere the service imports it."""
    global FAKE_STATE
    FAKE_STATE = _FakeState()
    monkeypatch.setattr(tg_auth, "TelegramClient", _FakeClient)
    # Clear any pending state carried over from a previous test.
    tg_auth._pending.clear()
    yield
    tg_auth._pending.clear()


def _create_slot(client: TestClient, token: str, label: str = "main") -> dict:
    response = client.post(
        "/api/telegram/accounts",
        json={"label": label},
        headers=auth_header(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_response_hides_api_hash_column(client: TestClient) -> None:
    token = bootstrap_login(client)
    account = _create_slot(client, token)
    assert account["has_api_hash"] is False
    assert account["api_id"] is None
    assert "api_hash" not in account


def test_send_code_then_verify_marks_authorised(client: TestClient) -> None:
    token = bootstrap_login(client)
    account = _create_slot(client, token)

    sent = client.post(
        f"/api/telegram/accounts/{account['id']}/send-code",
        json={"api_id": 12345, "api_hash": "deadbeefdeadbeef", "phone": "+79990001122"},
        headers=auth_header(token),
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["pending"] is True
    assert sent.json()["expires_in"] == tg_auth.PENDING_TTL_SECONDS

    # State should show api_id + has_api_hash now, hash itself must stay server-side.
    listed = client.get(
        "/api/telegram/accounts", headers=auth_header(token)
    ).json()[0]
    assert listed["api_id"] == 12345
    assert listed["has_api_hash"] is True
    assert "api_hash" not in listed

    verified = client.post(
        f"/api/telegram/accounts/{account['id']}/verify",
        json={"code": "54321"},
        headers=auth_header(token),
    )
    assert verified.status_code == 200, verified.text
    assert verified.json() == {"is_authorized": True, "needs_password": False}

    after = client.get("/api/telegram/accounts", headers=auth_header(token)).json()[0]
    assert after["is_authorized"] is True
    assert FAKE_STATE.sign_in_calls[0]["phone"] == "+79990001122"
    assert FAKE_STATE.sign_in_calls[0]["code"] == "54321"


def test_2fa_password_flow(client: TestClient) -> None:
    from telethon.errors import SessionPasswordNeededError

    token = bootstrap_login(client)
    account = _create_slot(client, token)

    client.post(
        f"/api/telegram/accounts/{account['id']}/send-code",
        json={"api_id": 12345, "api_hash": "deadbeefdead", "phone": "+79990001122"},
        headers=auth_header(token),
    ).raise_for_status()

    # First verify raises 2FA-needed — session stays alive, account stays unauthorised.
    FAKE_STATE.sign_in_exc = SessionPasswordNeededError(request=None)
    step1 = client.post(
        f"/api/telegram/accounts/{account['id']}/verify",
        json={"code": "54321"},
        headers=auth_header(token),
    )
    assert step1.status_code == 200
    assert step1.json() == {"is_authorized": False, "needs_password": True}
    assert client.get("/api/telegram/accounts", headers=auth_header(token)).json()[0][
        "is_authorized"
    ] is False

    # Second verify with the password finishes sign-in.
    step2 = client.post(
        f"/api/telegram/accounts/{account['id']}/verify",
        json={"password": "super-secret"},
        headers=auth_header(token),
    )
    assert step2.status_code == 200
    assert step2.json() == {"is_authorized": True, "needs_password": False}
    assert FAKE_STATE.sign_in_calls[-1]["password"] == "super-secret"


def test_invalid_code_returns_400_and_keeps_pending(client: TestClient) -> None:
    from telethon.errors import PhoneCodeInvalidError

    token = bootstrap_login(client)
    account = _create_slot(client, token)

    client.post(
        f"/api/telegram/accounts/{account['id']}/send-code",
        json={"api_id": 12345, "api_hash": "deadbeefdead", "phone": "+79990001122"},
        headers=auth_header(token),
    ).raise_for_status()

    FAKE_STATE.sign_in_exc = PhoneCodeInvalidError(request=None)
    bad = client.post(
        f"/api/telegram/accounts/{account['id']}/verify",
        json={"code": "00000"},
        headers=auth_header(token),
    )
    assert bad.status_code == 400
    assert bad.json()["detail"] == "Неверный код подтверждения"

    # Pending session is still alive — second attempt succeeds.
    FAKE_STATE.sign_in_exc = None
    ok = client.post(
        f"/api/telegram/accounts/{account['id']}/verify",
        json={"code": "54321"},
        headers=auth_header(token),
    )
    assert ok.status_code == 200
    assert ok.json()["is_authorized"] is True


def test_verify_without_send_code_returns_409(client: TestClient) -> None:
    token = bootstrap_login(client)
    account = _create_slot(client, token)
    response = client.post(
        f"/api/telegram/accounts/{account['id']}/verify",
        json={"code": "54321"},
        headers=auth_header(token),
    )
    assert response.status_code == 409


def test_send_code_maps_bad_api_id(client: TestClient) -> None:
    from telethon.errors import ApiIdInvalidError

    token = bootstrap_login(client)
    account = _create_slot(client, token)

    FAKE_STATE.send_code_exc = ApiIdInvalidError(request=None)
    response = client.post(
        f"/api/telegram/accounts/{account['id']}/send-code",
        json={"api_id": 1, "api_hash": "deadbeefdead", "phone": "+79990001122"},
        headers=auth_header(token),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Неверные API_ID / API_HASH"


def test_logout_clears_authorised_flag(client: TestClient) -> None:
    token = bootstrap_login(client)
    account = _create_slot(client, token)

    client.post(
        f"/api/telegram/accounts/{account['id']}/send-code",
        json={"api_id": 12345, "api_hash": "deadbeefdead", "phone": "+79990001122"},
        headers=auth_header(token),
    ).raise_for_status()
    client.post(
        f"/api/telegram/accounts/{account['id']}/verify",
        json={"code": "54321"},
        headers=auth_header(token),
    ).raise_for_status()

    resp = client.post(
        f"/api/telegram/accounts/{account['id']}/logout",
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_authorized"] is False


def test_only_owner_can_start_auth(client: TestClient) -> None:
    admin_token = bootstrap_login(client)
    client.post(
        "/api/users",
        json={"username": "bob", "password": "password123"},
        headers=auth_header(admin_token),
    )
    bob_token = client.post(
        "/api/auth/login",
        json={"username": "bob", "password": "password123"},
    ).json()["access_token"]

    account = _create_slot(client, admin_token)

    response = client.post(
        f"/api/telegram/accounts/{account['id']}/send-code",
        json={"api_id": 12345, "api_hash": "deadbeefdead", "phone": "+79990001122"},
        headers=auth_header(bob_token),
    )
    assert response.status_code == 403
