"""Системные настройки: домены, TLS, профиль и обновление панели."""

from __future__ import annotations

import shlex
import socket

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import db, tls
from app.config import Settings
from app.providers.docker import DockerError, DockerProvider
from app.settings import settings as app_settings
from app.version import __version__

router = APIRouter(prefix="/api/v1/system", tags=["system"])


class TlsIn(BaseModel):
    domain: str = ""
    email: str = ""
    enabled: bool = False


class ProfileIn(BaseModel):
    panel_name: str = ""
    public_url: str = ""
    onboarded: bool = False


@router.get("/tls")
async def get_tls() -> dict:
    settings = Settings.load()
    return await tls.status(settings)


@router.put("/tls")
async def put_tls(payload: TlsIn) -> dict:
    settings = Settings.load()
    try:
        return await tls.apply(settings, payload.domain, payload.email, payload.enabled)
    except tls.TlsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/profile")
async def get_profile() -> dict:
    return {
        "panel_name": db.get_setting("panel_name", "Servatory"),
        "public_url": db.get_setting("public_url", ""),
        "onboarded": db.get_setting("onboarded") == "1",
    }


@router.patch("/profile")
async def save_profile(payload: ProfileIn) -> dict:
    name = payload.panel_name.strip()
    url = payload.public_url.strip()
    if len(name) > 80:
        raise HTTPException(status_code=400, detail="название длиннее 80 символов")
    if url and not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="адрес должен начинаться с http:// или https://")
    if len(url) > 500:
        raise HTTPException(status_code=400, detail="адрес длиннее 500 символов")
    db.set_setting("panel_name", name or "Servatory")
    db.set_setting("public_url", url)
    db.set_setting("onboarded", "1" if payload.onboarded else "0")
    return await get_profile()


def _provider() -> DockerProvider:
    return DockerProvider(app_settings.docker.socket, app_settings.docker.timeout)


async def _self_container(client: DockerProvider) -> dict | None:
    for name in (socket.gethostname(), "servatory"):
        try:
            return await client.inspect(name)
        except DockerError:
            continue
    return None


def _compose_targets(info: dict | None) -> tuple[str, str]:
    labels = ((info or {}).get("Config") or {}).get("Labels") or {}
    workdir = str(labels.get("com.docker.compose.project.working_dir") or "")
    files = str(labels.get("com.docker.compose.project.config_files") or "")
    config = files.split(",")[0].strip()
    if not workdir or not config:
        return "", ""
    return workdir, config


@router.get("/update")
async def update_info() -> dict:
    client = _provider()
    try:
        info = await _self_container(client)
    except DockerError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    workdir, config = _compose_targets(info)
    image = ((info or {}).get("Config") or {}).get("Image") or ""
    return {
        "version": __version__,
        "compose": bool(workdir and config),
        "image": str(image),
    }


@router.post("/update")
async def update_panel() -> dict:
    """Запускает helper, который обновляет compose-проект панели."""
    client = _provider()
    try:
        info = await _self_container(client)
    except DockerError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    workdir, config = _compose_targets(info)
    if not workdir or not config:
        raise HTTPException(
            status_code=400,
            detail="панель запущена не через compose; обновите её командой docker compose up -d",
        )

    script = (
        "sleep 2; "
        f"cd {shlex.quote(workdir)} && "
        f"docker compose -f {shlex.quote(config)} pull --ignore-buildable && "
        f"docker compose -f {shlex.quote(config)} up -d --build --remove-orphans"
    )
    try:
        await client.run_detached(
            "docker:27-cli",
            ["sh", "-c", script],
            [
                f"{workdir}:{workdir}",
                "/var/run/docker.sock:/var/run/docker.sock",
            ],
            workdir=workdir,
        )
    except DockerError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "ok": True,
        "message": "Обновление запущено. Панель перезапустится через несколько секунд.",
    }
