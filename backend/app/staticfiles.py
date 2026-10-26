"""Отдача собранного интерфейса и маршрутов Vue внутри /ui."""

from __future__ import annotations

import pathlib

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

STATIC_DIR = pathlib.Path("/app/static")


class SPAStaticFiles(StaticFiles):
    """Отдаёт index.html для внутренних маршрутов вроде /ui/services/name."""

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and "." not in path.rsplit("/", 1)[-1]:
                return await super().get_response("index.html", scope)
            raise


def mount_ui(app: FastAPI) -> None:
    if STATIC_DIR.is_dir():
        app.mount("/ui", SPAStaticFiles(directory=str(STATIC_DIR), html=True), name="ui")
