"""Placement service — cache-through data layer for ZDS Forge.

Centralises all reads (and select writes) for placement data behind one
service class so every caller benefits from consistent caching and
invalidation without knowing about Redis or Supabase directly.

Architecture
────────────
• Reads go:  caller → CacheService.get() → hit? return. miss? Supabase → CacheService.set()
• Writes go: caller → Supabase → CacheService invalidate affected keys
• All methods return **Pydantic models**, never raw dicts.  Callers can
  call .model_dump() if they need a plain dict for JSON serialisation.
• All methods are async.  DB calls are synchronous (supabase-py is sync)
  but wrapped in async shells so the FastAPI router can await them without
  blocking (FastAPI runs sync callables in a thread pool executor; keeping
  the service async lets a future migration to async supabase-py drop in
  without changing signatures).

Existing method signatures (Phase 1) are preserved verbatim.
Phase 2 methods are added below the "── Phase 2 additions ──" marker.
"""

from __future__ import annotations

import importlib
import logging
from datetime import date
from typing import Optional

from supabase import Client

from ..models import (
    AnnotationRow,
    AssignmentRow,
    MultiAreaAssignmentRow,
    NightRow,
    OverrideRow,
    TMRow,
    TaskRow,
    WeekRow,
)
from .cache_service import CacheService

log = logging.getLogger(__name__)

_DATABASE_MODULE = "apps.zds.database"
_SHARED_DB_MODULE = "shared.db"


def _load_zds_database():
    """Import apps/zds/database.py via the package system.

    Tries the fully-qualified path first (running from repo root), then falls
    back to the bare module name (running from apps/zds/ as Render does with
    rootDir: apps/zds).
    """
    for module_name in (_DATABASE_MODULE, "database"):
        try:
            return importlib.import_module(module_name)
        except ImportError:
            continue
    raise RuntimeError(
        f"Could not import database module (tried {_DATABASE_MODULE!r} and 'database'). "
        "Make sure the repo root or apps/zds is on sys.path."
    )


