"""Пароли и права."""

from __future__ import annotations

import hashlib
import hmac
import secrets

ITERATIONS = 200_000
ROLES = ("superadmin", "admin", "operator", "viewer")

ROLE_PERMISSIONS = {
    "superadmin": {"view", "control", "manage", "users", "audit"},
    "admin": {"view", "control", "manage", "audit"},
    "operator": {"view", "control"},
    "viewer": {"view"},
}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$")
        if algorithm != "pbkdf2":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def permissions_for(role: str) -> set[str]:
    return ROLE_PERMISSIONS.get(role, set())


def required_permission(method: str, path: str) -> str | None:
    """Какое право нужно для запроса."""
    if not path.startswith("/api/"):
        return None
    if path.startswith("/api/v1/auth/"):
        return None
    if path.startswith("/api/v1/users"):
        return "users"
    if path.startswith("/api/v1/audit"):
        return "audit"
    if method in ("GET", "HEAD", "OPTIONS"):
        return "view"
    if "/actions/" in path:
        return "control"
    return "manage"


def audit_action(method: str, path: str) -> tuple[str, str] | None:
    """Человеческое действие и объект для журнала."""
    if path.startswith("/api/v1/auth/"):
        return None
    if path.startswith("/api/v1/users"):
        return "пользователи", path
    if "/actions/" in path:
        action = path.rsplit("/", 1)[-1]
        return action, path
    if "restore" in path:
        return "восстановление", path
    if "/backups" in path:
        return "бэкап", path
    if "/link" in path:
        return "ссылка", path
    if path.startswith("/api/v1/groups") or "/group" in path:
        return "группа", path
    if path == "/api/v1/containers" and method == "POST":
        return "установка", path
    if "/compose" in path:
        return "установка YAML", path
    if path.startswith("/api/v1/containers") and method == "DELETE":
        return "удаление", path
    return method.lower(), path
