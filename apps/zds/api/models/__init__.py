"""Pydantic v2 row models for ZDS Forge API.

All models use ConfigDict(from_attributes=True) so they accept both
ORM objects and raw Supabase row dicts via model_validate(row).

Field types intentionally use plain Python scalars (str, int, bool, dict,
list) rather than UUID / datetime objects because supabase-py returns
columns as JSON-decoded Python values — UUIDs are strings, timestamps
are ISO strings, JSONB columns are dicts, arrays are lists.
"""

from .annotation import AnnotationRow
from .assignment import AssignmentRow, MultiAreaAssignmentRow
from .override import OverrideRow
from .planning import (
    NightPlanningSnapshot,
    OverrideSummary,
    PlanningLinks,
    PlanningNote,
    WeeklyPlanningOverviewResponse,
    WeekMeta,
    WeekMetrics,
)
from .task import TaskRow
from .tm import TMRow
from .week import NightRow, WeekRow

__all__ = [
    # Row models
    "WeekRow",
    "NightRow",
    "TaskRow",
    "AnnotationRow",
    "OverrideRow",
    "TMRow",
    "AssignmentRow",
    "MultiAreaAssignmentRow",
    # Planning models (GLC-12)
    "WeekMeta",
    "NightPlanningSnapshot",
    "WeekMetrics",
    "PlanningNote",
    "OverrideSummary",
    "PlanningLinks",
    "WeeklyPlanningOverviewResponse",
]
