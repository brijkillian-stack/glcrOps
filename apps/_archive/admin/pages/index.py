"""
apps/admin/pages/index.py — Sudo Admin hub (/admin)

Three-section card grid surfacing all long-tail Memory pages that don't
have a permanent slot in the 60px nav rail.

  ACTIVITY    — Logs, Threads, Floor Walk, Write-Ups
  WORKFLOWS   — Shift Recap, Areas, Engine Config
  SYSTEM      — Health, Today (legacy), Deployment (legacy)

Card counts (where cheap to fetch) come from AdminHubState.load_hub.
"""

import reflex as rx
from apps.admin.state import AdminHubState
from shared.components.admin_card import admin_card
from shared.components.admin_section_head import admin_section_head


# ── Header ────────────────────────────────────────────────────────────────────

def _hub_header() -> rx.Component:
    return rx.el.div(
        # Eyebrow
        rx.el.div(
            "GLCR · OPERATIONS · ADMIN",
            style={
                "fontSize": "10px",
                "fontWeight": "700",
                "letterSpacing": "0.14em",
                "textTransform": "uppercase",
                "color": "var(--gold)",
                "fontFamily": "var(--font)",
                "marginBottom": "8px",
            },
        ),
        # Heading
        rx.el.div(
            "Sudo Admin",
            style={
                "fontFamily": "var(--serif)",
                "fontSize": "26px",
                "fontWeight": "400",
                "fontStyle": "italic",
                "letterSpacing": "-0.015em",
                "color": "var(--ink)",
                "marginBottom": "6px",
            },
        ),
        # Subhead
        rx.el.div(
            "Long-tail surfaces tucked behind the avatar. "
            "The day-to-day flow lives in the rail to the left.",
            style={
                "fontSize": "14px",
                "color": "var(--ink2)",
                "lineHeight": "1.5",
                "maxWidth": "520px",
            },
        ),
        class_name="admin-hub-header",
    )


# ── Sections ──────────────────────────────────────────────────────────────────

def _activity_section() -> rx.Component:
    return rx.el.div(
        admin_section_head("Activity"),
        rx.el.div(
            admin_card(
                "⌖", "Logs",
                "Captured operational events",
                "/logs",
                count=AdminHubState.logs_recent.to_string(),
            ),
            admin_card(
                "✉", "Threads",
                "Cross-shift conversations",
                "/threads",
            ),
            admin_card(
                "◊", "Floor Walk",
                "Tonight's walk capture",
                "/floor",
            ),
            admin_card(
                "⚑", "Write-Ups",
                "TM disciplinary write-ups",
                "/writeups",
            ),
            class_name="admin-hub-grid",
        ),
        class_name="admin-hub-section",
    )


def _workflows_section() -> rx.Component:
    return rx.el.div(
        admin_section_head("Workflows"),
        rx.el.div(
            admin_card(
                "✎", "Shift Recap",
                "Compile + review nightly recaps",
                "/recap",
            ),
            admin_card(
                "▦", "Areas",
                "Per-area oversight + audits",
                "/areas",
            ),
            admin_card(
                "⚙", "Engine Config",
                "Tune the placement engine (coming Phase 4c)",
                "/admin/engine",
            ),
            class_name="admin-hub-grid",
        ),
        class_name="admin-hub-section",
    )


def _system_section() -> rx.Component:
    return rx.el.div(
        admin_section_head("System"),
        rx.el.div(
            admin_card(
                "♡", "Health",
                "Backend health + capture velocity",
                "/health",
            ),
            admin_card(
                "⌘", "Today (legacy)",
                "Old Memory dashboard (pre-Shift HUD)",
                "/admin/today",
            ),
            admin_card(
                "▤", "Deployment (legacy)",
                "Old Memory deployment view",
                "/admin/deployment",
            ),
            class_name="admin-hub-grid",
        ),
        class_name="admin-hub-section",
    )


# ── Page ──────────────────────────────────────────────────────────────────────

def admin_page() -> rx.Component:
    return rx.el.div(
        _hub_header(),
        rx.el.div(
            _activity_section(),
            _workflows_section(),
            _system_section(),
            class_name="admin-hub-body",
        ),
        class_name="admin-hub-page",
    )
