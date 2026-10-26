"""Поиск образов и тегов Docker Hub."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app import images

router = APIRouter(prefix="/api/v1", tags=["images"])


@router.get("/images/search")
async def search_images(q: str = Query(min_length=2, max_length=64)) -> dict:
    try:
        results = await images.search(q.strip())
    except images.ImageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"query": q, "count": len(results), "results": results}


@router.get("/images/tags")
async def image_tags(name: str = Query(min_length=1, max_length=200)) -> dict:
    try:
        tags = await images.tags(name.strip())
    except images.ImageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"name": name, "tags": tags}


@router.get("/images/details")
async def image_details(name: str = Query(min_length=1, max_length=200)) -> dict:
    try:
        return await images.details(name.strip())
    except images.ImageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
