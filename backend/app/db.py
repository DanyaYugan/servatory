"""Хранилище групп и привязок контейнеров.

SQLite в каталоге данных. Контейнеры привязываются по имени: идентификатор
меняется при пересоздании, имя остаётся.
"""

from __future__ import annotations

import pathlib
import sqlite3
import time

from app.settings import settings

DB_PATH = settings.data_dir / "servatory.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS container_groups (
    container_name TEXT PRIMARY KEY,
    group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS container_links (
    container_name TEXT PRIMARY KEY,
    url TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at INTEGER NOT NULL,
    login TEXT NOT NULL,
    action TEXT NOT NULL,
    object TEXT NOT NULL,
    result TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS checks (
    container_name TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    interval INTEGER NOT NULL DEFAULT 60,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_at INTEGER NOT NULL DEFAULT 0,
    last_ok INTEGER NOT NULL DEFAULT 0,
    last_code INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    csrf TEXT NOT NULL,
    login TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


SCHEMA_VERSION = 1

MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        );
        """,
    ),
]


def init_db() -> None:
    pathlib.Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with connect() as connection:
        connection.executescript(SCHEMA)
        current = int(connection.execute("PRAGMA user_version").fetchone()[0])
        for version, sql in MIGRATIONS:
            if version > current:
                connection.executescript(sql)
                connection.execute(f"PRAGMA user_version = {version}")
                connection.commit()
                current = version


def list_groups() -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT id, name, position FROM groups ORDER BY position, name"
        ).fetchall()
    return [dict(row) for row in rows]


def create_group(name: str) -> dict:
    with connect() as connection:
        position = connection.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 FROM groups"
        ).fetchone()[0]
        cursor = connection.execute(
            "INSERT INTO groups (name, position) VALUES (?, ?)", (name, position)
        )
        group_id = cursor.lastrowid
        connection.commit()
        row = connection.execute(
            "SELECT id, name, position FROM groups WHERE id = ?", (group_id,)
        ).fetchone()
    return dict(row)


def rename_group(group_id: int, name: str) -> dict | None:
    with connect() as connection:
        connection.execute("UPDATE groups SET name = ? WHERE id = ?", (name, group_id))
        connection.commit()
        row = connection.execute(
            "SELECT id, name, position FROM groups WHERE id = ?", (group_id,)
        ).fetchone()
    return dict(row) if row else None


def delete_group(group_id: int) -> bool:
    with connect() as connection:
        cursor = connection.execute("DELETE FROM groups WHERE id = ?", (group_id,))
        connection.commit()
        return cursor.rowcount > 0


def reorder_groups(ids: list[int]) -> None:
    with connect() as connection:
        for position, group_id in enumerate(ids, start=1):
            connection.execute(
                "UPDATE groups SET position = ? WHERE id = ?", (position, group_id)
            )
        connection.commit()


def assign_container(container_name: str, group_id: int | None) -> None:
    with connect() as connection:
        if group_id is None:
            connection.execute(
                "DELETE FROM container_groups WHERE container_name = ?",
                (container_name,),
            )
        else:
            position = connection.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 FROM container_groups "
                "WHERE group_id = ?",
                (group_id,),
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO container_groups (container_name, group_id, position) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(container_name) DO UPDATE SET "
                "group_id = excluded.group_id, position = excluded.position",
                (container_name, group_id, position),
            )
        connection.commit()


def forget_container(container_name: str) -> None:
    with connect() as connection:
        connection.execute(
            "DELETE FROM container_groups WHERE container_name = ?", (container_name,)
        )
        connection.execute(
            "DELETE FROM container_links WHERE container_name = ?", (container_name,)
        )
        connection.commit()


def group_map() -> dict[str, dict]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT cg.container_name, cg.position, g.id, g.name "
            "FROM container_groups cg JOIN groups g ON g.id = cg.group_id"
        ).fetchall()
    return {
        row["container_name"]: {
            "id": row["id"],
            "name": row["name"],
            "position": row["position"],
        }
        for row in rows
    }


def set_link(container_name: str, url: str | None) -> None:
    with connect() as connection:
        if url is None:
            connection.execute(
                "DELETE FROM container_links WHERE container_name = ?",
                (container_name,),
            )
        else:
            connection.execute(
                "INSERT INTO container_links (container_name, url) VALUES (?, ?) "
                "ON CONFLICT(container_name) DO UPDATE SET url = excluded.url",
                (container_name, url),
            )
        connection.commit()


def link_map() -> dict[str, str]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT container_name, url FROM container_links"
        ).fetchall()
    return {row["container_name"]: row["url"] for row in rows}


def create_session(token_hash: str, csrf: str, login: str, role: str, expires_at: int) -> None:
    with connect() as connection:
        connection.execute(
            "INSERT INTO sessions (token_hash, csrf, login, role, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (token_hash, csrf, login, role, int(time.time()), expires_at),
        )
        connection.commit()


def get_session(token_hash: str) -> dict | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT token_hash, csrf, login, role, expires_at FROM sessions "
            "WHERE token_hash = ?",
            (token_hash,),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def delete_session(token_hash: str) -> None:
    with connect() as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
        connection.commit()


def purge_sessions() -> None:
    with connect() as connection:
        connection.execute("DELETE FROM sessions WHERE expires_at < ?", (int(time.time()),))
        connection.commit()


def count_users() -> int:
    with connect() as connection:
        return int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])


def list_users() -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT id, login, role, created_at FROM users ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]


def get_user_by_login(login: str) -> dict | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT id, login, password_hash, role, created_at FROM users WHERE login = ?",
            (login,),
        ).fetchone()
    return dict(row) if row else None


def get_user(user_id: int) -> dict | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT id, login, role, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


def create_user(login: str, password_hash: str, role: str) -> dict:
    with connect() as connection:
        cursor = connection.execute(
            "INSERT INTO users (login, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (login, password_hash, role, int(time.time())),
        )
        connection.commit()
        user_id = cursor.lastrowid
        row = connection.execute(
            "SELECT id, login, role, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return dict(row)


def update_user(
    user_id: int, role: str | None = None, password_hash: str | None = None
) -> dict | None:
    with connect() as connection:
        if role is not None:
            connection.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
        if password_hash is not None:
            connection.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id)
            )
        connection.commit()
        row = connection.execute(
            "SELECT id, login, role, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


def delete_user(user_id: int) -> bool:
    with connect() as connection:
        cursor = connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
        connection.commit()
        return cursor.rowcount > 0


def count_superadmins() -> int:
    with connect() as connection:
        return int(
            connection.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'superadmin'"
            ).fetchone()[0]
        )


def delete_sessions_for_login(login: str) -> None:
    with connect() as connection:
        connection.execute("DELETE FROM sessions WHERE login = ?", (login,))
        connection.commit()


def update_sessions_role(login: str, role: str) -> None:
    with connect() as connection:
        connection.execute("UPDATE sessions SET role = ? WHERE login = ?", (role, login))
        connection.commit()


def add_audit(
    login: str, action: str, obj: str, result: str, detail: str = ""
) -> None:
    with connect() as connection:
        connection.execute(
            "INSERT INTO audit (at, login, action, object, result, detail) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (int(time.time()), login, action, obj, result, detail[:500]),
        )
        connection.commit()


def list_audit(limit: int = 100) -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT id, at, login, action, object, result, detail FROM audit "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_check(container_name: str) -> dict | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM checks WHERE container_name = ?", (container_name,)
        ).fetchone()
    return dict(row) if row else None


def list_checks() -> list[dict]:
    with connect() as connection:
        rows = connection.execute("SELECT * FROM checks").fetchall()
    return [dict(row) for row in rows]


def save_check(container_name: str, url: str, interval: int, enabled: bool) -> dict:
    with connect() as connection:
        connection.execute(
            "INSERT INTO checks (container_name, url, interval, enabled) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(container_name) DO UPDATE SET "
            "url = excluded.url, interval = excluded.interval, enabled = excluded.enabled",
            (container_name, url, interval, 1 if enabled else 0),
        )
        connection.commit()
    return get_check(container_name) or {}


def update_check_result(
    container_name: str, ok: bool, code: int, error: str
) -> None:
    with connect() as connection:
        connection.execute(
            "UPDATE checks SET last_at = ?, last_ok = ?, last_code = ?, last_error = ? "
            "WHERE container_name = ?",
            (int(time.time()), 1 if ok else 0, code, error[:300], container_name),
        )
        connection.commit()


def delete_check(container_name: str) -> None:
    with connect() as connection:
        connection.execute("DELETE FROM checks WHERE container_name = ?", (container_name,))
        connection.commit()


def get_setting(key: str, default: str = "") -> str:
    with connect() as connection:
        row = connection.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
    return str(row["value"]) if row else default


def set_setting(key: str, value: str) -> None:
    with connect() as connection:
        connection.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        connection.commit()


def all_settings() -> dict[str, str]:
    with connect() as connection:
        rows = connection.execute("SELECT key, value FROM settings").fetchall()
    return {str(row["key"]): str(row["value"]) for row in rows}
