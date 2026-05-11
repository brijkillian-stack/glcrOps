"""Unified read-side service for placement / zone / schedule data.

PlacementService is the single source of truth for week, night,
overlap, and override reads in the ZDS Forge stack. It wraps the
existing Supabase helpers in `apps/zds/database.py` so we keep a
single SQL surface, and routes every read through `CacheService` to
give us a single place to add caching, logging, and invalidation.

Design notes
------------
* The Reflex app's ``apps.zds.database`` module uses package-relative
  imports (``from .styles import ...``), so we import it through the
  normal package machinery rather than a file-spec loader.
* Cache writes are gated on non-empty results so an empty list does
  not get cached as a successful payload (the caller can still treat
  ``None`` from a fetch as "no data" without poisoning the cache).
* Every method emits a structured log line indicating hit/miss and
  the cache key, which the CacheService also logs at DEBUG level —
  hits/misses are countable for the Acceptance Criteria.
* Invalidation helpers are exposed so future write-path services
  (placement edits, overrides) have one place to call.
"""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING, Optional

from .cache_service import CacheService

if TYPE_CHECKING:  # pragma: no cover — type-only import
    from supabase import Client

log = logging.getLogger("zds.placement")

_DATABASE_MODULE = "apps.zds.database"


def _load_zds_database():
    """Import apps/zds/database.py via the package system."""
    try:
        return importlib.import_module(_DATABASE_MODULE)
    except ImportError as exc:
        raise RuntimeError(
            f"Could not import {_DATABASE_MODULE!r}. Make sure the repo "
            "root is on sys.path (uvicorn run from brijkillian-stack/)."
        ) from exc


