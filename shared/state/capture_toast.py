"""
shared/state/capture_toast.py — Simple 3-second non-undoable capture toast.

Used by Phase 4a capture flows (call-out, kudos, BEO, command palette) to give
visual feedback after a successful write without exposing an Undo button
(captures are permanent and not reversible from the HUD).

The JS auto-dismiss is handled by assets/capture_toast.js which watches for
.capture-toast-panel and dispatches capture_toast_state.dismiss after 3s.
"""

from __future__ import annotations

import reflex as rx


class CaptureToastState(rx.State):
    """Simple 3-second auto-dismiss toast for capture confirmations."""

    message: str = ""
    visible: bool = False

    def show(self, message: str):
        """Show the toast with the given message. Call from within another
        event handler via: ct = await self.get_state(CaptureToastState); ct.show(msg)
        """
        self.message = message
        self.visible = True

    @rx.event
    def dismiss(self):
        """Dismiss the toast. Called by JS auto-dismiss after 3s."""
        self.visible = False
        self.message = ""
