"""Бэкапы томов контейнеров.

Архив создаётся одноразовым контейнером alpine: он видит те же тома,
что и сервис, и складывает tar.gz в том бэкапов.
"""

from __future__ import annotations

import asyncio
import pathlib
import tarfile
import time
from dataclasses import dataclass

from app.providers.docker import ContainerNotFound, DockerError, DockerProvider
from app.settings import settings

HELPER_IMAGE = "alpine:3.20"
SKIP_DESTINATIONS = {"/var/run/docker.sock", "/backup"}


class BackupError(RuntimeError):
    """Не удалось создать или проверить копию."""


@dataclass
class Backup:
    name: str
    size: int
    created: int

    def as_dict(self) -> dict:
        return {"name": self.name, "size": self.size, "created": self.created}


def backup_dir() -> pathlib.Path:
    path = pathlib.Path(settings.backups.dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_backups(container_name: str) -> list[Backup]:
    directory = backup_dir()
    items = []
    for path in directory.glob(f"{container_name}-*.tar.gz"):
        stat = path.stat()
        items.append(Backup(name=path.name, size=stat.st_size, created=int(stat.st_mtime)))
    items.sort(key=lambda item: item.created, reverse=True)
    return items


def verify_archive(path: pathlib.Path) -> int:
    """Проверяет, что архив читается и не пустой. Возвращает число файлов."""
    if not path.is_file() or path.stat().st_size == 0:
        raise BackupError("архив не создан или пустой")
    try:
        with tarfile.open(path, "r:gz") as archive:
            count = sum(1 for member in archive if member.isfile() or member.isdir())
    except (tarfile.TarError, OSError) as exc:
        raise BackupError(f"архив повреждён: {exc}") from exc
    if count == 0:
        raise BackupError("в архиве нет файлов")
    return count


def prune(container_name: str, keep: int, protect: set[str] | None = None) -> list[str]:
    keep_names = protect or set()
    removed = []
    candidates = [
        entry for entry in list_backups(container_name) if entry.name not in keep_names
    ]
    for item in candidates[keep:]:
        (backup_dir() / item.name).unlink(missing_ok=True)
        removed.append(item.name)
    return removed


def _mounts(raw: dict) -> tuple[list[str], list[str]]:
    binds: list[str] = []
    targets: list[str] = []
    for mount in raw.get("Mounts") or []:
        if mount.get("Type") not in ("volume", "bind"):
            continue
        destination = str(mount.get("Destination", ""))
        if not destination or destination in SKIP_DESTINATIONS:
            continue
        source = mount.get("Name") or mount.get("Source")
        if not source:
            continue
        binds.append(f"{source}:{destination}")
        targets.append(destination.lstrip("/"))
    return binds, targets


async def create_backup(
    provider: DockerProvider,
    container_name: str,
    container_id: str,
    protect: set[str] | None = None,
) -> dict:
    raw = await provider.inspect(container_id)
    binds, targets = _mounts(raw)
    if not targets:
        raise BackupError("у контейнера нет томов для копирования")

    stamp = time.strftime("%Y-%m-%d_%H%M%S")
    directory = backup_dir()
    archive_name = f"{container_name}-{stamp}.tar.gz"
    counter = 1
    while (directory / archive_name).exists():
        archive_name = f"{container_name}-{stamp}-{counter}.tar.gz"
        counter += 1
    cmd = ["tar", "czf", f"/backup/{archive_name}", "-C", "/", *targets]
    helper_binds = binds + [f"{settings.backups.volume}:/backup"]

    try:
        code, logs = await provider.run_helper(HELPER_IMAGE, cmd, helper_binds)
    except ContainerNotFound as exc:
        raise BackupError(str(exc)) from exc
    except DockerError as exc:
        raise BackupError(f"Docker: {exc}") from exc

    if code != 0:
        raise BackupError(f"tar завершился с кодом {code}: {logs.strip()[-400:]}")

    path = directory / archive_name
    try:
        files = verify_archive(path)
    except BackupError:
        path.unlink(missing_ok=True)
        raise

    removed = prune(container_name, settings.backups.keep, protect)
    return {
        "name": archive_name,
        "size": path.stat().st_size,
        "files": files,
        "removed": removed,
    }


def _restore_script(archive_name: str, targets: list[str]) -> str:
    lines = ["set -e"]
    for target in targets:
        lines.append(
            f'if [ -d "/{target}" ]; then '
            f'find "/{target}" -mindepth 1 -maxdepth 1 -exec rm -rf {{}} +; fi'
        )
        lines.append(f'mkdir -p "/{target}"')
    lines.append(f'tar xzf "/backup/{archive_name}" -C /')
    return "\n".join(lines)


async def _unpack(
    provider: DockerProvider, binds: list[str], archive_name: str, targets: list[str]
) -> None:
    cmd = ["sh", "-c", _restore_script(archive_name, targets)]
    code, logs = await provider.run_helper(
        HELPER_IMAGE, cmd, binds + [f"{settings.backups.volume}:/backup"]
    )
    if code != 0:
        raise BackupError(f"распаковка завершилась с кодом {code}: {logs.strip()[-400:]}")


async def restore_backup(
    provider: DockerProvider, container_name: str, container_id: str, archive_name: str
) -> dict:
    """Восстанавливает тома из копии. Перед этим делает safety-копию."""
    archive_path = backup_dir() / archive_name
    if not archive_path.is_file():
        raise BackupError(f"копия не найдена: {archive_name}")
    verify_archive(archive_path)

    raw = await provider.inspect(container_id)
    binds, targets = _mounts(raw)
    if not targets:
        raise BackupError("у контейнера нет томов для восстановления")

    safety = await create_backup(provider, container_name, container_id, protect={archive_name})
    safety_name = safety["name"]

    await provider.stop(container_id)
    try:
        await _unpack(provider, binds, archive_name, targets)
    except BackupError:
        await provider.start(container_id)
        raise

    await provider.start(container_id)
    await asyncio.sleep(2)
    state = str((await provider.inspect(container_id)).get("State", {}).get("Status", ""))
    if state != "running":
        try:
            await provider.stop(container_id)
            await _unpack(provider, binds, safety_name, targets)
            await provider.start(container_id)
        except (DockerError, BackupError):
            pass
        raise BackupError(
            f"контейнер не запустился после восстановления; "
            f"safety-копия: {safety_name}"
        )

    return {
        "ok": True,
        "restored": archive_name,
        "safety": safety_name,
        "state": state,
    }
