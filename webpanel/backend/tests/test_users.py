from fastapi.testclient import TestClient

from tests.conftest import auth_header, bootstrap_login


def test_bootstrap_creates_first_user(client: TestClient) -> None:
    response = client.post(
        "/api/users/bootstrap",
        json={"username": "admin", "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "admin"
    assert body["id"] is not None


def test_bootstrap_rejected_when_user_exists(client: TestClient) -> None:
    bootstrap_login(client)
    response = client.post(
        "/api/users/bootstrap",
        json={"username": "second", "password": "password123"},
    )
    assert response.status_code == 409


def test_create_user_requires_auth(client: TestClient) -> None:
    bootstrap_login(client)
    response = client.post(
        "/api/users",
        json={"username": "bob", "password": "password123"},
    )
    assert response.status_code == 401


def test_authenticated_user_can_invite(client: TestClient) -> None:
    token = bootstrap_login(client)
    response = client.post(
        "/api/users",
        json={"username": "bob", "password": "password123"},
        headers=auth_header(token),
    )
    assert response.status_code == 201
    assert response.json()["username"] == "bob"


def test_duplicate_username_rejected(client: TestClient) -> None:
    token = bootstrap_login(client, username="admin")
    response = client.post(
        "/api/users",
        json={"username": "admin", "password": "password123"},
        headers=auth_header(token),
    )
    assert response.status_code == 409


def test_list_users(client: TestClient) -> None:
    token = bootstrap_login(client)
    client.post(
        "/api/users",
        json={"username": "bob", "password": "password123"},
        headers=auth_header(token),
    )
    response = client.get("/api/users", headers=auth_header(token))
    assert response.status_code == 200
    usernames = {entry["username"] for entry in response.json()}
    assert usernames == {"admin", "bob"}


def test_cannot_delete_last_user(client: TestClient) -> None:
    token = bootstrap_login(client)
    me = client.get("/api/auth/me", headers=auth_header(token)).json()
    response = client.delete(f"/api/users/{me['id']}", headers=auth_header(token))
    assert response.status_code == 400


def test_cannot_delete_self(client: TestClient) -> None:
    token = bootstrap_login(client)
    client.post(
        "/api/users",
        json={"username": "bob", "password": "password123"},
        headers=auth_header(token),
    )
    me = client.get("/api/auth/me", headers=auth_header(token)).json()
    response = client.delete(f"/api/users/{me['id']}", headers=auth_header(token))
    assert response.status_code == 400


def test_can_delete_other_user(client: TestClient) -> None:
    token = bootstrap_login(client)
    bob = client.post(
        "/api/users",
        json={"username": "bob", "password": "password123"},
        headers=auth_header(token),
    ).json()
    response = client.delete(f"/api/users/{bob['id']}", headers=auth_header(token))
    assert response.status_code == 204
    remaining = client.get("/api/users", headers=auth_header(token)).json()
    assert {u["username"] for u in remaining} == {"admin"}


def test_patch_user_updates_password_and_status(client: TestClient) -> None:
    token = bootstrap_login(client)
    bob = client.post(
        "/api/users",
        json={"username": "bob", "password": "password123"},
        headers=auth_header(token),
    ).json()
    response = client.patch(
        f"/api/users/{bob['id']}",
        json={"password": "newpassword456", "is_active": False},
        headers=auth_header(token),
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    # Deactivated user can no longer log in
    login = client.post(
        "/api/auth/login",
        json={"username": "bob", "password": "newpassword456"},
    )
    assert login.status_code == 401
