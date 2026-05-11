"""Assignment row models.

AssignmentRow     — one row from the zone_assignments table.
MultiAreaAssignmentRow — one row from the multi_area_assignments table (Phase 4 live ops).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class AssignmentRow(BaseModel):
    """One row from the `zone_assignments` table.

    Shape mirrors what fetch_zone_assignments returns before the display-field
    enrichment that state.py layers on. Use this for raw data-layer reads;
    state.py's ZoneSlot TypedDict covers the display-enriched form.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    night_id: str
    slot_key: str
    slot_type: str            # "zone" | "aux" | "rr"
    rr_side: str = ""
    tm_id: Optional[str] = None
    is_locked: bool = False
    sort_order: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MultiAreaAssignmentRow(BaseModel):
    """One row from the `multi_area_assignments` table.

    Used by Phase 4 live ops when a TM covers more than one zone area during
    a single shift. The pre-shift deployment engine still uses single-slot
    assignments; this table is the supervisor's live-ops override layer.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    night_id: str
    tm_id: str
    primary_area: str
    additional_areas: list[str] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
