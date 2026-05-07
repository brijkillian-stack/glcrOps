"""
shared/components/nav_rail.py — 60px unified nav rail (GShiftPage Phase 2)

Single rail used by every page (Memory + ZDS). Contains:
  • Logo G-mark  → /
  • 6 nav items  with active-state chip
  • Avatar chip  → dropdown (theme toggle, Sudo Admin, Sign out)

The active_route prefix-match determines which chip is highlighted.
/zds/* routes use .contains() since the ZDS section has sub-routes.
All others use exact == match.

Avatar dropdown state lives in AvatarMenuState (shared/state/avatar_menu.py).
Outside-click-close is handled by assets/avatar_menu.js.
"""

import reflex as rx
from shared.base import AppState
from shared.auth import AuthState
from shared.state.avatar_menu import AvatarMenuState


def _nav_item(glyph: str, label: str, href: str, is_active) -> rx.Component:
    """One 40×40 nav chip. `is_active` is a Reflex Var[bool]."""
    return rx.el.a(
        glyph,
        href=href,
        title=label,
        aria_label=label,
        class_name=rx.cond(is_active, "nav-rail-item active", "nav-rail-item"),
    )


def _avatar_dropdown() -> rx.Component:
    """Dropdown panel that appears when the avatar chip is clicked."""
    from apps.zds.state import ZdsState  # lazy import — avoids circular dep

    return rx.cond(
        AvatarMenuState.open,
        rx.el.div(
            # Theme toggle
            rx.el.button(
                rx.cond(
                    ZdsState.theme == "dark",
                    "☀ Light mode",
                    "☾ Dark mode",
                ),
                on_click=[ZdsState.toggle_theme, AvatarMenuState.close],
                class_name="nav-rail-menu-item",
            ),
            # Sudo Admin stub
            rx.el.a(
                "⚙ Sudo Admin",
                href="/admin",
                on_click=AvatarMenuState.close,
                class_name="nav-rail-menu-item",
            ),
            # Sign out
            rx.el.button(
                "⇲ Sign out",
                on_click=[AuthState.sign_out, AvatarMenuState.close],
                class_name="nav-rail-menu-item nav-rail-menu-item-danger",
            ),
            class_name="nav-rail-avatar-menu",
        ),
        rx.fragment(),
    )


def nav_rail() -> rx.Component:
    """60px sticky left nav rail. Mount once per page via the wrapper."""
    active = AppState.active_route

    return rx.el.nav(
        # ── Logo G-mark ──────────────────────────────────────────────────
        rx.el.a(
            "G",
            href="/",
            title="Home",
            aria_label="Home",
            class_name="nav-rail-logo",
        ),

        # ── Line separator ────────────────────────────────────────────────
        rx.el.div(class_name="nav-rail-divider"),

        # ── Nav items ─────────────────────────────────────────────────────
        _nav_item("⊙", "Shift",    "/shift",    active == "/shift"),
        _nav_item("▦", "ZDS",      "/zds",      active.contains("/zds")),
        _nav_item("⌕", "Search",   "/search",   active == "/search"),
        _nav_item("◍", "People",   "/people",   active == "/people"),
        _nav_item("☐", "Tasks",    "/tasks",    active == "/tasks"),
        _nav_item("✦", "Patterns", "/patterns", active == "/patterns"),

        # ── Spacer ────────────────────────────────────────────────────────
        rx.el.div(class_name="nav-rail-spacer"),

        # ── Avatar chip + dropdown ────────────────────────────────────────
        rx.el.div(
            rx.el.button(
                "BK",
                class_name="nav-rail-avatar",
                on_click=AvatarMenuState.toggle,
                aria_label="Account menu",
                title="Account",
            ),
            _avatar_dropdown(),
            style={"position": "relative"},
        ),

        class_name="nav-rail",
    )
