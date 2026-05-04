"""
components/sidebar.py — Shared sidebar navigation
"""

import reflex as rx
from shared.base import AppState
from apps.glcr.state.today import TodayState

NAV_ITEMS = [
    ("⊙", "Today",      "/"),
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


def sidebar() -> rx.Component:
    return rx.el.aside(
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
