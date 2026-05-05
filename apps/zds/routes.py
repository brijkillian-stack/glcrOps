"""ZDS (Zone Deployment System) route definitions."""

from .pages import index, week_overview, deployment, schedule_editor_page
from .state import ZdsState
from .state_schedule import ScheduleEditorState

# All ZDS routes are public (no auth required for now)
PUBLIC_ROUTES = [
    "/zds/",
    "/zds/week/[week_id]",
    "/zds/week/[week_id]/day/[night_id]",
    "/zds/week/[week_id]/schedule",
]

# Route table: (page_fn, route_path, title, on_load_list)
ROUTES = [
    (index,                "/zds/",                              "GLCR Deployments", [ZdsState.load_weeks]),
    (week_overview,        "/zds/week/[week_id]",                "Week Overview",    [ZdsState.on_week_overview_load]),
    (deployment,           "/zds/week/[week_id]/day/[night_id]", "Zone Sheet",       [ZdsState.on_day_load]),
    (schedule_editor_page, "/zds/week/[week_id]/schedule",       "Week Schedule",    [ScheduleEditorState.on_load]),
]
