"""ZDS (Zone Deployment System) route definitions."""

from .pages import index, week_overview, deployment, schedule_editor_page
from .state import ZdsState
from .state_schedule import ScheduleEditorState

# All ZDS routes are public (no auth required for now).
# 2026-05-06 — dropped trailing slash on the root. Next.js (under Reflex)
# normalises trailing slashes by default, so /zds/ redirects to /zds and
# then 404'd because the route table only registered the slashed form.
# Symptom: clicking the "ZDS" pill from any non-ZDS page bounced back to
# the page you started on. Aliased both forms in PUBLIC_ROUTES so existing
# bookmarks keep working.
PUBLIC_ROUTES = [
    "/zds",
    "/zds/",
    "/zds/week/[week_id]",
    "/zds/week/[week_id]/day/[night_id]",
    "/zds/week/[week_id]/schedule",
]

# Route table: (page_fn, route_path, title, on_load_list)
ROUTES = [
    (index,                "/zds",                               "GLCR Deployments", [ZdsState.load_weeks]),
    (week_overview,        "/zds/week/[week_id]",                "Week Overview",    [ZdsState.on_week_overview_load]),
    (deployment,           "/zds/week/[week_id]/day/[night_id]", "Zone Sheet",       [ZdsState.on_day_load]),
    (schedule_editor_page, "/zds/week/[week_id]/schedule",       "Week Schedule",    [ScheduleEditorState.on_load]),
]
