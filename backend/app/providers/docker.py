"""Docker-провайдер: список, действия, установка и удаление.

Сейчас только локальный сокет; удалённые хосты появятся в 0.3.0.
"""

from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass, field
from urllib.parse import quote

import httpx


class DockerError(RuntimeError):
    """Docker недоступен или ответил ошибкой."""


class ContainerNotFound(DockerError):
    """Контейнер не найден."""


@dataclass
class PortMapping:
    private: int
    public: int | None = None
    kind: str = "tcp"


@dataclass
class Container:
    id: str
    name: str
    image: str
    state: str
    status: str
    created: int
    ports: list[PortMapping] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)

    @property
    def short_id(self) -> str:
        return self.id[:12]

    @property
    def label(self) -> str:
        """Человеческое состояние для интерфейса."""
        if self.state == "running":
            return "работает"
        if self.state == "exited":
            return "остановлен"
        if self.state == "paused":
            return "пауза"
        return self.state


@dataclass
class NewContainer:
    name: str
    image: str
    ports: list[tuple[int, int, str]] = field(default_factory=list)
    volumes: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    restart: str = "unless-stopped"


def parse_port(raw: dict) -> PortMapping:
    return PortMapping(
        private=int(raw.get("PrivatePort", 0)),
        public=int(raw["PublicPort"]) if raw.get("PublicPort") else None,
        kind=str(raw.get("Type", "tcp")),
    )


def parse_container(raw: dict) -> Container:
    names = raw.get("Names") or []
    name = names[0].lstrip("/") if names else str(raw.get("Id", ""))[:12]

    # Docker отдаёт отдельные записи для IPv4 и IPv6 — оставляем уникальные
    ports: list[PortMapping] = []
    seen: set[tuple[int, int | None, str]] = set()
    for item in raw.get("Ports") or []:
        port = parse_port(item)
        key = (port.private, port.public, port.kind)
        if key not in seen:
            seen.add(key)
            ports.append(port)

    return Container(
        id=str(raw.get("Id", "")),
        name=name,
        image=str(raw.get("Image", "")),
        state=str(raw.get("State", "unknown")),
        status=str(raw.get("Status", "")),
        created=int(raw.get("Created", 0) or 0),
        ports=ports,
        labels={str(k): str(v) for k, v in (raw.get("Labels") or {}).items()},
    )


def build_recreate_payload(raw: dict) -> dict:
    """Собирает тело create из ответа inspect, чтобы пересоздать контейнер."""
    config = raw.get("Config") or {}
    host = raw.get("HostConfig") or {}
    host_keys = (
        "Binds", "PortBindings", "RestartPolicy", "NetworkMode", "Privileged",
        "CapAdd", "CapDrop", "Devices", "Dns", "ExtraHosts", "Tmpfs", "Ulimits",
        "AutoRemove", "Init", "ReadonlyRootfs", "SecurityOpt",
    )
    payload: dict = {
        "Image": config.get("Image", ""),
        "HostConfig": {key: host[key] for key in host_keys if key in host},
    }
    for key in (
        "Env", "Cmd", "Entrypoint", "Labels", "ExposedPorts", "WorkingDir",
        "User", "StopSignal", "StopTimeout",
    ):
        if config.get(key) is not None:
            payload[key] = config[key]

    networks = (raw.get("NetworkSettings") or {}).get("Networks") or {}
    mode = host.get("NetworkMode", "")
    if networks and mode not in ("default", "bridge", "host", "none", ""):
        payload["NetworkingConfig"] = {
            "EndpointsConfig": {name: {} for name in networks}
        }
    return payload


