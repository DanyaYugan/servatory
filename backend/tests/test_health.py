"""Базовые проверки каркаса."""

from fastapi.testclient import TestClient

from app.main import app
from app.version import __version__

client = TestClient(app)
_login = client.post("/api/v1/auth/login", json={"login": "admin", "password": "admin"})
client.headers["X-CSRF-Token"] = _login.json()["csrf"]
anon = TestClient(app)


def test_health_open() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__


def test_ready_open() -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_meta_requires_auth() -> None:
    response = anon.get("/api/v1/meta")
    assert response.status_code == 401


def test_meta_with_auth() -> None:
    response = client.get("/api/v1/meta")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == __version__
    assert body["schema"] >= 1
    assert "user" not in body


def test_wrong_password_rejected() -> None:
    response = anon.post(
        "/api/v1/auth/login", json={"login": "admin", "password": "wrong"}
    )
    assert response.status_code == 401
