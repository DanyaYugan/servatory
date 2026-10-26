"""Разбор docker-compose YAML и подсказки из README."""

import pytest

from app.compose import ComposeError, parse_compose
from app.image_hints import extract_hints

COMPOSE = """
services:
  app:
    image: nginx:alpine
    ports:
      - "8084:80"
    volumes:
      - ./data:/data
    environment:
      TZ: UTC
    restart: always
"""

README = """
```yaml
services:
  uptime-kuma:
    image: louislam/uptime-kuma:1
    ports:
      - 3001:3001
    volumes:
      - ./uptime-kuma:/app/data
```
"""


def test_parse_compose() -> None:
    spec = parse_compose(COMPOSE)
    assert spec.name == "app"
    assert spec.image == "nginx:alpine"
    assert spec.ports == [(8084, 80, "tcp")]
    assert spec.volumes == ["data:/data"]
    assert spec.env == {"TZ": "UTC"}
    assert spec.restart == "always"


def test_compose_one_service_only() -> None:
    text = """
services:
  a:
    image: nginx
  b:
    image: redis
"""
    with pytest.raises(ComposeError):
        parse_compose(text)


def test_compose_requires_image() -> None:
    with pytest.raises(ComposeError):
        parse_compose("services:\n  app:\n    ports: ['80:80']")


def test_compose_requires_services() -> None:
    with pytest.raises(ComposeError):
        parse_compose("image: nginx")


def test_extract_hints() -> None:
    hints = extract_hints(README)
    assert any(port.startswith("3001:3001") for port in hints["ports"])
    assert "uptime-kuma:/app/data" in hints["volumes"]
