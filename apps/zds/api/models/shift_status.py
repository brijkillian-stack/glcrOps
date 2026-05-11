"""Pydantic models for the live On-Shift Status endpoint.

Separate from the ZDS Forge pre-shift planning models on purpose:
these describe a *snapshot* of the running grave shift (current
coverage, who is doubled up, heat per slot, fatigue per TM).

The schema is read-mostly. Mutations land via `MultiAreaAssignmentPatch`
on the PATCH endpoint, which writes back to the same `zone_assignments`
and `overlap_assignments` rows the ZDS planner produces — so live edits
stay coherent with the pre-shift plan.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class AssignmentReason(str, Enum):
    """Why a TM is in a particular slot tonight.

    `primary` is derived (the lowest-sort_order zone_assignment per TM).
    `overlap_pm` / `overlap_am` come from the `overlap_assignments` table.
    `secondary_zone` is any extra `zone_assignments` row beyond the primary.
    `coverage` and `training` are reserved for future write-side use when
    a supervisor consciously double-stacks a TM mid-shift.
    """

    primary = "primary"
    secondary_zone = "secondary_zone"
    overlap_pm = "overlap_pm"
    overlap_am = "overlap_am"
    coverage = "coverage"
    training = "training"
    other = "other"


SourceTable = Literal["zone_assignments", "overlap_assignments"]


class MultiAreaAssignment(BaseModel):
    """One slot a TM is responsible for tonight.

    Primary + additional zones are the same shape — they're distinguished
    by `reason`. The (`source_table`, `assignment_id`) pair is the write
    key the PATCH endpoint uses to mutate this row.
    """

    assignment_id: str
    source_table: SourceTable
    slot_key: str = Field(..., description="Canonical key, e.g. 'zone_3', 'rr_1', 'PMOL1'.")
    slot_label: str = Field("", description="Short display label, e.g. 'Z3', 'RR 1 M', 'PM Overlap 1'.")
    area: str = Field("", description="Floor area / zone label, e.g. 'Slot Bank A'.")
    reason: AssignmentReason
    is_filled: bool = False
    is_locked: bool = False


class TmCoverage(BaseModel):
    """One team member's footprint for the night.

    `primary_zone` is None when the TM is on shift via overlap only
    (e.g. PMOL-only TMs do not own a zone). `additional_zones` is empty
    in the common single-slot case.
    """

    tm_id: str
    display_name: str
    primary_zone: Optional[MultiAreaAssignment] = None
    additional_zones: list[MultiAreaAssignment] = Field(default_factory=list)
    fatigue_index: float = 0.0
    fatigue_window_days: int = 7
    is_called_off: bool = False

    @property
    def total_slots(self) -> int:
        return (1 if self.primary_zone else 0) + len(self.additional_zones)

    @property
    def is_multi_area(self) -> bool:
        return self.total_slots > 1


class HeatLevel(int, Enum):
    """0=open · 1=ok-light · 2=ok · 3=stretched · 4=warn (called-off occupant)."""

    open = 0
    ok_light = 1
    ok = 2
    stretched = 3
    warn = 4


class CoverageHeatmapCell(BaseModel):
    """One slot in the coverage heatmap.

    `heat_level` is a derived enum so the UI can pick a color without
    re-implementing the rule. `tm_fatigue` is the occupant's fatigue
    score (0 when slot is open).
    """

    slot_key: str
    slot_label: str
    area: str = ""
    is_filled: bool
    is_locked: bool
    is_warn: bool = Field(False, description="True when occupant is called off tonight.")
    tm_id: str = ""
    tm_name: str = ""
    tm_fatigue: float = 0.0
    heat_level: HeatLevel
    assignment_id: str = ""
    source_table: SourceTable = "zone_assignments"


class CoverageStats(BaseModel):
    """Top-of-page counters — what supervisors glance at first."""

    total_slots: int
    filled: int
    open: int
    locked: int
    called_off: int
    multi_area_tms: int = Field(0, description="Count of TMs assigned to >1 slot tonight.")
    fatigue_avg: float = 0.0
    fatigue_max: float = 0.0


class OnShiftStatusResponse(BaseModel):
    """Full snapshot of the current grave shift.

    Returned by `GET /v1/shift/on-shift-status`. Production callers cache
    this for ~15s in the UI; freshness past that is enforced by the
    PATCH endpoint invalidating Redis on every write.
    """

    night_id: str
    night_date: str = Field(..., description="ISO date of the shift start, e.g. '2026-05-11'.")
    day_name: str = ""
    shift_label: str = "Grave"
    generated_at: str = Field(..., description="ISO-8601 server timestamp at response time.")
    stats: CoverageStats
    tm_coverage: list[TmCoverage]
    heatmap: list[CoverageHeatmapCell]


# ── PATCH body ──────────────────────────────────────────────────────


class MultiAreaAssignmentPatch(BaseModel):
    """Mutate a single assignment row.

    `source_table` resolves which physical table to write into. `tm_id`
    set to `None` clears the slot (and unsets `is_filled`). `tm_id`
    omitted (not provided) means "don't change the occupant".
    """

    source_table: SourceTable
    tm_id: Optional[str] = Field(
        default=None,
        description="New occupant entity id; None to clear. Omit to leave unchanged.",
    )
    is_locked: Optional[bool] = Field(
        default=None,
        description="Toggle the row's lock; omit to leave unchanged.",
    )
    # Note: 'reason' isn't persisted today — it's derived from slot
    # category. Reserved for a future column or metadata jsonb without
    # changing the wire shape.
    reason: Optional[AssignmentReason] = None


class AssignmentPatchResponse(BaseModel):
    """Echoed back so the caller can reconcile its local state."""

    assignment_id: str
    source_table: SourceTable
    tm_id: Optional[str] = None
    is_filled: bool
    is_locked: bool
