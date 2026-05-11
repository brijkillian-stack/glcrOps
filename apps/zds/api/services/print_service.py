"""Print service — renders the GLCR Zone Deployment Book.

This is Brian's originally specified service, with three corrections
documented in the foundation commit:

  1. `Optional` is imported (was used in `_warm_cache` but missing).
  2. The renderer module that actually exposes `render_week_html` /
     `render_night_html` is `apps/zds/print_renderer.py`, not the
     engine's `render_deployment_book.py`. The engine file builds the
     static archive book and doesn't have those entry points.
  3. `print_renderer.py` uses package-relative imports (`from .
     import database`, `from .components.glcr_icons import …`) so it
     has to be loaded through the regular package import machinery —
     `importlib.util.spec_from_file_location` would break those.
     We use `importlib.import_module` to preserve the dynamic flavor
     while still going through Python's package system.
"""

from __future__ import annotations

import importlib
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
        # Real PDF rendering (WeasyPrint/Playwright) is a follow-up.
        # For now, return the HTML bytes so the route is wired and
        # callers get something useful instead of a 404/500.
        html = await self.render_week_html(week_id)
        return html.encode("utf-8")

    async def render_night_pdf(self, night_id: str) -> bytes:
        html = await self.render_night_html(night_id)
        return html.encode("utf-8")
