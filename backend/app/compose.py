"""Разбор docker-compose YAML для установки сервиса.

Поддерживается один сервис: имя, образ, порты, тома, переменные, restart.
"""

from __future__ import annotations

import yaml

from app.providers.docker import NewContainer


class ComposeError(ValueError):
    """YAML не подходит для установки."""


def _ports(items: object) -> list[tuple[int, int, str]]:
    result: list[tuple[int, int, str]] = []
    for item in items or []:
        text = str(item)
        body, _, kind = text.partition("/")
        kind = kind or "tcp"
        parts = body.split(":")
        if len(parts) == 1:
            public = private = parts[0]
        elif len(parts) == 2:
            public, private = parts
        elif len(parts) == 3:
            public, private = parts[1], parts[2]
        else:
            raise ComposeError(f"непонятный порт: {text}")
        if not public.isdigit() or not private.isdigit():
            raise ComposeError(f"непонятный порт: {text}")
        result.append((int(public), int(private), kind))
    return result


def _volumes(items: object) -> list[str]:
    result: list[str] = []
    for item in items or []:
        text = str(item)
        source, sep, target = text.partition(":")
        if not sep:
            raise ComposeError(f"том должен быть в виде источник:/путь: {text}")
        if source.startswith("./"):
            source = source[2:]
        result.append(f"{source}:{target}")
    return result


def _env(items: object) -> dict[str, str]:
    if isinstance(items, dict):
        return {str(key): "" if value is None else str(value) for key, value in items.items()}
    result: dict[str, str] = {}
    for item in items or []:
        key, sep, value = str(item).partition("=")
        if not sep:
            raise ComposeError(f"переменная должна быть KEY=VALUE: {item}")
        result[key] = value
    return result


def parse_compose(text: str, name: str | None = None) -> NewContainer:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ComposeError(f"не удалось разобрать YAML: {exc}") from exc
    if not isinstance(data, dict) or "services" not in data:
        raise ComposeError("нужен блок services")

    services = data.get("services") or {}
    if not isinstance(services, dict) or not services:
        raise ComposeError("в services нет сервисов")
    if len(services) > 1:
        raise ComposeError("пока поддерживается один сервис в YAML")

    service_name, service = next(iter(services.items()))
    if not isinstance(service, dict):
        raise ComposeError("сервис должен быть объектом")
    image = service.get("image")
    if not image:
        raise ComposeError("у сервиса нет image")

    container_name = name or service.get("container_name") or service_name
    return NewContainer(
        name=str(container_name),
        image=str(image),
        ports=_ports(service.get("ports")),
        volumes=_volumes(service.get("volumes")),
        env=_env(service.get("environment")),
        restart=str(service.get("restart") or "unless-stopped"),
    )
