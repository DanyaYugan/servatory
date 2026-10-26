"""Проверка сессии, прав и CSRF, запись в журнал."""

from __future__ import annotations

import time

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app import auth, db, security


class SessionGuard(BaseHTTPMiddleware):
    """Пускает только с сессией, проверяет право и CSRF, пишет журнал."""

    async def dispatch(self, request, call_next):
        path = request.url.path
        if auth.is_public(path):
            return await call_next(request)

        token = request.cookies.get(auth.COOKIE_NAME)
        session = db.get_session(auth.token_hash(token)) if token else None
        if not session or session["expires_at"] < time.time():
            return JSONResponse({"detail": "требуется вход"}, status_code=401)

        request.state.session = session
        needed = security.required_permission(request.method, path)
        if needed and needed not in security.permissions_for(session["role"]):
            return JSONResponse({"detail": "недостаточно прав"}, status_code=403)

        mutating = request.method in auth.MUTATING_METHODS and path.startswith("/api")
        if mutating and request.headers.get("x-csrf-token") != session["csrf"]:
            return JSONResponse({"detail": "неверный CSRF-токен"}, status_code=403)

        response = await call_next(request)
        if mutating:
            action = security.audit_action(request.method, path)
            if action:
                db.add_audit(
                    session["login"],
                    action[0],
                    action[1],
                    "ok" if response.status_code < 400 else "ошибка",
                    str(response.status_code),
                )
        return response
