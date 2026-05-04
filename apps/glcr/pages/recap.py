"""
pages/recap.py — Shift Recap page

Left column: chronological timeline of tonight's captures.
Right column: auto-generated plain-text email draft, editable and copyable.
"""

import reflex as rx
from ..state.recap import ShiftRecapState
from shared.base import AppState
from shared.components.sidebar import sidebar
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
            rx.cond(ShiftRecapState.generating, "Generating…", "⟳  Regenerate"),
            class_name=rx.cond(
                ShiftRecapState.generating, "btn btn-ghost", "btn btn-ghost"
            ),
            on_click=ShiftRecapState.generate_draft,
            disabled=ShiftRecapState.generating,
            style={"fontSize": "12px"},
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
    return rx.el.div(
        rx.el.h2("Draft Recap", class_name="section-title"),
        rx.cond(
            ShiftRecapState.draft_ready,
            rx.fragment(
                draft_toolbar(),
                email_subject_row(),
                rx.el.textarea(
                    value=ShiftRecapState.draft,
                    on_change=ShiftRecapState.set_draft,
                    class_name="recap-draft-area",
                    spellcheck=False,
                ),
            ),
            rx.el.div(
                rx.cond(
                    ShiftRecapState.generating,
                    rx.el.p(
                        "Generating recap draft…",
                        style={"fontSize": "13px", "color": "var(--fg-3)",
                               "fontStyle": "italic", "textAlign": "center",
                               "padding": "48px 24px"},
                    ),
                    rx.el.div(
                        rx.el.p(
                            "Recap will auto-generate when tonight's logs are loaded.",
                            style={"fontSize": "13px", "color": "var(--fg-3)",
                                   "fontStyle": "italic", "marginBottom": "16px"},
                        ),
                        rx.el.button(
                            "⟳  Generate Draft",
                            class_name="btn btn-primary",
                            on_click=ShiftRecapState.generate_draft,
                            style={"fontSize": "13px"},
                        ),
                        style={"textAlign": "center", "padding": "48px 24px"},
                    ),
                ),
                class_name="recap-draft-empty",
            ),
        ),
        class_name="recap-draft",
    )


# ── Recap page ────────────────────────────────────────────────────────────────

def recap_page() -> rx.Component:
    return rx.el.div(
        sidebar(),
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
