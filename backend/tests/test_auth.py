"""Вход, сессии и CSRF."""

from fastapi.testclient import TestClient

from app.main import app

AUTH = ("admin", "admin")


def test_login_bad_password() -> None:
    client = TestClient(app)
    response = client.post("/api/v1/auth/login", json={"login": "admin", "password": "wrong"})
    assert response.status_code == 401


def test_login_and_me() -> None:
    client = TestClient(app)
    response = client.post("/api/v1/auth/login", json={"login": "admin", "password": "admin"})
    assert response.status_code == 200
    body = response.json()
    assert body["login"] == "admin"
    assert body["role"] == "superadmin"
    assert body["csrf"]

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["login"] == "admin"


def test_me_requires_session() -> None:
    client = TestClient(app)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_csrf_required() -> None:
    client = TestClient(app)
    login = client.post("/api/v1/auth/login", json={"login": "admin", "password": "admin"})
    csrf = login.json()["csrf"]

    response = client.post("/api/v1/groups", json={"name": "Без токена"})
    assert response.status_code == 403

    response = client.post(
        "/api/v1/groups", json={"name": "С токеном"}, headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 201


def test_logout() -> None:
    client = TestClient(app)
    login = client.post("/api/v1/auth/login", json={"login": "admin", "password": "admin"})
    csrf = login.json()["csrf"]
    response = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401
