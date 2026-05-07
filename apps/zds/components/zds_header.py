"""
components/zds_header.py — Sticky top header for every ZDS page.

Hosts the GLCR/ZDS app switcher plus the page title and any per-page
right-side action (e.g. "New Week" button). Replaces the bespoke
top-nav hstack each ZDS page used to roll inline.
"""

import reflex as rx
from shared.components.app_switcher import app_switcher
from apps.zds.state import ZdsState


def zds_header(
    title: str,
    subtitle: str = "",
    *,
    right: rx.Component | None = None,
) -> rx.Component:
    """Sticky header for ZDS pages.

    Args:
        title: Page heading (e.g. "GLCR · Grave Deployment").
        subtitle: Smaller line under the title.
        right: Optional right-side action (button, badge, etc.).
    """
    title_block = rx.vstack(
        rx.heading(title, size="6"),
        rx.cond(
            subtitle != "",
            rx.text(subtitle, size="2", color="#6b7280"),
            rx.fragment(),
        ),
        gap="0",
    )

    # Sun/moon theme toggle: show sun icon in dark mode (click to go light),
    # moon icon in light mode (click to go dark)
    theme_toggle = rx.button(
        rx.cond(
            ZdsState.theme == "dark",
            rx.icon("sun", size=16),
            rx.icon("moon", size=16),
        ),
        on_click=ZdsState.toggle_theme,
        height="40px",
        padding="8px 12px",
        border="1px solid #e5e7eb",
        background="white",
        color="#374151",
        border_radius="6px",
        cursor="pointer",
        transition="all 0.2s ease",
        _hover={
            "border_color": "#d1d5db",
            "background": "#f9fafb",
        },
    )

    children = [
        app_switcher(),
        title_block,
        rx.spacer(),
        theme_toggle,
    ]
    if right is not None:
        children.append(right)

    return rx.hstack(
        *children,
        width="100%",
        align="center",
        gap="20px",
        padding="20px 32px",
        border_bottom="1px solid #e5e7eb",
        background="white",
        position="sticky",
        top="0",
        z_index="10",
        # chip-header: dark CSS adds dotted-circle overlay + dark gradient bg
        class_name="chip-header",
    )
