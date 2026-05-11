"""Read-side service for placement (zone / overlap) data.

For now this is a thin cache-through wrapper over the Reflex-app's
`apps/zds/database.py` helpers. Centralizing reads here means future
write-path services (placement edits, locking, etc.) have one place
to invalidate.

The deeper unification of this service with the engine's data layer
is tracked in the "unified data layer" workstream — this stub is the
foundation, not the final shape.
"""

from __future__ import annotations

import importlib
import logging
from typing import Optional

from supabase import Client

from .cache_service import CacheService

log = logging.getLogger(__name__)

# `apps/zds/database.py` uses package-relative imports (`from .styles
# import ...`) so it has to come in through the regular package import
# machinery — a file-spec loader breaks those relative imports.
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
    """Cache-through reader for week + night placement data."""

    WEEK_TTL = 60
    NIGHT_TTL = 30

    def __init__(self, supabase: Client, cache: Optional[CacheService] = None):
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

    # ── Week ──────────────────────────────────────────────────────

    async def get_week(self, week_id: str) -> Optional[dict]:
        key = f"zds:week:{week_id}"
        cached = await self.cache.get(key)
        if cached is not None:
            return cached
        try:
            week = self.db.fetch_week(week_id)
        except Exception as exc:
            log.warning("fetch_week(%s) failed: %s", week_id, exc)
            return None
        if week:
            await self.cache.set(key, week, ttl=self.WEEK_TTL)
        return week

    async def get_week_nights(self, week_id: str) -> list[dict]:
        key = f"zds:week:{week_id}:nights"
        cached = await self.cache.get(key)
        if cached is not None:
            return cached
        try:
            nights = self.db.fetch_nights(week_id) or []
        except Exception as exc:
            log.warning("fetch_nights(%s) failed: %s", week_id, exc)
            return []
        await self.cache.set(key, nights, ttl=self.WEEK_TTL)
        return nights

    async def get_week_assignments(self, week_id: str) -> dict[str, list[dict]]:
        """Return {night_id: [zone_assignment_rows, ...]} for the week.

        Warms per-night cache as a side effect so the renderer's
        downstream calls hit Redis.
        """
        key = f"zds:week:{week_id}:assignments"
        cached = await self.cache.get(key)
        if cached is not None:
            return cached

        nights = await self.get_week_nights(week_id)
        out: dict[str, list[dict]] = {}
        for night in nights:
            nid = night.get("id")
            if not nid:
                continue
            out[nid] = await self.get_night_assignments(nid)
        await self.cache.set(key, out, ttl=self.WEEK_TTL)
        return out

    # ── Night ─────────────────────────────────────────────────────

    async def get_night_assignments(self, night_id: str) -> list[dict]:
        key = f"zds:night:{night_id}:assignments"
        cached = await self.cache.get(key)
        if cached is not None:
            return cached
        try:
            rows = self.db.fetch_zone_assignments(night_id) or []
        except Exception as exc:
            log.warning("fetch_zone_assignments(%s) failed: %s", night_id, exc)
            return []
        await self.cache.set(key, rows, ttl=self.NIGHT_TTL)
        return rows

    async def get_night_overlaps(self, night_id: str) -> list[dict]:
        key = f"zds:night:{night_id}:overlaps"
        cached = await self.cache.get(key)
        if cached is not None:
            return cached
        try:
            rows = self.db.fetch_overlap_assignments(night_id) or []
        except Exception as exc:
            log.warning("fetch_overlap_assignments(%s) failed: %s", night_id, exc)
            return []
        await self.cache.set(key, rows, ttl=self.NIGHT_TTL)
        return rows

    # ── Invalidation hooks (for future write paths) ──────────────

    async def invalidate_night(self, night_id: str) -> None:
        await self.cache.delete(
            f"zds:night:{night_id}:assignments",
            f"zds:night:{night_id}:overlaps",
        )

    async def invalidate_week(self, week_id: str) -> None:
        await self.cache.delete(
            f"zds:week:{week_id}",
            f"zds:week:{week_id}:nights",
            f"zds:week:{week_id}:assignments",
        )
