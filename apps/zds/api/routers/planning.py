"""Planning router — weekly pre-shift planning overview (GLC-12).

Public surface
──────────────
    GET /v1/planning/weekly/{week_id}
            → WeeklyPlanningOverviewResponse (application/json)

The response aggregates:
  • Week metadata (id, dates, status)
  • Night-by-night coverage snapshots (filled/unfilled slots, overrides)
  • Aggregated metrics (fatigue index, gaps, multi-area overlaps)
  • Synthetic planning notes generated from coverage analysis
  • Active slot_assignment overrides across all nights
  • Quick-action links (print HTML/PDF, reoptimize)

Cache strategy
──────────────
PlanningService caches the computed overview for 15 s keyed by week_id.
This is intentionally short — supervisors edit placements actively in the
hour before shift; stale coverage counts are worse than extra DB round-trips.

The endpoint itself adds ``Cache-Control: private, max-age=15`` so the
browser won't replay the response beyond that window.

Error envelopes
───────────────
    404 → {"error": "not_found", "detail": "..."}
    503 → {"error": "planning_unavailable", "detail": "..."}
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.dependencies import get_planning_service, get_placement_service
from ..models.planning import WeeklyPlanningOverviewResponse
from ..models.tm import TMRow
from ..models.week import WeekRow
from ..services.placement_service import PlacementService
from ..services.planning_service import PlanningService

log = logging.getLogger("zds.api.planning")

router = APIRouter(prefix="/v1/planning", tags=["Planning"])

_CACHE_CONTROL = "private, max-age=15"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _not_found(detail: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": "not_found", "detail": detail},
    )


def _planning_unavailable(detail: str) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"error": "planning_unavailable", "detail": detail},
    )


# ═════════════════════════════════════════════════════════════════════════════
# Endpoints
# ═════════════════════════════════════════════════════════════════════════════

@router.get(
    "/tasks",
    summary="Zone task catalogue",
    responses={200: {"description": "Active zone tasks, optionally filtered by slot type / key"}},
)
async def list_zone_tasks(
    slot_type: str | None = Query(None, description="zone | restroom | auxiliary"),
    slot_key:  str | None = Query(None, description="e.g. zone_8, rr_1_2, trash_1"),
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Return active zone_tasks, optionally filtered for a specific slot.

    Used by the Daily Planner task picker sheet.  Pass slot_type + slot_key
    to get only the tasks relevant to that slot (plus AM/PM overlap tasks).
    Omit both to get the full catalogue.
    """
    try:
        return await placement_service.list_zone_tasks(
            slot_type=slot_type,
            slot_key=slot_key,
        )
    except Exception as exc:
        log.exception("list_zone_tasks raised")
        raise HTTPException(status_code=503, detail={"error": "unavailable", "detail": str(exc)})


@router.get(
    "/tms",
    response_model=list[TMRow],
    summary="Active TM roster",
    responses={200: {"description": "All active TMs ordered by display name"}},
)
async def list_tms(
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Return all active TMs from the entities table.

    Used by the Daily Planner TM picker sheet — cached for 10 min in
    PlacementService (TM_TTL = 600 s).  Not paginated — the roster is
    small enough to load in full and filter client-side.
    """
    try:
        return await placement_service.list_active_tms()
    except Exception as exc:
        log.exception("list_active_tms raised")
        raise HTTPException(status_code=503, detail={"error": "unavailable", "detail": str(exc)})


@router.get(
    "/weeks",
    response_model=list[WeekRow],
    summary="List recent weeks",
    responses={200: {"description": "Most recent weeks ordered by week_ending desc"}},
)
async def list_weeks(
    limit: int = 12,
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Return the most recent *limit* weeks from Supabase, ordered newest first.

    Used by the Launchpad page to populate the Recent Weeks list.
    Not cached — list view needs freshness so newly-created weeks appear immediately.
    """
    try:
        weeks = await placement_service.list_recent_weeks(limit=limit)
        return weeks
    except Exception as exc:
        log.exception("list_recent_weeks raised")
        raise HTTPException(status_code=503, detail={"error": "unavailable", "detail": str(exc)})


@router.get(
    "/weekly/{week_id}",
    response_model=WeeklyPlanningOverviewResponse,
    summary="Weekly planning overview",
    responses={
        200: {"description": "Full planning overview for the week"},
        404: {"description": "Week not found"},
        503: {"description": "Planning data temporarily unavailable"},
    },
)
async def get_weekly_planning_overview(
    week_id: str,
    planning_service: PlanningService = Depends(get_planning_service),
):
    """Return a comprehensive pre-shift planning overview for the week.

    Aggregates coverage health, gap counts, active overrides, multi-area
    overlaps, and quick-action links into a single response.  Suitable for
    powering a planning dashboard without client-side data stitching.

    The response is cached for 15 seconds in PlanningService.  Callers that
    need guaranteed fresh data should call the invalidation endpoint first
    (or simply wait for the TTL to expire).

    Night snapshots include ``reoptimize_recommended=true`` for any night
    with unfilled slots, making it easy for clients to surface actionable
    gaps.
    """
    try:
        overview = await planning_service.get_weekly_overview(week_id)
    except Exception as exc:
        log.exception("PlanningService.get_weekly_overview(%s) raised", week_id)
        raise _planning_unavailable(str(exc))

    if overview is None:
        raise _not_found(f"Week not found: {week_id!r}")

    from fastapi.responses import JSONResponse

    return JSONResponse(
        content=overview.model_dump(),
        headers={"Cache-Control": _CACHE_CONTROL},
    )
