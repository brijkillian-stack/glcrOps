"""
components/palette.py — ⌘K Command palette overlay

Static placeholder for Phase 1. Search wiring comes in Phase 2.
"""

import reflex as rx
from shared.base import AppState


def command_palette() -> rx.Component:
    return rx.cond(
        AppState.palette_open,
        rx.el.div(
            rx.el.div(
                rx.el.input(
                    class_name="palette-input",
                    placeholder="Search anything — name, topic, date…",
                    auto_focus=True,
                    value=AppState.palette_query,
                    on_change=AppState.set_palette_query,
                ),
                rx.el.div(
                    rx.el.div(
                        "Start typing to search notes, TMs, tasks, and threads.",
                        style={"padding": "24px", "color": "var(--fg-3)",
                               "fontSize": "13px", "textAlign": "center"},
                    ),
                    class_name="palette-results",
                ),
                rx.el.div(
                    rx.el.span(rx.el.span("↑↓", class_name="kbd"), " navigate"),
                    rx.el.span(rx.el.span("↵", class_name="kbd"), " open"),
                    rx.el.span(
                        rx.el.span("esc", class_name="kbd"), " close",
                        style={"marginLeft": "auto"},
                    ),
                    class_name="palette-foot",
                ),
                class_name="palette",
                on_click=rx.stop_propagation,
            ),
            class_name="palette-scrim",
            on_click=AppState.close_palette,
        ),
        rx.fragment(),
    )
