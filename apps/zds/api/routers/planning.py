"""Planning router — pre-shift simulation endpoints.

Public surface:
    POST /v1/planning/reoptimize

Body (JSON):
    {
        "week_id": "uuid",
        "unavailable_team_members": ["Joy", "Mike S"],  # display names; optional
        "force_z9": false                                # optional, default false
    }

Returns the engine's new placements together with a diff against the current
`zone_assignments` rows so the planner can preview impact before applying.
The endpoint never writes — applying is a separate workflow.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.dependencies import get_redis_client, get_supabase_client
from ..services.cache_service import CacheService
from ..services.reoptimize_service import ReoptimizeService

router = APIRouter(prefix="/v1/planning", tags=["Planning"])


class ReoptimizeRequest(BaseModel):
    week_id: str = Field(..., min_length=1, description="UUID of the week to reoptimize.")
    unavailable_team_members: list[str] = Field(
        default_factory=list,
        description="Display names of TMs to treat as called-off for this simulation.",
    )
    force_z9: bool = Field(
        default=False,
        description="When true, Zone 9 fills before the skippable zones.",
    )


class DiffSummary(BaseModel):
    total_engine_slots: int
    changed: int
    unchanged: int
    newly_filled: int
    newly_unfilled: int
    locked_preserved: int


class DiffChange(BaseModel):
    date: str
    slot_key: str
    rr_side: Optional[str] = None
    before: str
    after: str
    kind: str


class ReoptimizeDiff(BaseModel):
    summary: DiffSummary
    changes: list[DiffChange]


class ReoptimizeOverrides(BaseModel):
    unavailable_team_members: list[str]
    force_z9: bool


class ReoptimizeEngineInfo(BaseModel):
    error: Optional[str] = None
    config_used: Optional[dict] = None


class ReoptimizeResponse(BaseModel):
    week_id: str
    week_ending: str = ""
    overrides: ReoptimizeOverrides
    engine: ReoptimizeEngineInfo
    placements: list[dict]
    unresolved: list[dict]
    diff: ReoptimizeDiff
    cached: bool = False


@router.post("/reoptimize", response_model=ReoptimizeResponse)
async def reoptimize(
    body: ReoptimizeRequest,
    supabase=Depends(get_supabase_client),
    redis=Depends(get_redis_client),
) -> ReoptimizeResponse:
    cache = CacheService(redis)
    service = ReoptimizeService(supabase, cache=cache)
    result = await service.reoptimize(
        week_id=body.week_id,
        unavailable_team_members=body.unavailable_team_members,
        force_z9=body.force_z9,
    )

    # Week-not-found is the only condition that justifies a non-2xx — engine
    # errors come back inside the payload so the planner UI can still render
    # the partial result (e.g. show which schedule file was used).
    if not result.get("engine") and result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])

    return ReoptimizeResponse(**result)
