"""Override row model (engine_overrides table, slot_assignment type)."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class OverrideRow(BaseModel):
    """A slot-level supervisor override stored in `engine_overrides`.

    PlacementService.list_overrides / apply_override surface only rows with
    override_type="slot_assignment". The full engine_overrides table supports
    other types (called_off, must_deploy, etc.) used by the fill engine.

    `slot_key` and `tm_id` are stored in the `payload` JSONB column.
    PlacementService.list_overrides reconstructs them into these typed fields.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    week_id: str
    tm_id: Optional[str] = None      # None = slot cleared
    override_date: str                # ISO date of the night
    override_type: str = "slot_assignment"
    slot_key: str = ""                # e.g. "Z1", "Z9", "AUX-1" (from payload)
    note: str = ""
    payload: Any = None               # raw JSONB; callers should use slot_key/tm_id
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    expires_at: Optional[str] = None
