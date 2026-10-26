"""Вход, выход и текущий пользователь."""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app import auth, db, security
from app.settings import settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginIn(BaseModel):
    login: str
    password: str


class PasswordIn(BaseModel):
    current: str
    password: str


def _bootstrap_admin(login: str, password: str) -> dict | None:
    """Первый вход: если пользователей нет, создаём администратора из конфига."""
    if db.count_users() or login != settings.auth.login or password != settings.auth.password:
        return None
    db.create_user(login, security.hash_password(password), settings.auth.role)
    return db.get_user_by_login(login)


@router.post("/login")
async def login(payload: LoginIn, request: Request, response: Response) -> dict:
    user = db.get_user_by_login(payload.login)
    if user is None:
        user = _bootstrap_admin(payload.login, payload.password)
    if user is None or not security.verify_password(payload.password, user["password_hash"]):
        db.add_audit(payload.login, "вход", "панель", "неудача")
        raise HTTPException(status_code=401, detail="неверный логин или пароль")

    db.purge_sessions()
    token = auth.new_token()
    csrf = auth.new_csrf()
    expires = int(time.time()) + settings.auth.session_hours * 3600
    db.create_session(
        auth.token_hash(token), csrf, user["login"], user["role"], expires
    )

    response.set_cookie(
        auth.COOKIE_NAME,
        token,
        max_age=settings.auth.session_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )
    db.add_audit(user["login"], "вход", "панель", "ok")
    return {
        "login": user["login"],
        "role": user["role"],
        "permissions": sorted(security.permissions_for(user["role"])),
        "csrf": csrf,
    }


@router.get("/me")
async def me(request: Request) -> dict:
    session = getattr(request.state, "session", None)
    if not session:
        raise HTTPException(status_code=401, detail="требуется вход")
    return {
        "login": session["login"],
        "role": session["role"],
        "permissions": sorted(security.permissions_for(session["role"])),
        "csrf": session["csrf"],
    }


@router.post("/password")
async def change_password(payload: PasswordIn, request: Request, response: Response) -> dict:
    """Смена своего пароля. После смены все сессии завершаются."""
    session = getattr(request.state, "session", None) or {}
    user = db.get_user_by_login(session.get("login", ""))
    if user is None or not security.verify_password(payload.current, user["password_hash"]):
        raise HTTPException(status_code=400, detail="текущий пароль неверен")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="пароль не короче 6 символов")
    db.update_user(user["id"], password_hash=security.hash_password(payload.password))
    db.delete_sessions_for_login(user["login"])
    db.add_audit(user["login"], "пароль", "своя учётка", "ok")
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return {"ok": True, "relogin": True}


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(auth.COOKIE_NAME)
    session = getattr(request.state, "session", None) or {}
    if token:
        db.delete_session(auth.token_hash(token))
    if session.get("login"):
        db.add_audit(session["login"], "выход", "панель", "ok")
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return {"ok": True}
