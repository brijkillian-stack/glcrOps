"""
apps/admin/pages/today.py — Admin alias for the legacy Memory dashboard.

Route: /admin/today
Renders the legacy today_page() from apps/glcr/pages/today.py with an
admin breadcrumb sub-bar above it.

The page uses TodayState (loaded via on_load in routes.py) — the same
state class the GLCR /today page used before Phase 3 redirected /today
to the new Shift HUD.
"""

import reflex as rx
from apps.glcr.pages.today import today_page
from shared.components.admin_section_head import admin_breadcrumb


def admin_today_page() -> rx.Component:
    return rx.el.div(
        admin_breadcrumb(section="System", page_title="Today (legacy)"),
        rx.el.div(
            today_page(),
            class_name="admin-subpage-content",
        ),
        class_name="admin-subpage-wrapper",
    )
