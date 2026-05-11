"""
state/writeups.py — WriteupsState

Loads progressive discipline write-up records from notes flagged as write-ups.
"""

import reflex as rx
from shared.base import AppState
from shared.db import list_writeups


class WriteupsState(AppState):
    # ── Writeups data ─────────────────────────────────────────────────────────
    writeups: list[dict] = []
    level_filter: str = "all"  # "all" | "verbal" | "written" | "final"

    # ── Page state ────────────────────────────────────────────────────────────
    loading: bool = True
    error: str = ""

    # ── Events ────────────────────────────────────────────────────────────────

    @rx.event
    async def load_writeups(self, level_filter: str = "all"):
        """Load write-ups filtered by discipline level."""
        self.loading = True
        self.error = ""
        self.level_filter = level_filter
        yield

        try:
            self.writeups = list_writeups(level_filter=level_filter)
        except Exception as exc:
            self.error = str(exc)
        finally:
            self.loading = False

    @rx.event
    async def set_filter(self, level: str):
        """Change the discipline level filter."""
        yield WriteupsState.load_writeups(level)

    @rx.event
    async def reload_writeups(self):
        """Manual refresh button."""
        yield WriteupsState.load_writeups(self.level_filter)
