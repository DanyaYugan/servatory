"""Журнал действий."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app import db

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("")
async def list_audit(limit: int = Query(default=100, ge=1, le=500)) -> dict:
    return {"items": db.list_audit(limit)}
