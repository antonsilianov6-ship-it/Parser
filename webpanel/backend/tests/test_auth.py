from fastapi.testclient import TestClient

from tests.conftest import auth_header, bootstrap_login


def test_login_rejects_unknown_user(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "nobody", "password": "whatever12"},
    )
    assert response.status_code == 401


def test_login_rejects_bad_password(client: TestClient) -> None:
    client.post(
        "/api/users/bootstrap",
        json={"username": "admin", "password": "correct-horse"},
    )
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_login_issues_token_and_me_returns_user(client: TestClient) -> None:
    token = bootstrap_login(client, "admin", "password123")
    response = client.get("/api/auth/me", headers=auth_header(token))
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "admin"
    assert body["is_active"] is True


def test_me_requires_auth(client: TestClient) -> None:
    response = client.get("/api/auth/me")
    assert response.status_code == 401
