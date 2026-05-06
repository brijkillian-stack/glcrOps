"""
section_head.py — Section header with optional eyebrow + thin gold rule.

Used above each zone group in the ZDS deployment grid (and anywhere else we
want the dark-mode eyebrow + gold-rule pattern).

Visual stack (top → bottom):
  ┌──────────────────────────────────────────────────────┐
  │  ZONE GRID                        ← eyebrow (optional)
  │  ────────────────────────────     ← gold rule (always)
  └──────────────────────────────────────────────────────┘

Then the caller renders the actual section content below.

Usage:
    section_head("Zone Grid")
    section_head("Overlap Pool", count=12)
    section_head("Overlap Pool", count=rx.Var("state.pool_count"), eyebrow_text=False)
"""
from __future__ import annotations
import reflex as rx
from shared.components.eyebrow import eyebrow


def section_head(
    label: str | rx.Var,
    *,
    count: int | rx.Var | None = None,
    show_eyebrow: bool = True,
) -> rx.Component:
    """Render an eyebrow + gold rule section header.

    Args:
        label:        Section label string (rendered as an eyebrow span).
        count:        Optional integer count rendered as a badge to the right
                      of the label. Can be a Reflex Var for reactive counts.
        show_eyebrow: If False, omits the eyebrow text and renders only the
                      gold rule (useful when a heading element is already
                      rendered by the caller).
    """
    # Build eyebrow row
    if show_eyebrow:
        label_el = rx.hstack(
            eyebrow(label),
            rx.cond(
                count is not None,
                rx.badge(
                    count,
                    color_scheme="blue",
                    variant="subtle",
                    size="1",
                    font_size="9px",
                    font_weight="700",
                    letter_spacing="0.04em",
                ),
                rx.box(),
            ),
            align="center",
            gap="6px",
            margin_bottom="4px",
        ) if count is not None else rx.hstack(
            eyebrow(label),
            align="center",
            margin_bottom="4px",
        )
    else:
        label_el = rx.box()

    return rx.box(
        label_el,
        rx.box(class_name="section-gold-rule"),
    )
