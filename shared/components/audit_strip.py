"""
audit_strip.py — Fixed audit strip for ZDS pages.

Shows save state in the bottom-right corner:
  • Green dot + "Saved {time}" — after the last successful write
  • Amber dot + "Unsaved changes" — if change_count > 0 and not yet saved
  • Hidden — when the board is clean (no edits, no saves this session)

CSS lives in assets/zds_dark.css (.audit-strip, .audit-dot-*, .audit-text-*).
Mounted once at the app level by _with_zds_chrome in brijkillian_stack.py.
"""

import reflex as rx
from apps.zds.state import ZdsState


def audit_strip() -> rx.Component:
    """Bottom-right fixed strip showing save / unsaved state."""
    return rx.box(
        # ── Saved state ──────────────────────────────────────────────────────
        rx.cond(
            ZdsState.last_saved_at != "",
            rx.box(
                rx.box(class_name="audit-dot audit-dot-saved"),
                rx.text(
                    "Saved ",
                    rx.el.span(ZdsState.last_saved_at, class_name="audit-text-meta"),
                    class_name="audit-text-saved",
                ),
                display="flex",
                align_items="center",
                gap="8px",
            ),
            # ── Unsaved state (edits pending, no save yet) ──────────────────
            rx.cond(
                ZdsState.has_changes,
                rx.box(
                    rx.box(class_name="audit-dot audit-dot-unsaved"),
                    rx.text("Unsaved changes", class_name="audit-text-unsaved"),
                    display="flex",
                    align_items="center",
                    gap="8px",
                ),
                rx.fragment(),  # clean — show nothing
            ),
        ),
        class_name="audit-strip",
        # Hide the strip entirely when there's nothing to show
        display=rx.cond(
            (ZdsState.last_saved_at != "") | ZdsState.has_changes,
            "flex",
            "none",
        ),
    )
