"""Пользователи, роли и права."""

import pathlib

import pytest
from fastapi.testclient import TestClient

import app.api.containers as containers_api
from app import db
from app.main import app
from app.providers.docker import Container


def make_client(login: str, password: str) -> tuple[TestClient, str]:
    client = TestClient(app)
    response = client.post("/api/v1/auth/login", json={"login": login, "password": password})
    assert response.status_code == 200, response.text
    return client, response.json()["csrf"]


@pytest.fixture
def users_db(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "users.db")
    db.init_db()
    yield


def test_bootstrap_admin(users_db) -> None:
    client, _ = make_client("admin", "admin")
    me = client.get("/api/v1/auth/me").json()
    assert me["role"] == "superadmin"
    assert "users" in me["permissions"]
    assert db.count_users() == 1


def test_create_user_and_login(users_db) -> None:
    admin, csrf = make_client("admin", "admin")
    response = admin.post(
        "/api/v1/users",
        json={"login": "operator", "password": "secret1", "role": "operator"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 201
    assert response.json()["user"]["role"] == "operator"

    operator, _ = make_client("operator", "secret1")
    me = operator.get("/api/v1/auth/me").json()
    assert me["login"] == "operator"
    assert "control" in me["permissions"]
    assert "manage" not in me["permissions"]


def test_viewer_cannot_install(users_db) -> None:
    admin, csrf = make_client("admin", "admin")
    admin.post(
        "/api/v1/users",
        json={"login": "viewer", "password": "secret1", "role": "viewer"},
        headers={"X-CSRF-Token": csrf},
    )
    viewer, vcsrf = make_client("viewer", "secret1")
    response = viewer.post(
        "/api/v1/containers",
        json={"name": "x", "image": "nginx"},
        headers={"X-CSRF-Token": vcsrf},
    )
    assert response.status_code == 403


def test_operator_can_control(users_db, monkeypatch: pytest.MonkeyPatch) -> None:
    admin, csrf = make_client("admin", "admin")
    admin.post(
        "/api/v1/users",
        json={"login": "operator", "password": "secret1", "role": "operator"},
        headers={"X-CSRF-Token": csrf},
    )

    class Provider:
        async def start(self, container_id: str) -> None:
            pass

    monkeypatch.setattr(containers_api, "provider", lambda: Provider())
    operator, oc = make_client("operator", "secret1")
    response = operator.post(
        "/api/v1/containers/abc/actions/start", headers={"X-CSRF-Token": oc}
    )
    assert response.status_code == 200


def test_operator_cannot_manage_users(users_db) -> None:
    admin, csrf = make_client("admin", "admin")
    admin.post(
        "/api/v1/users",
        json={"login": "operator", "password": "secret1", "role": "operator"},
        headers={"X-CSRF-Token": csrf},
    )
    operator, _ = make_client("operator", "secret1")
    assert operator.get("/api/v1/users").status_code == 403


def test_cannot_delete_last_superadmin(users_db) -> None:
    admin, csrf = make_client("admin", "admin")
    users = admin.get("/api/v1/users").json()["users"]
    response = admin.delete(
        f"/api/v1/users/{users[0]['id']}", headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 400


def test_container_list_for_operator(users_db, monkeypatch: pytest.MonkeyPatch) -> None:
    class Provider:
        async def list_containers(self) -> list[Container]:
            return []

    admin, csrf = make_client("admin", "admin")
    admin.post(
        "/api/v1/users",
        json={"login": "operator", "password": "secret1", "role": "operator"},
        headers={"X-CSRF-Token": csrf},
    )
    monkeypatch.setattr(containers_api, "provider", lambda: Provider())
    operator, _ = make_client("operator", "secret1")
    assert operator.get("/api/v1/containers").status_code == 200

def test_cannot_change_own_role(users_db) -> None:
    admin, csrf = make_client("admin", "admin")
    me = admin.get("/api/v1/auth/me").json()
    users = admin.get("/api/v1/users").json()["users"]
    me_id = next(user["id"] for user in users if user["login"] == me["login"])
    response = admin.patch(
        f"/api/v1/users/{me_id}",
        json={"role": "viewer"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 400


def test_change_own_password(users_db) -> None:
    admin, csrf = make_client("admin", "admin")
    response = admin.post(
        "/api/v1/auth/password",
        json={"current": "admin", "password": "newpass1"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    assert admin.get("/api/v1/auth/me").status_code == 401

    old = TestClient(app).post(
        "/api/v1/auth/login", json={"login": "admin", "password": "admin"}
    )
    assert old.status_code == 401

    new, _ = make_client("admin", "newpass1")
    assert new.get("/api/v1/auth/me").status_code == 200
