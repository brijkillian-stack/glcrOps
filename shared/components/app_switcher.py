"""
components/app_switcher.py — GLCR / ZDS app switcher + ZDS theme toggle

Renders two pills side by side (GLCR / ZDS) and, when on a ZDS surface,
a sun/moon theme toggle next to them. The active app is determined from
AppState.active_route — any route starting with /zds is the ZDS app,
everything else is GLCR Memory.

Used in three places:
  - shared/components/sidebar.py (top of GLCR sidebar)
  - apps/zds/pages/*.py (top nav of every ZDS page)
  - apps/zds/components/zds_header.py (transitionally; the header was
    the only place the toggle lived, but every ZDS page that mounted
    app_switcher directly was missing it. Moving the toggle here means
    Week Overview, Deployment, and Schedule editor all get it for free.)

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


def _theme_toggle() -> rx.Component:
    """Sun/moon button — flips ZdsState.theme between dark and light.
    Visible only when on a ZDS route (Memory pages don't use this state).
    """
    # Local import to avoid a hard top-level dep on apps/zds when this
    # component is rendered from the Memory-only sidebar.
    from apps.zds.state import ZdsState
    is_zds = AppState.active_route.contains("/zds")
    return rx.cond(
        is_zds,
        rx.button(
            rx.cond(
                ZdsState.theme == "dark",
                rx.icon("sun",  size=16),
                rx.icon("moon", size=16),
            ),
            on_click=ZdsState.toggle_theme,
            class_name="zds-theme-toggle",
            variant="ghost",
            size="2",
            aria_label="Toggle dark / light mode",
            cursor="pointer",
        ),
        rx.fragment(),
    )


def app_switcher() -> rx.Component:
    """Two-pill GLCR / ZDS switcher + theme toggle (ZDS routes only)."""
    is_zds = AppState.active_route.contains("/zds")
    return rx.el.div(
        _pill("GLCR", "/", ~is_zds),
        _pill("ZDS",  "/zds", is_zds),
        _theme_toggle(),
        class_name="app-switcher",
    )
