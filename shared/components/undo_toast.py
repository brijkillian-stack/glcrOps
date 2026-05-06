"""
shared/components/undo_toast.py — Slide-in undo toast

Mount global_undo_toast() once at app root in both _with_grok and
_with_zds_chrome. Shows when UndoState.toast_open is True.

The MutationObserver in assets/undo_toast.js watches for .undo-toast-panel
appearing in the DOM and fires a 5-second auto-dismiss by dispatching
UndoState.dismiss via window._reflexDispatch. Clicking "Undo" or "×" will
dismiss early.
"""

import reflex as rx
from shared.state.undo import UndoState


def global_undo_toast() -> rx.Component:
    """Fixed bottom-right undo toast. Mount once at app root."""
    return rx.box(
        rx.cond(
            UndoState.toast_open,
            rx.box(
                rx.icon("rotate-ccw", size=15, color="#30b2ff", flex_shrink="0"),
                rx.text(
                    UndoState.last_label,
                    size="2",
                    color="#e8edf2",
                    flex="1",
                    min_width="0",
                    overflow="hidden",
                    text_overflow="ellipsis",
                ),
                rx.button(
                    "Undo",
                    on_click=UndoState.undo,
                    size="1",
                    variant="solid",
                    color_scheme="blue",
                    cursor="pointer",
                    flex_shrink="0",
                ),
                rx.el.button(
                    "×",
                    on_click=UndoState.dismiss,
                    class_name="undo-toast-close",
                ),
                class_name="undo-toast-panel",
            ),
            rx.fragment(),
        ),
        class_name="undo-toast-root",
    )
