"""Пользователи и роли. Доступ только у superadmin."""

from __future__ import annotations

import re
import sqlite3

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app import db, security

router = APIRouter(prefix="/api/v1/users", tags=["users"])

LOGIN_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{1,31}$")


class UserIn(BaseModel):
    login: str
    password: str
    role: str = "viewer"


class UserPatch(BaseModel):
    password: str | None = None
    role: str | None = None


def _check_role(role: str) -> None:
    if role not in security.ROLES:
        raise HTTPException(status_code=400, detail=f"неизвестная роль: {role}")


@router.get("")
async def list_users() -> dict:
    return {"users": db.list_users()}


@router.post("", status_code=201)
async def create_user(payload: UserIn) -> dict:
    if not LOGIN_RE.match(payload.login):
        raise HTTPException(
            status_code=400,
            detail="логин: латиница, цифры, точка, дефис, подчёркивание, 2–32 символа",
        )
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="пароль не короче 6 символов")
    _check_role(payload.role)
    try:
        user = db.create_user(
            payload.login, security.hash_password(payload.password), payload.role
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="такой логин уже есть") from exc
    return {"user": user}


@router.patch("/{user_id}")
async def update_user(user_id: int, payload: UserPatch, request: Request) -> dict:
    user = db.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="пользователь не найден")
    session = getattr(request.state, "session", None) or {}
    if payload.role is not None and session.get("login") == user["login"]:
        raise HTTPException(status_code=400, detail="нельзя менять роль своей учётной записи")
    if payload.role is not None:
        _check_role(payload.role)
        if (
            user["role"] == "superadmin"
            and payload.role != "superadmin"
            and db.count_superadmins() <= 1
        ):
            raise HTTPException(status_code=400, detail="нельзя убрать последнего superadmin")
    password_hash = None
    if payload.password is not None:
        if len(payload.password) < 6:
            raise HTTPException(status_code=400, detail="пароль не короче 6 символов")
        password_hash = security.hash_password(payload.password)
    updated = db.update_user(user_id, role=payload.role, password_hash=password_hash)
    if payload.role is not None:
        db.update_sessions_role(user["login"], payload.role)
    if payload.password is not None:
        db.delete_sessions_for_login(user["login"])
    return {"user": updated}


@router.delete("/{user_id}")
async def delete_user(user_id: int, request: Request) -> dict:
    user = db.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="пользователь не найден")
    session = getattr(request.state, "session", None) or {}
    if session.get("login") == user["login"]:
        raise HTTPException(status_code=400, detail="нельзя удалить себя")
    if user["role"] == "superadmin" and db.count_superadmins() <= 1:
        raise HTTPException(status_code=400, detail="нельзя удалить последнего superadmin")
    db.delete_sessions_for_login(user["login"])
    db.delete_user(user_id)
    return {"ok": True, "id": user_id}
