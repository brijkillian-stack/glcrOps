"""Week and Night row models."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class WeekRow(BaseModel):
    """One row from the `weeks` table."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    week_ending: str          # ISO date string "YYYY-MM-DD"
    label: str
    status: str               # "draft" | "published" | "archived"
    schedule_path: Optional[str] = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class NightRow(BaseModel):
    """One row from the `nights` table."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    week_id: str
    night_date: str           # ISO date string "YYYY-MM-DD"
    day_name: str             # "Friday" | "Saturday" … "Thursday"
    day_num: int              # 1–7
    page_num: int
    in_rotation: int          # 1 = in rotation, 0 = off
    breaks_5: int
    breaks_9: int
    breaks_4: int
    is_locked: bool = False
    locked_by: str = ""
    locked_at: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
