"""
components/sidebar.py — Shared sidebar navigation
"""

import reflex as rx
from shared.base import AppState
from shared.components.app_switcher import app_switcher
from apps.glcr.state.today import TodayState

NAV_ITEMS = [
    ("◎", "Home",       "/"),
    ("⊙", "Today",      "/today"),
    ("⌕", "Search",     "/search"),
    ("◉", "Logs",       "/logs"),
    ("◍", "People",     "/people"),
    ("❯❯","Threads",    "/threads"),
    ("☐", "Tasks",      "/tasks"),
    ("✦", "Patterns",   "/patterns"),
    ("♥", "Health",     "/health"),
]

NAV_EXTRA = [
    ("≡", "Shift Recap",  "/recap"),
    ("◫", "Floor Walk",   "/floor"),
    ("⊞", "Areas",        "/areas"),
    ("⊟", "Write-Ups",    "/writeups"),
    ("▦", "Deployment",   "/deployment"),
]


def _nav_item(icon: str, label: str, route: str) -> rx.Component:
    return rx.link(
        rx.el.span(icon, class_name="nav-icon"),
        rx.el.span(label, class_name="nav-label"),
        href=route,
        class_name=rx.cond(
            AppState.active_route == route,
            "nav-item active",
            "nav-item",
        ),
    )


def _action_item(icon: str, label: str, on_click) -> rx.Component:
    """Sidebar entry that fires an event handler instead of navigating.

    Used for actions that open overlays (e.g. Area Check) but should live
    in the nav for thumb-reach + visibility on every page.
    """
    return rx.el.button(
        rx.el.span(icon, class_name="nav-icon"),
        rx.el.span(label, class_name="nav-label"),
        on_click=on_click,
        class_name="nav-item",
        # Match the rx.link defaults so the button looks like a nav item
        style={
            "background": "transparent",
            "border": "none",
            "width": "100%",
            "textAlign": "left",
            "cursor": "pointer",
            "font": "inherit",
        },
    )


def sidebar() -> rx.Component:
    return rx.el.aside(
        # App switcher (GLCR / ZDS)
        app_switcher(),
        # Brand
        rx.el.div(
            rx.el.div(class_name="brand-mark"),
            rx.el.span("Graves Ops"),
            class_name="sidebar-brand",
        ),
        # Nav
        rx.el.nav(
            *[_nav_item(icon, label, route) for icon, label, route in NAV_ITEMS],
            rx.el.div(class_name="nav-divider"),
            *[_nav_item(icon, label, route) for icon, label, route in NAV_EXTRA],
            # Phase M — Area Check action lives in the nav for visibility
            # on every page. It fires an overlay rather than navigating.
            rx.el.div(class_name="nav-divider"),
            _action_item("★", "Area Check", AppState.open_area_check),
            class_name="sidebar-nav",
        ),
        # Footer
        rx.el.div(
            rx.el.span(class_name="dot dot-positive"),
            rx.el.span(TodayState.backend_status_label),
            rx.el.div(
                rx.el.button(
                    rx.cond(AppState.dark_mode, "☀", "☾"),
                    on_click=AppState.toggle_dark_mode,
                    class_name="sidebar-dark-btn",
                    title=rx.cond(AppState.dark_mode, "Switch to light mode", "Switch to dark mode"),
                ),
                rx.el.span("⌘K", class_name="kbd"),
                style={"marginLeft": "auto", "display": "flex",
                       "alignItems": "center", "gap": "6px"},
            ),
            class_name="sidebar-foot",
            on_click=AppState.open_palette,
            style={"cursor": "pointer"},
        ),
        class_name="sidebar",
    )
