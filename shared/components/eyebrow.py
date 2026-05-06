"""
eyebrow.py — Small uppercase label used above section headings in ZDS.

Renders a single <span> with the .section-eyebrow CSS class from zds_dark.css.
Works in both light and dark contexts (light mode: --fg-3 color; dark mode: #4d6a82).

Usage:
    eyebrow("Zone Grid")
    eyebrow("Overlap Pool", color="#30b2ff")  # override color inline
"""
import reflex as rx


def eyebrow(label: str, **props) -> rx.Component:
    """Render a small all-caps eyebrow label above a section heading.

    Args:
        label: The text to display (rendered as-is; no automatic uppercasing
               — the CSS handles letter-spacing + text-transform).
        **props: Additional Reflex props forwarded to the rx.text element.
    """
    return rx.text(
        label,
        class_name="section-eyebrow",
        **props,
    )
