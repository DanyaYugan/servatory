"""Сессии и CSRF."""

from __future__ import annotations

import hashlib
import secrets

COOKIE_NAME = "servatory_session"
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

PUBLIC_PATHS = {
    "/health",
    "/ready",
    "/api/v1/auth/login",
    "/docs",
    "/openapi.json",
}


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def new_csrf() -> str:
    return secrets.token_urlsafe(24)


def is_public(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith("/ui")
