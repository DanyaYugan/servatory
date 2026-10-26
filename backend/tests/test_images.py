"""Поиск образов: разбор ответов и API."""

import pytest
from fastapi.testclient import TestClient

import app.api.images as images_api
from app.images import parse_search, parse_tags
from app.main import app

client = TestClient(app)
_login = client.post("/api/v1/auth/login", json={"login": "admin", "password": "admin"})
client.headers["X-CSRF-Token"] = _login.json()["csrf"]

SEARCH_PAYLOAD = {
    "results": [
        {
            "repo_name": "louislam/uptime-kuma",
            "short_description": "monitoring",
            "star_count": 741,
            "pull_count": 195000000,
            "is_official": False,
        }
    ]
}


def test_parse_search() -> None:
    results = parse_search(SEARCH_PAYLOAD)
    assert results[0]["name"] == "louislam/uptime-kuma"
    assert results[0]["stars"] == 741
    assert results[0]["official"] is False


def test_parse_tags() -> None:
    assert parse_tags({"results": [{"name": "1"}, {"name": "latest"}]}) == ["1", "latest"]


def test_search_requires_auth() -> None:
    anonymous = TestClient(app)
    assert anonymous.get("/api/v1/images/search?q=nginx").status_code == 401


def test_search_api(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_search(query: str, limit: int = 10) -> list[dict]:
        return parse_search(SEARCH_PAYLOAD)

    monkeypatch.setattr(images_api.images, "search", fake_search)
    response = client.get("/api/v1/images/search?q=uptime")
    assert response.status_code == 200
    assert response.json()["results"][0]["name"] == "louislam/uptime-kuma"


def test_tags_api(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_tags(name: str, limit: int = 20) -> list[str]:
        return ["1", "latest"]

    monkeypatch.setattr(images_api.images, "tags", fake_tags)
    response = client.get("/api/v1/images/tags?name=louislam/uptime-kuma")
    assert response.status_code == 200
    assert response.json()["tags"] == ["1", "latest"]


def test_short_query_rejected() -> None:
    assert client.get("/api/v1/images/search?q=n").status_code == 422
