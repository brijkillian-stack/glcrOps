"""
components/capture.py — ⌘N Quick capture modal

Phase 1: UI wired to AppState. Actual DB write via MCP bridge comes in Phase 2
(the MCP server is the write path; the dashboard is primarily read).
For now, the modal opens, accepts input, and shows a "saved" confirmation.
"""

import reflex as rx
from shared.base import AppState


def capture_modal() -> rx.Component:
    return rx.cond(
        AppState.capture_open,
        rx.el.div(
            rx.el.div(
                # Head
                rx.el.div(
                    rx.el.h2("Capture a note", class_name="modal-title"),
                    rx.el.button(
                        "×",
                        class_name="btn btn-ghost",
                        on_click=AppState.close_capture,
                        style={"fontSize": "18px", "width": "28px", "height": "28px",
                               "borderRadius": "8px"},
                    ),
                    class_name="modal-head",
                ),
                # Body
                rx.el.div(
                    rx.el.div(
                        rx.el.label("What happened?"),
                        rx.el.textarea(
                            placeholder="Joy was exceptional in Z9 tonight — fast, composed under pressure",
                            value=AppState.capture_content,
                            on_change=AppState.set_capture_content,
                            auto_focus=True,
                        ),
                        class_name="field",
                    ),
                    rx.el.div(
                        rx.el.div(
                            rx.el.label("Type"),
                            rx.el.select(
                                rx.el.option("observation"),
                                rx.el.option("kudos"),
                                rx.el.option("flag"),
                                rx.el.option("request"),
                                rx.el.option("feedback"),
                                rx.el.option("incident"),
                                value=AppState.capture_type,
                                on_change=AppState.set_capture_type,
                            ),
                            class_name="field",
                        ),
                        rx.el.div(
                            rx.el.label("Sentiment"),
                            rx.el.select(
                                rx.el.option("—", value="neutral"),
                                rx.el.option("positive"),
                                rx.el.option("negative"),
                                rx.el.option("neutral"),
                                rx.el.option("flag"),
                                value=AppState.capture_sentiment,
                                on_change=AppState.set_capture_sentiment,
                            ),
                            class_name="field",
                        ),
                        class_name="field-row",
                    ),
                    rx.el.div(
                        rx.el.label("TMs / Entities"),
                        rx.el.input(
                            placeholder="Joy, Z9, Cookie",
                            value=AppState.capture_entities,
                            on_change=AppState.set_capture_entities,
                        ),
                        class_name="field",
                    ),
                    rx.el.div(
                        rx.el.div(
                            rx.el.label("Date"),
                            rx.el.input(
                                type="date",
                                value=AppState.capture_date,
                                on_change=AppState.set_capture_date,
                            ),
                            class_name="field",
                        ),
                        rx.el.div(
                            rx.el.label("Author"),
                            rx.el.input(value="brian", read_only=True),
                            class_name="field",
                        ),
                        class_name="field-row",
                    ),
                    class_name="modal-body",
                ),
                # Footer
                rx.el.div(
                    rx.el.button(
                        "Close",
                        class_name="btn btn-ghost",
                        on_click=AppState.close_capture,
                    ),
                    rx.el.button(
                        "Save →",
                        class_name="btn btn-primary",
                        on_click=AppState.save_capture,
                    ),
                    class_name="modal-foot",
                ),
                class_name="modal",
                on_click=rx.stop_propagation,
            ),
            class_name="modal-scrim",
            on_click=AppState.close_capture,
        ),
        rx.fragment(),
    )
