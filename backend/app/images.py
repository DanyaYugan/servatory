"""Поиск образов на Docker Hub с кешем."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.image_hints import extract_hints

CACHE_TTL = 300
_cache: dict[str, tuple[float, Any]] = {}


class ImageError(RuntimeError):
    """Docker Hub недоступен."""


def parse_search(payload: dict) -> list[dict]:
    results = []
    for item in payload.get("results") or []:
        results.append(
            {
                "name": str(item.get("repo_name", "")),
                "description": str(item.get("short_description") or ""),
                "stars": int(item.get("star_count") or 0),
                "pulls": int(item.get("pull_count") or 0),
                "official": bool(item.get("is_official")),
            }
        )
    return results


def parse_tags(payload: dict) -> list[str]:
    return [str(item.get("name", "")) for item in payload.get("results") or []]


def _cached(key: str) -> Any | None:
    item = _cache.get(key)
    if not item:
        return None
    created, value = item
    if time.time() - created > CACHE_TTL:
        _cache.pop(key, None)
        return None
    return value


def _store(key: str, value: Any) -> Any:
    _cache[key] = (time.time(), value)
    return value


async def _get(path: str, params: dict) -> dict:
    try:
        async with httpx.AsyncClient(base_url="https://hub.docker.com", timeout=10) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise ImageError(f"Docker Hub недоступен: {exc}") from exc


async def search(query: str, limit: int = 10) -> list[dict]:
    key = f"search:{query}:{limit}"
    cached = _cached(key)
    if cached is not None:
        return cached
    payload = await _get(
        "/v2/search/repositories/", {"query": query, "page_size": limit}
    )
    return _store(key, parse_search(payload))


async def tags(name: str, limit: int = 20) -> list[str]:
    key = f"tags:{name}:{limit}"
    cached = _cached(key)
    if cached is not None:
        return cached
    payload = await _get(
        f"/v2/repositories/{name}/tags",
        {"page_size": limit, "ordering": "last_updated"},
    )
    return _store(key, parse_tags(payload))


async def details(name: str) -> dict:
    key = f"details:{name}"
    cached = _cached(key)
    if cached is not None:
        return cached
    payload = await _get(f"/v2/repositories/{name}/", {})
    result = {
        "name": name,
        "description": str(payload.get("short_description") or ""),
        "hints": extract_hints(str(payload.get("full_description") or "")),
    }
    return _store(key, result)
