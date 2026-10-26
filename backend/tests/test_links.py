"""Ссылки на сервисы: автоматическая и своя."""

import pathlib

import pytest
from fastapi.testclient import TestClient

import app.api.containers as containers_api
from app import db
from app.main import app
from app.providers.docker import parse_container

client = TestClient(app)
_login = client.post("/api/v1/auth/login", json={"login": "admin", "password": "admin"})
client.headers["X-CSRF-Token"] = _login.json()["csrf"]
anon = TestClient(app)
AUTH = ("admin", "admin")

RAW = {
    "Id": "id1234567890",
    "Names": ["/web"],
    "Image": "nginx:alpine",
    "State": "running",
    "Status": "Up",
    "Created": 1700000000,
    "Ports": [{"PrivatePort": 80, "PublicPort": 8080, "Type": "tcp"}],
    "Labels": {},
}


class FakeProvider:
    async def list_containers(self):
        return [parse_container(RAW)]


@pytest.fixture
def links_db(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "links.db")
    db.init_db()
    monkeypatch.setattr(containers_api, "provider", lambda: FakeProvider())
    fresh = client.post(
        "/api/v1/auth/login", json={"login": "admin", "password": "admin"}
    )
    client.headers["X-CSRF-Token"] = fresh.json()["csrf"]
    yield


def test_default_link_uses_host_and_port(links_db) -> None:
    body = client.get("/api/v1/containers", auth=AUTH).json()
    item = body["containers"][0]
    assert item["link"] == "http://testserver:8080"
    assert item["link_custom"] is False


def test_custom_link_overrides(links_db) -> None:
    response = client.post(
        "/api/v1/containers/web/link",
        json={"url": "https://example.com/web"},
        auth=AUTH,
    )
    assert response.status_code == 200
    item = client.get("/api/v1/containers", auth=AUTH).json()["containers"][0]
    assert item["link"] == "https://example.com/web"
    assert item["link_custom"] is True


def test_empty_link_returns_default(links_db) -> None:
    client.post("/api/v1/containers/web/link", json={"url": "https://x.test"}, auth=AUTH)
    client.post("/api/v1/containers/web/link", json={"url": ""}, auth=AUTH)
    item = client.get("/api/v1/containers", auth=AUTH).json()["containers"][0]
    assert item["link"] == "http://testserver:8080"
    assert item["link_custom"] is False


def test_any_link_allowed(links_db) -> None:
    response = client.post(
        "/api/v1/containers/web/link", json={"url": "ftp://x"}, auth=AUTH
    )
    assert response.status_code == 200


def test_link_requires_auth(links_db) -> None:
    response = anon.post("/api/v1/containers/web/link", json={"url": ""})
    assert response.status_code == 401
