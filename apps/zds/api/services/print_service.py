"""Print service — sacred-renderer adapter.

Calls ``apps/zds/print_renderer.py`` (and the engine's
``render_deployment_book.py`` for archive builds) verbatim.  No
modifications to either module are permitted — the Phase 0 visual
regression suite enforces this.

Architecture
────────────
The renderer functions (``render_week_html``, ``render_night_html``)
call Supabase directly.  PrintService doesn't inject data into them;
it owns the cache layer wrapped *around* them.

Cache strategy
──────────────
Every cached HTML/PDF entry is keyed with a content hash:

    print:week:{week_id}:{hash}.html
    print:week:{week_id}:{hash}.pdf

The hash is ``sha1(json({week_ending, sorted_night_ids, sorted_tm_ids}))[:8]``.
It changes whenever PlacementService caches are busted (i.e., when any
write invalidates the assignment or night cache).  Because the hash
computation reads through PlacementService (which reflects latest DB
state after invalidation), stale HTML/PDF entries are never served after
a supervisor edit — they just expire at their natural TTL while the new
hash key holds the fresh render.

``invalidate_week_prints`` explicitly clears all print:week:{id}:*
keys for cases where a manual cache flush is required (admin tooling,
tests, etc.).

PDF generation
──────────────
weasyprint converts the rendered HTML to PDF.  It is a hard dependency
for PDF endpoints — no fallback.  If it is not installed, PDF endpoints
raise RenderError immediately.  Install it separately:

    pip install weasyprint

On macOS you also need: brew install pango cairo
"""

from __future__ import annotations

import hashlib
import importlib
import json
import logging
import tempfile
from pathlib import Path
from typing import Optional

from .cache_service import CacheService
from .exceptions import NightNotFoundError, RenderError, WeekNotFoundError
from .placement_service import PlacementService

log = logging.getLogger(__name__)

_RENDERER_MODULE = "apps.zds.print_renderer"


def _load_renderer():
    """Import apps/zds/print_renderer.py via the package system.

    Package-relative imports inside print_renderer.py (``from . import
    database``, etc.) require the regular package machinery — not
    spec_from_file_location which would break them.
    """
    try:
        return importlib.import_module(_RENDERER_MODULE)
    except ImportError as exc:
        raise RuntimeError(
            f"Could not import renderer {_RENDERER_MODULE!r}. "
            "Run uvicorn from brijkillian-stack/ so the repo root is on sys.path."
        ) from exc


