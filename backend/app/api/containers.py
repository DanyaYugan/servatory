"""Эндпоинты контейнеров: список, действия, установка, удаление."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app import backups, db
from app.compose import ComposeError, parse_compose
from app.providers.docker import (
    Container,
    ContainerNotFound,
    DockerError,
    DockerProvider,
    NewContainer,
)
from app.settings import settings

router = APIRouter(prefix="/api/v1", tags=["containers"])

ACTIONS = ("start", "stop", "restart")
RESTART_POLICIES = ("no", "always", "unless-stopped", "on-failure")
NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,62}$")
ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class CheckIn(BaseModel):
    url: str = ""
    interval: int = 60
    enabled: bool = True


class ComposeIn(BaseModel):
    yaml: str
    name: str | None = None


class RestoreIn(BaseModel):
    confirm: str


class LinkIn(BaseModel):
    url: str | None = None


class InstallRequest(BaseModel):
    name: str
    image: str
    ports: list[str] = Field(default_factory=list)
    volumes: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    restart: str = "unless-stopped"


def provider() -> DockerProvider:
    return DockerProvider(settings.docker.socket, settings.docker.timeout)


def container_dict(item: Container) -> dict:
    return {
        "id": item.id,
        "short_id": item.short_id,
        "name": item.name,
        "image": item.image,
        "state": item.state,
        "label": item.label,
        "status": item.status,
        "created": item.created,
        "ports": [
            {"private": port.private, "public": port.public, "type": port.kind}
            for port in item.ports
        ],
        "labels": item.labels,
        "group": None,
    }


def _link_fields(item: Container, request: Request, custom: str | None) -> dict:
    """Своя ссылка важнее автоматической по первому опубликованному порту."""
    if custom:
        return {"link": custom, "link_custom": True}
    public_port = next((port.public for port in item.ports if port.public), None)
    if public_port:
        host = request.url.hostname or "localhost"
        scheme = request.url.scheme or "http"
        return {"link": f"{scheme}://{host}:{public_port}", "link_custom": False}
    return {"link": None, "link_custom": False}


def _decorate(
    item: Container,
    request: Request,
    *,
    groups: dict | None = None,
    links: dict | None = None,
) -> dict:
    """Добавляет к контейнеру группу, ссылку и проверку."""
    groups = groups if groups is not None else db.group_map()
    links = links if links is not None else db.link_map()
    data = container_dict(item)
    data["group"] = groups.get(item.name)
    data["check"] = db.get_check(item.name)
    data.update(_link_fields(item, request, links.get(item.name)))
    return data


async def _find(client: DockerProvider, name: str) -> Container:
    try:
        containers = await client.list_containers()
    except DockerError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    item = next((entry for entry in containers if entry.name == name), None)
    if item is None:
        raise HTTPException(status_code=404, detail=f"контейнер не найден: {name}")
    return item


def _archive_name(archive: str) -> str:
    if "/" in archive or "\\" in archive or archive in ("", ".", ".."):
        raise HTTPException(status_code=400, detail="недопустимое имя архива")
    return archive


def parse_ports(items: list[str]) -> list[tuple[int, int, str]]:
    """Разбирает строки вида «8080:80» или «8080:80/tcp»."""
    result: list[tuple[int, int, str]] = []
    for item in items:
        text = item.strip()
        if not text:
            continue
        body, _, kind = text.partition("/")
        kind = kind or "tcp"
        host, sep, container = body.partition(":")
        if not sep or not host.isdigit() or not container.isdigit():
            raise ValueError(f"порт должен быть в виде 8080:80: {item}")
        public, private = int(host), int(container)
        if kind not in ("tcp", "udp"):
            raise ValueError(f"неизвестный протокол: {kind}")
        if not (1 <= public <= 65535 and 1 <= private <= 65535):
            raise ValueError(f"порт вне диапазона: {item}")
        result.append((public, private, kind))
    return result


def parse_volumes(items: list[str]) -> list[str]:
    """Разбирает строки вида «data:/data» или «/host:/data»."""
    result: list[str] = []
    for item in items:
        text = item.strip()
        if not text:
            continue
        source, sep, target = text.partition(":")
        if not sep or not source or not target or not target.startswith("/"):
            raise ValueError(f"том должен быть в виде имя:/путь: {item}")
        result.append(f"{source}:{target}")
    return result


def validate_install(payload: InstallRequest) -> NewContainer:
    if not NAME_RE.match(payload.name):
        raise ValueError("имя: латиница, цифры, точка, дефис, подчёркивание")
    if not payload.image.strip():
        raise ValueError("не задан образ")
    if payload.restart not in RESTART_POLICIES:
        raise ValueError(f"неизвестная политика перезапуска: {payload.restart}")
    for key in payload.env:
        if not ENV_KEY_RE.match(key):
            raise ValueError(f"недопустимое имя переменной: {key}")
    return NewContainer(
        name=payload.name,
        image=payload.image.strip(),
        ports=parse_ports(payload.ports),
        volumes=parse_volumes(payload.volumes),
        env=dict(payload.env),
        restart=payload.restart,
    )


async def _create(client: DockerProvider, spec: NewContainer) -> str:
    try:
        await client.pull_image(spec.image)
        return await client.create_container(spec)
    except DockerError as exc:
        text = str(exc)
        status = 409 if text.startswith("имя занято") else 503
        raise HTTPException(status_code=status, detail=text) from exc


async def _created(client: DockerProvider, container_id: str, request: Request) -> dict:
    try:
        containers = await client.list_containers()
    except DockerError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    created = next((item for item in containers if item.id == container_id), None)
    if created is None:
        return {"ok": True, "id": container_id}
    return {"ok": True, "container": _decorate(created, request)}


@router.get("/containers")
async def list_containers(request: Request) -> dict:
    """Все контейнеры локального Docker."""
    try:
        containers = await provider().list_containers()
    except DockerError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    groups = db.group_map()
    links = db.link_map()
    items = [_decorate(item, request, groups=groups, links=links) for item in containers]
    return {"count": len(items), "containers": items}


@router.get("/containers/{container_name}/check")
async def get_check(container_name: str) -> dict:
    return {"check": db.get_check(container_name)}


@router.put("/containers/{container_name}/check")
async def save_check(container_name: str, payload: CheckIn) -> dict:
    if payload.url and not payload.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="адрес должен начинаться с http:// или https://")
    if not 10 <= payload.interval <= 3600:
        raise HTTPException(status_code=400, detail="интервал: от 10 до 3600 секунд")
    if not payload.url.strip():
        db.delete_check(container_name)
        return {"ok": True, "check": None}
    check = db.save_check(container_name, payload.url.strip(), payload.interval, payload.enabled)
    return {"ok": True, "check": check}


@router.delete("/containers/{container_name}/check")
async def delete_check(container_name: str) -> dict:
    db.delete_check(container_name)
    return {"ok": True, "check": None}


@router.get("/containers/{container_name}/logs")
async def get_logs(container_name: str, tail: int = 200) -> dict:
    client = provider()
    item = await _find(client, container_name)
    try:
        text = await client.logs(item.id, max(10, min(tail, 2000)))
    except DockerError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"logs": text}


@router.get("/containers/{container_name}")
async def get_container(container_name: str, request: Request) -> dict:
    """Один контейнер с томами и сетью — для страницы сервиса."""
    client = provider()
    item = await _find(client, container_name)
    raw: dict = {}
    try:
        raw = await client.inspect(item.id)
    except DockerError:
        raw = {}

    data = _decorate(item, request)
    data["volumes"] = [
        {
            "type": mount.get("Type"),
            "source": mount.get("Name") or mount.get("Source"),
            "destination": mount.get("Destination"),
            "readonly": not mount.get("RW", True),
        }
        for mount in raw.get("Mounts") or []
        if mount.get("Destination") != "/var/run/docker.sock"
    ]
    data["network"] = (raw.get("HostConfig") or {}).get("NetworkMode", "")
    data["created"] = raw.get("Created", data.get("created"))
    return {"container": data}


@router.post("/containers/compose", status_code=201)
async def install_compose(payload: ComposeIn, request: Request) -> dict:
    """Устанавливает один сервис из docker-compose YAML."""
    try:
        spec = parse_compose(payload.yaml, payload.name)
    except ComposeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    client = provider()
    container_id = await _create(client, spec)
    return await _created(client, container_id, request)


@router.post("/containers", status_code=201)
async def install_container(payload: InstallRequest, request: Request) -> dict:
    """Скачивает образ, создаёт и запускает контейнер."""
    try:
        spec = validate_install(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    client = provider()
    container_id = await _create(client, spec)
    return await _created(client, container_id, request)


@router.delete("/containers/{container_id}")
async def delete_container(container_id: str, keep_volume: bool = True) -> dict:
    """Останавливает и удаляет контейнер. Тома по умолчанию сохраняются."""
    client = provider()
    try:
        containers = await client.list_containers()
        name = next((item.name for item in containers if item.id == container_id), None)
        await client.remove(container_id, remove_volumes=not keep_volume)
        if name:
            db.forget_container(name)
    except ContainerNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DockerError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"ok": True, "id": container_id, "keep_volume": keep_volume}


@router.get("/containers/{container_name}/backups")
async def list_backups(container_name: str) -> dict:
    items = backups.list_backups(container_name)
    return {"count": len(items), "backups": [item.as_dict() for item in items]}


@router.post("/containers/{container_name}/backups", status_code=201)
async def create_backup(container_name: str) -> dict:
    client = provider()
    item = await _find(client, container_name)
    try:
        result = await backups.create_backup(client, container_name, item.id)
    except backups.BackupError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **result}


@router.post("/containers/{container_name}/backups/{archive}/restore")
async def restore_backup(container_name: str, archive: str, payload: RestoreIn) -> dict:
    """Восстанавливает тома из копии после подтверждения именем сервиса."""
    if payload.confirm != container_name:
        raise HTTPException(status_code=400, detail="подтверждение не совпадает с именем")
    _archive_name(archive)
    client = provider()
    item = await _find(client, container_name)
    try:
        return await backups.restore_backup(client, container_name, item.id, archive)
    except backups.BackupError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/containers/{container_name}/backups/{archive}")
async def delete_backup(container_name: str, archive: str) -> dict:
    _archive_name(archive)
    path = backups.backup_dir() / archive
    if not path.is_file():
        raise HTTPException(status_code=404, detail="копия не найдена")
    path.unlink()
    return {"ok": True, "name": archive}


@router.post("/containers/{container_name}/link")
async def set_container_link(container_name: str, payload: LinkIn) -> dict:
    """Своя ссылка на сервис. Пусто — вернуть автоматическую."""
    url = (payload.url or "").strip() or None
    if url is not None and len(url) > 500:
        raise HTTPException(status_code=400, detail="ссылка слишком длинная")
    db.set_link(container_name, url)
    return {"ok": True, "container": container_name, "link": url}


@router.post("/containers/{container_id}/actions/update")
async def update_container(container_id: str) -> dict:
    """Скачивает новый образ и пересоздаёт контейнер, при сбое откатывает."""
    try:
        return await provider().update(container_id)
    except ContainerNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DockerError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/containers/{container_id}/actions/{action}")
async def container_action(container_id: str, action: str) -> dict:
    """Запуск, остановка или перезапуск контейнера."""
    if action not in ACTIONS:
        raise HTTPException(status_code=400, detail=f"неизвестное действие: {action}")
    try:
        await getattr(provider(), action)(container_id)
    except ContainerNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DockerError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"ok": True, "id": container_id, "action": action}
