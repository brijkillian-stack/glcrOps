"""apps/admin/routes.py — Sudo Admin route definitions (Phase 4b).

Routes registered here:
  /admin             — Sudo Admin hub (AdminHubState.load_hub)
  /admin/today       — Legacy Memory dashboard (TodayState.load_today)
  /admin/deployment  — Legacy deployment view (DeploymentState.load_roster)
  /admin/engine      — Engine Configurator stub (Phase 4c placeholder)

All routes are TIER 2 (viewer-OK) — the require_unlock guard is prepended
by brijkillian_stack.py at registration time.
"""

from .pages.index import admin_page
from .pages.today import admin_today_page
from .pages.deployment import admin_deployment_page
from .pages.engine import admin_engine_page
from .state import AdminHubState

from apps.glcr.state.today import TodayState
from apps.glcr.state.deployment import DeploymentState

PUBLIC_ROUTES: list[str] = []

# Route table: (page_fn, route_path, title, on_load_list)
ROUTES = [
    (admin_page,            "/admin",             "Sudo Admin · GLCR Ops",          [AdminHubState.load_hub]),
    (admin_today_page,      "/admin/today",       "Today (legacy) · GLCR Ops",      [TodayState.load_today]),
    (admin_deployment_page, "/admin/deployment",  "Deployment (legacy) · GLCR Ops", [DeploymentState.load_roster]),
    (admin_engine_page,     "/admin/engine",      "Engine Config · GLCR Ops",       []),
]
