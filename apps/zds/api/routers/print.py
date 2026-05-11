"""Print router — Zone Deployment Book HTML / PDF endpoints.

Public surface:
    GET /v1/print/week/{week_id}?format=html|pdf
    GET /v1/print/night/{night_id}?format=html|pdf

Returns are wrapped in fastapi.Response so HTML stays HTML (not
JSON-encoded) and PDFs get the correct content-type.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path
from fastapi.responses import Response

from ..core.dependencies import get_redis_client, get_supabase_client
from ..services.cache_service import CacheService
from ..services.print_service import PrintService

router = APIRouter(prefix="/v1/print", tags=["Print"])


@router.get("/week/{week_id}")
async def export_week(
    week_id: str = Path(...),
    format: str = "html",
    supabase=Depends(get_supabase_client),
    redis=Depends(get_redis_client),
):
    cache = CacheService(redis)
    service = PrintService(supabase, cache=cache)
    if format == "pdf":
        pdf_bytes = await service.render_week_pdf(week_id)
        return Response(content=pdf_bytes, media_type="application/pdf")
    html = await service.render_week_html(week_id)
    return Response(content=html, media_type="text/html")


@router.get("/night/{night_id}")
async def export_night(
    night_id: str = Path(...),
    format: str = "html",
    supabase=Depends(get_supabase_client),
    redis=Depends(get_redis_client),
):
    cache = CacheService(redis)
    service = PrintService(supabase, cache=cache)
    if format == "pdf":
        pdf_bytes = await service.render_night_pdf(night_id)
        return Response(content=pdf_bytes, media_type="application/pdf")
    html = await service.render_night_html(night_id)
    return Response(content=html, media_type="text/html")
