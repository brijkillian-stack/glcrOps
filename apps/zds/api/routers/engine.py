"""Engine router — run the ZDS fill engine from the web UI.

Public surface
──────────────
    POST /v1/engine/night/{night_id}/run   → EngineRunResult
    POST /v1/engine/week/{week_id}/run     → EngineRunResult

Both endpoints run ``fill_engine.py`` as a subprocess (via engine_bridge),
apply the results to Supabase zone_assignments (respecting is_locked),
invalidate the placement cache, and return a summary the frontend can
display as a completion toast.

Because the engine subprocess can take up to 90 s, both endpoints use
``asyncio.to_thread`` to avoid blocking the FastAPI event loop.

Error handling
──────────────
• Engine subprocess failure → 200 with success=False and a human-readable
  error string.  The frontend should surface this as an error toast rather
  than retrying indefinitely.
• Night/week not found       → 404
• Unexpected exception       → 503
"""

from __future__ import annotations

import asyncio
import importlib
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..core.dependencies import get_placement_service
from ..services.placement_service import PlacementService

log = logging.getLogger("zds.api.engine")

# ── Lazy engine imports (same importlib pattern as placement_service.py) ──────
# We must use importlib.import_module so that each module is registered under
# its full package name (e.g. "apps.zds.database").  A bare
# `from database import ...` would import it as a top-level module, causing
# the relative import `from .engine_bridge import ...` inside database.py to
# raise "attempted relative import with no known parent package".

_ENGINE_BRIDGE_MODULE = "apps.zds.engine_bridge"
_DATABASE_MODULE      = "apps.zds.database"


def _load_engine_bridge():
    for name in (_ENGINE_BRIDGE_MODULE, "zds.engine_bridge", "engine_bridge"):
        try:
            return importlib.import_module(name)
        except ImportError:
            continue
    raise RuntimeError(
        f"Could not import engine_bridge (tried {_ENGINE_BRIDGE_MODULE!r}, "
        "'zds.engine_bridge', 'engine_bridge')"
    )


def _load_database():
    for name in (_DATABASE_MODULE, "zds.database", "database"):
        try:
            return importlib.import_module(name)
        except ImportError:
            continue
    raise RuntimeError(
        f"Could not import database (tried {_DATABASE_MODULE!r}, "
        "'zds.database', 'database')"
    )

router = APIRouter(prefix="/v1/engine", tags=["Engine"])


# ── Response model ────────────────────────────────────────────────────────────

class EngineRunResult(BaseModel):
    success:            bool
    scope:              str        # "night" | "week"
    updated:            int        # slots filled/updated
    locked_skipped:     int        # is_locked slots left untouched
    unresolved_cleared: int        # slots cleared because no eligible TM
    unresolved:         list[str]  # slot codes with no assignment
    fill_rate:          float      # 0–100 (percent of filled slots post-run)
    week_ending:        str        # "YYYY-MM-DD" from the engine audit
    message:            str        # human-readable summary
    error:              Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=404, detail={"error": "not_found", "detail": detail})

def _unavailable(detail: str) -> HTTPException:
    return HTTPException(status_code=503, detail={"error": "unavailable", "detail": detail})


def _run_engine_sync(week_id: str, target_night_id: Optional[str] = None) -> dict:
    """Synchronous wrapper — runs inside asyncio.to_thread.

    Uses importlib loaders so database.py is always imported under its full
    package name, keeping its internal relative imports (`from .engine_bridge`)
    valid regardless of the server's working directory.
    """
    try:
        bridge_mod = _load_engine_bridge()
        db_mod     = _load_database()
        run_fill_engine    = bridge_mod.run_fill_engine
        sync_engine_to_week = db_mod.sync_engine_to_week
    except Exception as exc:
        return {
            "success": False, "scope": "unknown",
            "updated": 0, "locked_skipped": 0, "unresolved_cleared": 0,
            "unresolved": [], "fill_rate": 0.0, "week_ending": "",
            "message": "", "error": f"Import failed: {exc}",
        }

    scope = "night" if target_night_id else "week"
    log.info("Running fill engine [scope=%s week=%s night=%s]",
             scope, week_id, target_night_id or "—")

    # Look up the week's linked schedule file so the engine runs on the
    # correct ADP export rather than whatever file happens to be newest.
    schedule_file: Optional[str] = None
    try:
        from shared.db import get_client as _get_db
        _sb = _get_db()
        _wk = _sb.table("weeks").select("schedule_path").eq("id", week_id).single().execute()
        schedule_file = (_wk.data or {}).get("schedule_path") or None
        if schedule_file:
            log.info("Engine will use schedule file: %s", schedule_file)
        else:
            log.warning("Week %s has no schedule_path — engine will auto-detect", week_id)
    except Exception as exc:
        log.warning("Could not read schedule_path for week %s: %s", week_id, exc)

    engine_result = run_fill_engine(schedule_file=schedule_file)

    if engine_result.get("error"):
        return {
            "success": False, "scope": scope,
            "updated": 0, "locked_skipped": 0, "unresolved_cleared": 0,
            "unresolved": [], "fill_rate": 0.0,
            "week_ending": engine_result.get("week_ending", ""),
            "message": "",
            "error": engine_result["error"],
        }

    sync_summary = sync_engine_to_week(
        week_id,
        engine_result,
        target_night_id=target_night_id,
    )

    if sync_summary.get("error"):
        return {
            "success": False, "scope": scope,
            "updated": 0, "locked_skipped": 0, "unresolved_cleared": 0,
            "unresolved": [], "fill_rate": 0.0,
            "week_ending": engine_result.get("week_ending", ""),
            "message": "",
            "error": sync_summary["error"],
        }

    updated   = sync_summary.get("updated", 0)
    locked    = sync_summary.get("skipped_locked", 0)
    cleared   = sync_summary.get("unresolved_cleared", 0)
    unresolved_list = [
        p.get("zone_slot", "?")
        for p in (engine_result.get("unresolved", []) or [])
    ]

    bits = [f"{updated} slot(s) filled"]
    if cleared:   bits.append(f"{cleared} cleared (no eligible TM)")
    if locked:    bits.append(f"{locked} locked preserved")
    if unresolved_list: bits.append(f"{len(unresolved_list)} unresolved")
    message = "Engine ran (" + scope + "): " + ", ".join(bits) + "."

    # Rough fill rate from placements list
    all_placed = engine_result.get("placements", []) or []
    night_placed = [
        p for p in all_placed
        if (not target_night_id) or (p.get("night_id") == target_night_id)
    ]
    fill_rate = 0.0
    if all_placed:
        filled = sum(1 for p in (night_placed or all_placed) if p.get("tm_display_name"))
        total  = len(night_placed or all_placed)
        fill_rate = round((filled / total * 100) if total else 0.0, 1)

    return {
        "success":            True,
        "scope":              scope,
        "updated":            updated,
        "locked_skipped":     locked,
        "unresolved_cleared": cleared,
        "unresolved":         unresolved_list,
        "fill_rate":          fill_rate,
        "week_ending":        engine_result.get("week_ending", ""),
        "message":            message,
        "error":              None,
    }


