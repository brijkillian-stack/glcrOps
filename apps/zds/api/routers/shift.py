"""Shift router — live On-Shift Status + multi-area assignment edits.

Public surface:
    GET   /v1/shift/on-shift-status[?night_id=...]
    PATCH /v1/shift/assignments/{assignment_id}

GET resolves to tonight when `night_id` is omitted using the shift-start
anchor convention (mid-shift before 7am ET → yesterday's deployment).
PATCH updates one assignment row in either `zone_assignments` or
`overlap_assignments`; supervisors use it to drop a TM onto an
additional zone or to clear an overlap mid-shift.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from ..core.dependencies import get_redis_client, get_supabase_client
from ..models.shift_status import (
    AssignmentPatchResponse,
    MultiAreaAssignmentPatch,
    OnShiftStatusResponse,
)
from ..services.cache_service import CacheService
from ..services.on_shift_status_service import OnShiftStatusService

router = APIRouter(prefix="/v1/shift", tags=["Shift"])


def _service(supabase, redis) -> OnShiftStatusService:
    return OnShiftStatusService(supabase, cache=CacheService(redis))


@router.get("/on-shift-status", response_model=OnShiftStatusResponse)
async def on_shift_status(
    night_id: Optional[str] = Query(
        default=None,
        description="Explicit night id; omitted = resolve tonight via ET shift-start anchor.",
    ),
    supabase=Depends(get_supabase_client),
    redis=Depends(get_redis_client),
) -> OnShiftStatusResponse:
    try:
        return await _service(supabase, redis).get_status(night_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch(
    "/assignments/{assignment_id}",
    response_model=AssignmentPatchResponse,
)
async def patch_assignment(
    patch: MultiAreaAssignmentPatch,
    assignment_id: str = Path(..., description="UUID of the assignment row."),
    supabase=Depends(get_supabase_client),
    redis=Depends(get_redis_client),
) -> AssignmentPatchResponse:
    try:
        return await _service(supabase, redis).patch_assignment(assignment_id, patch)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
