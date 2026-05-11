"""Reoptimize service — dry-run placement simulation with planning overrides.

Wraps `apps.zds.engine_bridge.run_fill_engine` (which already supports the
`simulated_unavailable` config_override key) and adds a `force_z9` toggle plus
a before/after diff against the current week's `zone_assignments` rows.

This service never writes to Supabase — it's strictly a planning preview.
Applying the new placements is a separate workflow (sync_engine_to_week).
"""

from __future__ import annotations

import hashlib
import importlib
import json
import logging
from typing import Any, Iterable, Optional

from supabase import Client

from .cache_service import CacheService
from .placement_service import PlacementService

log = logging.getLogger(__name__)

_BRIDGE_MODULE = "apps.zds.engine_bridge"


def _load_engine_bridge():
    try:
        return importlib.import_module(_BRIDGE_MODULE)
    except ImportError as exc:
        raise RuntimeError(
            f"Could not import {_BRIDGE_MODULE!r}. Make sure the repo "
            "root is on sys.path (uvicorn run from repo root)."
        ) from exc


class ReoptimizeService:
    """Run the placement engine with planning overrides and return a diff."""

    CACHE_TTL = 120  # seconds — short, since planners iterate quickly
    CACHE_PREFIX = "zds:reoptimize"

    def __init__(self, supabase: Client, cache: Optional[CacheService] = None):
        self.supabase = supabase
        self.cache = cache or CacheService(None)
        self.placement = PlacementService(supabase, cache=self.cache)
        self._bridge = None

    @property
    def bridge(self):
        if self._bridge is None:
            self._bridge = _load_engine_bridge()
        return self._bridge

    # ── Public API ────────────────────────────────────────────────────

    async def reoptimize(
        self,
        week_id: str,
        unavailable_team_members: Optional[Iterable[str]] = None,
        force_z9: bool = False,
    ) -> dict:
        """Simulate a reoptimized placement run.

        Returns a dict with the engine result, the diff against the current
        week, and a `cached` flag indicating whether the response came from
        Redis (when configured).
        """
        unavailable = sorted({_norm_name(n) for n in (unavailable_team_members or []) if _norm_name(n)})
        cache_key = self._cache_key(week_id, unavailable, force_z9)

        cached = await self.cache.get(cache_key)
        if cached is not None:
            cached["cached"] = True
            return cached

        # 1. Fetch the current week state up front so we can diff afterwards.
        week = await self.placement.get_week(week_id)
        if not week:
            return {
                "week_id": week_id,
                "error": f"Week {week_id!r} not found.",
                "engine": None,
                "placements": [],
                "unresolved": [],
                "diff": _empty_diff(),
                "cached": False,
            }

        before_by_key = await self._current_assignments_by_key(week_id)

        # 2. Run the engine with overrides.
        config_override: dict[str, Any] = {}
        if unavailable:
            config_override["simulated_unavailable"] = list(unavailable)
        if force_z9:
            config_override["force_z9"] = True

        engine_result = self.bridge.run_fill_engine(
            schedule_file=None,
            config_override=config_override or None,
        )

        if engine_result.get("error"):
            log.warning(
                "reoptimize(%s) engine error: %s",
                week_id,
                engine_result["error"],
            )

        # 3. Build the diff.
        diff = _build_diff(before_by_key, engine_result.get("placements") or [])

        payload = {
            "week_id": week_id,
            "week_ending": engine_result.get("week_ending") or week.get("week_ending", ""),
            "overrides": {
                "unavailable_team_members": unavailable,
                "force_z9": force_z9,
            },
            "engine": {
                "error": engine_result.get("error"),
                "config_used": engine_result.get("config_used"),
            },
            "placements": engine_result.get("placements") or [],
            "unresolved": engine_result.get("unresolved") or [],
            "diff": diff,
            "cached": False,
        }

        # Only cache successful runs — error responses change with infra.
        if not engine_result.get("error"):
            await self.cache.set(cache_key, payload, ttl=self.CACHE_TTL)

        return payload

    async def invalidate(self, week_id: str) -> int:
        """Drop all cached reoptimize responses for a week (e.g. after a sync)."""
        return await self.cache.invalidate_prefix(f"{self.CACHE_PREFIX}:{week_id}:")

    # ── Internals ─────────────────────────────────────────────────────

    def _cache_key(self, week_id: str, unavailable: list[str], force_z9: bool) -> str:
        payload = json.dumps(
            {"u": sorted(unavailable), "z9": bool(force_z9)},
            sort_keys=True,
        )
        digest = hashlib.sha1(payload.encode()).hexdigest()[:12]
        return f"{self.CACHE_PREFIX}:{week_id}:{digest}"

    async def _current_assignments_by_key(self, week_id: str) -> dict[tuple, dict]:
        """Build {(date, slot_key, rr_side): {tm_name, ...}} from current DB state.

        `rr_side` is "" for non-RR slots so the dict key stays JSON-friendly.
        """
        nights = await self.placement.get_week_nights(week_id)
        out: dict[tuple, dict] = {}
        for night in nights:
            night_id = night.get("id")
            date_iso = (night.get("night_date") or "")[:10]
            if not night_id or not date_iso:
                continue
            rows = await self.placement.get_night_assignments(night_id)
            for row in rows:
                key = (
                    date_iso,
                    row.get("slot_key") or "",
                    row.get("rr_side") or "",
                )
                out[key] = {
                    "tm_id": row.get("tm_id"),
                    "tm_name": row.get("tm_name") or "",
                    "is_locked": bool(row.get("is_locked")),
                }
        return out


