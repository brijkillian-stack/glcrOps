"""
apps/admin/pages/deployment.py — Admin alias for the legacy deployment page.

Route: /admin/deployment
Renders the legacy deployment_page() from apps/glcr/pages/deployment.py
with an admin breadcrumb sub-bar above it.

Uses DeploymentState (loaded via on_load in routes.py).
"""

import reflex as rx
from apps.glcr.pages.deployment import deployment_page
from shared.components.admin_section_head import admin_breadcrumb


def admin_deployment_page() -> rx.Component:
    return rx.el.div(
        admin_breadcrumb(section="System", page_title="Deployment (legacy)"),
        rx.el.div(
            deployment_page(),
            class_name="admin-subpage-content",
        ),
        class_name="admin-subpage-wrapper",
    )
