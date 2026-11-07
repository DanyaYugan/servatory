"""Профиль панели и служебные настройки."""

import pathlib

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture
def system_db(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "system.db")
    db.init_db()
    yield


def make_client() -> tuple[TestClient, str]:
    client = TestClient(app)
    response = client.post("/api/v1/auth/login", json={"login": "admin", "password": "admin"})
    assert response.status_code == 200, response.text
    return client, response.json()["csrf"]


def test_profile_defaults(system_db) -> None:
    client, _ = make_client()
    body = client.get("/api/v1/system/profile").json()
    assert body["panel_name"] == "Servatory"
    assert body["onboarded"] is False


def test_profile_save(system_db) -> None:
    client, csrf = make_client()
    response = client.patch(
        "/api/v1/system/profile",
        json={
            "panel_name": "Домашняя панель",
            "public_url": "https://panel.example.com",
            "onboarded": True,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    body = client.get("/api/v1/system/profile").json()
    assert body["panel_name"] == "Домашняя панель"
    assert body["public_url"] == "https://panel.example.com"
    assert body["onboarded"] is True


def test_profile_bad_url(system_db) -> None:
    client, csrf = make_client()
    response = client.patch(
        "/api/v1/system/profile",
        json={"panel_name": "x", "public_url": "ftp://x", "onboarded": True},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 400
