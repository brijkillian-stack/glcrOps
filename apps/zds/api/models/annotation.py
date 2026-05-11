"""Annotation row model (zds_annotations table)."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class AnnotationRow(BaseModel):
    """One row from the `zds_annotations` table.

    Unique constraint: (week_ending, day, target_kind, target_ref, annotation_kind).
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    week_ending: str          # ISO date string "YYYY-MM-DD"
    day: str                  # "fri" | "sat" | … | "thu"
    target_kind: str          # "task" | "tm" | "card"
    target_ref: str           # task UUID, tm_id, or card code
    annotation_kind: str      # "highlight" | "adhoc_task" | "note" | …
    value: Any                # JSONB — dict in practice
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
