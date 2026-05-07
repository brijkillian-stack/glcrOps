"""apps/admin/routes.py — Sudo Admin route definitions (Phase 2 stub)."""

from .pages.index import admin_page

PUBLIC_ROUTES: list[str] = []

# Route table: (page_fn, route_path, title, on_load_list)
ROUTES = [
    (admin_page, "/admin", "Sudo Admin · GLCR Ops", []),
]
