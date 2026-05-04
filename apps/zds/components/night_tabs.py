"""Night selector tab bar."""

import reflex as rx
from ..state import ZdsState


def _night_tab(night: dict) -> rx.Component:
    is_active = ZdsState.current_night_id == night["id"]
    return rx.button(
        rx.vstack(
            rx.text(night["day_name"], size="2", weight="bold"),
            rx.text(night["night_date"], size="1", color=rx.cond(is_active, "#1d4ed8", "#9ca3af")),
            gap="0", align="center",
        ),
        variant=rx.cond(is_active, "solid", "ghost"),
        color_scheme=rx.cond(is_active, "blue", "gray"),
        on_click=ZdsState.select_night(night["id"]),
        padding="8px 16px",
        border_radius="8px",
        height="auto",
    )


def night_tab_bar() -> rx.Component:
    return rx.hstack(
        rx.foreach(ZdsState.nights, _night_tab),
        gap="4px",
        padding="12px 0 4px",
        overflow_x="auto",
        width="100%",
    )
