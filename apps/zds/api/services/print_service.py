"""Print service — renders the GLCR Zone Deployment Book.

HTML path is sacred: it calls `apps/zds/print_renderer.py` unchanged
(same module that produces the supervisor-trusted book today).

PDF path renders that HTML through WeasyPrint. The HTML already
declares `@page { size: 11in 8.5in landscape; margin: 0; }` and the
on-screen print helper chrome is hidden by `@media print { .screen-only
{ display: none !important; } }`, so the generated PDF matches the
"Print to PDF" output a supervisor would get from Chrome — minus the
helper buttons, by design.
"""

from __future__ import annotations

import importlib
import io
from typing import Optional

from supabase import Client

from .cache_service import CacheService
from .placement_service import PlacementService


class PrintService:
    RENDERER_MODULE = "apps.zds.print_renderer"

    def __init__(self, supabase: Client, cache: CacheService = None):
        self.supabase = supabase
        self.cache = cache or CacheService(None)
        self._load_renderer()
        self.placement = PlacementService(supabase, cache=self.cache)

    def _load_renderer(self):
        try:
            self.rdb = importlib.import_module(self.RENDERER_MODULE)
        except ImportError as exc:
            raise RuntimeError(
                f"Could not import renderer module {self.RENDERER_MODULE!r}. "
                "Make sure the repo root is on sys.path (uvicorn run from "
                "brijkillian-stack/)."
            ) from exc

    async def _warm_cache(
        self,
        week_id: Optional[str] = None,
        night_id: Optional[str] = None,
    ):
        if week_id:
            await self.placement.get_week_assignments(week_id)
        if night_id:
            await self.placement.get_night_assignments(night_id)

    async def render_week_html(self, week_id: str) -> str:
        await self._warm_cache(week_id=week_id)
        return self.rdb.render_week_html(week_id)

    async def render_night_html(self, night_id: str) -> str:
        await self._warm_cache(night_id=night_id)
        return self.rdb.render_night_html(night_id)

    async def render_week_pdf(self, week_id: str) -> bytes:
        html = await self.render_week_html(week_id)
        return _html_to_pdf(html)

    async def render_night_pdf(self, night_id: str) -> bytes:
        html = await self.render_night_html(night_id)
        return _html_to_pdf(html)


def _html_to_pdf(html: str) -> bytes:
    """Convert an HTML book into a landscape PDF via WeasyPrint.

    Imported lazily so the route doesn't pay WeasyPrint's startup cost
    (font/cairo init) until a PDF is actually requested, and so a
    missing system dep produces a clean 500 with a useful message
    instead of a server that won't even import.
    """
    try:
        from weasyprint import HTML
    except ImportError as exc:
        raise RuntimeError(
            "WeasyPrint not installed. Add `weasyprint` to requirements.txt "
            "and ensure libpango / libcairo are present on the host."
        ) from exc

    buf = io.BytesIO()
    HTML(string=html).write_pdf(target=buf)
    return buf.getvalue()
