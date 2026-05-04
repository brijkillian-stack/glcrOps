"""
pages/threads.py — Threads page

Displays auto-grouped topics from recent notes. Each card shows title, status,
note count, and last active time. Click to expand and see linked notes.
"""

import reflex as rx
from ..state.threads import ThreadsState
from shared.base import AppState
from shared.components.sidebar import sidebar
from shared.components.ui import empty_state, skeleton_card
from shared.db import _format_ts


def page_header() -> rx.Component:
    return rx.el.header(
        rx.el.div(
            rx.el.h1("Threads", class_name="page-title"),
            rx.el.p("Auto-grouped topics from recent notes",
                    class_name="page-summary"),
            class_name="page-head-content",
        ),
        class_name="page-head",
    )


def thread_card(item: dict) -> rx.Component:
    """A single thread card with expand/collapse."""
    is_expanded = ThreadsState.expanded_thread_id == item["id"]

    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.h3(item["title"], class_name="card-title"),
                rx.el.div(
                    rx.el.span(
                        item.get("status", "active"),
                        class_name="chip chip-blue",
                    ),
                    rx.el.span(
                        f"{item.get('note_count', 0)} notes",
                        style={"fontSize": "11px", "color": "var(--fg-3)"},
                    ),
                    rx.el.span(
                        item.get("last_active_relative", "—"),
                        style={"fontSize": "11px", "color": "var(--fg-3)"},
                    ),
                    class_name="card-meta",
                    style={"gap": "8px"},
                ),
                class_name="card-body",
                style={"flex": "1"},
            ),
            rx.el.button(
                rx.cond(is_expanded, "▼", "▶"),
                on_click=ThreadsState.expand_thread(item["id"]),
                style={
                    "background": "none",
                    "border": "none",
                    "color": "var(--fg-3)",
                    "cursor": "pointer",
                    "padding": "4px 8px",
                    "fontSize": "14px",
                },
            ),
            class_name="card-row",
            style={"justifyContent": "space-between", "alignItems": "center"},
        ),
        # Expanded notes section
        rx.cond(
            is_expanded,
            rx.el.div(
                rx.foreach(
                    ThreadsState.expanded_thread_notes,
                    lambda note: rx.el.div(
                        rx.el.div(
                            note["captured_at"],
                            style={
                                "fontSize": "11px",
                                "color": "var(--fg-3)",
                                "minWidth": "60px",
                            },
                        ),
                        rx.el.div(
                            note["content"],
                            style={
                                "flex": "1",
                                "color": "var(--fg-2)",
                                "fontSize": "12px",
                                "lineHeight": "1.4",
                            },
                        ),
                        class_name="feed-item",
                        style={"gap": "12px", "padding": "8px 0"},
                    ),
                ),
                style={
                    "borderTop": "1px solid var(--bg-2)",
                    "marginTop": "12px",
                    "paddingTop": "12px",
                },
            ),
            rx.fragment(),
        ),
        class_name="card",
    )


def threads_section() -> rx.Component:
    """Thread cards grid."""
    return rx.el.div(
        rx.el.h2("Topics", class_name="section-title"),
        rx.cond(
            ThreadsState.loading,
            rx.fragment(skeleton_card(), skeleton_card()),
            rx.cond(
                ThreadsState.threads.length() > 0,
                rx.foreach(ThreadsState.threads, thread_card),
                empty_state(
                    "Threads will appear here",
                    "Threads are auto-grouped from recent notes. This happens once the nightly cluster job runs (Phase 5).",
                ),
            ),
        ),
    )


def threads_page() -> rx.Component:
    return rx.el.div(
        sidebar(),
        rx.el.main(
            page_header(),
            threads_section(),
            class_name="main",
        ),
        class_name=AppState.app_class_name,
    )
