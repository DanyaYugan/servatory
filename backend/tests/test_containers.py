"""Проверки провайдера и API контейнеров."""

import pytest
from fastapi.testclient import TestClient

import app.api.containers as containers_api
from app.main import app
from app.providers.docker import (
    Container,
    ContainerNotFound,
    DockerError,
    PortMapping,
    build_recreate_payload,
    parse_container,
)

client = TestClient(app)
_login = client.post("/api/v1/auth/login", json={"login": "admin", "password": "admin"})
client.headers["X-CSRF-Token"] = _login.json()["csrf"]
anon = TestClient(app)
AUTH = ("admin", "admin")

RAW = {
    "Id": "abc123def4567890",
    "Names": ["/servatory"],
    "Image": "servatory:local",
    "State": "running",
    "Status": "Up 5 minutes (healthy)",
    "Created": 1700000000,
    "Ports": [{"PrivatePort": 8090, "PublicPort": 8090, "Type": "tcp"}],
    "Labels": {"servatory.role": "panel"},
}


def test_parse_container() -> None:
    item = parse_container(RAW)
    assert item.name == "servatory"
    assert item.image == "servatory:local"
    assert item.state == "running"
    assert item.label == "работает"
    assert item.short_id == "abc123def456"
    assert item.ports == [PortMapping(private=8090, public=8090, kind="tcp")]
    assert item.labels["servatory.role"] == "panel"


def test_parse_container_without_public_port() -> None:
    item = parse_container({**RAW, "Ports": [{"PrivatePort": 5432, "Type": "tcp"}]})
    assert item.ports[0].public is None


def test_api_requires_auth() -> None:
    response = anon.get("/api/v1/containers")
    assert response.status_code == 401


