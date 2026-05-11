"""
pages/recap.py — Shift Recap page

Left column: chronological timeline of tonight's captures.
Right column: auto-generated plain-text email draft, editable and copyable.
"""

import reflex as rx
from ..state.recap import ShiftRecapState
from shared.base import AppState
from shared.components.ui import empty_state, feed_row
from shared.components.palette import command_palette
from shared.components.capture import capture_modal


# ── Page header ───────────────────────────────────────────────────────────────

def page_header() -> rx.Component:
    return rx.el.header(
        rx.el.div("Shift Recap", class_name="page-eyebrow"),
        rx.el.div(
            rx.el.h1(
                rx.cond(
                    ShiftRecapState.date_display != "",
                    ShiftRecapState.date_display,
                    "Tonight",
                ),
                class_name="page-title",
                style={"marginBottom": "0"},
            ),
            # Date picker
            rx.el.input(
                type="date",
                value=ShiftRecapState.shift_date,
                on_change=ShiftRecapState.change_date,
                style={
                    "fontSize": "13px", "color": "var(--fg-3)",
                    "background": "var(--surface-card)",
                    "border": "1px solid var(--border-subtle)",
                    "borderRadius": "var(--r-md)",
                    "padding": "4px 10px",
                    "outline": "none",
                    "cursor": "pointer",
                },
            ),
            style={
                "display": "flex", "alignItems": "center",
                "gap": "16px", "flexWrap": "wrap",
            },
        ),
        class_name="page-head",
        style={"marginBottom": "28px"},
    )


# ── Timeline column ───────────────────────────────────────────────────────────

