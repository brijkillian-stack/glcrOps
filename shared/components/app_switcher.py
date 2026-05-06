"""
components/app_switcher.py — GLCR / ZDS app switcher

Renders two pills side by side. The active app is determined from
AppState.active_route — any route starting with /zds/ is the ZDS app,
everything else is GLCR Memory.

Used in two places:
  - shared/components/sidebar.py (top of GLCR sidebar)
  - apps/zds/pages/*.py (top nav of every ZDS page)

Switching is plain navigation; no extra state needed.
"""

import reflex as rx
from shared.base import AppState


def _pill(label: str, route: str, is_active) -> rx.Component:
    """One app pill. `is_active` is a Reflex Var, not a Python bool."""
    return rx.link(
        rx.el.span(label),
        href=route,
        class_name=rx.cond(is_active, "app-pill active", "app-pill"),
    )


def app_switcher() -> rx.Component:
    """Two-pill GLCR / ZDS switcher. Same component used in both apps."""
    is_zds = AppState.active_route.contains("/zds")
    return rx.el.div(
        _pill("GLCR", "/", ~is_zds),
        _pill("ZDS",  "/zds", is_zds),
        class_name="app-switcher",
    )
