"""Task row model (zone_tasks table)."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class TaskRow(BaseModel):
    """One row from the `zone_tasks` table.

    Columns match the _TASK_SELECT constant in shared/db.py:
        id,name,code,description,default_zone,category,active,
        target_codes,days_active,display_order,archived_at,
        estimated_duration_min,notes,created_at,updated_at
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    default_zone: Optional[str] = None
    category: Optional[str] = None
    active: bool = True
    target_codes: Optional[Any] = None    # JSONB array
    days_active: Optional[Any] = None     # JSONB array or null
    display_order: Optional[int] = None
    archived_at: Optional[str] = None
    estimated_duration_min: Optional[int] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