def icon_cls_for(item: dict):
    return rx.cond(
        item["note_type"] == "kudos",   "feed-icon feed-icon-gold",
        rx.cond(
            item["note_type"] == "flag",     "feed-icon feed-icon-flag",
            rx.cond(
                item["note_type"] == "incident", "feed-icon feed-icon-flag",
                rx.cond(
                    item["note_type"] == "callout",  "feed-icon feed-icon-flag",
                    rx.cond(
                        item["note_type"] == "beo",      "feed-icon feed-icon-flag",
                        rx.cond(
                            item["note_type"] == "floor_walk", "feed-icon feed-icon-blue",
                            rx.cond(
                                item["note_type"] == "huddle",     "feed-icon feed-icon-blue",
                                "feed-icon",
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def timeline_item(item: dict) -> rx.Component:
    return rx.el.div(
        rx.el.div(item["timestamp_display"], class_name="feed-time"),
        rx.el.div(item["icon"], class_name=icon_cls_for(item)),
        rx.el.div(item["text"], class_name="feed-text"),
        class_name="feed-item",
    )


def timeline_column() -> rx.Component:
    return rx.el.div(
        rx.el.h2(
            "Tonight's Log",
            rx.el.span(
                rx.cond(
                    ShiftRecapState.loading,
                    "—",
                    ShiftRecapState.timeline_count.to_string(),
                ),
                style={
                    "fontWeight": "500",
                    "textTransform": "none",
                    "letterSpacing": "0",
                    "fontSize": "12px",
                    "color": "var(--fg-mute)",
                    "marginLeft": "8px",
                },
            ),
            class_name="section-title",
        ),
        rx.cond(
            ShiftRecapState.loading,
            rx.el.div(
                *[rx.el.div(
                    rx.el.div(
                        class_name="skeleton",
                        style={"height": "11px", "width": "40px"},
                    ),
                    rx.el.div(
                        class_name="skeleton",
                        style={"height": "11px", "flex": "1", "marginLeft": "8px"},
                    ),
                    class_name="feed-item",
                    style={"gap": "12px"},
                ) for _ in range(8)],
                class_name="feed",
            ),
            rx.cond(
                ShiftRecapState.timeline_count > 0,
                rx.el.div(
                    rx.foreach(ShiftRecapState.timeline, timeline_item),
                    class_name="feed",
                ),
                empty_state(
                    "No captures yet",
                    "Notes logged tonight will appear here.",
                ),
            ),
        ),
        class_name="recap-timeline",
    )


# ── Draft column ──────────────────────────────────────────────────────────────

def draft_toolbar() -> rx.Component:
    return rx.el.div(
        rx.el.button(
            rx.cond(ShiftRecapState.refreshing, "Refreshing…", "↻  Refresh from data"),
            class_name="btn btn-ghost",
            on_click=ShiftRecapState.refresh_from_data,
            disabled=ShiftRecapState.refreshing,
            style={"fontSize": "12px"},
            title="Re-pull call-offs / overlaps / captures from Supabase",
        ),
        rx.el.button(
            rx.cond(ShiftRecapState.compiling, "Compiling…", "⟳  Compile draft"),
            class_name="btn btn-ghost",
            on_click=ShiftRecapState.compile_draft,
            disabled=ShiftRecapState.compiling,
            style={"fontSize": "12px"},
            title="Rebuild the email-ready draft from the section fields below",
        ),
        rx.cond(
            ShiftRecapState.draft_ready,
            rx.el.button(
                rx.cond(ShiftRecapState.copy_done, "✓ Copied", "Copy"),
                class_name="btn btn-ghost",
                on_click=ShiftRecapState.copy_draft,
                style=rx.cond(
                    ShiftRecapState.copy_done,
                    {"color": "var(--accent-positive)", "fontSize": "12px"},
                    {"fontSize": "12px"},
                ),
            ),
            rx.fragment(),
        ),
        rx.cond(
            ShiftRecapState.draft_ready,
            rx.el.a(
                "✉ Open in Outlook",
                href=ShiftRecapState.mailto_href,
                target="_blank",
                rel="noopener",
                class_name="btn btn-primary",
                style={"fontSize": "12px", "textDecoration": "none",
                       "display": "inline-flex", "alignItems": "center"},
            ),
            rx.fragment(),
        ),
        style={"display": "flex", "gap": "8px", "marginBottom": "8px", "flexWrap": "wrap"},
    )


# ── Section editor primitives ────────────────────────────────────────────────

def _section_label(text: str) -> rx.Component:
    return rx.el.div(
        text,
        style={
            "fontSize": "10.5px", "fontWeight": "700",
            "letterSpacing": "0.08em", "textTransform": "uppercase",
            "color": "var(--fg-3)", "marginBottom": "4px",
        },
    )


def _line_field(label: str, value, on_change_handler) -> rx.Component:
    """One-line text input — used for short Team Updates fields."""
    return rx.el.div(
        _section_label(label),
        rx.el.input(
            type="text",
            value=value,
            on_change=on_change_handler,
            placeholder="None",
            style={
                "width": "100%", "fontSize": "13px",
                "padding": "6px 10px",
                "border": "1px solid var(--border-subtle)",
                "borderRadius": "var(--r-md)",
                "background": "var(--surface-card)",
                "color": "var(--fg-1)",
                "outline": "none",
            },
        ),
        style={"marginBottom": "10px"},
    )


def _multi_field(label: str, value, on_change_handler,
                 placeholder: str = "", min_height: str = "70px") -> rx.Component:
    """Multi-line textarea — used for overlaps + narrative."""
    return rx.el.div(
        _section_label(label),
        rx.el.textarea(
            value=value,
            on_change=on_change_handler,
            placeholder=placeholder,
            spellcheck=False,
            style={
                "width": "100%", "fontSize": "13px",
                "padding": "8px 10px",
                "border": "1px solid var(--border-subtle)",
                "borderRadius": "var(--r-md)",
                "background": "var(--surface-card)",
                "color": "var(--fg-1)",
                "outline": "none",
                "minHeight": min_height, "resize": "vertical",
                "fontFamily": "inherit",
            },
        ),
        style={"marginBottom": "10px"},
    )


def _section_group(title: str, *children) -> rx.Component:
    """Visual grouping for a labeled section of the editor."""
    return rx.el.div(
        rx.el.h3(
            title,
            style={
                "fontSize": "13px", "fontWeight": "700",
                "color": "var(--fg-1)", "marginBottom": "10px",
                "letterSpacing": "-0.01em",
            },
        ),
        *children,
        style={
            "padding": "12px 14px",
            "background": "var(--surface-canvas)",
            "border": "1px solid var(--border-subtle)",
            "borderRadius": "var(--r-md)",
            "marginBottom": "12px",
        },
    )


def section_editor() -> rx.Component:
    """Phase L — structured editor for each section of the recap."""
    s = ShiftRecapState
    return rx.el.div(
        # Team Updates
        _section_group(
            "Team Updates",
            _line_field("Days",      s.team_days,      s.set_team_days),
            _line_field("Swings",    s.team_swings,    s.set_team_swings),
            _line_field("Graves",    s.team_graves,    s.set_team_graves),
            _line_field("Utilities", s.team_utilities, s.set_team_utilities),
            _line_field("BCOs",      s.team_bcos,      s.set_team_bcos),
            _line_field("BEOs",      s.team_beos,      s.set_team_beos),
        ),
        # Overlaps
        _section_group(
            "Overlaps",
            _multi_field(
                "Graves", s.overlap_graves, s.set_overlap_graves,
                placeholder="• Doug – Vacuuming, Bottles, and Glass\n• Gage – Glass, Counters, and Trash",
                min_height="80px",
            ),
            _multi_field(
                "Swings", s.overlap_swings, s.set_overlap_swings,
                placeholder="• Darlene did executive offices\n• Jared did zone 10",
                min_height="70px",
            ),
            _multi_field(
                "Days", s.overlap_days, s.set_overlap_days,
                placeholder="• Char – CBK and Shkode",
                min_height="70px",
            ),
        ),
        # Operational systems
        _section_group(
            "MPulse, Access Control, and Uniform Updates",
            _line_field("MPulse",         s.mpulse,         s.set_mpulse),
            _line_field("Access Control", s.access_control, s.set_access_control),
            _line_field("Uniforms",       s.uniforms,       s.set_uniforms),
        ),
        # Huddle + Narrative
        _section_group(
            "Huddle",
            _multi_field("Attendance", s.huddle, s.set_huddle,
                         placeholder="Zach, Melissa, Darlene were in huddle today.",
                         min_height="50px"),
        ),
        _section_group(
            "Shift & Floor Walk Notes",
            _multi_field(
                "Narrative", s.floor_walk_notes, s.set_floor_walk_notes,
                placeholder="How the night went, what came up, what was handled, what's outstanding.",
                min_height="160px",
            ),
        ),
        style={"marginBottom": "16px"},
    )


def email_subject_row() -> rx.Component:
    return rx.cond(
        ShiftRecapState.draft_ready,
        rx.el.div(
            rx.el.span("Subject: ", style={"fontSize": "11px", "color": "var(--fg-4)",
                                            "fontWeight": "600", "flexShrink": "0"}),
            rx.el.span(ShiftRecapState.email_subject,
                       style={"fontSize": "12px", "color": "var(--fg-2)"}),
            style={"display": "flex", "alignItems": "center", "gap": "4px",
                   "marginBottom": "10px", "padding": "6px 10px",
                   "background": "var(--surface-canvas)",
                   "borderRadius": "var(--r-md)",
                   "border": "1px solid var(--border-subtle)"},
        ),
        rx.fragment(),
    )


def draft_column() -> rx.Component:
    """Phase L — section editor on top, compiled draft + email actions below."""
    return rx.el.div(
        rx.el.h2("Recap Sections", class_name="section-title"),
        section_editor(),
        # Toolbar + compiled output
        draft_toolbar(),
        email_subject_row(),
        rx.el.h3(
            "Compiled Draft",
            style={
                "fontSize": "11px", "fontWeight": "700",
                "letterSpacing": "0.08em", "textTransform": "uppercase",
                "color": "var(--fg-3)", "marginBottom": "6px",
            },
        ),
        rx.cond(
            ShiftRecapState.draft_ready,
            rx.el.textarea(
                value=ShiftRecapState.draft,
                on_change=ShiftRecapState.set_draft,
                class_name="recap-draft-area",
                spellcheck=False,
            ),
            rx.el.div(
                rx.el.p(
                    "Click Compile draft to generate the email-ready text.",
                    style={"fontSize": "13px", "color": "var(--fg-3)",
                           "fontStyle": "italic", "textAlign": "center",
                           "padding": "32px 24px"},
                ),
                class_name="recap-draft-empty",
            ),
        ),
        class_name="recap-draft",
    )


# ── Recap page ────────────────────────────────────────────────────────────────

def recap_page() -> rx.Component:
    return rx.el.div(
        rx.el.main(
            page_header(),
            rx.el.section(
                timeline_column(),
                draft_column(),
                class_name="recap-grid",
            ),
            class_name="main",
        ),
        # FAB
        rx.el.button(
            "+",
            class_name="fab",
            on_click=AppState.open_capture,
            title="Capture (⌘N)",
            aria_label="Quick capture",
        ),
        # Overlays
        command_palette(),
        capture_modal(),
        class_name=AppState.app_class_name,
    )
