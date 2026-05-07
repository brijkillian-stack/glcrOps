"""
shared/state/kudos_modal.py — KudosModalState

Manages the ★ Kudos modal on the Shift HUD:
  1. Brian picks a TM and writes a short observation (1–3 lines)
  2. On submit: inserts a note (content_type=kudos) into public.notes, closes, toasts
"""

from __future__ import annotations

import traceback
from typing import TypedDict

import reflex as rx


class _TmOption(TypedDict):
    name: str
    tm_id: str


class KudosModalState(rx.State):
    open: bool = False
    avail_tms: list[_TmOption] = []
    picked_name: str = ""
    picked_tm_id: str = ""
    text: str = ""
    submitting: bool = False

    @rx.event
    async def open_modal(self):
        from apps.shift.state import ShiftState
        shift = await self.get_state(ShiftState)
        # All active TMs are eligible for kudos (including those already noted)
        self.avail_tms = [
            _TmOption(name=c["name"], tm_id=c["tm_id"])
            for c in shift.roster_chips
        ]
        self.picked_name = ""
        self.picked_tm_id = ""
        self.text = ""
        self.submitting = False
        self.open = True

    @rx.event
    def pick_tm(self, name: str, tm_id: str):
        self.picked_name = name
        self.picked_tm_id = tm_id

    @rx.event
    def set_text(self, val: str):
        self.text = val

    @rx.event
    def close(self):
        self.open = False

    @rx.event
    async def submit(self):
        if not self.picked_name or not self.text.strip():
            return
        self.submitting = True
        try:
            from apps.shift.state import ShiftState
            from shared.db import insert_note, lookup_entity_id_by_name
            from shared.state.capture_toast import CaptureToastState

            shift = await self.get_state(ShiftState)
            shift_date = shift.shift_date_iso
            event_id = shift.shift_log_event_id or None

            tm_id = self.picked_tm_id or ""
            if not tm_id:
                tm_id = shift.roster_name_to_id.get(self.picked_name, "")
            if not tm_id:
                tm_id = lookup_entity_id_by_name(self.picked_name) or ""

            meta: dict = {"section": "Floor Walk"}
            if event_id:
                meta["event_id"] = event_id

            insert_note(
                content=self.text.strip(),
                content_type="kudos",
                sentiment="positive",
                original_date=shift_date,
                author="brian",
                captured_via="shift-hud",
                metadata=meta,
                entity_ids=[tm_id] if tm_id else [],
                event_id=event_id,
            )

            ct = await self.get_state(CaptureToastState)
            ct.show(f"Captured kudos for {self.picked_name}")

            self.open = False
            shift2 = await self.get_state(ShiftState)
            await shift2._build_tasks()
            await shift2._build_activity()

        except Exception:
            print(f"[KudosModal.submit] error:\n{traceback.format_exc()}")
        finally:
            self.submitting = False
