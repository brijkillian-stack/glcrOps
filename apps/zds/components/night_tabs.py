"""Night selector tab bar."""

import reflex as rx
from ..state import ZdsState


def _night_tab(night: dict) -> rx.Component:
    is_active = ZdsState.current_night_id == night["id"]
    # Drop the Chakra variant/color_scheme — those inject inline text colors
    # that override our .night-tab / .night-tab-active CSS classes. Use a
    # plain rx.button with cursor pointer and let the CSS in zds_dark.css +
    # styles.css drive backgrounds + text. Day titles now read white on
    # dark and ink on light, both for active and inactive states.
    return rx.button(
        rx.vstack(
            rx.text(night["day_name"], size="2", weight="bold",
                    class_name="night-tab-day"),
            rx.text(night["night_date"], size="1",
                    class_name="night-tab-date"),
            gap="0", align="center",
        ),
        variant="ghost",
        color_scheme="gray",
        on_click=ZdsState.select_night(night["id"]),
        padding="8px 16px",
        border_radius="8px",
        height="auto",
        class_name=rx.cond(is_active, "night-tab night-tab-active", "night-tab"),
    )


def night_tab_bar() -> rx.Component:
    return rx.hstack(
        rx.foreach(ZdsState.nights, _night_tab),
        gap="4px",
        padding="12px 0 4px",
        overflow_x="auto",
        width="100%",
        class_name="night-tabs-bar",
    )
