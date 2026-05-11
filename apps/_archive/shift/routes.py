"""Shift HUD route definitions."""

from .pages.index import shift_page
from .state import ShiftState

# All routes are viewer-OK (PIN gated only) — consistent with ZDS tier.
PUBLIC_ROUTES: list[str] = []

# (page_fn, route_path, title, on_load_list)
ROUTES = [
    (shift_page, "/shift", "Shift HUD · GLCR", [ShiftState.on_load]),
]
