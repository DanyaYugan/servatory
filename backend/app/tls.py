"""Домены и TLS: Caddy рядом с панелью.

Панель создаёт контейнер servatory-caddy через Docker API, пишет Caddyfile
в свой каталог данных и перезапускает Caddy. Панель остаётся на 8090,
Caddy слушает 80 и 443.
"""

from __future__ import annotations

import asyncio
import pathlib
import re
import socket

import httpx

from app import db
from app.config import Settings

CADDY_NAME = "servatory-caddy"
CADDY_IMAGE = "caddy:2-alpine"
DOMAIN_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9.-]{0,251}[a-zA-Z0-9])?$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class TlsError(RuntimeError):
    """Не удалось применить настройки TLS."""


def _client(settings: Settings) -> httpx.AsyncClient:
    transport = httpx.AsyncHTTPTransport(uds=settings.docker.socket)
    return httpx.AsyncClient(transport=transport, base_url="http://docker", timeout=300)


def validate(domain: str, email: str) -> None:
    if not DOMAIN_RE.match(domain):
        raise TlsError("домен: латиница, цифры, точка и дефис")
    if email and not EMAIL_RE.match(email):
        raise TlsError("почта выглядит неправильно")


async def _inspect(client: httpx.AsyncClient, name: str) -> dict | None:
    response = await client.get(f"/containers/{name}/json")
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def _is_internal(domain: str) -> bool:
    if domain in ("localhost",):
        return True
    return bool(re.match(r"^[0-9.]+$", domain))


def _caddyfile(domain: str, email: str, upstream: str) -> str:
    lines = ["{", "\tadmin 0.0.0.0:2019"]
    if email:
        lines.append(f"\temail {email}")
    lines.append("}")
    lines.append("")
    lines.append(f"{domain} {{")
    if _is_internal(domain):
        lines.append("\ttls internal")
    lines.append(f"\treverse_proxy {upstream}:8090")
    lines.append("}")
    return "\n".join(lines) + "\n"


async def _self_info(client: httpx.AsyncClient) -> tuple[str, str, str]:
    """Имя контейнера панели, сеть и каталог данных на хосте."""
    info = None
    for name in (socket.gethostname(), "servatory"):
        info = await _inspect(client, name)
        if info:
            break
    if not info:
        raise TlsError("не удалось найти контейнер панели в Docker")
    name = str(info.get("Name", "/servatory")).lstrip("/")
    networks = (info.get("NetworkSettings") or {}).get("Networks") or {}
    network = next(iter(networks), "bridge")
    source = ""
    for mount in info.get("Mounts") or []:
        if mount.get("Destination") == "/data":
            source = str(mount.get("Source") or "")
            break
    if not source:
        raise TlsError("каталог данных /data не смонтирован с хоста")
    return name, network, source


async def status(settings: Settings) -> dict:
    enabled = db.get_setting("tls_enabled") == "1"
    domain = db.get_setting("tls_domain")
    email = db.get_setting("tls_email")
    result = {
        "enabled": enabled,
        "domain": domain,
        "email": email,
        "container": None,
        "url": f"https://{domain}" if domain and enabled else "",
    }
    try:
        async with _client(settings) as client:
            info = await _inspect(client, CADDY_NAME)
    except (httpx.HTTPError, OSError, TlsError):
        info = None
    if info:
        state = info.get("State") or {}
        result["container"] = {
            "exists": True,
            "running": bool(state.get("Running")),
            "status": state.get("Status", ""),
            "error": state.get("Error", ""),
        }
    return result


async def apply(settings: Settings, domain: str, email: str, enabled: bool) -> dict:
    domain = domain.strip().lower()
    email = email.strip()
    if enabled:
        validate(domain, email)

    db.set_setting("tls_domain", domain)
    db.set_setting("tls_email", email)
    db.set_setting("tls_enabled", "1" if enabled else "0")

    if not enabled:
        await _remove(settings)
        return await status(settings)

    caddy_dir = pathlib.Path(settings.data_dir) / "caddy"
    caddy_dir.mkdir(parents=True, exist_ok=True)

    try:
        async with _client(settings) as client:
            upstream, network, source = await _self_info(client)
            caddyfile = _caddyfile(domain, email, upstream)
            (caddy_dir / "Caddyfile").write_text(caddyfile, encoding="utf-8")

            await _pull(client)
            await _remove_with(client)
            payload = {
                "Image": CADDY_IMAGE,
                "Cmd": [
                    "caddy",
                    "run",
                    "--config",
                    "/etc/caddy/Caddyfile",
                    "--adapter",
                    "caddyfile",
                ],
                "ExposedPorts": {"80/tcp": {}, "443/tcp": {}, "2019/tcp": {}},
                "HostConfig": {
                    "Binds": [
                        f"{source}/caddy:/etc/caddy",
                        "servatory-caddy-data:/data",
                    ],
                    "PortBindings": {
                        "80/tcp": [{"HostPort": "80"}],
                        "443/tcp": [{"HostPort": "443"}],
                    },
                    "RestartPolicy": {"Name": "unless-stopped"},
                    "NetworkMode": network,
                },
                "NetworkingConfig": {"EndpointsConfig": {network: {}}},
            }
            created = await client.post(
                "/containers/create", params={"name": CADDY_NAME}, json=payload
            )
            if created.status_code >= 400:
                raise TlsError(f"Docker create: {created.text}")
            container_id = created.json()["Id"]
            started = await client.post(f"/containers/{container_id}/start")
            if started.status_code >= 400:
                raise TlsError(f"Docker start: {started.text}")
            await asyncio.sleep(1)
    except (httpx.HTTPError, OSError) as exc:
        raise TlsError(f"Docker недоступен: {exc}") from exc

    return await status(settings)


async def _pull(client: httpx.AsyncClient) -> None:
    image = await client.get(f"/images/{CADDY_IMAGE}/json")
    if image.status_code == 200:
        return
    response = await client.post(
        "/images/create", params={"fromImage": "caddy", "tag": "2-alpine"}
    )
    if response.status_code >= 400:
        raise TlsError(f"не удалось скачать Caddy: {response.text}")


async def _remove_with(client: httpx.AsyncClient) -> None:
    await client.delete(f"/containers/{CADDY_NAME}", params={"force": "1"})


async def _remove(settings: Settings) -> None:
    try:
        async with _client(settings) as client:
            await _remove_with(client)
    except (httpx.HTTPError, OSError):
        pass