def test_api_lists_containers(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeProvider:
        async def list_containers(self) -> list[Container]:
            return [parse_container(RAW)]

    monkeypatch.setattr(containers_api, "provider", lambda: FakeProvider())
    response = client.get("/api/v1/containers", auth=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["containers"][0]["name"] == "servatory"
    assert body["containers"][0]["ports"][0]["public"] == 8090


def test_api_returns_503_when_docker_down(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenProvider:
        async def list_containers(self) -> list[Container]:
            raise DockerError("Docker недоступен: сокет не найден")

    monkeypatch.setattr(containers_api, "provider", lambda: BrokenProvider())
    response = client.get("/api/v1/containers", auth=AUTH)
    assert response.status_code == 503
    assert "Docker" in response.json()["detail"]
def test_duplicate_ports_removed() -> None:
    raw = {
        **RAW,
        "Ports": [
            {"PrivatePort": 8090, "PublicPort": 8090, "Type": "tcp"},
            {"PrivatePort": 8090, "PublicPort": 8090, "Type": "tcp"},
        ],
    }
    assert len(parse_container(raw).ports) == 1


class ActionProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def start(self, container_id: str) -> None:
        self.calls.append(("start", container_id))

    async def stop(self, container_id: str) -> None:
        self.calls.append(("stop", container_id))

    async def restart(self, container_id: str) -> None:
        self.calls.append(("restart", container_id))


def test_action_requires_auth() -> None:
    response = anon.post("/api/v1/containers/abc/actions/start")
    assert response.status_code == 401


def test_action_rejects_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = ActionProvider()
    monkeypatch.setattr(containers_api, "provider", lambda: fake)
    response = client.post("/api/v1/containers/abc/actions/remove", auth=AUTH)
    assert response.status_code == 400


def test_action_calls_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = ActionProvider()
    monkeypatch.setattr(containers_api, "provider", lambda: fake)
    for action in ("start", "stop", "restart"):
        response = client.post(f"/api/v1/containers/abc/actions/{action}", auth=AUTH)
        assert response.status_code == 200
        assert response.json()["action"] == action
    assert fake.calls == [("start", "abc"), ("stop", "abc"), ("restart", "abc")]


def test_action_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    class Missing:
        async def start(self, container_id: str) -> None:
            raise ContainerNotFound("контейнер не найден")

    monkeypatch.setattr(containers_api, "provider", lambda: Missing())
    response = client.post("/api/v1/containers/abc/actions/start", auth=AUTH)
    assert response.status_code == 404

class InstallProvider:
    def __init__(self) -> None:
        self.removed: list[tuple[str, bool]] = []
        self.created: list[object] = []

    async def pull_image(self, image: str) -> None:
        pass

    async def create_container(self, spec: object) -> str:
        self.created.append(spec)
        return "new-id-123"

    async def list_containers(self) -> list[Container]:
        return [parse_container({**RAW, "Id": "new-id-123", "Names": ["/new-service"]})]

    async def remove(self, container_id: str, remove_volumes: bool = False) -> None:
        self.removed.append((container_id, remove_volumes))


def test_install_requires_auth() -> None:
    response = anon.post("/api/v1/containers", json={"name": "x", "image": "nginx"})
    assert response.status_code == 401


def test_install_creates_container(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = InstallProvider()
    monkeypatch.setattr(containers_api, "provider", lambda: fake)
    response = client.post(
        "/api/v1/containers",
        auth=AUTH,
        json={
            "name": "new-service",
            "image": "nginx:alpine",
            "ports": ["8081:80/tcp"],
            "volumes": ["data:/data"],
            "env": {"TZ": "Asia/Yekaterinburg"},
            "restart": "unless-stopped",
        },
    )
    assert response.status_code == 201
    assert response.json()["container"]["name"] == "new-service"
    spec = fake.created[0]
    assert spec.ports == [(8081, 80, "tcp")]
    assert spec.volumes == ["data:/data"]


def test_install_rejects_bad_name() -> None:
    response = client.post(
        "/api/v1/containers",
        auth=AUTH,
        json={"name": "плохое имя", "image": "nginx"},
    )
    assert response.status_code == 400


def test_install_rejects_bad_port() -> None:
    response = client.post(
        "/api/v1/containers",
        auth=AUTH,
        json={"name": "ok", "image": "nginx", "ports": ["8080"]},
    )
    assert response.status_code == 400


def test_install_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    class Busy(InstallProvider):
        async def create_container(self, spec: object) -> str:
            raise DockerError("имя занято: new-service")

    monkeypatch.setattr(containers_api, "provider", lambda: Busy())
    response = client.post(
        "/api/v1/containers",
        auth=AUTH,
        json={"name": "new-service", "image": "nginx"},
    )
    assert response.status_code == 409


def test_delete_keeps_volume_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = InstallProvider()
    monkeypatch.setattr(containers_api, "provider", lambda: fake)
    response = client.delete("/api/v1/containers/abc", auth=AUTH)
    assert response.status_code == 200
    assert fake.removed == [("abc", False)]


def test_delete_can_remove_volume(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = InstallProvider()
    monkeypatch.setattr(containers_api, "provider", lambda: fake)
    response = client.delete("/api/v1/containers/abc?keep_volume=false", auth=AUTH)
    assert response.status_code == 200
    assert fake.removed == [("abc", True)]

INSPECT = {
    "Name": "/demo",
    "Image": "sha256:oldimage",
    "Config": {
        "Image": "nginx:alpine",
        "Env": ["TZ=UTC"],
        "Cmd": ["nginx", "-g", "daemon off;"],
        "Labels": {"a": "b"},
        "ExposedPorts": {"80/tcp": {}},
    },
    "HostConfig": {
        "Binds": ["data:/data"],
        "PortBindings": {"80/tcp": [{"HostPort": "8080"}]},
        "RestartPolicy": {"Name": "unless-stopped"},
        "NetworkMode": "bridge",
    },
    "NetworkSettings": {"Networks": {"bridge": {}}},
}


def test_build_recreate_payload() -> None:
    payload = build_recreate_payload(INSPECT)
    assert payload["Image"] == "nginx:alpine"
    assert payload["HostConfig"]["Binds"] == ["data:/data"]
    assert payload["HostConfig"]["PortBindings"]["80/tcp"][0]["HostPort"] == "8080"
    assert payload["Env"] == ["TZ=UTC"]
    assert "NetworkingConfig" not in payload


def test_update_calls_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    class UpdateProvider:
        async def update(self, container_id: str) -> dict:
            return {"changed": True, "id": "new", "name": "demo"}

    monkeypatch.setattr(containers_api, "provider", lambda: UpdateProvider())
    response = client.post("/api/v1/containers/abc/actions/update", auth=AUTH)
    assert response.status_code == 200
    assert response.json()["changed"] is True

def test_container_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    class DetailProvider:
        async def list_containers(self) -> list[Container]:
            return [parse_container(RAW)]

        async def inspect(self, container_id: str) -> dict:
            return {
                "Id": container_id,
                "Created": "2026-10-23T00:00:00Z",
                "HostConfig": {"NetworkMode": "bridge"},
                "Mounts": [
                    {"Type": "volume", "Name": "data", "Destination": "/data", "RW": True}
                ],
            }

    monkeypatch.setattr(containers_api, "provider", lambda: DetailProvider())
    response = client.get("/api/v1/containers/servatory", auth=AUTH)
    assert response.status_code == 200
    body = response.json()["container"]
    assert body["name"] == "servatory"
    assert body["volumes"][0]["source"] == "data"
    assert body["network"] == "bridge"
