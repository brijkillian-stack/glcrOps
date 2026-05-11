"""Planning router — pre-shift what-if simulation.

Public surface:
    POST /v1/planning/simulate

The request describes a baseline scope (a `week_id` or single
`night_id`), a list of staffing changes to apply, and optional
constraints to evaluate. The response returns baseline + scenario
metrics (coverage / fatigue / overlap / constraint violations) plus
the delta. The endpoint is non-destructive — no database writes ever
happen here.
"""

from __future__ import annotations

import logging
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from ..core.dependencies import get_redis_client, get_supabase_client
from ..services.cache_service import CacheService
from ..services.simulation_service import (
    SimulationError,
    SimulationService,
    VALID_CHANGE_KINDS,
    VALID_CONSTRAINT_KINDS,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/planning", tags=["Planning"])


# ── Request models ──────────────────────────────────────────────────


class StaffingChange(BaseModel):
    """One mutation applied to the baseline snapshot.

    Field requirements depend on `kind`; the service raises
    `SimulationError` (→ 400) when required fields are missing.
    """
    kind: Literal[
        "mark_unavailable",
        "remove_assignment",
        "add_assignment",
        "reassign",
    ]
    night_id: Optional[str] = None
    night_ids: Optional[list[str]] = None
    tm_id: Optional[str] = None
    tm_name: Optional[str] = None
    tm_skill: Optional[int] = None
    assignment_id: Optional[str] = None
    target_assignment_id: Optional[str] = None
    note: Optional[str] = None


class Constraint(BaseModel):
    kind: Literal[
        "max_consecutive_nights",
        "max_nights_per_week",
        "min_coverage",
        "exclude_zone",
        "require_skill_min",
    ]
    value: Optional[float] = None
    target: Optional[str] = None
    note: Optional[str] = None


class SimulateRequest(BaseModel):
    week_id: Optional[str] = Field(
        default=None, description="Simulate over every night in this week."
    )
    night_id: Optional[str] = Field(
        default=None, description="Simulate a single night."
    )
    staffing_changes: list[StaffingChange] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    include_overlaps: bool = True
    include_fatigue: bool = True

    @model_validator(mode="after")
    def _exactly_one_scope(self) -> "SimulateRequest":
        if bool(self.week_id) == bool(self.night_id):
            raise ValueError("provide exactly one of week_id or night_id")
        return self


# ── Response models ─────────────────────────────────────────────────
#
# Returned as plain dicts from the service — modelled here so the
# OpenAPI schema stays useful for clients.


class CoverageByNight(BaseModel):
    night_date: str
    day_name: str
    filled: int
    total: int
    unfilled: int
    fill_rate: float


class CoverageByType(BaseModel):
    filled: int
    total: int
    fill_rate: float


class CoverageMetrics(BaseModel):
    total_slots: int
    filled_slots: int
    unfilled_slots: int
    fill_rate: float
    by_type: dict[str, CoverageByType]
    by_night: dict[str, CoverageByNight]


class OverlapMetrics(BaseModel):
    pm_filled: int
    pm_total: int
    pm_fill_rate: float
    am_filled: int
    am_total: int
    am_fill_rate: float


class FatiguePerTM(BaseModel):
    tm_id: str
    tm_name: str
    nights_worked: int
    slot_count: int
    consecutive_nights: int
    avg_skill: float


class FatigueMetrics(BaseModel):
    tm_count: int
    avg_nights_per_tm: float
    max_nights_per_tm: int
    max_consecutive_nights: int
    per_tm: list[FatiguePerTM]


class Violation(BaseModel):
    kind: str
    severity: Literal["info", "warning", "error"]
    detail: str
    value: Optional[float] = None
    target: Optional[str] = None
    affected: list[dict[str, Any]] = Field(default_factory=list)


class ScenarioImpact(BaseModel):
    coverage: CoverageMetrics
    overlap: Optional[OverlapMetrics] = None
    fatigue: Optional[FatigueMetrics] = None
    violations: list[Violation]


class CoverageDelta(BaseModel):
    filled_delta: int
    unfilled_delta: int
    fill_rate_delta: float
    violations_delta: int


class SimulateResponse(BaseModel):
    scope: Literal["week", "night"]
    target_id: str
    applied_changes: int
    elapsed_ms: int
    baseline: ScenarioImpact
    scenario: ScenarioImpact
    delta: CoverageDelta


# ── Route ───────────────────────────────────────────────────────────


@router.post(
    "/simulate",
    response_model=SimulateResponse,
    summary="Non-destructive what-if simulation",
    description=(
        "Apply staffing changes and constraints to a baseline week or night "
        "and return coverage / fatigue / overlap impact. Never writes to "
        "the database."
    ),
)
async def simulate(
    payload: SimulateRequest,
    supabase=Depends(get_supabase_client),
    redis=Depends(get_redis_client),
) -> SimulateResponse:
    service = SimulationService(supabase, cache=CacheService(redis))
    try:
        result = await service.simulate(
            week_id=payload.week_id,
            night_id=payload.night_id,
            staffing_changes=[c.model_dump(exclude_none=True)
                              for c in payload.staffing_changes],
            constraints=[c.model_dump(exclude_none=True)
                         for c in payload.constraints],
            include_overlaps=payload.include_overlaps,
            include_fatigue=payload.include_fatigue,
        )
    except SimulationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        log.exception("simulate failed (scope=%s)",
                      "week" if payload.week_id else "night")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="simulation failed",
        )
    return SimulateResponse(**result)


# Expose the kind allow-lists so clients can introspect (small build-once dict).

@router.get(
    "/simulate/kinds",
    summary="List supported staffing-change and constraint kinds",
)
async def list_kinds() -> dict[str, list[str]]:
    return {
        "staffing_changes": sorted(VALID_CHANGE_KINDS),
        "constraints":      sorted(VALID_CONSTRAINT_KINDS),
    }
