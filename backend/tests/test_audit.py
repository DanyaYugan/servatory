"""Журнал действий и проверки работоспособности."""

import pathlib

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.providers.docker import decode_logs


@pytest.fixture
def users_db(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "audit.db")
    db.init_db()
    yield


def make_client(login: str = "admin", password: str = "admin") -> tuple[TestClient, str]:
    client = TestClient(app)
    response = client.post("/api/v1/auth/login", json={"login": login, "password": password})
    assert response.status_code == 200, response.text
    return client, response.json()["csrf"]


def test_audit_login(users_db) -> None:
    client, _ = make_client()
    items = client.get("/api/v1/audit").json()["items"]
    assert any(item["action"] == "вход" for item in items)


def test_operator_cannot_read_audit(users_db) -> None:
    admin, csrf = make_client()
    admin.post(
        "/api/v1/users",
        json={"login": "operator", "password": "secret1", "role": "operator"},
        headers={"X-CSRF-Token": csrf},
    )
    operator, _ = make_client("operator", "secret1")
    assert operator.get("/api/v1/audit").status_code == 403


def test_check_crud(users_db) -> None:
    client, csrf = make_client()
    response = client.put(
        "/api/v1/containers/demo/check",
        json={"url": "http://example.com", "interval": 60, "enabled": True},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    check = client.get("/api/v1/containers/demo/check").json()["check"]
    assert check["url"] == "http://example.com"

    response = client.put(
        "/api/v1/containers/demo/check",
        json={"url": "ftp://x", "interval": 60},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 400

    assert client.delete(
        "/api/v1/containers/demo/check", headers={"X-CSRF-Token": csrf}
    ).status_code == 200
    assert client.get("/api/v1/containers/demo/check").json()["check"] is None


def test_decode_logs_plain() -> None:
    assert decode_logs(b"hello\n") == "hello\n"


def test_decode_logs_frames() -> None:
    payload = b"\x01\x00\x00\x00\x00\x00\x00\x05hello"
    assert decode_logs(payload) == "hello"
