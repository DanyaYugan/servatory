"""Настройки Servatory.

Источник правды — файл config.toml в каталоге данных.
Переменные окружения перекрывают значения из файла: это нужно для Docker,
где порт и каталог удобнее задавать в .env.

Пример файла — deploy/docker/config.example.toml.
"""

from __future__ import annotations

import os
import pathlib
import tomllib
from dataclasses import dataclass

DEFAULT_CONFIG = """# Servatory — настройки.
# Файл читается при старте. Переменные окружения перекрывают значения отсюда.

[server]
host = "0.0.0.0"
port = 8090

[auth]
# первый администратор; нужен только при пустой базе
login = "admin"
password = "admin"
role = "superadmin"
# время жизни сессии в часах
session_hours = 12

[ui]
language = "ru"
theme = "dark"

[logging]
level = "info"

[docker]
# путь к сокету Docker внутри контейнера или на хосте
socket = "/var/run/docker.sock"
timeout = 5

[backups]
# каталог архивов и том Docker для них
dir = "/backups"
volume = "servatory-backups"
# сколько копий хранить на сервис
keep = 5

[features]
demo = false
"""

VALID_ROLES = ("superadmin", "admin", "operator", "viewer")


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else None


def _env_int(name: str) -> int | None:
    value = _env(name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _env_bool(name: str) -> bool | None:
    value = _env(name)
    if value is None:
        return None
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class ServerSettings:
    host: str = "0.0.0.0"
    port: int = 8090

    def validate(self) -> None:
        if not 1 <= self.port <= 65535:
            raise ValueError(f"порт вне диапазона: {self.port}")


@dataclass(frozen=True)
class AuthSettings:
    login: str = "admin"
    password: str = "admin"
    role: str = "superadmin"
    session_hours: int = 12

    def validate(self) -> None:
        if not self.login:
            raise ValueError("логин не может быть пустым")
        if not self.password:
            raise ValueError("пароль не может быть пустым")
        if self.role not in VALID_ROLES:
            raise ValueError(f"неизвестная роль: {self.role}")
        if not 1 <= self.session_hours <= 720:
            raise ValueError("время жизни сессии: от 1 до 720 часов")


@dataclass(frozen=True)
class BackupsSettings:
    dir: str = "/backups"
    volume: str = "servatory-backups"
    keep: int = 5

    def validate(self) -> None:
        if self.keep < 1:
            raise ValueError("хранить нужно хотя бы одну копию")


@dataclass(frozen=True)
class DockerSettings:
    socket: str = "/var/run/docker.sock"
    timeout: float = 5.0

    def validate(self) -> None:
        if not self.socket:
            raise ValueError("не задан путь к сокету Docker")


@dataclass(frozen=True)
class Settings:
    data_dir: pathlib.Path
    config_path: pathlib.Path
    server: ServerSettings
    auth: AuthSettings
    docker: DockerSettings
    backups: BackupsSettings
    log_level: str
    demo: bool
    language: str
    theme: str

    @classmethod
    def load(cls) -> Settings:
        data_dir = pathlib.Path(_env("SERVATORY_DATA") or "/data")
        config_path = pathlib.Path(_env("SERVATORY_CONFIG") or data_dir / "config.toml")

        raw: dict = {}
        if config_path.is_file():
            try:
                raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
            except (OSError, tomllib.TOMLDecodeError) as exc:
                raise ValueError(f"не удалось прочитать {config_path}: {exc}") from exc

        server = raw.get("server", {})
        auth = raw.get("auth", {})
        ui = raw.get("ui", {})
        logging_cfg = raw.get("logging", {})
        features = raw.get("features", {})
        docker_cfg = raw.get("docker", {})
        backups_cfg = raw.get("backups", {})

        server_settings = ServerSettings(
            host=_env("SERVATORY_HOST") or str(server.get("host", "0.0.0.0")),
            port=_env_int("SERVATORY_PORT") or int(server.get("port", 8090)),
        )
        auth_settings = AuthSettings(
            login=_env("SERVATORY_ADMIN_LOGIN")
            or _env("SERVATORY_ADMIN_USER")
            or str(auth.get("login", "admin")),
            password=_env("SERVATORY_ADMIN_PASSWORD") or str(auth.get("password", "admin")),
            role=str(auth.get("role", "superadmin")),
            session_hours=int(
                _env("SERVATORY_SESSION_HOURS") or auth.get("session_hours", 12)
            ),
        )

        docker_settings = DockerSettings(
            socket=_env("SERVATORY_DOCKER_SOCKET")
            or str(docker_cfg.get("socket", "/var/run/docker.sock")),
            timeout=float(_env("SERVATORY_DOCKER_TIMEOUT") or docker_cfg.get("timeout", 5)),
        )

        backups_settings = BackupsSettings(
            dir=_env("SERVATORY_BACKUP_DIR") or str(backups_cfg.get("dir", "/backups")),
            volume=_env("SERVATORY_BACKUP_VOLUME")
            or str(backups_cfg.get("volume", "servatory-backups")),
            keep=int(_env("SERVATORY_BACKUP_KEEP") or backups_cfg.get("keep", 5)),
        )

        settings = cls(
            data_dir=data_dir,
            config_path=config_path,
            server=server_settings,
            auth=auth_settings,
            docker=docker_settings,
            backups=backups_settings,
            log_level=(
                _env("SERVATORY_LOG_LEVEL") or str(logging_cfg.get("level", "info"))
            ).lower(),
            demo=(
                _env_bool("SERVATORY_DEMO")
                if _env_bool("SERVATORY_DEMO") is not None
                else bool(features.get("demo", False))
            ),
            language=str(ui.get("language", "ru")),
            theme=str(ui.get("theme", "dark")),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        self.server.validate()
        self.auth.validate()
        self.docker.validate()
        self.backups.validate()

    def ensure_dirs(self) -> None:
        """Создаёт каталог состояния и файл настроек, если их нет."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(DEFAULT_CONFIG, encoding="utf-8")
            try:
                self.config_path.chmod(0o600)
            except OSError:
                pass
