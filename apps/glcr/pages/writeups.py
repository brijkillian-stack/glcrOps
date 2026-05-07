"""
pages/writeups.py — Write-Ups (Progressive Discipline) page

Displays write-up records in reverse chronological order, with filtering by
discipline level (verbal, written, final).
"""

import reflex as rx
from ..state.writeups import WriteupsState
from shared.base import AppState
from shared.components.ui import empty_state, skeleton_card
from shared.db import _format_ts


def page_header() -> rx.Component:
    return rx.el.header(
        rx.el.div(
            rx.el.h1("Write-Ups", class_name="page-title"),
            rx.el.p("Progressive discipline records",
                    class_name="page-summary"),
            class_name="page-head-content",
        ),
        class_name="page-head",
    )


def filter_chips() -> rx.Component:
    """Filter chips: All / Verbal / Written / Final."""
    def chip_btn(label: str, value: str) -> rx.Component:
        is_active = WriteupsState.level_filter == value
        return rx.el.button(
            label,
            on_click=WriteupsState.set_filter(value),
            class_name=rx.cond(
                is_active,
                "filter-chip filter-chip-active",
                "filter-chip",
            ),
            style={
                "cursor": "pointer",
                "padding": "6px 12px",
                "fontSize": "12px",
                "fontWeight": rx.cond(is_active, "600", "400"),
                "color": rx.cond(
                    is_active,
                    "var(--accent-blue)",
                    "var(--fg-3)",
                ),
                "borderBottom": rx.cond(
                    is_active,
                    "2px solid var(--accent-blue)",
                    "2px solid transparent",
                ),
                "border": "none",
                "background": "none",
            },
        )

    return rx.el.div(
        chip_btn("All", "all"),
        chip_btn("Verbal", "verbal"),
        chip_btn("Written", "written"),
        chip_btn("Final", "final"),
        style={
            "display": "flex",
            "gap": "16px",
            "borderBottom": "1px solid var(--bg-2)",
            "marginBottom": "20px",
            "paddingBottom": "12px",
        },
    )


def writeup_card(item: dict) -> rx.Component:
    """A single write-up card."""
    tm_name = item.get("tm_display_name", "—")
    date_str = item.get("original_date", "")
    content = item.get("content", "")
    level = item.get("discipline_level", "")

    level_badge = rx.cond(
        level == "verbal",
        rx.el.span("Verbal", class_name="chip chip-blue"),
        rx.cond(
            level == "written",
            rx.el.span("Written", class_name="chip chip-flag"),
            rx.cond(
                level == "final",
                rx.el.span("Final", class_name="chip chip-flag"),
                rx.fragment(),
            ),
        ),
    )

    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.p(tm_name, class_name="card-title"),
                rx.el.div(
                    level_badge,
                    rx.el.span(
                        date_str,
                        style={"fontSize": "11px", "color": "var(--fg-3)"},
                    ),
                    class_name="card-meta",
                ),
                class_name="card-body",
            ),
            class_name="card-row",
        ),
        rx.el.p(
            content,
            style={
                "fontSize": "12px",
                "color": "var(--fg-2)",
                "lineHeight": "1.5",
                "margin": "8px 0 0",
            },
        ),
        class_name="card",
    )


def writeups_section() -> rx.Component:
    """Write-ups list with filter."""
    return rx.el.div(
        rx.el.h2("Records", class_name="section-title"),
        filter_chips(),
        rx.cond(
            WriteupsState.loading,
            rx.fragment(skeleton_card(), skeleton_card()),
            rx.cond(
                WriteupsState.writeups.length() > 0,
                rx.foreach(WriteupsState.writeups, writeup_card),
                empty_state(
                    "No write-ups recorded yet",
                    "Progressive discipline records will appear here.",
                ),
            ),
        ),
    )


def writeups_page() -> rx.Component:
    return rx.el.div(
        rx.el.main(
            page_header(),
            writeups_section(),
            class_name="main",
        ),
        class_name=AppState.app_class_name,
    )
