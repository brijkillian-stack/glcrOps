"""Nights router — per-night placement data for the Next.js ZDS frontend.

Public surface
──────────────
    GET /v1/nights/{night_id}/placements
            → NightPlacementsResponse (application/json)

Returns all zone/restroom/aux slot assignments and break-wave groupings
for a single night.  This is the primary feed for the Daily Planner and
Break Sheet pages in the Next.js app.

Cache strategy
──────────────
Zone and break assignments are cached for 30 s in PlacementService.
The ``Cache-Control`` header matches so the browser won't replay stale
coverage data longer than the server cache TTL.

Error envelopes
───────────────
    404 → {"error": "not_found", "detail": "..."}
    503 → {"error": "unavailable", "detail": "..."}
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..core.dependencies import get_placement_service
from ..models.night import NightPlacementsResponse, build_night_response
from ..services.placement_service import PlacementService

log = logging.getLogger("zds.api.nights")

router = APIRouter(prefix="/v1/nights", tags=["Nights"])

_CACHE_CONTROL = "private, max-age=30"

# Import ZONE_LABELS lazily so the router stays importable even when running
# outside the monorepo (e.g. standalone Forge container without the full
# apps.zds package installed).
try:
    from apps.zds.styles import ZONE_LABELS as _ZONE_LABELS
except ImportError:
    try:
        from zds.styles import ZONE_LABELS as _ZONE_LABELS
    except ImportError:
        try:
            from styles import ZONE_LABELS as _ZONE_LABELS  # type: ignore[import]
        except ImportError:
            _ZONE_LABELS = {}


def _not_found(detail: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": "not_found", "detail": detail},
    )


def _unavailable(detail: str) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"error": "unavailable", "detail": detail},
    )


# ═════════════════════════════════════════════════════════════════════════════
# GET /v1/nights/{night_id}/placements
# ═════════════════════════════════════════════════════════════════════════════

@router.get(
    "/{night_id}/placements",
    response_model=NightPlacementsResponse,
    summary="Night placements",
    responses={
        200: {"description": "Zone + break placements for the night"},
        404: {"description": "Night not found"},
        503: {"description": "Placement data temporarily unavailable"},
    },
)
async def get_night_placements(
    night_id: str,
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Return all slot assignments and break-wave groupings for one night.

    Fetches zone assignments and break assignments in parallel, then
    assembles the ``NightPlacementsResponse`` used by the Next.js
    Daily Planner and Break Sheet pages.

    The response shape mirrors the ``NightPlacements`` TypeScript interface
    in ``apps/web/lib/sync.ts``.  Keep both in sync when adding fields.
    """
    # Resolve the night row first (needed for date + day_name in response).
    try:
        night = await placement_service.get_night(night_id)
    except Exception as exc:
        log.exception("get_night(%s) raised", night_id)
        raise _unavailable(str(exc))

    if night is None:
        raise _not_found(f"Night not found: {night_id!r}")

    # Fetch assignments in parallel.
    try:
        zone_rows, break_rows = await asyncio.gather(
            placement_service.get_night_assignments(night_id),
            placement_service.get_night_breaks(night_id),
        )
    except Exception as exc:
        log.exception("Parallel fetch for night %s raised", night_id)
        raise _unavailable(str(exc))

    # night may be a NightRow Pydantic model — convert to dict for builder.
    night_dict = night.model_dump() if hasattr(night, "model_dump") else dict(night)

    try:
        response = build_night_response(
            night      = night_dict,
            zone_rows  = zone_rows,
            break_rows = break_rows,
            zone_labels= _ZONE_LABELS,
        )
    except Exception as exc:
        log.exception("build_night_response(%s) raised", night_id)
        raise _unavailable(f"Response assembly failed: {exc}")

    from fastapi.responses import JSONResponse
    return JSONResponse(
        content=response.model_dump(),
        headers={"Cache-Control": _CACHE_CONTROL},
    )


# ═════════════════════════════════════════════════════════════════════════════
# PATCH /v1/nights/{night_id}/placements/{slot_id}
# ═════════════════════════════════════════════════════════════════════════════

class AssignTMPayload(BaseModel):
    tm_id: Optional[str] = None   # None = clear the slot


