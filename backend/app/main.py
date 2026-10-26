"""Servatory — панель управления сервисами на Docker.

Приложение FastAPI: жизненный цикл, проверка сессий, роутеры и отдача
собранного интерфейса. Работа с Docker — app.providers, бэкапы — app.backups,
настройки — app.config.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app import checks, db, security
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.containers import router as containers_router
from app.api.groups import router as groups_router
from app.api.images import router as images_router
from app.api.system import router as system_router
from app.api.users import router as users_router
from app.middleware import SessionGuard
from app.settings import settings
from app.staticfiles import mount_ui
from app.version import __build__, __version__

STARTED_AT = time.time()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
logger = logging.getLogger("servatory")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    db.init_db()
    if db.count_users() == 0:
        db.create_user(
            settings.auth.login,
            security.hash_password(settings.auth.password),
            settings.auth.role,
        )
    task = asyncio.create_task(checks.checker_loop())
    logger.info(
        "servatory %s (%s) стартует, данные в %s",
        __version__,
        __build__,
        settings.data_dir,
    )
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    logger.info("servatory остановлен")


app = FastAPI(
    title="Servatory",
    version=__version__,
    description="Панель управления сервисами на Docker",
    lifespan=lifespan,
)

app.add_middleware(SessionGuard)
app.include_router(auth_router)
app.include_router(audit_router)
app.include_router(containers_router)
app.include_router(groups_router)
app.include_router(images_router)
app.include_router(users_router)
app.include_router(system_router)


@app.get("/health")
async def health() -> dict:
    """Живость процесса."""
    return {"status": "ok", "version": __version__, "uptime": int(time.time() - STARTED_AT)}


@app.get("/ready")
async def ready() -> JSONResponse:
    """Готовность: каталог данных доступен."""
    try:
        settings.ensure_dirs()
    except OSError as exc:
        logger.error("каталог данных недоступен: %s", exc)
        return JSONResponse({"status": "not ready", "reason": str(exc)}, status_code=503)
    return JSONResponse({"status": "ready"})


@app.get("/api/v1/meta")
async def meta() -> dict:
    """Публичная версия, схема данных и режим TLS."""
    return {
        "version": __version__,
        "schema": db.SCHEMA_VERSION,
        "tls_mode": "https" if db.get_setting("tls_enabled") == "1" else "none",
        "demo": settings.demo,
    }


@app.get("/")
async def root() -> dict:
    """Короткая информация для проверки, что сервис жив."""
    return {"service": "servatory", "version": __version__, "ui": "/ui/", "docs": "/docs"}


mount_ui(app)
