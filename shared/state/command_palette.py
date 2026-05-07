"""
shared/state/command_palette.py — CommandPaletteState

The + FAB / ⌘K command palette for the Shift HUD:
  - 4 quick-action buttons (⚑ Call-out / ★ Kudos / ⊟ BEO / 📋 Compile Recap)
  - Free-text textarea for unstructured captures (written as reference notes)
  - ⌘K (Mac) / Ctrl+K (Win) toggles open; Esc closes

The JS handler in assets/command_palette.js dispatches
command_palette_state.toggle when ⌘K is pressed (ignores input focus).
"""

from __future__ import annotations

import traceback

import reflex as rx


class CommandPaletteState(rx.State):
    open: bool = False
    raw_text: str = ""
    submitting: bool = False

    @rx.event
    def toggle(self):
        self.open = not self.open
        if self.open:
            self.raw_text = ""

    @rx.event
    def close(self):
        self.open = False

    @rx.event
    def set_raw_text(self, val: str):
        self.raw_text = val

    @rx.event
    async def open_call_out(self):
        """Close palette and open call-out modal."""
        from shared.state.call_out_modal import CallOutModalState
        self.open = False
        co = await self.get_state(CallOutModalState)
        await co.open_modal()

    @rx.event
    async def open_kudos(self):
        """Close palette and open kudos modal."""
        from shared.state.kudos_modal import KudosModalState
        self.open = False
        km = await self.get_state(KudosModalState)
        await km.open_modal()

    @rx.event
    async def open_beo(self):
        """Close palette and open BEO modal."""
        from shared.state.beo_modal import BeoModalState
        self.open = False
        bm = await self.get_state(BeoModalState)
        await bm.open_modal()

    @rx.event
    async def submit_raw(self):
        """Write the textarea content as a free-form reference note."""
        text = self.raw_text.strip()
        if not text:
            return
        self.submitting = True
        try:
            from apps.shift.state import ShiftState
            from shared.db import insert_note
            from shared.state.capture_toast import CaptureToastState

            shift = await self.get_state(ShiftState)
            shift_date = shift.shift_date_iso
            event_id = shift.shift_log_event_id or None

            meta: dict = {"source": "command_palette", "raw": text}
            if event_id:
                meta["event_id"] = event_id

            insert_note(
                content=text,
                content_type="reference",
                sentiment="neutral",
                original_date=shift_date,
                author="brian",
                captured_via="shift-hud",
                metadata=meta,
                event_id=event_id,
            )

            ct = await self.get_state(CaptureToastState)
            ct.show("Captured. Run a recap to consume.")

            self.open = False
            self.raw_text = ""
            shift2 = await self.get_state(ShiftState)
            await shift2._build_tasks()
            await shift2._build_activity()

        except Exception:
            print(f"[CommandPalette.submit_raw] error:\n{traceback.format_exc()}")
        finally:
            self.submitting = False
