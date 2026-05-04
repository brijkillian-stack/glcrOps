"""ZDS (Zone Deployment System) route definitions."""

from .pages import index, week_overview, deployment
from .state import ZdsState

# All ZDS routes are public (no auth required for now)
PUBLIC_ROUTES = ["/zds/", "/zds/week/[week_id]", "/zds/week/[week_id]/day/[night_id]"]

# Route table: (page_fn, route_path, title, on_load_list)
# The week_overview + deployment routes need their state hydrated from URL
# params on every navigation — on_<X>_load reads router.page.params and
# fetches the matching week / night from Supabase.
ROUTES = [
    (index,          "/zds/",                                  "GLCR Deployments", [ZdsState.load_weeks]),
    (week_overview,  "/zds/week/[week_id]",                    "Week Overview",    [ZdsState.on_week_overview_load]),
    (deployment,     "/zds/week/[week_id]/day/[night_id]",     "Zone Sheet",       [ZdsState.on_day_load]),
]
