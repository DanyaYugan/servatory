"""Системные настройки: домены и TLS."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import tls
from app.config import Settings

router = APIRouter(prefix="/api/v1/system", tags=["system"])


class TlsIn(BaseModel):
    domain: str = ""
    email: str = ""
    enabled: bool = False


@router.get("/tls")
async def get_tls() -> dict:
    settings = Settings.load()
    return await tls.status(settings)


@router.put("/tls")
async def put_tls(payload: TlsIn) -> dict:
    settings = Settings.load()
    try:
        return await tls.apply(settings, payload.domain, payload.email, payload.enabled)
    except tls.TlsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