class PrintService:
    """Cache-through adapter for the sacred Zone Deployment Book renderer.

    Raises
    ------
    WeekNotFoundError
        When the requested week_id is not in the DB.
    NightNotFoundError
        When the requested night_id is not in the DB.
    RenderError
        When the renderer raises any exception.
    """

    HTML_TTL = 3600   # 1 hour  — HTML is cheap to re-render
    PDF_TTL  = 7200   # 2 hours — PDF is CPU-heavy (weasyprint)

    def __init__(self, placement: PlacementService, cache: CacheService):
        self.placement = placement
        self.cache = cache
        self._renderer = None   # lazy-loaded to avoid import side effects at DI time

    @property
    def renderer(self):
        if self._renderer is None:
            self._renderer = _load_renderer()
        return self._renderer

    # ── Content hashing ───────────────────────────────────────────────────

    async def _week_content_hash(self, week_id: str) -> str:
        """Compute a short hash that changes whenever week/assignment data changes.

        Reads through the PlacementService cache layer — so if assignments
        were invalidated by a write, the hash will reflect the fresh data
        on the very next call.
        """
        week    = await self.placement.get_week(week_id) or {}
        nights  = await self.placement.get_week_nights(week_id)
        assigns = await self.placement.get_week_assignments(week_id)

        night_ids = sorted(n.get("id", "") for n in nights)

        # For each night, capture sorted list of assigned TM IDs (or "" for empty).
        tm_ids: dict[str, list[str]] = {}
        for nid in night_ids:
            rows = assigns.get(nid, [])
            tm_ids[nid] = sorted(r.get("tm_id") or "" for r in rows)

        payload = json.dumps(
            {
                "week_ending": week.get("week_ending", ""),
                "status":      week.get("status", ""),
                "night_ids":   night_ids,
                "tm_ids":      tm_ids,
            },
            sort_keys=True,
        )
        return hashlib.sha1(payload.encode()).hexdigest()[:8]

    async def _night_content_hash(self, night_id: str) -> str:
        """Same as _week_content_hash but for a single night."""
        rows = await self.placement.get_night_assignments(night_id)
        night = await self.placement.get_night(night_id)

        payload = json.dumps(
            {
                "night_id":  night_id,
                "night_date": night.night_date if night else "",
                "tm_ids":    sorted(r.get("tm_id") or "" for r in rows),
            },
            sort_keys=True,
        )
        return hashlib.sha1(payload.encode()).hexdigest()[:8]

    # ── Week HTML ─────────────────────────────────────────────────────────

    async def render_week_html(self, week_id: str) -> tuple[bytes, str]:
        """Return *(html_bytes, filename)* for a full-week deployment book.

        The filename embeds the content hash so browsers can use it as a
        cache-busting hint without needing ``Cache-Control: no-cache``.
        """
        week = await self.placement.get_week(week_id)
        if not week:
            raise WeekNotFoundError(week_id)

        content_hash = await self._week_content_hash(week_id)
        cache_key    = f"print:week:{week_id}:{content_hash}"

        cached = await self.cache.get(cache_key)
        if cached is not None:
            log.debug("print cache hit: %s", cache_key)
            html_str = cached if isinstance(cached, str) else str(cached)
            filename = self._week_filename(week, content_hash, "html")
            return html_str.encode("utf-8"), filename

        log.debug("print cache miss — rendering week %s", week_id)
        try:
            html_str = self.renderer.render_week_html(week_id)
        except Exception as exc:
            raise RenderError(
                f"Renderer failed for week {week_id}: {exc}"
            ) from exc

        await self.cache.set(cache_key, html_str, ttl=self.HTML_TTL)
        filename = self._week_filename(week, content_hash, "html")
        return html_str.encode("utf-8"), filename

    # ── Week PDF ──────────────────────────────────────────────────────────

    async def render_week_pdf(self, week_id: str) -> tuple[bytes, str]:
        """Return *(pdf_bytes, filename)* for a full-week deployment book PDF."""
        week = await self.placement.get_week(week_id)
        if not week:
            raise WeekNotFoundError(week_id)

        content_hash = await self._week_content_hash(week_id)
        cache_key    = f"print:week:{week_id}:{content_hash}:pdf"

        cached = await self.cache.get(cache_key)
        if cached is not None:
            log.debug("pdf cache hit: %s", cache_key)
            pdf_bytes = (
                bytes(cached) if isinstance(cached, list)
                else cached.encode("latin-1") if isinstance(cached, str)
                else cached
            )
            return pdf_bytes, self._week_filename(week, content_hash, "pdf")

        # Render HTML first (re-uses its own cache).
        html_bytes, _ = await self.render_week_html(week_id)
        pdf_bytes = self._html_to_pdf(html_bytes.decode("utf-8"))

        # Store PDF bytes as a Latin-1 string (JSON-safe binary representation).
        await self.cache.set(
            cache_key,
            html_bytes.decode("utf-8"),  # cache the source HTML for re-conversion
            ttl=self.PDF_TTL,
        )
        return pdf_bytes, self._week_filename(week, content_hash, "pdf")

    # ── Night HTML ────────────────────────────────────────────────────────

    async def render_night_html(self, night_id: str) -> tuple[bytes, str]:
        """Return *(html_bytes, filename)* for a single night."""
        night = await self.placement.get_night(night_id)
        if not night:
            raise NightNotFoundError(night_id)

        content_hash = await self._night_content_hash(night_id)
        cache_key    = f"print:night:{night_id}:{content_hash}"

        cached = await self.cache.get(cache_key)
        if cached is not None:
            log.debug("print cache hit: %s", cache_key)
            return cached.encode("utf-8"), self._night_filename(night, content_hash, "html")

        log.debug("print cache miss — rendering night %s", night_id)
        try:
            html_str = self.renderer.render_night_html(night_id)
        except Exception as exc:
            raise RenderError(
                f"Renderer failed for night {night_id}: {exc}"
            ) from exc

        await self.cache.set(cache_key, html_str, ttl=self.HTML_TTL)
        return html_str.encode("utf-8"), self._night_filename(night, content_hash, "html")

    # ── Night PDF ─────────────────────────────────────────────────────────

    async def render_night_pdf(self, night_id: str) -> tuple[bytes, str]:
        """Return *(pdf_bytes, filename)* for a single night PDF."""
        night = await self.placement.get_night(night_id)
        if not night:
            raise NightNotFoundError(night_id)

        content_hash = await self._night_content_hash(night_id)
        cache_key    = f"print:night:{night_id}:{content_hash}:pdf"

        cached = await self.cache.get(cache_key)
        if cached is not None:
            pdf_bytes = (
                cached.encode("latin-1") if isinstance(cached, str) else cached
            )
            return pdf_bytes, self._night_filename(night, content_hash, "pdf")

        html_bytes, _ = await self.render_night_html(night_id)
        pdf_bytes = self._html_to_pdf(html_bytes.decode("utf-8"))
        await self.cache.set(cache_key, html_bytes.decode("utf-8"), ttl=self.PDF_TTL)
        return pdf_bytes, self._night_filename(night, content_hash, "pdf")

    # ── Cache invalidation ────────────────────────────────────────────────

    async def invalidate_week_prints(self, week_id: str) -> int:
        """Explicitly bust all cached print artifacts for a week.

        Returns the count of keys deleted.  Call after any write that
        changes the rendered content (the content-hash mechanism handles
        this automatically, but explicit invalidation is useful for admin
        tooling and tests).
        """
        deleted = await self.cache.delete_pattern(f"print:week:{week_id}:*")
        log.info("invalidated %d print cache entries for week %s", deleted, week_id)
        return deleted

    async def invalidate_night_prints(self, night_id: str) -> int:
        """Bust all cached print artifacts for a night."""
        deleted = await self.cache.delete_pattern(f"print:night:{night_id}:*")
        log.info("invalidated %d print cache entries for night %s", deleted, night_id)
        return deleted

    # ── PDF conversion ────────────────────────────────────────────────────

    @staticmethod
    def _html_to_pdf(html: str) -> bytes:
        """Convert HTML to PDF bytes via weasyprint.

        weasyprint is the ONE PDF engine in this codebase.  No fallback.
        If it is not installed, RenderError is raised immediately — do
        not add silent degradation.
        """
        try:
            from weasyprint import HTML as WP_HTML  # type: ignore[import]
        except ImportError as exc:
            raise RenderError(
                "weasyprint is not installed. "
                "Install it: pip install weasyprint. "
                "On macOS also: brew install pango cairo"
            ) from exc

        try:
            return WP_HTML(string=html).write_pdf()
        except Exception as exc:
            raise RenderError(f"weasyprint PDF conversion failed: {exc}") from exc

    # ── Filename helpers ──────────────────────────────────────────────────

    @staticmethod
    def _week_filename(week: dict, content_hash: str, ext: str) -> str:
        we = week.get("week_ending", "unknown")
        return f"zone_deployment_book_{we}_{content_hash}.{ext}"

    @staticmethod
    def _night_filename(night, content_hash: str, ext: str) -> str:
        date = getattr(night, "night_date", None) or "unknown"
        day  = (getattr(night, "day_name", None) or "night").lower()[:3]
        return f"zone_deployment_book_{date}_{day}_{content_hash}.{ext}"
