"""
engine_result_dialog.py — Phase K.1

Modal that surfaces what the deployment engine actually did after a run.
Pops up after Run Engine (Night/Week) and after Set Break Waves so Brian
sees a structured summary instead of silent grid updates.

State: ZdsState.engine_result (dict), ZdsState.engine_result_open (bool)
"""

import reflex as rx
from ..state import ZdsState


def _stat(label: str, value, color: str) -> rx.Component:
    """One stat tile in the summary header."""
    return rx.vstack(
        rx.text(value, size="6", weight="bold", color=color, line_height="1"),
        rx.text(label, size="1", color="#6b7280",
                letter_spacing="0.06em", text_transform="uppercase"),
        gap="2px", align="center",
        padding="10px 16px",
        border="1px solid #e5e7eb",
        border_radius="8px",
        flex="1",
    )


def _unresolved_row(item) -> rx.Component:
    """One row in the unresolved-slots list. `item` is a UnresolvedSlot Var."""
    return rx.hstack(
        rx.icon("triangle-alert", size=12, color="#b45309"),
        rx.text(
            item["date"], " · ", item["zone_slot"],
            size="2", color="#92400e", weight="medium",
        ),
        rx.cond(
            item["priority"] > 0,
            rx.badge(
                "P", item["priority"].to_string(),
                size="1", color_scheme="amber", variant="soft",
            ),
            rx.fragment(),
        ),
        gap="6px", align="center",
        padding="4px 10px",
        background="#fffbeb",
        border_radius="4px",
        width="100%",
    )


def engine_result_dialog() -> rx.Component:
    """The modal. Renders only when ZdsState.engine_result_open is True."""
    r = ZdsState.engine_result
    return rx.dialog.root(
        rx.dialog.content(
            # ── Header ──
            rx.hstack(
                rx.cond(
                    r["success"],
                    rx.icon("circle-check", size=18, color="#059669"),
                    rx.icon("circle-alert", size=18, color="#dc2626"),
                ),
                rx.text(
                    rx.cond(r["success"], "Engine ran", "Engine error"),
                    size="4", weight="bold",
                ),
                rx.spacer(),
                rx.badge(
                    rx.cond(r["scope"] == "week", "Week", "Night"),
                    color_scheme="blue",
                    variant="soft",
                ),
                width="100%", align="center",
            ),

            # ── Error message (only when !success) ──
            rx.cond(
                ~r["success"],
                rx.callout(
                    r["message"],
                    color_scheme="red",
                    icon="triangle-alert",
                    size="1",
                ),
                rx.fragment(),
            ),

            # ── Stats row (only when success) ──
            rx.cond(
                r["success"],
                rx.hstack(
                    _stat("Filled",      r["updated"],            "#059669"),
                    _stat("Locked",      r["locked_skipped"],     "#b45309"),
                    _stat("Cleared",     r["unresolved_cleared"], "#9ca3af"),
                    _stat("Unresolved",  r["unresolved"].length(),"#dc2626"),
                    width="100%", gap="8px",
                ),
                rx.fragment(),
            ),

            # ── Week ending tag ──
            rx.cond(
                r["week_ending"] != "",
                rx.text(
                    "Week ending ", r["week_ending"],
                    size="1", color="#9ca3af",
                ),
                rx.fragment(),
            ),

            # ── Unresolved details ──
            rx.cond(
                r["unresolved"].length() > 0,
                rx.vstack(
                    rx.text(
                        "Unresolved slots — engine couldn't fill these:",
                        size="2", weight="bold", color="#7c2d12",
                    ),
                    rx.scroll_area(
                        rx.vstack(
                            rx.foreach(r["unresolved"], _unresolved_row),
                            gap="4px", width="100%",
                        ),
                        max_height="240px",
                        width="100%",
                    ),
                    width="100%", gap="6px",
                ),
                rx.fragment(),
            ),

            # ── Footer ──
            rx.hstack(
                rx.spacer(),
                rx.dialog.close(
                    rx.button(
                        "Done",
                        size="2",
                        on_click=ZdsState.close_engine_result,
                    ),
                ),
                width="100%",
            ),

            max_width="560px",
            padding="20px",
        ),
        open=ZdsState.engine_result_open,
        # Closes the dialog when user clicks outside / hits Esc — the dialog
        # itself sends `False` here, which triggers our explicit close handler.
        on_open_change=ZdsState.set_engine_result_open,
    )
