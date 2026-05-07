"""shared/state/avatar_menu.py — Avatar dropdown open/close state (Phase 2)."""

import reflex as rx


class AvatarMenuState(rx.State):
    """Small state that tracks whether the avatar chip dropdown is open."""

    open: bool = False

    def toggle(self):
        self.open = not self.open

    def close(self):
        self.open = False
