"""Проверки групп и порядка."""

import pathlib

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app

client = TestClient(app)
_login = client.post("/api/v1/auth/login", json={"login": "admin", "password": "admin"})
client.headers["X-CSRF-Token"] = _login.json()["csrf"]
anon = TestClient(app)
AUTH = ("admin", "admin")


@pytest.fixture
def groups_db(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "groups.db")
    db.init_db()
    fresh = client.post("/api/v1/auth/login", json={"login": "admin", "password": "admin"})
    client.headers["X-CSRF-Token"] = fresh.json()["csrf"]
    yield


def test_groups_crud(groups_db) -> None:
    created = client.post("/api/v1/groups", json={"name": "Медиа"}, auth=AUTH)
    assert created.status_code == 201
    group_id = created.json()["group"]["id"]

    listed = client.get("/api/v1/groups", auth=AUTH).json()["groups"]
    assert [item["name"] for item in listed] == ["Медиа"]

    renamed = client.patch(
        f"/api/v1/groups/{group_id}", json={"name": "Медиа и кино"}, auth=AUTH
    )
    assert renamed.status_code == 200
    assert renamed.json()["group"]["name"] == "Медиа и кино"

    deleted = client.delete(f"/api/v1/groups/{group_id}", auth=AUTH)
    assert deleted.status_code == 200
    assert client.get("/api/v1/groups", auth=AUTH).json()["groups"] == []


def test_group_name_conflict(groups_db) -> None:
    client.post("/api/v1/groups", json={"name": "Дом"}, auth=AUTH)
    response = client.post("/api/v1/groups", json={"name": "Дом"}, auth=AUTH)
    assert response.status_code == 409


def test_reorder_groups(groups_db) -> None:
    first = client.post("/api/v1/groups", json={"name": "A"}, auth=AUTH).json()["group"]["id"]
    second = client.post("/api/v1/groups", json={"name": "B"}, auth=AUTH).json()["group"]["id"]
    response = client.post("/api/v1/groups/reorder", json={"ids": [second, first]}, auth=AUTH)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["groups"]] == [second, first]


def test_assign_container(groups_db) -> None:
    created = client.post("/api/v1/groups", json={"name": "Медиа"}, auth=AUTH)
    group_id = created.json()["group"]["id"]
    response = client.post(
        "/api/v1/containers/miniflux/group",
        json={"group_id": group_id},
        auth=AUTH,
    )
    assert response.status_code == 200
    assert db.group_map()["miniflux"]["id"] == group_id

    response = client.post(
        "/api/v1/containers/miniflux/group", json={"group_id": None}, auth=AUTH
    )
    assert response.status_code == 200
    assert "miniflux" not in db.group_map()


def test_assign_unknown_group(groups_db) -> None:
    response = client.post(
        "/api/v1/containers/x/group", json={"group_id": 999}, auth=AUTH
    )
    assert response.status_code == 404