# ═════════════════════════════════════════════════════════════════════════════
# POST /v1/engine/night/{night_id}/run
# ═════════════════════════════════════════════════════════════════════════════

@router.post(
    "/night/{night_id}/run",
    response_model=EngineRunResult,
    summary="Run the fill engine for a single night",
    responses={
        200: {"description": "Engine completed (check success field for pass/fail)"},
        404: {"description": "Night not found"},
        503: {"description": "Unexpected server error"},
    },
)
async def run_engine_night(
    night_id: str,
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Run fill_engine.py and apply results to one night's zone_assignments.

    Locked slots are never overwritten.  After sync the night's placement
    cache is invalidated so the next GET /placements returns fresh data.

    The engine runs as a subprocess (slow — up to 90 s); the endpoint uses
    ``asyncio.to_thread`` to avoid blocking the event loop.
    """
    # Resolve night → week_id
    try:
        night = await placement_service.get_night(night_id)
    except Exception as exc:
        log.exception("get_night(%s) failed", night_id)
        raise _unavailable(str(exc))

    if night is None:
        raise _not_found(f"Night not found: {night_id!r}")

    night_dict = night.model_dump() if hasattr(night, "model_dump") else dict(night)
    week_id    = night_dict.get("week_id")
    if not week_id:
        raise _unavailable("Night has no associated week_id")

    log.info("Engine run requested for night %s (week %s)", night_id, week_id)

    # Run engine in thread pool — it's a long-running synchronous subprocess
    try:
        result = await asyncio.to_thread(
            _run_engine_sync, week_id, night_id
        )
    except Exception as exc:
        log.exception("_run_engine_sync raised for night %s", night_id)
        raise _unavailable(str(exc))

    # Invalidate cache so next placements fetch is fresh
    try:
        await placement_service.invalidate_night(night_id)
    except Exception as exc:
        log.warning("Cache invalidation failed for night %s: %s", night_id, exc)

    log.info(
        "Engine run complete [night=%s success=%s updated=%s]",
        night_id, result.get("success"), result.get("updated"),
    )
    return EngineRunResult(**result)


# ═════════════════════════════════════════════════════════════════════════════
# POST /v1/engine/week/{week_id}/run
# ═════════════════════════════════════════════════════════════════════════════

@router.post(
    "/week/{week_id}/run",
    response_model=EngineRunResult,
    summary="Run the fill engine for an entire week",
    responses={
        200: {"description": "Engine completed (check success field for pass/fail)"},
        404: {"description": "Week not found"},
        503: {"description": "Unexpected server error"},
    },
)
async def run_engine_week(
    week_id: str,
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Run fill_engine.py and apply results to all nights in a week.

    Same as the night endpoint but without ``target_night_id`` so all nights
    in the week are updated.  Used by the Week Overview "Run Engine" action.
    """
    try:
        week = await placement_service.get_week(week_id)
    except Exception as exc:
        log.exception("get_week(%s) failed", week_id)
        raise _unavailable(str(exc))

    if week is None:
        raise _not_found(f"Week not found: {week_id!r}")

    log.info("Engine run requested for week %s", week_id)

    try:
        result = await asyncio.to_thread(
            _run_engine_sync, week_id, None
        )
    except Exception as exc:
        log.exception("_run_engine_sync raised for week %s", week_id)
        raise _unavailable(str(exc))

    # Invalidate all nights in the week
    try:
        await placement_service.invalidate_week(week_id)
    except Exception as exc:
        log.warning("Cache invalidation failed for week %s: %s", week_id, exc)

    log.info(
        "Engine run complete [week=%s success=%s updated=%s]",
        week_id, result.get("success"), result.get("updated"),
    )
    return EngineRunResult(**result)
