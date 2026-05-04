"""
components/tm_drawer.py — Global TM quick-peek overlay

A lightweight right-side panel that can be mounted on any page.
Uses PeopleState (which inherits AppState) so state is shared across
the entire session — calling PeopleState.open_drawer(tm_id) or
PeopleState.open_drawer_by_name(name) from any page opens this panel.

Layout (single-tab, read-only quick view):
  ┌─────────────────────────────┐
  │  Name  ●  score  [status]   │  ← header
  │  ─────────────────────────  │
  │  Recent notes (last 4)      │  ← body
  │  ─────────────────────────  │
  │  [View full profile →]      │  ← footer link
  └─────────────────────────────┘

The full 4-tab drawer remains on the People page (/people).
"""

import reflex as rx
from ..state.people import PeopleState
from shared.base import AppState


# ── Score badge ───────────────────────────────────────────────────────────────

def _score_dot(score: float) -> rx.Component:
    cls = rx.cond(
        score >= 8, "score-badge score-badge-top",
        rx.cond(score >= 6, "score-badge score-badge-solid",
        rx.cond(score >= 4, "score-badge score-badge-mid",
                "score-badge score-badge-low")),
    )
    return rx.el.span(score.to_string(), class_name=cls)


def _status_pill(status: str) -> rx.Component:
    cls = rx.cond(
        status == "active",   "status-pill status-active",
        rx.cond(status == "loa", "status-pill status-loa",
                "status-pill status-inactive"),
    )
    return rx.el.span(status, class_name=cls)


# ── Recent note row ───────────────────────────────────────────────────────────

def _peek_note_row(note: dict) -> rx.Component:
    return rx.el.div(
        rx.el.span(note["ts_display"],   class_name="peek-note-ts"),
        rx.el.span(note["icon"],         class_name="peek-note-icon"),
        rx.el.span(note["excerpt"],      class_name="peek-note-text"),
        class_name="peek-note-row",
    )


# ── Drawer panel ──────────────────────────────────────────────────────────────

def _drawer_header() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(PeopleState.drawer_name, class_name="peek-name"),
            _score_dot(PeopleState.drawer_skill_score),
            _status_pill(PeopleState.drawer_status),
            class_name="peek-header-left",
        ),
        rx.el.button(
            "✕",
            on_click=PeopleState.close_drawer,
            class_name="peek-close-btn",
            title="Close",
        ),
        class_name="peek-header",
    )


def _drawer_body() -> rx.Component:
    return rx.cond(
        PeopleState.drawer_loading,
        # Loading skeleton
        rx.el.div(
            *[rx.el.div(
                rx.el.div(class_name="skeleton", style={"height": "10px", "width": "40px"}),
                rx.el.div(class_name="skeleton",
                          style={"height": "10px", "flex": "1", "marginLeft": "8px"}),
                class_name="peek-note-row",
                style={"gap": "10px"},
            ) for _ in range(4)],
            class_name="peek-body",
        ),
        # Notes list (last 4 from drawer_notes, which loads all 30)
        rx.cond(
            PeopleState.drawer_note_count > 0,
            rx.el.div(
                rx.el.p("Recent activity", class_name="peek-section-label"),
                rx.foreach(
                    PeopleState.drawer_notes_preview,
                    _peek_note_row,
                ),
                class_name="peek-body",
            ),
            rx.el.div(
                rx.el.p(
                    "No notes yet for this team member.",
                    style={"color": "var(--fg-3)", "fontSize": "12px",
                           "padding": "20px 0", "textAlign": "center"},
                ),
                class_name="peek-body",
            ),
        ),
    )


def _drawer_footer() -> rx.Component:
    return rx.el.div(
        rx.el.button(
            "+ Log observation",
            class_name="btn btn-primary",
            on_click=AppState.open_capture_for(PeopleState.drawer_name),
            style={"fontSize": "12px", "padding": "7px 14px"},
        ),
        rx.link(
            "View full profile →",
            href=rx.cond(
                PeopleState.drawer_tm_id != "",
                "/people",
                "/people",
            ),
            class_name="peek-full-link",
            on_click=PeopleState.close_drawer,
        ),
        class_name="peek-footer",
    )


# ── Public component — mount on any page ──────────────────────────────────────

def global_tm_drawer() -> rx.Component:
    """
    Mount this inside the root div of any page to enable the global TM
    quick-peek drawer. Trigger it from anywhere via:
      on_click=PeopleState.open_drawer(tm_id)
      on_click=PeopleState.open_drawer_by_name(name)
    """
    return rx.cond(
        PeopleState.drawer_open,
        rx.el.div(
            # Click-away scrim
            rx.el.div(
                on_click=PeopleState.close_drawer,
                class_name="drawer-scrim",
            ),
            # Panel
            rx.el.div(
                _drawer_header(),
                _drawer_body(),
                _drawer_footer(),
                class_name="drawer-panel peek-panel",
                style={"width": "380px"},
            ),
            class_name="drawer-root",
        ),
        rx.fragment(),
    )


# ── Helper: clickable TM name span ────────────────────────────────────────────

def tm_name_link(name: str, tm_id: str = "", extra_class: str = "") -> rx.Component:
    """
    Renders a clickable TM name that opens the global drawer.
    Pass tm_id when available (preferred); falls back to name lookup.
    """
    cls = ("tm-name-link " + extra_class).strip()
    if tm_id:
        return rx.el.span(
            name,
            on_click=PeopleState.open_drawer(tm_id),
            class_name=cls,
            title=f"View {name}'s profile",
        )
    return rx.el.span(
        name,
        on_click=PeopleState.open_drawer_by_name(name),
        class_name=cls,
        title=f"View {name}'s profile",
    )
