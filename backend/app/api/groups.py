"""Группы сервисов: создание, порядок, привязка контейнеров."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import db

router = APIRouter(prefix="/api/v1", tags=["groups"])


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class ReorderIn(BaseModel):
    ids: list[int]


class AssignIn(BaseModel):
    group_id: int | None = None


def _check_name(name: str) -> str:
    value = name.strip()
    if not value or len(value) > 64:
        raise HTTPException(status_code=400, detail="имя группы: от 1 до 64 символов")
    return value


@router.get("/groups")
async def list_groups() -> dict:
    return {"groups": db.list_groups()}


@router.post("/groups", status_code=201)
async def create_group(payload: GroupIn) -> dict:
    name = _check_name(payload.name)
    try:
        group = db.create_group(name)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail=f"группа уже есть: {name}") from exc
    return {"group": group}


@router.patch("/groups/{group_id}")
async def rename_group(group_id: int, payload: GroupIn) -> dict:
    name = _check_name(payload.name)
    try:
        group = db.rename_group(group_id, name)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail=f"группа уже есть: {name}") from exc
    if group is None:
        raise HTTPException(status_code=404, detail="группа не найдена")
    return {"group": group}


@router.delete("/groups/{group_id}")
async def delete_group(group_id: int) -> dict:
    if not db.delete_group(group_id):
        raise HTTPException(status_code=404, detail="группа не найдена")
    return {"ok": True, "id": group_id}


@router.post("/groups/reorder")
async def reorder_groups(payload: ReorderIn) -> dict:
    known = {item["id"] for item in db.list_groups()}
    if set(payload.ids) - known:
        raise HTTPException(status_code=400, detail="неизвестная группа в списке")
    db.reorder_groups(payload.ids)
    return {"groups": db.list_groups()}


@router.post("/containers/{container_name}/group")
async def assign_container(container_name: str, payload: AssignIn) -> dict:
    if payload.group_id is not None:
        known = {item["id"] for item in db.list_groups()}
        if payload.group_id not in known:
            raise HTTPException(status_code=404, detail="группа не найдена")
    db.assign_container(container_name, payload.group_id)
    return {"ok": True, "container": container_name, "group_id": payload.group_id}
