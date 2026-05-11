"""Planning router — pre-shift dashboard endpoints.

Public surface:
    GET /v1/planning/weekly/{week_id}

Returns the weekly planning overview (week meta, per-night staffing /
coverage gaps / notes / call-offs / overlap fill, schedule overrides,
and rolled-up totals) for the Next.js weekly view.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path

from ..core.dependencies import get_redis_client, get_supabase_client
from ..services.cache_service import CacheService
from ..services.planning_service import PlanningService, WeeklyPlanningOverview

router = APIRouter(prefix="/v1/planning", tags=["Planning"])


@router.get("/weekly/{week_id}", response_model=WeeklyPlanningOverview)
async def get_weekly_overview(
    week_id: str = Path(...),
    supabase=Depends(get_supabase_client),
    redis=Depends(get_redis_client),
) -> WeeklyPlanningOverview:
    cache = CacheService(redis)
    service = PlanningService(supabase, cache=cache)
    overview = await service.get_weekly_overview(week_id)
    if overview is None:
        raise HTTPException(status_code=404, detail=f"Week {week_id!r} not found")
    return overview