@router.patch(
    "/{night_id}/placements/{slot_id}",
    summary="Assign or clear a TM on a slot",
    responses={
        200: {"description": "Slot updated"},
        404: {"description": "Night or slot not found"},
        503: {"description": "Update failed"},
    },
)
async def patch_night_placement(
    night_id: str,
    slot_id: str,
    payload: AssignTMPayload,
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Assign a TM to a slot or clear it (tm_id=null).

    Writes directly to ``zone_assignments`` and invalidates the night's
    assignment cache so the next ``GET /placements`` returns fresh data.

    The Next.js Daily Planner calls this optimistically — it applies the
    change locally via SWR and revalidates after the response.
    """
    try:
        row = await placement_service.patch_assignment_tm(
            slot_id=slot_id,
            tm_id=payload.tm_id,
        )
    except Exception as exc:
        log.exception("patch_assignment_tm(%s) raised", slot_id)
        raise _unavailable(str(exc))

    if not row:
        raise _not_found(f"Slot not found: {slot_id!r}")

    return {"slot_id": slot_id, "tm_id": payload.tm_id, "updated": True}


# ═════════════════════════════════════════════════════════════════════════════
# PATCH /v1/nights/{night_id}/placements/{slot_id}/tasks
# ═════════════════════════════════════════════════════════════════════════════

class SlotTasksPayload(BaseModel):
    tasks: list[str]   # ordered list of task name strings


@router.patch(
    "/{night_id}/placements/{slot_id}/tasks",
    summary="Replace custom task list on a slot",
    responses={
        200: {"description": "Tasks updated"},
        404: {"description": "Slot not found"},
        503: {"description": "Update failed"},
    },
)
async def patch_slot_tasks(
    night_id: str,
    slot_id: str,
    payload: SlotTasksPayload,
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Replace the custom_tasks array on a zone_assignments row.

    tasks is the complete desired list of task name strings — the caller
    sends the full updated array, not a delta.  Sending an empty list
    clears all custom tasks for the slot.

    Invalidates the night assignment cache so the next GET /placements
    returns fresh data including the updated task list.
    """
    try:
        row = await placement_service.patch_slot_tasks(
            slot_id=slot_id,
            tasks=payload.tasks,
        )
    except Exception as exc:
        log.exception("patch_slot_tasks(%s) raised", slot_id)
        raise _unavailable(str(exc))

    if not row:
        raise _not_found(f"Slot not found: {slot_id!r}")

    return {"slot_id": slot_id, "tasks": payload.tasks, "updated": True}


# ═════════════════════════════════════════════════════════════════════════════
# PATCH /v1/nights/{night_id}/breaks/move
# ═════════════════════════════════════════════════════════════════════════════

class BreakMovePayload(BaseModel):
    tm_id:     str
    from_wave: int   # 1 | 2 | 3
    to_wave:   int   # 1 | 2 | 3


@router.patch(
    "/{night_id}/breaks/move",
    summary="Move a TM between break waves",
    responses={
        200: {"description": "Break wave updated"},
        404: {"description": "Night not found or TM not in wave"},
        503: {"description": "Update failed"},
    },
)
async def move_break_tm(
    night_id: str,
    payload: BreakMovePayload,
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Move a TM from one break wave to another within a night.

    Updates all break_assignments rows for this night/TM where
    break_wave == from_wave, setting break_wave = to_wave.
    Invalidates the breaks cache.

    The Next.js sync layer calls this optimistically after moveBreakTM
    so break changes survive a page refresh.
    """
    try:
        count = await placement_service.move_break_tm(
            night_id=night_id,
            tm_id=payload.tm_id,
            from_wave=payload.from_wave,
            to_wave=payload.to_wave,
        )
    except Exception as exc:
        log.exception("move_break_tm(night=%s) raised", night_id)
        raise _unavailable(str(exc))

    if count == 0:
        raise _not_found(
            f"TM {payload.tm_id!r} not found in wave {payload.from_wave} for night {night_id!r}"
        )

    return {
        "night_id":  night_id,
        "tm_id":     payload.tm_id,
        "from_wave": payload.from_wave,
        "to_wave":   payload.to_wave,
        "rows_moved": count,
    }
