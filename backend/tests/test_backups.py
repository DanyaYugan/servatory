"""Бэкапы томов: создание, проверка, хранение."""

import io
import pathlib
import tarfile
import time
from types import SimpleNamespace

import pytest

from app import backups


def make_tar(path: pathlib.Path, name: str = "data/file.txt") -> None:
    with tarfile.open(path, "w:gz") as archive:
        info = tarfile.TarInfo(name)
        payload = b"hello"
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))


@pytest.fixture
def backup_settings(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    stub = SimpleNamespace(
        backups=SimpleNamespace(dir=str(tmp_path), keep=2, volume="servatory-backups")
    )
    monkeypatch.setattr(backups, "settings", stub)
    return tmp_path


@pytest.mark.asyncio
async def test_create_backup(backup_settings, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeProvider:
        async def inspect(self, container_id: str) -> dict:
            return {
                "Mounts": [
                    {"Type": "volume", "Name": "data", "Destination": "/data"},
                    {
                        "Type": "bind",
                        "Source": "/var/run/docker.sock",
                        "Destination": "/var/run/docker.sock",
                    },
                ]
            }

        async def run_helper(self, image: str, cmd: list[str], binds: list[str]):
            name = cmd[2].split("/")[-1]
            make_tar(backup_settings / name)
            return 0, ""

    result = await backups.create_backup(FakeProvider(), "demo", "id1")
    assert result["files"] == 1
    assert (backup_settings / result["name"]).is_file()


@pytest.mark.asyncio
async def test_backup_without_mounts(backup_settings) -> None:
    class Empty:
        async def inspect(self, container_id: str) -> dict:
            return {"Mounts": []}

    with pytest.raises(backups.BackupError):
        await backups.create_backup(Empty(), "demo", "id1")


def test_verify_corrupt(backup_settings) -> None:
    path = backup_settings / "broken.tar.gz"
    path.write_bytes(b"not a tar")
    with pytest.raises(backups.BackupError):
        backups.verify_archive(path)


def test_prune_keeps_newest(backup_settings) -> None:
    now = time.time()
    for index in range(4):
        path = backup_settings / f"demo-{index}.tar.gz"
        make_tar(path)
        path.touch()
        import os

        os.utime(path, (now + index, now + index))

    removed = backups.prune("demo", 2)
    assert len(removed) == 2
    left = sorted(item.name for item in backups.list_backups("demo"))
    assert left == ["demo-2.tar.gz", "demo-3.tar.gz"]


def test_restore_script_clears_and_unpacks() -> None:
    script = backups._restore_script("demo.tar.gz", ["app/data"])
    assert 'tar xzf "/backup/demo.tar.gz" -C /' in script
    assert "/app/data" in script
    assert "rm -rf" in script


def test_prune_protects_archive(backup_settings) -> None:
    now = time.time()
    for index in range(4):
        path = backup_settings / f"demo-{index}.tar.gz"
        make_tar(path)
        import os

        os.utime(path, (now + index, now + index))

    removed = backups.prune("demo", 1, protect={"demo-0.tar.gz"})
    left = {item.name for item in backups.list_backups("demo")}
    assert "demo-0.tar.gz" in left
    assert len(removed) == 2
