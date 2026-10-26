"""Проверки файла настроек."""

import os
import pathlib

from app.config import Settings


def test_default_config_created(tmp_path: pathlib.Path) -> None:
    old_data = os.environ.get("SERVATORY_DATA")
    old_config = os.environ.get("SERVATORY_CONFIG")
    try:
        os.environ["SERVATORY_DATA"] = str(tmp_path)
        os.environ.pop("SERVATORY_CONFIG", None)
        settings = Settings.load()
        settings.ensure_dirs()
        assert settings.config_path == tmp_path / "config.toml"
        assert settings.config_path.is_file()
        text = settings.config_path.read_text(encoding="utf-8")
        assert 'role = "superadmin"' in text
    finally:
        if old_data is not None:
            os.environ["SERVATORY_DATA"] = old_data
        else:
            os.environ.pop("SERVATORY_DATA", None)
        if old_config is not None:
            os.environ["SERVATORY_CONFIG"] = old_config


def test_file_overrides_defaults(tmp_path: pathlib.Path) -> None:
    config = tmp_path / "custom.toml"
    config.write_text(
        """
[server]
host = "127.0.0.1"
port = 9099

[auth]
login = "root"
password = "s3cret"
role = "superadmin"

[ui]
language = "ru"
theme = "dark"
""",
        encoding="utf-8",
    )
    old_config = os.environ.get("SERVATORY_CONFIG")
    old_port = os.environ.get("SERVATORY_PORT")
    try:
        os.environ["SERVATORY_CONFIG"] = str(config)
        os.environ.pop("SERVATORY_PORT", None)
        settings = Settings.load()
        assert settings.server.port == 9099
        assert settings.server.host == "127.0.0.1"
        assert settings.auth.login == "root"
        assert settings.auth.password == "s3cret"
        assert settings.auth.role == "superadmin"
    finally:
        if old_config is not None:
            os.environ["SERVATORY_CONFIG"] = old_config
        else:
            os.environ.pop("SERVATORY_CONFIG", None)
        if old_port is not None:
            os.environ["SERVATORY_PORT"] = old_port


def test_env_overrides_file(tmp_path: pathlib.Path) -> None:
    config = tmp_path / "custom.toml"
    config.write_text(
        """
[server]
port = 9099

[auth]
login = "root"
password = "s3cret"
""",
        encoding="utf-8",
    )
    old_config = os.environ.get("SERVATORY_CONFIG")
    old_port = os.environ.get("SERVATORY_PORT")
    old_login = os.environ.get("SERVATORY_ADMIN_LOGIN")
    try:
        os.environ["SERVATORY_CONFIG"] = str(config)
        os.environ["SERVATORY_PORT"] = "8091"
        os.environ["SERVATORY_ADMIN_LOGIN"] = "envuser"
        settings = Settings.load()
        assert settings.server.port == 8091
        assert settings.auth.login == "envuser"
    finally:
        for key, value in (
            ("SERVATORY_CONFIG", old_config),
            ("SERVATORY_PORT", old_port),
            ("SERVATORY_ADMIN_LOGIN", old_login),
        ):
            if value is not None:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)