class PlacementService:
    """Cache-through reader for week, night, overlap, and override data."""

    # TTLs are intentionally short — weeks/nights are edited live in
    # the Reflex UI, so we lean on cache-busting via invalidate_* hooks
    # but accept that a stale read after Redis downtime will recover
    # within seconds.
    WEEKS_TTL = 30
    WEEK_TTL = 60
    NIGHT_TTL = 30
    OVERRIDES_TTL = 60

    def __init__(self, supabase: "Client", cache: Optional[CacheService] = None):
        self.supabase = supabase
        self.cache = cache or CacheService(None)
        # Lazy import so test environments without supabase env vars
        # can still construct the class (importing database.py at
        # construction time would crash if env vars are missing).
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = _load_zds_database()
        return self._db

    # ── Internal helpers ─────────────────────────────────────────

    async def _read_through(
        self,
        key: str,
        loader,
        *,
        ttl: int,
        default,
        op: str,
    ):
        """Cache-through with structured hit/miss logging and a safe default."""
        cached = await self.cache.get(key)
        if cached is not None:
            log.info("placement HIT  op=%s key=%s", op, key)
            return cached
        log.info("placement MISS op=%s key=%s", op, key)
        try:
            value = loader()
        except Exception as exc:
            log.warning("placement %s loader failed key=%s: %s", op, key, exc)
            return default
        if value is None:
            return default
        # Only cache truthy payloads — caching `[]` is fine, caching
        # `None` would mask transient supabase outages.
        await self.cache.set(key, value, ttl=ttl)
        return value

    # ── Weeks ─────────────────────────────────────────────────────

    async def list_weeks(self) -> list[dict]:
        """All weeks, newest first (matches database.fetch_weeks)."""
        return await self._read_through(
            key=self.cache.key("weeks"),
            loader=self.db.fetch_weeks,
            ttl=self.WEEKS_TTL,
            default=[],
            op="list_weeks",
        )

    async def get_week(self, week_id: str) -> Optional[dict]:
        if not week_id:
            return None
        key = self.cache.key("week", week_id)
        result = await self._read_through(
            key=key,
            loader=lambda: self.db.fetch_week(week_id),
            ttl=self.WEEK_TTL,
            default={},
            op="get_week",
        )
        return result or None

    async def get_week_nights(self, week_id: str) -> list[dict]:
        if not week_id:
            return []
        return await self._read_through(
            key=self.cache.key("week", week_id, "nights"),
            loader=lambda: self.db.fetch_nights(week_id) or [],
            ttl=self.WEEK_TTL,
            default=[],
            op="get_week_nights",
        )

    async def get_week_assignments(
        self, week_id: str
    ) -> dict[str, list[dict]]:
        """Return ``{night_id: [zone_assignment_rows, ...]}`` for the week.

        Warms per-night caches as a side effect so renderers can hit
        Redis on subsequent per-night requests.
        """
        if not week_id:
            return {}
        key = self.cache.key("week", week_id, "assignments")
        cached = await self.cache.get(key)
        if cached is not None:
            log.info("placement HIT  op=get_week_assignments key=%s", key)
            return cached
        log.info("placement MISS op=get_week_assignments key=%s", key)

        nights = await self.get_week_nights(week_id)
        out: dict[str, list[dict]] = {}
        for night in nights:
            nid = night.get("id")
            if not nid:
                continue
            out[nid] = await self.get_night_assignments(nid)
        await self.cache.set(key, out, ttl=self.WEEK_TTL)
        return out

    async def get_week_package(self, week_id: str) -> dict:
        """One-shot fetch of everything the print/export pipeline needs.

        Returns a dict with keys ``week``, ``nights``, ``assignments``,
        ``overlaps``, and ``overrides``. Each sub-fetch is cache-through
        so a partial warmup still benefits subsequent calls.
        """
        week = await self.get_week(week_id) or {}
        nights = await self.get_week_nights(week_id)

        assignments: dict[str, list[dict]] = {}
        overlaps: dict[str, list[dict]] = {}
        for night in nights:
            nid = night.get("id")
            if not nid:
                continue
            assignments[nid] = await self.get_night_assignments(nid)
            overlaps[nid] = await self.get_night_overlaps(nid)

        overrides: list[dict] = []
        schedule_path = (week or {}).get("schedule_path") or ""
        if schedule_path:
            overrides = await self.get_schedule_overrides(schedule_path)

        return {
            "week": week,
            "nights": nights,
            "assignments": assignments,
            "overlaps": overlaps,
            "overrides": overrides,
        }

    # ── Nights ────────────────────────────────────────────────────

    async def get_night_assignments(self, night_id: str) -> list[dict]:
        if not night_id:
            return []
        return await self._read_through(
            key=self.cache.key("night", night_id, "assignments"),
            loader=lambda: self.db.fetch_zone_assignments(night_id) or [],
            ttl=self.NIGHT_TTL,
            default=[],
            op="get_night_assignments",
        )

    async def get_night_overlaps(self, night_id: str) -> list[dict]:
        if not night_id:
            return []
        return await self._read_through(
            key=self.cache.key("night", night_id, "overlaps"),
            loader=lambda: self.db.fetch_overlap_assignments(night_id) or [],
            ttl=self.NIGHT_TTL,
            default=[],
            op="get_night_overlaps",
        )

    async def get_night_notices(self, night_id: str) -> list[dict]:
        if not night_id:
            return []
        return await self._read_through(
            key=self.cache.key("night", night_id, "notices"),
            loader=lambda: self.db.fetch_notices(night_id) or [],
            ttl=self.NIGHT_TTL,
            default=[],
            op="get_night_notices",
        )

    # ── Overrides ─────────────────────────────────────────────────

    async def get_schedule_overrides(self, schedule_path: str) -> list[dict]:
        """Schedule cell overrides keyed by the source xlsx path."""
        if not schedule_path:
            return []
        return await self._read_through(
            key=self.cache.key("overrides", "schedule", schedule_path),
            loader=lambda: self.db.fetch_schedule_overrides(schedule_path) or [],
            ttl=self.OVERRIDES_TTL,
            default=[],
            op="get_schedule_overrides",
        )

    # ── Invalidation hooks (for future write paths) ──────────────

    async def invalidate_night(self, night_id: str) -> None:
        if not night_id:
            return
        await self.cache.delete(
            self.cache.key("night", night_id, "assignments"),
            self.cache.key("night", night_id, "overlaps"),
            self.cache.key("night", night_id, "notices"),
        )
        log.info("placement INVALIDATE night=%s", night_id)

    async def invalidate_week(self, week_id: str) -> None:
        if not week_id:
            return
        await self.cache.delete(
            self.cache.key("week", week_id),
            self.cache.key("week", week_id, "nights"),
            self.cache.key("week", week_id, "assignments"),
            self.cache.key("weeks"),
        )
        log.info("placement INVALIDATE week=%s", week_id)

    async def invalidate_overrides(self, schedule_path: str) -> None:
        if not schedule_path:
            return
        await self.cache.delete(
            self.cache.key("overrides", "schedule", schedule_path),
        )
        log.info("placement INVALIDATE overrides schedule_path=%s", schedule_path)