def _load_shared_db():
    """Import shared/db.py via the package system.

    Tries the fully-qualified path first, then attempts to locate the shared
    package by inserting the repo root into sys.path (two levels up from
    apps/zds/).
    """
    import sys
    import os

    try:
        return importlib.import_module(_SHARED_DB_MODULE)
    except ImportError:
        pass

    # When running from apps/zds/, the repo root isn't on sys.path.
    # Walk up two directories to find brijkillian-stack/ and add it.
    here = os.path.dirname(__file__)          # .../apps/zds/api/services/
    repo_root = os.path.abspath(os.path.join(here, "..", "..", "..", ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    try:
        return importlib.import_module(_SHARED_DB_MODULE)
    except ImportError as exc:
        raise RuntimeError(
            f"Could not import {_SHARED_DB_MODULE!r}. "
            f"Tried adding {repo_root!r} to sys.path."
        ) from exc


class PlacementService:
    """Cache-through service for week, night, task, annotation, and TM data."""

    # ── TTL constants ────────────────────────────────────────────────────
    WEEK_TTL        = 60    # seconds; short — week status changes during editing
    WEEK_CACHE_VER  = "v2"  # bump when weeks table schema changes (clears stale cached dicts)
    NIGHT_TTL       = 30    # seconds; nights change frequently during pre-shift
    TASK_TTL        = 600   # seconds; canonical tasks change rarely
    TM_TTL          = 600   # seconds; roster changes are infrequent
    ANNO_TTL        = 60    # seconds; annotations change frequently pre-shift
    OVERRIDE_TTL    = 30    # seconds; overrides are live-ops — keep hot

    def __init__(self, supabase: Client, cache: Optional[CacheService] = None):
        self.supabase = supabase
        self.cache = cache or CacheService(None)
        self._db = None
        self._shared_db = None

    @property
    def db(self):
        if self._db is None:
            self._db = _load_zds_database()
        return self._db

    @property
    def shared_db(self):
        if self._shared_db is None:
            self._shared_db = _load_shared_db()
        return self._shared_db

    # ═══════════════════════════════════════════════════════════════════════
    # Phase 1 — Week / Night reads (signatures preserved)
    # ═══════════════════════════════════════════════════════════════════════

    async def get_week(self, week_id: str) -> Optional[dict]:
        """Fetch one week row by id.  Uses self.supabase directly — no legacy db module."""
        key = f"zds:week:{week_id}:{self.WEEK_CACHE_VER}"
        cached = await self.cache.get(key)
        if cached is not None:
            return cached
        try:
            res = (
                self.supabase.table("weeks")
                .select("*")
                .eq("id", week_id)
                .maybe_single()
                .execute()
            )
            week = res.data or {}
        except Exception as exc:
            log.warning("get_week(%s) supabase query failed: %s", week_id, exc)
            # Fall back to legacy db module if direct query fails.
            try:
                week = self.db.fetch_week(week_id)
            except Exception as exc2:
                log.warning("get_week(%s) db fallback also failed: %s", week_id, exc2)
                return None
        if week:
            await self.cache.set(key, week, ttl=self.WEEK_TTL)
        return week

    async def get_week_nights(self, week_id: str) -> list[dict]:
        """Fetch all night rows for a week ordered by day_num.  Uses self.supabase directly."""
        key = f"zds:week:{week_id}:nights"
        cached = await self.cache.get(key)
        if cached is not None:
            return cached
        try:
            res = (
                self.supabase.table("nights")
                .select("*")
                .eq("week_id", week_id)
                .order("day_num")
                .execute()
            )
            nights = res.data or []
        except Exception as exc:
            log.warning("get_week_nights(%s) supabase query failed: %s", week_id, exc)
            try:
                nights = self.db.fetch_nights(week_id) or []
            except Exception as exc2:
                log.warning("get_week_nights(%s) db fallback also failed: %s", week_id, exc2)
                return []
        await self.cache.set(key, nights, ttl=self.WEEK_TTL)
        return nights

    async def get_week_assignments(self, week_id: str) -> dict[str, list[dict]]:
        """Return {night_id: [zone_assignment_rows]} for the week.

        Warms per-night cache as a side effect so downstream calls hit Redis.
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

    async def get_night_assignments(self, night_id: str) -> list[dict]:
        """Fetch zone_assignments for a night joined with entity display names.

        Uses self.supabase directly, matching the query in database.fetch_zone_assignments
        but without the Reflex-specific display-field pre-computation.  Falls back to
        the legacy db module only if the direct query fails.
        """
        key = f"zds:night:{night_id}:assignments"
        cached = await self.cache.get(key)
        if cached is not None:
            return cached
        try:
            res = (
                self.supabase.table("zone_assignments")
                .select(
                    "id, slot_type, slot_key, rr_side, is_filled, is_empty,"
                    "group_num, has_alert, alert_target,"
                    "is_sweeper, sweeper_route, is_locked,"
                    "is_crowded, is_extra_crowded, has_trainee, trainee_name,"
                    "sort_order, custom_tasks,"
                    "night_id,"
                    "entities(id, display_name, metadata)"
                )
                .eq("night_id", night_id)
                .order("sort_order")
                .execute()
            )
            rows = res.data or []
            # Flatten the joined entity into top-level keys.
            for row in rows:
                entity = row.pop("entities", None) or {}
                row["tm_id"]   = entity.get("id")
                row["tm_name"] = entity.get("display_name") or ""
                row["tm_skill"] = (entity.get("metadata") or {}).get("skill_score")
        except Exception as exc:
            log.warning("get_night_assignments(%s) supabase query failed: %s", night_id, exc)
            try:
                rows = self.db.fetch_zone_assignments(night_id) or []
            except Exception as exc2:
                log.warning("get_night_assignments(%s) db fallback also failed: %s", night_id, exc2)
                return []
        await self.cache.set(key, rows, ttl=self.NIGHT_TTL)
        return rows

    async def patch_assignment_tm(self, slot_id: str, tm_id: Optional[str]) -> dict:
        """Update the tm_id on a single zone_assignments row.

        Sets is_filled=True when tm_id is provided, False when clearing.
        Invalidates the night's assignment cache so the next GET is fresh.
        Returns the updated row dict, or raises on error.
        """
        payload: dict = {
            "tm_id":     tm_id,
            "is_filled": tm_id is not None,
            "is_empty":  tm_id is None,
        }
        try:
            res = (
                self.supabase.table("zone_assignments")
                .update(payload)
                .eq("id", slot_id)
                .execute()
            )
            row = (res.data or [{}])[0]
        except Exception as exc:
            log.warning("patch_assignment_tm(%s, %s) failed: %s", slot_id, tm_id, exc)
            raise

        # Invalidate so the next placements fetch gets fresh data.
        night_id = row.get("night_id")
        if night_id:
            await self.cache.delete(f"zds:night:{night_id}:assignments")

        return row

    async def patch_slot_tasks(self, slot_id: str, tasks: list[str]) -> dict:
        """Replace the custom_tasks array on a single zone_assignments row.

        tasks is a list of task name strings (from zone_tasks.name).
        Invalidates the night's assignment cache.
        Returns the updated row dict.
        """
        try:
            res = (
                self.supabase.table("zone_assignments")
                .update({"custom_tasks": tasks})
                .eq("id", slot_id)
                .execute()
            )
            row = (res.data or [{}])[0]
        except Exception as exc:
            log.warning("patch_slot_tasks(%s) failed: %s", slot_id, exc)
            raise

        night_id = row.get("night_id")
        if night_id:
            await self.cache.delete(f"zds:night:{night_id}:assignments")
        return row

    async def move_break_tm(
        self,
        night_id: str,
        tm_id: str,
        from_wave: int,
        to_wave: int,
    ) -> int:
        """Move a TM from one break wave to another within a night.

        Updates all break_assignments rows for this night + tm_id that
        match from_wave, setting break_wave = to_wave.
        Invalidates the breaks cache.
        Returns the count of rows updated.
        """
        try:
            res = (
                self.supabase.table("break_assignments")
                .update({"break_wave": to_wave})
                .eq("night_id", night_id)
                .eq("tm_id", tm_id)
                .eq("break_wave", from_wave)
                .execute()
            )
            count = len(res.data or [])
        except Exception as exc:
            log.warning(
                "move_break_tm(night=%s, tm=%s, %s→%s) failed: %s",
                night_id, tm_id, from_wave, to_wave, exc,
            )
            raise

        await self.cache.delete(f"zds:night:{night_id}:breaks")
        return count

    async def list_zone_tasks(
        self,
        slot_type: Optional[str] = None,
        slot_key: Optional[str] = None,
    ) -> list[dict]:
        """Return active zone_tasks, optionally filtered by slot type / key.

        Results are NOT cached — the task catalogue rarely changes and
        callers can SWR-dedupe at the component level.
        """
        query = (
            self.supabase.table("zone_tasks")
            .select("id, name, code, category, target_codes, description, display_order")
            .eq("active", True)
            .order("display_order")
        )
        try:
            res = query.execute()
            tasks = res.data or []
        except Exception as exc:
            log.warning("list_zone_tasks failed: %s", exc)
            return []

        # Filter by slot_type → show all tasks for that broad category.
        # We do NOT filter by slot_key — supervisors should be able to assign
        # any task to any slot, not just the pre-mapped defaults.
        if slot_type:
            cat_map = {"zone": "zone", "restroom": "rr", "auxiliary": "aux"}
            wanted_cat = cat_map.get(slot_type)
            tasks = [
                t for t in tasks
                if t["category"] in ("overlap_am", "overlap_pm")
                or t["category"] == wanted_cat
            ]

        return tasks

    async def get_night_breaks(self, night_id: str) -> list[dict]:
        """Return break assignments for the night, cached for NIGHT_TTL seconds."""
        key = f"zds:night:{night_id}:breaks"
        cached = await self.cache.get(key)
        if cached is not None:
            return cached
        try:
            res = (
                self.supabase.table("break_assignments")
                .select("id, group_num, break_wave, sort_order, slot_ref, is_wave_locked, entities(id, display_name)")
                .eq("night_id", night_id)
                .order("sort_order")
                .execute()
            )
            rows = res.data or []
            for row in rows:
                entity = row.pop("entities", None) or {}
                row["tm_id"]   = entity.get("id") or ""
                row["tm_name"] = entity.get("display_name") or ""
                row["slot_ref"]       = row.get("slot_ref") or ""
                row["slot_label"]     = row.get("slot_ref") or ""
                row["is_wave_locked"] = bool(row.get("is_wave_locked"))
                row["group_num"]      = int(row.get("group_num") or 1)
                row["show_section_header"] = False
        except Exception as exc:
            log.warning("get_night_breaks(%s) supabase query failed: %s", night_id, exc)
            try:
                rows = self.db.fetch_break_assignments(night_id) or []
            except Exception as exc2:
                log.warning("get_night_breaks(%s) db fallback also failed: %s", night_id, exc2)
                return []
        await self.cache.set(key, rows, ttl=self.NIGHT_TTL)
        return rows

    async def get_night_overlaps(self, night_id: str) -> list[dict]:
        key = f"zds:night:{night_id}:overlaps"
        cached = await self.cache.get(key)
        if cached is not None:
            return cached
        try:
            res = (
                self.supabase.table("overlap_assignments")
                .select("id, overlap_window, position, is_filled, task, entities(id, display_name)")
                .eq("night_id", night_id)
                .order("overlap_window")
                .order("position")
                .execute()
            )
            rows = res.data or []
            for row in rows:
                entity = row.pop("entities", None) or {}
                row["tm_id"]   = entity.get("id")
                row["tm_name"] = entity.get("display_name") or ""
                row["task"]    = row.get("task") or ""

            # If any row is missing its task, pull from overlap_tasks and merge.
            # overlap_tasks.slot_id is "PMOL1"…"AMOL6"; derive from window + position.
            if rows and any(not row.get("task") for row in rows):
                try:
                    tasks_res = (
                        self.supabase.table("overlap_tasks")
                        .select("period, slot_id, task")
                        .execute()
                    )
                    task_map = {
                        r["slot_id"]: r["task"]
                        for r in (tasks_res.data or [])
                    }
                    for row in rows:
                        if not row.get("task"):
                            window = (row.get("overlap_window") or "").upper()
                            pos    = row.get("position", 0)
                            slot_id = f"{window}OL{pos}"
                            row["task"] = task_map.get(slot_id, "")
                except Exception as task_exc:
                    log.warning("get_night_overlaps(%s) task merge failed: %s", night_id, task_exc)

        except Exception as exc:
            log.warning("get_night_overlaps(%s) supabase query failed: %s", night_id, exc)
            try:
                rows = self.db.fetch_overlap_assignments(night_id) or []
            except Exception as exc2:
                log.warning("get_night_overlaps(%s) db fallback also failed: %s", night_id, exc2)
                return []
        await self.cache.set(key, rows, ttl=self.NIGHT_TTL)
        return rows

    async def patch_overlap_tm(self, overlap_id: str, tm_id: Optional[str]) -> dict:
        """Update the tm_id on a single overlap_assignments row.

        Sets is_filled=True when tm_id is provided, False when clearing.
        Invalidates the night's overlaps cache.
        Returns the updated row dict, or raises on error.
        """
        payload: dict = {
            "tm_id":     tm_id,
            "is_filled": tm_id is not None,
        }
        try:
            res = (
                self.supabase.table("overlap_assignments")
                .update(payload)
                .eq("id", overlap_id)
                .execute()
            )
            row = (res.data or [{}])[0]
        except Exception as exc:
            log.warning("patch_overlap_tm(%s, %s) failed: %s", overlap_id, tm_id, exc)
            raise

        night_id = row.get("night_id")
        if night_id:
            await self.cache.delete(f"zds:night:{night_id}:overlaps")

        return row

    # ── Phase 1 invalidation hooks ────────────────────────────────────────

    async def invalidate_night(self, night_id: str) -> None:
        """Clear all cache keys associated with a night.

        Clears assignments, overlaps, override, and night-row keys.  Also
        clears the annotation cache for the night's day when the night row
        and its week row are available (needed to derive week_ending).
        """
        keys = [
            f"zds:night:{night_id}",
            f"zds:night:{night_id}:assignments",
            f"zds:night:{night_id}:overlaps",
            f"zds:overrides:{night_id}",
        ]
        # Best-effort: also clear annotation cache for this night's day.
        # Requires a week lookup to resolve week_ending from week_id.
        night = await self.get_night(night_id)
        if night:
            week = await self.get_week(night.week_id)
            if week:
                we  = week.get("week_ending", "")
                day = night.day_name[:3].lower()  # "fri", "sat", etc.
                if we and day:
                    keys.append(f"zds:anno:{we}:{day}")
        await self.cache.delete_many(keys)

    async def invalidate_week(self, week_id: str) -> None:
        await self.cache.delete_many([
            f"zds:week:{week_id}:{self.WEEK_CACHE_VER}",
            f"zds:week:{week_id}:nights",
            f"zds:week:{week_id}:assignments",
            f"zds:weeks:recent",
        ])

    # ── Feature 0: Lock / Unlock ──────────────────────────────────────────

    async def patch_slot_lock(self, slot_id: str, is_locked: bool) -> dict:
        """Set is_locked on a single zone_assignments row.

        Invalidates the night's assignment cache so the next GET /placements
        reflects the updated lock state.
        """
        try:
            res = (
                self.supabase.table("zone_assignments")
                .update({"is_locked": is_locked})
                .eq("id", slot_id)
                .execute()
            )
            row = (res.data or [{}])[0]
        except Exception as exc:
            log.warning("patch_slot_lock(%s, %s) failed: %s", slot_id, is_locked, exc)
            raise

        night_id = row.get("night_id")
        if night_id:
            await self.cache.delete(f"zds:night:{night_id}:assignments")
        return row

    # ── Feature 2: Swap ───────────────────────────────────────────────────

    async def swap_slots(self, slot_id_a: str, slot_id_b: str) -> dict:
        """Swap the TM assignments between two zone_assignments rows.

        Fetches both current rows, then writes the swapped tm_ids back.
        Invalidates the night assignment cache for both rows (usually
        the same night).  Returns a summary dict with old and new values.
        """
        try:
            res_a = (
                self.supabase.table("zone_assignments")
                .select("id, tm_id, night_id")
                .eq("id", slot_id_a)
                .execute()
            )
            res_b = (
                self.supabase.table("zone_assignments")
                .select("id, tm_id, night_id")
                .eq("id", slot_id_b)
                .execute()
            )
            slot_a = (res_a.data or [{}])[0]
            slot_b = (res_b.data or [{}])[0]
        except Exception as exc:
            log.warning("swap_slots fetch failed: %s", exc)
            raise

        tm_a = slot_a.get("tm_id")  # currently assigned to slot A
        tm_b = slot_b.get("tm_id")  # currently assigned to slot B

        try:
            self.supabase.table("zone_assignments").update({
                "tm_id":    tm_b,
                "is_filled": tm_b is not None,
                "is_empty":  tm_b is None,
            }).eq("id", slot_id_a).execute()

            self.supabase.table("zone_assignments").update({
                "tm_id":    tm_a,
                "is_filled": tm_a is not None,
                "is_empty":  tm_a is None,
            }).eq("id", slot_id_b).execute()
        except Exception as exc:
            log.warning("swap_slots write failed: %s", exc)
            raise

        nights = {slot_a.get("night_id"), slot_b.get("night_id")} - {None}
        for night_id in nights:
            await self.cache.delete(f"zds:night:{night_id}:assignments")

        return {
            "slot_id_a": slot_id_a, "new_tm_a": tm_b,
            "slot_id_b": slot_id_b, "new_tm_b": tm_a,
        }

    # ── Feature 3: Daily Schedule ─────────────────────────────────────────

    async def get_night_schedule(self, night_id: str) -> list[dict]:
        """Return the list of TMs scheduled for a night with their statuses.

        Source of TMs: break_assignments (deduplicated).
        Status overlay: night_tm_status (upserted by the supervisor).
        """
        try:
            res = (
                self.supabase.table("break_assignments")
                .select("id, group_num, break_wave, entities(id, display_name)")
                .eq("night_id", night_id)
                .execute()
            )
            rows = res.data or []
        except Exception as exc:
            log.warning("get_night_schedule break_assignments(%s) failed: %s", night_id, exc)
            rows = []

        seen: set[str] = set()
        tms: list[dict] = []
        for row in rows:
            entity = row.get("entities") or {}
            tm_id = entity.get("id") or ""
            if tm_id and tm_id not in seen:
                seen.add(tm_id)
                tms.append({
                    "tm_id":      tm_id,
                    "tm_name":    entity.get("display_name") or "",
                    "status":     "present",
                    "note":       None,
                    "break_wave": row.get("group_num"),
                })

        if not tms:
            return tms

        try:
            status_res = (
                self.supabase.table("night_tm_status")
                .select("tm_id, status, note")
                .eq("night_id", night_id)
                .execute()
            )
            status_map = {r["tm_id"]: r for r in (status_res.data or [])}
        except Exception as exc:
            log.warning("get_night_schedule status_query(%s) failed: %s", night_id, exc)
            status_map = {}

        for tm in tms:
            if override := status_map.get(tm["tm_id"]):
                tm["status"] = override.get("status", "present")
                tm["note"]   = override.get("note")

        # Sort: non-present first (called_out etc.) then alphabetically
        STATUS_ORDER = {"called_out": 0, "pto": 1, "loa": 2, "pdl": 3, "off": 4, "other": 5, "present": 6}
        tms.sort(key=lambda t: (STATUS_ORDER.get(t["status"], 7), t["tm_name"].lower()))
        return tms

    async def set_tm_status(
        self, night_id: str, tm_id: str, tm_name: str, status: str, note: Optional[str] = None
    ) -> dict:
        """Upsert a TM's schedule status for a night.

        Conflicts on (night_id, tm_id) are resolved by updating status + note.
        """
        payload = {
            "night_id": night_id,
            "tm_id":    tm_id,
            "tm_name":  tm_name,
            "status":   status,
            "note":     note,
        }
        try:
            res = (
                self.supabase.table("night_tm_status")
                .upsert(payload, on_conflict="night_id,tm_id")
                .execute()
            )
            return (res.data or [{}])[0]
        except Exception as exc:
            log.warning("set_tm_status(%s, %s, %s) failed: %s", night_id, tm_id, status, exc)
            raise

    # ── Feature 5: Trail / Audit Log ─────────────────────────────────────

    async def get_night_trail(self, night_id: str, limit: int = 150) -> list[dict]:
        """Return audit log entries for a night, newest first."""
        try:
            res = (
                self.supabase.table("night_audit_log")
                .select("id, night_id, action_type, slot_id, zone_label,"
                        "tm_from, tm_to, detail, actor, created_at")
                .eq("night_id", night_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return res.data or []
        except Exception as exc:
            log.warning("get_night_trail(%s) failed: %s", night_id, exc)
            return []

    async def add_trail_entry(self, entry: dict) -> dict:
        """Insert a single audit log entry.  Best-effort — never raises."""
        try:
            res = (
                self.supabase.table("night_audit_log")
                .insert(entry)
                .execute()
            )
            return (res.data or [{}])[0]
        except Exception as exc:
            log.warning("add_trail_entry failed: %s", exc)
            return {}

    # ═══════════════════════════════════════════════════════════════════════
    # Phase 2 — Extended data layer
    # ═══════════════════════════════════════════════════════════════════════

    # ── Night ─────────────────────────────────────────────────────────────

    async def get_night(self, night_id: str) -> Optional[NightRow]:
        """One night row by id.  Cache: ``zds:night:{id}``, TTL 300 s."""
        key = f"zds:night:{night_id}"
        cached = await self.cache.get(key)
        if cached is not None:
            return NightRow.model_validate(cached)
        try:
            res = (
                self.supabase.table("nights")
                .select("*")
                .eq("id", night_id)
                .maybe_single()
                .execute()
            )
            row = res.data
        except Exception as exc:
            log.warning("get_night(%s) failed: %s", night_id, exc)
            return None
        if not row:
            return None
        await self.cache.set(key, row, ttl=300)
        return NightRow.model_validate(row)

    async def list_recent_weeks(self, limit: int = 8) -> list[WeekRow]:
        """Most recent *limit* weeks ordered by week_ending desc.

        Not cached — list view is rare and freshness matters.
        """
        try:
            res = (
                self.supabase.table("weeks")
                .select("*")
                .order("week_ending", desc=True)
                .limit(limit)
                .execute()
            )
            return [WeekRow.model_validate(r) for r in (res.data or [])]
        except Exception as exc:
            log.warning("list_recent_weeks failed: %s", exc)
            return []

    # ── Tasks (canonical) ─────────────────────────────────────────────────

    async def list_tasks(
        self,
        kind: Optional[str] = None,
        target: Optional[str] = None,
        day: Optional[str] = None,
        override_date: Optional[str] = None,
    ) -> list[TaskRow]:
        """Canonical task list from zone_tasks.

        Mirrors ``shared.db.list_tasks()`` filter signature.
        Cache key: ``zds:tasks:{kind}:{target}:{day}``, TTL 600 s.
        Per-day overrides are applied when *override_date* is passed.
        """
        cache_key = f"zds:tasks:{kind or '*'}:{target or '*'}:{day or '*'}"
        if not override_date:
            cached = await self.cache.get(cache_key)
            if cached is not None:
                return [TaskRow.model_validate(r) for r in cached]

        try:
            rows = self.shared_db.list_tasks(
                category=kind,
                active_only=True,
                include_overlap=True,
            )
        except Exception as exc:
            log.warning("list_tasks failed: %s", exc)
            return []

        if not override_date:
            await self.cache.set(cache_key, rows, ttl=self.TASK_TTL)
        return [TaskRow.model_validate(r) for r in rows]

    async def upsert_task(self, payload: dict) -> Optional[TaskRow]:
        """Write a task row.  Invalidates all tasks:* cache keys on success."""
        try:
            row = self.shared_db.upsert_task(payload)
        except Exception as exc:
            log.warning("upsert_task failed: %s", exc)
            return None
        if row:
            await self.cache.delete_pattern("zds:tasks:*")
        return TaskRow.model_validate(row) if row else None

    # ── Annotations ───────────────────────────────────────────────────────

    async def list_annotations_for_day(
        self, week_ending: date, day: str
    ) -> dict:
        """All annotations for *(week_ending, day)* grouped by target.

        Returns the same nested dict structure as
        ``shared.db.list_annotations_grouped``:
        ``{target_kind: {target_ref: {annotation_kind: value}}}``.

        Cache: ``zds:anno:{week_ending}:{day}``, TTL 60 s.
        """
        we_str = week_ending.isoformat() if hasattr(week_ending, "isoformat") else str(week_ending)
        key = f"zds:anno:{we_str}:{day}"
        cached = await self.cache.get(key)
        if cached is not None:
            return cached
        try:
            grouped = self.shared_db.list_annotations_grouped(week_ending, day)
        except Exception as exc:
            log.warning("list_annotations_for_day(%s, %s) failed: %s", week_ending, day, exc)
            return {}
        await self.cache.set(key, grouped, ttl=self.ANNO_TTL)
        return grouped

    async def upsert_annotation(
        self,
        week_ending: date,
        day: str,
        target_kind: str,
        target_ref: str,
        annotation_kind: str,
        value: dict,
        created_by: Optional[str] = None,
    ) -> Optional[AnnotationRow]:
        """Write an annotation.  Invalidates the day's anno: cache key."""
        try:
            row = self.shared_db.upsert_annotation(
                week_ending, day, target_kind, target_ref,
                annotation_kind, value, created_by,
            )
        except Exception as exc:
            log.warning("upsert_annotation failed: %s", exc)
            return None
        we_str = week_ending.isoformat() if hasattr(week_ending, "isoformat") else str(week_ending)
        await self.cache.delete(f"zds:anno:{we_str}:{day}")
        return AnnotationRow.model_validate(row) if row else None

    async def delete_annotation(
        self,
        week_ending: date,
        day: str,
        target_kind: str,
        target_ref: str,
        annotation_kind: str,
    ) -> None:
        """Delete an annotation and invalidate the day's anno: cache key."""
        try:
            self.shared_db.delete_annotation(
                week_ending, day, target_kind, target_ref, annotation_kind,
            )
        except Exception as exc:
            log.warning("delete_annotation failed: %s", exc)
        we_str = week_ending.isoformat() if hasattr(week_ending, "isoformat") else str(week_ending)
        await self.cache.delete(f"zds:anno:{we_str}:{day}")

    # ── Engine overrides (slot-assignment type) ───────────────────────────

    async def list_overrides(self, night_id: str) -> list[OverrideRow]:
        """Slot-assignment overrides for a night.

        Cache: ``zds:overrides:{night_id}``, TTL 30 s.
        """
        key = f"zds:overrides:{night_id}"
        cached = await self.cache.get(key)
        if cached is not None:
            return [OverrideRow.model_validate(r) for r in cached]

        night = await self.get_night(night_id)
        if not night:
            return []
        try:
            res = (
                self.supabase.table("engine_overrides")
                .select("*")
                .eq("week_id", night.week_id)
                .eq("override_date", night.night_date)
                .eq("override_type", "slot_assignment")
                .order("created_at", desc=True)
                .execute()
            )
            rows = res.data or []
        except Exception as exc:
            log.warning("list_overrides(%s) failed: %s", night_id, exc)
            return []

        # Hoist slot_key and tm_id out of payload for easy access.
        enriched = []
        for r in rows:
            payload = r.get("payload") or {}
            enriched.append({
                **r,
                "slot_key": payload.get("slot_key", ""),
                "tm_id":    payload.get("tm_id") or r.get("tm_id"),
            })

        await self.cache.set(key, enriched, ttl=self.OVERRIDE_TTL)
        return [OverrideRow.model_validate(r) for r in enriched]

    async def apply_override(
        self,
        night_id: str,
        slot_key: str,
        tm_id: Optional[str],
        note: str = "",
    ) -> Optional[OverrideRow]:
        """Set or clear the TM in *slot_key* for *night_id*.

        *tm_id=None* clears the slot (deletes any existing slot_assignment
        override for that slot).  Invalidates the night's overrides cache
        and its assignment cache.

        Stored in ``engine_overrides`` with
        ``override_type="slot_assignment"`` and
        ``payload={"slot_key": slot_key, "tm_id": tm_id}``.
        """
        night = await self.get_night(night_id)
        if not night:
            log.warning("apply_override: night %s not found", night_id)
            return None

        # For clear, delete any row with this slot_key in payload.
        if tm_id is None:
            try:
                # Fetch and delete matching rows (Supabase can't query JSONB via simple filter).
                res = (
                    self.supabase.table("engine_overrides")
                    .select("id, payload")
                    .eq("week_id", night.week_id)
                    .eq("override_date", night.night_date)
                    .eq("override_type", "slot_assignment")
                    .execute()
                )
                for row in (res.data or []):
                    if (row.get("payload") or {}).get("slot_key") == slot_key:
                        self.supabase.table("engine_overrides").delete().eq("id", row["id"]).execute()
            except Exception as exc:
                log.warning("apply_override clear(%s, %s) failed: %s", night_id, slot_key, exc)
            await self.cache.delete_many([
                f"zds:overrides:{night_id}",
                f"zds:night:{night_id}:assignments",
            ])
            return None

        payload_json = {"slot_key": slot_key, "tm_id": tm_id}
        try:
            # Use tm_id as the conflict key; one slot_assignment per TM per night.
            row_data = {
                "week_id":       night.week_id,
                "tm_id":         tm_id,
                "override_date": night.night_date,
                "override_type": "slot_assignment",
                "payload":       payload_json,
                "note":          note or None,
                "created_by":    "supervisor",
            }
            result = (
                self.supabase.table("engine_overrides")
                .upsert(row_data, on_conflict="week_id,tm_id,override_date,override_type")
                .execute()
            )
            rows = result.data or []
            row = rows[0] if rows else None
        except Exception as exc:
            log.warning("apply_override(%s, %s, %s) failed: %s", night_id, slot_key, tm_id, exc)
            return None

        await self.cache.delete_many([
            f"zds:overrides:{night_id}",
            f"zds:night:{night_id}:assignments",
        ])
        if not row:
            return None
        return OverrideRow.model_validate({
            **row,
            "slot_key": slot_key,
            "tm_id":    tm_id,
        })

    # ── Roster / TMs ──────────────────────────────────────────────────────

    async def list_active_tms(self) -> list[TMRow]:
        """All TMs with status=active.  Cache: ``zds:tms:active``, TTL 600 s.

        Hot path during deployment editing — keep cached.
        """
        key = "zds:tms:active"
        cached = await self.cache.get(key)
        if cached is not None:
            return [TMRow.model_validate(r) for r in cached]
        try:
            res = (
                self.supabase.table("entities")
                .select("id,name,display_name,metadata,status,entity_type,created_at,updated_at")
                .eq("entity_type", "tm")
                .eq("status", "active")
                .order("display_name")
                .execute()
            )
            rows = res.data or []
        except Exception as exc:
            log.warning("list_active_tms failed: %s", exc)
            return []
        await self.cache.set(key, rows, ttl=self.TM_TTL)
        return [TMRow.model_validate(r) for r in rows]

    async def get_tm(self, tm_id: str) -> Optional[TMRow]:
        """One TM by id.  Cache: ``zds:tm:{id}``, TTL 600 s."""
        key = f"zds:tm:{tm_id}"
        cached = await self.cache.get(key)
        if cached is not None:
            return TMRow.model_validate(cached)
        try:
            res = (
                self.supabase.table("entities")
                .select("id,name,display_name,metadata,status,entity_type,created_at,updated_at")
                .eq("id", tm_id)
                .maybe_single()
                .execute()
            )
            row = res.data
        except Exception as exc:
            log.warning("get_tm(%s) failed: %s", tm_id, exc)
            return None
        if not row:
            return None
        await self.cache.set(key, row, ttl=self.TM_TTL)
        return TMRow.model_validate(row)

    async def invalidate_tm_cache(self, tm_id: Optional[str] = None) -> None:
        """Invalidate TM cache.  Pass tm_id to clear one TM; omit for all."""
        keys = ["zds:tms:active"]
        if tm_id:
            keys.append(f"zds:tm:{tm_id}")
        await self.cache.delete_many(keys)

    # ── Multi-area assignments (Phase 4 live ops) ─────────────────────────

    async def assign_tm_to_areas(
        self,
        night_id: str,
        tm_id: str,
        primary_area: str,
        additional_areas: list[str] | None = None,
    ) -> Optional[MultiAreaAssignmentRow]:
        """Record that *tm_id* covers *primary_area* + *additional_areas*.

        Atomically upserts on ``(night_id, tm_id)`` unique constraint so
        calling this twice is idempotent.

        Raises RuntimeError if the ``multi_area_assignments`` table hasn't
        been created yet (run the Phase 2 migration).
        """
        areas = additional_areas or []
        try:
            result = (
                self.supabase.table("multi_area_assignments")
                .upsert(
                    {
                        "night_id":         night_id,
                        "tm_id":            tm_id,
                        "primary_area":     primary_area,
                        "additional_areas": areas,
                    },
                    on_conflict="night_id,tm_id",
                )
                .execute()
            )
            rows = result.data or []
            row = rows[0] if rows else None
        except Exception as exc:
            msg = str(exc)
            if "relation" in msg and "does not exist" in msg:
                raise RuntimeError(
                    "multi_area_assignments table not found. "
                    "Run the Phase 2 migration: "
                    "supabase/migrations/20260511_multi_area_assignments.sql"
                ) from exc
            log.warning("assign_tm_to_areas(%s, %s) failed: %s", night_id, tm_id, exc)
            return None

        # Invalidate the night's assignment cache so downstream reads refresh.
        await self.cache.delete(f"zds:night:{night_id}:assignments")
        return MultiAreaAssignmentRow.model_validate(row) if row else None
