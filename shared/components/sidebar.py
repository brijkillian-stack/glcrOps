"""
components/sidebar.py — Shared sidebar navigation
"""

import reflex as rx
from shared.auth import AuthState
from shared.base import AppState
from shared.components.app_switcher import app_switcher
from apps.glcr.state.today import TodayState

# Nav items split by role tier (Path C+ 2026-05-05).
# Viewers (PIN only) see only NAV_VIEWER. Editors see everything.
NAV_VIEWER = [
    ("◎", "Home",       "/"),
    ("⊙", "Today",      "/today"),
]

NAV_EDITOR = [
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

# Aggregate kept for back-compat with any caller that imports NAV_ITEMS.
NAV_ITEMS = NAV_VIEWER + NAV_EDITOR


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
        # Nav — three sections, two of them gated by editor role
        rx.el.nav(
            # Always visible (viewer + editor)
            *[_nav_item(icon, label, route) for icon, label, route in NAV_VIEWER],
            # Editor-only Memory routes — hidden from viewers
            rx.cond(
                AuthState.is_zds_editor,                # any editor role
                rx.el.fragment(
                    rx.el.div(class_name="nav-divider"),
                    *[_nav_item(icon, label, route) for icon, label, route in NAV_EDITOR],
                    rx.el.div(class_name="nav-divider"),
                    *[_nav_item(icon, label, route) for icon, label, route in NAV_EXTRA],
                    # Phase M — Area Check (write surface; editor-only)
                    rx.el.div(class_name="nav-divider"),
                    _action_item("★", "Area Check", AppState.open_area_check),
                ),
            ),

            # ── Path C+ role chrome ────────────────────────────────────────
            rx.el.div(class_name="nav-divider"),

            # Role chip — shows current role (Viewer / ZDS Editor / Editor)
            rx.el.div(
                rx.el.span(AuthState.role_label, class_name="role-chip-label"),
                rx.cond(
                    AuthState.editor_email != "",
                    rx.el.span(AuthState.editor_email, class_name="role-chip-email"),
                ),
                class_name=rx.cond(
                    AuthState.is_editor,
                    "role-chip role-chip-editor",
                    rx.cond(
                        AuthState.is_zds_editor,
                        "role-chip role-chip-zds",
                        "role-chip role-chip-viewer",
                    ),
                ),
            ),

            # Editor sign-in / sign-out
            rx.cond(
                AuthState.editor_role == "viewer",
                # Viewer mode: show "Sign in as editor" link
                rx.link(
                    rx.el.span("✎", class_name="nav-icon"),
                    rx.el.span("Sign in as editor", class_name="nav-label"),
                    href="/login",
                    class_name="nav-item",
                ),
                # Editor (any tier): show "Sign out (viewer)" action
                _action_item("⇲", "Sign out (viewer)", AuthState.sign_out_editor),
            ),

            # Lock device — always available
            _action_item("⌶", "Lock device", AuthState.lock_device),
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