class DockerProvider:
    """Клиент Docker API по unix-сокету."""

    def __init__(self, socket: str, timeout: float = 5.0) -> None:
        self.socket = socket
        self.timeout = timeout

    def _client(self, timeout: float | None = None) -> httpx.AsyncClient:
        transport = httpx.AsyncHTTPTransport(uds=self.socket)
        return httpx.AsyncClient(
            transport=transport,
            base_url="http://docker",
            timeout=timeout if timeout is not None else self.timeout,
        )

    async def list_containers(self) -> list[Container]:
        try:
            async with self._client() as client:
                response = await client.get("/containers/json", params={"all": "1"})
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise DockerError(f"Docker ответил {exc.response.status_code}") from exc
        except (httpx.HTTPError, OSError) as exc:
            raise DockerError(f"Docker недоступен ({type(exc).__name__}): {exc}") from exc
        except ValueError as exc:
            raise DockerError(f"Docker вернул не JSON: {exc}") from exc

        if not isinstance(payload, list):
            raise DockerError("Docker вернул неожиданный ответ")

        containers = [parse_container(item) for item in payload]
        containers.sort(key=lambda item: item.name.lower())
        return containers

    async def _action(self, container_id: str, action: str) -> None:
        try:
            # stop может ждать до 10 секунд, поэтому таймаут больше
            async with self._client(timeout=max(self.timeout, 30)) as client:
                response = await client.post(f"/containers/{container_id}/{action}")
        except (httpx.HTTPError, OSError) as exc:
            raise DockerError(f"Docker недоступен ({type(exc).__name__}): {exc}") from exc

        if response.status_code in (204, 304):
            return
        if response.status_code == 404:
            raise ContainerNotFound(f"контейнер не найден: {container_id}")
        raise DockerError(f"Docker ответил {response.status_code}")

    async def start(self, container_id: str) -> None:
        await self._action(container_id, "start")

    async def stop(self, container_id: str) -> None:
        await self._action(container_id, "stop")

    async def restart(self, container_id: str) -> None:
        await self._action(container_id, "restart")

    async def pull_image(self, image: str) -> None:
        """Скачивает образ. Docker отдаёт поток, читаем его целиком."""
        repo, _, tag = image.partition(":")
        try:
            async with self._client(timeout=max(self.timeout, 600)) as client:
                response = await client.post(
                    "/images/create",
                    params={"fromImage": repo, "tag": tag or "latest"},
                )
                body = response.text
        except (httpx.HTTPError, OSError) as exc:
            raise DockerError(f"Docker недоступен ({type(exc).__name__}): {exc}") from exc

        if response.status_code >= 400:
            raise DockerError(f"не удалось скачать образ {image}: {response.status_code}")
        if '"error"' in body:
            raise DockerError(f"не удалось скачать образ {image}: {body[:200]}")

    async def create_container(self, spec: NewContainer) -> str:
        exposed = {f"{private}/{kind}": {} for _, private, kind in spec.ports}
        bindings = {
            f"{private}/{kind}": [{"HostPort": str(public)}]
            for public, private, kind in spec.ports
        }
        payload = {
            "Image": spec.image,
            "Env": [f"{key}={value}" for key, value in spec.env.items()],
            "ExposedPorts": exposed,
            "HostConfig": {
                "PortBindings": bindings,
                "Binds": spec.volumes,
                "RestartPolicy": {"Name": spec.restart},
            },
        }
        try:
            async with self._client(timeout=max(self.timeout, 60)) as client:
                response = await client.post(
                    "/containers/create",
                    params={"name": spec.name},
                    json=payload,
                )
                body = response.json() if response.content else {}
        except (httpx.HTTPError, OSError) as exc:
            raise DockerError(f"Docker недоступен ({type(exc).__name__}): {exc}") from exc
        except ValueError as exc:
            raise DockerError(f"Docker вернул не JSON: {exc}") from exc

        if response.status_code == 409:
            raise DockerError(f"имя занято: {spec.name}")
        if response.status_code >= 400:
            detail = body.get("message") if isinstance(body, dict) else ""
            raise DockerError(f"Docker ответил {response.status_code}: {detail}")

        container_id = str(body.get("Id", ""))
        if not container_id:
            raise DockerError("Docker не вернул идентификатор контейнера")
        await self.start(container_id)
        return container_id

    async def remove(self, container_id: str, remove_volumes: bool = False) -> None:
        try:
            async with self._client(timeout=max(self.timeout, 30)) as client:
                await client.post(f"/containers/{container_id}/stop")
                response = await client.delete(
                    f"/containers/{container_id}",
                    params={"v": "1" if remove_volumes else "0", "force": "0"},
                )
        except (httpx.HTTPError, OSError) as exc:
            raise DockerError(f"Docker недоступен ({type(exc).__name__}): {exc}") from exc

        if response.status_code in (204, 200):
            return
        if response.status_code == 404:
            raise ContainerNotFound(f"контейнер не найден: {container_id}")
        raise DockerError(f"Docker ответил {response.status_code}")
    async def _inspect(self, container_id: str) -> dict:
        try:
            async with self._client() as client:
                response = await client.get(f"/containers/{container_id}/json")
        except (httpx.HTTPError, OSError) as exc:
            raise DockerError(f"Docker недоступен ({type(exc).__name__}): {exc}") from exc
        if response.status_code == 404:
            raise ContainerNotFound(f"контейнер не найден: {container_id}")
        if response.status_code >= 400:
            raise DockerError(f"Docker ответил {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise DockerError(f"Docker вернул не JSON: {exc}") from exc

    async def _rename(self, container_id: str, name: str) -> None:
        try:
            async with self._client(timeout=max(self.timeout, 30)) as client:
                response = await client.post(
                    f"/containers/{container_id}/rename", params={"name": name}
                )
        except (httpx.HTTPError, OSError) as exc:
            raise DockerError(f"Docker недоступен ({type(exc).__name__}): {exc}") from exc
        if response.status_code not in (204, 200):
            raise DockerError(f"не удалось переименовать контейнер: {response.status_code}")

    async def _delete(self, container_id: str, volumes: bool = False) -> None:
        try:
            async with self._client(timeout=max(self.timeout, 30)) as client:
                response = await client.delete(
                    f"/containers/{container_id}",
                    params={"v": "1" if volumes else "0"},
                )
        except (httpx.HTTPError, OSError) as exc:
            raise DockerError(f"Docker недоступен ({type(exc).__name__}): {exc}") from exc
        if response.status_code not in (204, 200, 404):
            raise DockerError(f"не удалось удалить контейнер: {response.status_code}")

    async def _image_id(self, image: str) -> str:
        try:
            async with self._client() as client:
                response = await client.get(f"/images/{quote(image, safe='')}/json")
        except (httpx.HTTPError, OSError) as exc:
            raise DockerError(f"Docker недоступен ({type(exc).__name__}): {exc}") from exc
        if response.status_code >= 400:
            raise DockerError(f"образ не найден: {image}")
        return str(response.json().get("Id", ""))

    async def _create_from_payload(self, name: str, payload: dict) -> str:
        try:
            async with self._client(timeout=max(self.timeout, 60)) as client:
                response = await client.post(
                    "/containers/create", params={"name": name}, json=payload
                )
                body = response.json() if response.content else {}
        except (httpx.HTTPError, OSError) as exc:
            raise DockerError(f"Docker недоступен ({type(exc).__name__}): {exc}") from exc
        if response.status_code >= 400:
            raise DockerError(f"Docker ответил {response.status_code}")
        container_id = str(body.get("Id", ""))
        if not container_id:
            raise DockerError("Docker не вернул идентификатор контейнера")
        return container_id

    async def logs(self, container_id: str, tail: int = 200) -> str:
        try:
            async with self._client(timeout=max(self.timeout, 30)) as client:
                response = await client.get(
                    f"/containers/{container_id}/logs",
                    params={"stdout": "1", "stderr": "1", "tail": str(tail)},
                )
        except (httpx.HTTPError, OSError) as exc:
            raise DockerError(f"Docker недоступен ({type(exc).__name__}): {exc}") from exc
        if response.status_code >= 400:
            raise DockerError(f"Docker ответил {response.status_code}")
        return decode_logs(response.content)

    async def update(self, container_id: str) -> dict:
        """Тянет образ, пересоздаёт контейнер и откатывается при сбое."""
        raw = await self._inspect(container_id)
        name = str(raw.get("Name", "")).lstrip("/")
        image = str((raw.get("Config") or {}).get("Image", ""))
        old_image = str(raw.get("Image", ""))
        if not name or not image:
            raise DockerError("не удалось прочитать параметры контейнера")

        await self.pull_image(image)
        new_image = await self._image_id(image)
        if not new_image or new_image == old_image:
            return {"changed": False, "image": image, "id": container_id}

        payload = build_recreate_payload(raw)
        await self.stop(container_id)
        old_name = f"{name}-old-{int(time.time())}"
        await self._rename(container_id, old_name)

        new_id = ""
        try:
            new_id = await self._create_from_payload(name, payload)
            await self.start(new_id)
            await asyncio.sleep(2)
            state = str((await self._inspect(new_id)).get("State", {}).get("Status", ""))
            if state != "running":
                raise DockerError(f"новый контейнер не запустился: {state}")
            await self._delete(container_id)
        except Exception:
            if new_id:
                try:
                    await self._delete(new_id, volumes=True)
                except DockerError:
                    pass
            try:
                await self._rename(container_id, name)
                await self.start(container_id)
            except DockerError:
                pass
            raise

        return {
            "changed": True,
            "id": new_id,
            "image": image,
            "old_image": old_image.removeprefix("sha256:")[:12],
            "new_image": new_image.removeprefix("sha256:")[:12],
            "name": name,
        }
    async def inspect(self, container_id: str) -> dict:
        return await self._inspect(container_id)

    async def run_helper(self, image: str, cmd: list[str], binds: list[str]) -> tuple[int, str]:
        """Запускает одноразовый контейнер и возвращает код и логи."""
        await self.pull_image(image)
        name = f"servatory-job-{secrets.token_hex(4)}"
        payload = {
            "Image": image,
            "Cmd": cmd,
            "Tty": True,
            "HostConfig": {"Binds": binds, "NetworkMode": "none"},
        }
        container_id = await self._create_from_payload(name, payload)
        try:
            await self.start(container_id)
            code = await self._wait(container_id)
            logs = await self._logs(container_id)
            return code, logs
        finally:
            try:
                await self._delete(container_id, volumes=False)
            except DockerError:
                pass

    async def _wait(self, container_id: str) -> int:
        try:
            async with self._client(timeout=600) as client:
                response = await client.post(
                    f"/containers/{container_id}/wait", params={"condition": "not-running"}
                )
        except (httpx.HTTPError, OSError) as exc:
            raise DockerError(f"Docker недоступен ({type(exc).__name__}): {exc}") from exc
        if response.status_code >= 400:
            raise DockerError(f"не удалось дождаться контейнера: {response.status_code}")
        try:
            return int(response.json().get("StatusCode", 1))
        except ValueError:
            return 1

    async def _logs(self, container_id: str) -> str:
        try:
            async with self._client() as client:
                response = await client.get(
                    f"/containers/{container_id}/logs",
                    params={"stdout": "1", "stderr": "1"},
                )
        except (httpx.HTTPError, OSError):
            return ""
        return response.text[-2000:]


def decode_logs(payload: bytes) -> str:
    """Разбирает поток Docker: кадры или обычный текст."""
    text: list[str] = []
    index = 0
    while index + 8 <= len(payload):
        stream = payload[index]
        size = int.from_bytes(payload[index + 4:index + 8], "big")
        if stream not in (0, 1, 2) or size < 0 or index + 8 + size > len(payload):
            return payload.decode("utf-8", errors="replace")
        text.append(payload[index + 8:index + 8 + size].decode("utf-8", errors="replace"))
        index += 8 + size
    return "".join(text) if text else payload.decode("utf-8", errors="replace")
