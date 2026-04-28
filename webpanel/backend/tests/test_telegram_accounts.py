from fastapi.testclient import TestClient

from tests.conftest import auth_header, bootstrap_login


def _login_second_user(client: TestClient, admin_token: str) -> str:
    client.post(
        "/api/users",
        json={"username": "bob", "password": "password123"},
        headers=auth_header(admin_token),
    )
    response = client.post(
        "/api/auth/login",
        json={"username": "bob", "password": "password123"},
    )
    return response.json()["access_token"]


def test_create_account_stores_metadata(client: TestClient) -> None:
    token = bootstrap_login(client)
    response = client.post(
        "/api/telegram/accounts",
        json={"label": "main", "phone": "+79990001122", "is_shared": False},
        headers=auth_header(token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["label"] == "main"
    assert body["is_authorized"] is False
    assert body["is_shared"] is False
    assert body["session_path"].endswith("_main.session")


def test_duplicate_label_for_same_owner_rejected(client: TestClient) -> None:
    token = bootstrap_login(client)
    client.post(
        "/api/telegram/accounts",
        json={"label": "main"},
        headers=auth_header(token),
    )
    response = client.post(
        "/api/telegram/accounts",
        json={"label": "main"},
        headers=auth_header(token),
    )
    assert response.status_code == 409


def test_list_returns_owned_and_shared_accounts(client: TestClient) -> None:
    admin_token = bootstrap_login(client)
    bob_token = _login_second_user(client, admin_token)

    # Admin creates private and shared accounts.
    private = client.post(
        "/api/telegram/accounts",
        json={"label": "private", "is_shared": False},
        headers=auth_header(admin_token),
    ).json()
    shared = client.post(
        "/api/telegram/accounts",
        json={"label": "shared", "is_shared": True},
        headers=auth_header(admin_token),
    ).json()

    # Bob creates his own account.
    bobs_own = client.post(
        "/api/telegram/accounts",
        json={"label": "bobs"},
        headers=auth_header(bob_token),
    ).json()

    bob_view = client.get(
        "/api/telegram/accounts",
        headers=auth_header(bob_token),
    ).json()
    labels = {entry["label"] for entry in bob_view}
    assert labels == {"shared", "bobs"}
    ids = {entry["id"] for entry in bob_view}
    assert private["id"] not in ids
    assert shared["id"] in ids
    assert bobs_own["id"] in ids


def test_only_owner_can_update(client: TestClient) -> None:
    admin_token = bootstrap_login(client)
    bob_token = _login_second_user(client, admin_token)
    account = client.post(
        "/api/telegram/accounts",
        json={"label": "main", "is_shared": True},
        headers=auth_header(admin_token),
    ).json()

    response = client.patch(
        f"/api/telegram/accounts/{account['id']}",
        json={"is_shared": False},
        headers=auth_header(bob_token),
    )
    assert response.status_code == 403


def test_only_owner_can_delete(client: TestClient) -> None:
    admin_token = bootstrap_login(client)
    bob_token = _login_second_user(client, admin_token)
    account = client.post(
        "/api/telegram/accounts",
        json={"label": "main"},
        headers=auth_header(admin_token),
    ).json()

    forbidden = client.delete(
        f"/api/telegram/accounts/{account['id']}",
        headers=auth_header(bob_token),
    )
    assert forbidden.status_code == 403

    allowed = client.delete(
        f"/api/telegram/accounts/{account['id']}",
        headers=auth_header(admin_token),
    )
    assert allowed.status_code == 204


def test_share_toggle(client: TestClient) -> None:
    token = bootstrap_login(client)
    account = client.post(
        "/api/telegram/accounts",
        json={"label": "main", "is_shared": False},
        headers=auth_header(token),
    ).json()

    updated = client.patch(
        f"/api/telegram/accounts/{account['id']}",
        json={"is_shared": True, "label": "main-renamed"},
        headers=auth_header(token),
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["is_shared"] is True
    assert body["label"] == "main-renamed"
