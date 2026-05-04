"""ZDS (Zone Deployment System) route definitions."""

from .pages import index, week_overview, deployment

# All ZDS routes are public (no auth required for now)
PUBLIC_ROUTES = ["/zds/", "/zds/week/[week_id]", "/zds/week/[week_id]/day/[night_id]"]

# Route table: (page_fn, route_path, title, on_load_list)
ROUTES = [
    (index, "/zds/", "GLCR Deployments", []),
    (week_overview, "/zds/week/[week_id]", "Week Overview", []),
    (deployment, "/zds/week/[week_id]/day/[night_id]", "Zone Sheet", []),
]
