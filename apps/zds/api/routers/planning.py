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

from fastapi import APIRouter, Depends, HTTPException

from ..core.dependencies import get_planning_service
from ..models.planning import WeeklyPlanningOverviewResponse
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
