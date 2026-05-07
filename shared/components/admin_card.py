"""
shared/components/admin_card.py — Reusable Sudo Admin hub card.

Each card is an <a> tag with CSS class "admin-hub-card" (styled in
assets/admin_hub.css).  Hover produces border-color: var(--blue) +
background: var(--blue-dim) + translateY(-1px).

Usage:
    admin_card("⌖", "Logs", "Captured operational events", "/logs")
    admin_card("⚑", "Write-Ups", "TM disciplinary write-ups", "/writeups",
               count=AdminHubState.writeups_open.to_string())
"""

import reflex as rx


def admin_card(
    glyph: str,
    title: str,
    tagline: str,
    href: str,
    count=None,
) -> rx.Component:
    """Hub card.

    Args:
        glyph:   Unicode icon (16px, ink3).
        title:   Card title (Barlow 14px 600).
        tagline: Short description (ink3, 12px).
        href:    Destination route.
        count:   Optional count chip — pass a plain str or a Reflex Var
                 (e.g. AdminHubState.writeups_open.to_string()).
                 Omit (or pass None) to hide the chip.
    """
    top_row_children = [
        rx.el.span(
            glyph,
            style={
                "fontSize": "16px",
                "color": "var(--ink3)",
                "lineHeight": "1",
                "flexShrink": "0",
            },
        ),
        rx.el.span(
            title,
            style={
                "fontFamily": "var(--font)",
                "fontSize": "14px",
                "fontWeight": "600",
                "color": "var(--ink)",
                "letterSpacing": "0.01em",
            },
        ),
    ]

    if count is not None:
        top_row_children.append(
            rx.el.span(
                count,
                class_name="admin-card-count",
            )
        )

    return rx.el.a(
        rx.el.div(
            *top_row_children,
            style={
                "display": "flex",
                "alignItems": "center",
                "gap": "9px",
                "marginBottom": "7px",
            },
        ),
        rx.el.div(
            tagline,
            style={
                "fontFamily": "var(--font)",
                "fontSize": "12px",
                "color": "var(--ink3)",
                "lineHeight": "1.4",
            },
        ),
        href=href,
        class_name="admin-hub-card",
    )
