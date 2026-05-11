"""Print router — Zone Deployment Book HTML and PDF endpoints.

Public surface
──────────────
    GET /v1/print/week/{week_id}.html    → text/html
    GET /v1/print/week/{week_id}.pdf     → application/pdf
    GET /v1/print/night/{night_id}.html  → text/html
    GET /v1/print/night/{night_id}.pdf   → application/pdf

URL convention
──────────────
Suffixes in the path (not Accept headers) determine the format so
browsers open the right viewer without any content negotiation:
a .html URL renders inline in the browser tab; a .pdf URL opens
in the browser's built-in PDF viewer.

Error envelopes
───────────────
    404 → {"error": "not_found", "detail": "..."}
    500 → {"error": "render_failed", "detail": "..."}

Cache headers
─────────────
``Cache-Control: private, max-age=300`` on all responses.  The
PrintService already caches aggressively (1–2 h keyed by content
hash); the HTTP cache hint is a belt-and-suspenders hedge for CDNs
or browser history.

``Content-Disposition: inline; filename="…"`` carries the cache-bust
filename so devtools / download dialogs show the hash-bearing name.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response

from ..core.dependencies import get_print_service
from ..services.exceptions import NightNotFoundError, RenderError, WeekNotFoundError
from ..services.print_service import PrintService

log = logging.getLogger("zds.api.print")

router = APIRouter(prefix="/v1/print", tags=["Print"])

_CACHE_CONTROL = "private, max-age=300"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _not_found(detail: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": "not_found", "detail": detail},
    )


def _render_failed(detail: str) -> HTTPException:
    return HTTPException(
        status_code=500,
        detail={"error": "render_failed", "detail": detail},
    )


# ═════════════════════════════════════════════════════════════════════════════
# Week endpoints
# ═════════════════════════════════════════════════════════════════════════════

@router.get(
    "/week/{week_id}.html",
    response_class=HTMLResponse,
    summary="Full-week deployment book (HTML)",
    responses={
        200: {"content": {"text/html": {}}, "description": "Rendered HTML for the week"},
        404: {"description": "Week not found"},
        500: {"description": "Renderer failure"},
    },
)
async def export_week_html(
    week_id: str,
    print_service: PrintService = Depends(get_print_service),
):
    """Render the complete Zone Deployment Book for a week as HTML.

    The HTML is print-ready: open it in a browser and press Ctrl+P
    (or use the PDF endpoint which does the same via weasyprint).

    The response is cached aggressively in PrintService (TTL 1 h keyed
    by content hash).  Repeat calls that hit the cache respond in < 10 ms.
    """
    try:
        html_bytes, filename = await print_service.render_week_html(week_id)
    except WeekNotFoundError as exc:
        raise _not_found(str(exc))
    except RenderError as exc:
        log.exception("Renderer failed for week %s", week_id)
        raise _render_failed(str(exc))

    return HTMLResponse(
        content=html_bytes.decode("utf-8"),
        headers={
            "Cache-Control":       _CACHE_CONTROL,
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )


@router.get(
    "/week/{week_id}.pdf",
    summary="Full-week deployment book (PDF)",
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF for the week"},
        404: {"description": "Week not found"},
        500: {"description": "Renderer failure — weasyprint may not be installed"},
    },
)
async def export_week_pdf(
    week_id: str,
    print_service: PrintService = Depends(get_print_service),
):
    """Render the complete Zone Deployment Book for a week as a PDF.

    Uses weasyprint to convert the renderer's HTML output to PDF.
    Cached for 2 hours (keyed by content hash).  PDF generation is
    CPU-heavy; the long TTL is intentional.

    ``Content-Disposition: inline`` so the browser opens the PDF viewer
    rather than downloading — supervisors want to view, not download.
    """
    try:
        pdf_bytes, filename = await print_service.render_week_pdf(week_id)
    except WeekNotFoundError as exc:
        raise _not_found(str(exc))
    except RenderError as exc:
        log.exception("PDF render failed for week %s", week_id)
        raise _render_failed(str(exc))

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Cache-Control":       _CACHE_CONTROL,
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )


# ═════════════════════════════════════════════════════════════════════════════
# Night endpoints
# ═════════════════════════════════════════════════════════════════════════════

@router.get(
    "/night/{night_id}.html",
    response_class=HTMLResponse,
    summary="Single-night deployment book (HTML)",
    responses={
        200: {"content": {"text/html": {}}, "description": "Rendered HTML for the night"},
        404: {"description": "Night not found"},
        500: {"description": "Renderer failure"},
    },
)
async def export_night_html(
    night_id: str,
    print_service: PrintService = Depends(get_print_service),
):
    """Render a single night's deployment book pages as HTML (2 pages)."""
    try:
        html_bytes, filename = await print_service.render_night_html(night_id)
    except NightNotFoundError as exc:
        raise _not_found(str(exc))
    except RenderError as exc:
        log.exception("Renderer failed for night %s", night_id)
        raise _render_failed(str(exc))

    return HTMLResponse(
        content=html_bytes.decode("utf-8"),
        headers={
            "Cache-Control":       _CACHE_CONTROL,
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )


@router.get(
    "/night/{night_id}.pdf",
    summary="Single-night deployment book (PDF)",
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF for the night"},
        404: {"description": "Night not found"},
        500: {"description": "Renderer failure"},
    },
)
async def export_night_pdf(
    night_id: str,
    print_service: PrintService = Depends(get_print_service),
):
    """Render a single night's deployment book as PDF."""
    try:
        pdf_bytes, filename = await print_service.render_night_pdf(night_id)
    except NightNotFoundError as exc:
        raise _not_found(str(exc))
    except RenderError as exc:
        log.exception("PDF render failed for night %s", night_id)
        raise _render_failed(str(exc))

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Cache-Control":       _CACHE_CONTROL,
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )
