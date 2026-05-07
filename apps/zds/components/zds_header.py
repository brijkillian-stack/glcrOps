"""
components/zds_header.py — Sticky top header for every ZDS page.

Hosts the page title block and any per-page right-side action.
The app-switcher and theme toggle were removed in Phase 2 — they now
live in the unified 60px nav rail (shared/components/nav_rail.py).
"""

import reflex as rx


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

    children: list = [title_block, rx.spacer()]
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
