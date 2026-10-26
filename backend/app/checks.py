"""Фоновые проверки работоспособности по HTTP."""

from __future__ import annotations

import asyncio
import time

import httpx

from app import db

CHECK_EVERY = 30
TIMEOUT = 6


async def run_due_checks() -> int:
    """Проверяет те адреса, у которых подошёл интервал. Возвращает число проверок."""
    now = int(time.time())
    done = 0
    for check in db.list_checks():
        if not check["enabled"]:
            continue
        if check["last_at"] + max(10, int(check["interval"])) > now:
            continue
        code = 0
        error = ""
        ok = False
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
                response = await client.get(check["url"])
            code = response.status_code
            ok = code < 400
        except (httpx.HTTPError, OSError) as exc:
            error = f"{type(exc).__name__}: {exc}"[:300]
        db.update_check_result(check["container_name"], ok, code, error)
        done += 1
    return done


async def checker_loop() -> None:
    while True:
        try:
            await run_due_checks()
        except Exception:  # noqa: BLE001 — фоновая задача не должна падать
            pass
        await asyncio.sleep(CHECK_EVERY)