# ── Helpers ──────────────────────────────────────────────────────────


def _norm_name(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _empty_diff() -> dict:
    return {
        "summary": {
            "total_engine_slots": 0,
            "changed": 0,
            "unchanged": 0,
            "newly_filled": 0,
            "newly_unfilled": 0,
            "locked_preserved": 0,
        },
        "changes": [],
    }


def _engine_slot_to_db(engine_slot: str) -> Optional[tuple[str, str]]:
    """Map an engine slot code to (slot_key, rr_side). Returns None for slots
    that don't correspond to a `zone_assignments` row (overlaps, buddy)."""
    bridge = importlib.import_module(_BRIDGE_MODULE)
    if engine_slot in bridge._SKIP_SLOTS or engine_slot.startswith(("PMOL", "AMOL")):
        return None
    mapping = bridge.ENGINE_TO_SUPABASE.get(engine_slot)
    if not mapping:
        return None
    slot_key, rr_side = mapping
    return slot_key, rr_side or ""


def _build_diff(
    before_by_key: dict[tuple, dict],
    placements: list[dict],
) -> dict:
    """Compute the before/after comparison.

    `before_by_key` is keyed by (date, slot_key, rr_side); `placements` is
    the engine's raw output. Slots that don't map to a zone_assignments row
    (PM/AM overlaps, Z9 SR Buddy) are excluded from the diff so the numbers
    line up with what `sync_engine_to_week` would actually touch.
    """
    changes: list[dict] = []
    summary = {
        "total_engine_slots": 0,
        "changed": 0,
        "unchanged": 0,
        "newly_filled": 0,
        "newly_unfilled": 0,
        "locked_preserved": 0,
    }

    seen_keys: set[tuple] = set()

    for p in placements:
        engine_slot = p.get("zone_slot") or ""
        mapped = _engine_slot_to_db(engine_slot)
        if not mapped:
            continue
        slot_key, rr_side = mapped
        date_iso = str(p.get("date") or "")[:10]
        if not date_iso:
            continue

        key = (date_iso, slot_key, rr_side)
        seen_keys.add(key)
        summary["total_engine_slots"] += 1

        before = before_by_key.get(key) or {}
        before_name = before.get("tm_name") or ""
        after_name = p.get("tm_display_name") or ""
        locked = bool(before.get("is_locked"))

        if locked:
            # sync_engine_to_week never overwrites a locked slot. Surface
            # this so the UI can show "engine wanted X but the slot is locked".
            summary["locked_preserved"] += 1
            if before_name != after_name:
                changes.append({
                    "date": date_iso,
                    "slot_key": slot_key,
                    "rr_side": rr_side or None,
                    "before": before_name,
                    "after": after_name,
                    "kind": "locked",
                })
            continue

        if before_name == after_name:
            summary["unchanged"] += 1
            continue

        if before_name and not after_name:
            kind = "newly_unfilled"
            summary["newly_unfilled"] += 1
        elif not before_name and after_name:
            kind = "newly_filled"
            summary["newly_filled"] += 1
        else:
            kind = "swapped"

        summary["changed"] += 1
        changes.append({
            "date": date_iso,
            "slot_key": slot_key,
            "rr_side": rr_side or None,
            "before": before_name,
            "after": after_name,
            "kind": kind,
        })

    # Slots that existed before but the engine didn't touch (unresolved + not
    # produced as a placement) → if they had someone before, they're now blank.
    for key, before in before_by_key.items():
        if key in seen_keys:
            continue
        before_name = before.get("tm_name") or ""
        if not before_name:
            continue
        date_iso, slot_key, rr_side = key
        if bool(before.get("is_locked")):
            summary["locked_preserved"] += 1
            continue
        summary["changed"] += 1
        summary["newly_unfilled"] += 1
        changes.append({
            "date": date_iso,
            "slot_key": slot_key,
            "rr_side": rr_side or None,
            "before": before_name,
            "after": "",
            "kind": "newly_unfilled",
        })

    return {"summary": summary, "changes": changes}
