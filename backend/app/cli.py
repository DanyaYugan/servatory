"""Запуск Servatory с параметрами из config.toml.

Использование: python -m app.cli
"""

from __future__ import annotations

import logging

import uvicorn

from app.config import Settings
from app.version import __version__


def main() -> None:
    settings = Settings.load()
    settings.ensure_dirs()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
    )
    logging.getLogger("servatory").info(
        "Servatory %s, порт %s, настройки %s",
        __version__,
        settings.server.port,
        settings.config_path,
    )

    uvicorn.run(
        "app.main:app",
        host=settings.server.host,
        port=settings.server.port,
        log_level=settings.log_level,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
