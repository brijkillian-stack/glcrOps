"""TM row model (entities table, entity_type='tm')."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class TMRow(BaseModel):
    """One active TM row from the `entities` table.

    Only the fields selected by fetch_all_tms / fetch_entity are guaranteed
    present. `metadata` is a JSONB blob — shape varies; access defensively.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    display_name: Optional[str] = None
    metadata: Optional[Any] = None    # JSONB; dict in practice
    status: str = "active"
    entity_type: Optional[str] = "tm"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
