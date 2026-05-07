"""
shared/state/call_out_modal.py — CallOutModalState

Manages the ⚑ Call-Out modal on the Shift HUD:
  1. Opens with tonight's active TM roster (from ShiftState.roster_chips)
  2. Brian picks a TM, enters points (float) and an optional reason note
  3. On confirm: writes call_offs row, then inserts a note into public.notes
     (content_type=flag, section=Call-Outs in metadata), closes modal, shows toast
"""

from __future__ import annotations

import traceback
from typing import TypedDict

import reflex as rx


class _TmOption(TypedDict):
    name: str
    tm_id: str


_NOTE_OPTIONS = ["", "PTO", "LOA", "Possible Intermittent", "FMLA"]


class CallOutModalState(rx.State):
    open: bool = False
    avail_tms: list[_TmOption] = []
    picked_name: str = ""
    picked_tm_id: str = ""
    points_str: str = "0"
    note: str = ""
    submitting: bool = False

    @rx.event
    async def open_modal(self):
        from apps.shift.state import ShiftState
        shift = await self.get_state(ShiftState)
        # Offer active TMs only (exclude already-called-off 'x' chips)
        self.avail_tms = [
            _TmOption(name=c["name"], tm_id=c["tm_id"])
            for c in shift.roster_chips
            if c["kind"] != "x"
        ]
        self.picked_name = ""
        self.picked_tm_id = ""
        self.points_str = "0"
        self.note = ""
        self.submitting = False
        self.open = True

    @rx.event
    def pick_tm(self, name: str, tm_id: str):
        self.picked_name = name
        self.picked_tm_id = tm_id

    @rx.event
    def set_points(self, val: str):
        self.points_str = val

    @rx.event
    def set_note(self, val: str):
        self.note = val

    @rx.event
    def close(self):
        self.open = False

    @rx.event
    async def confirm(self):
        if not self.picked_name:
            return
        self.submitting = True
        try:
            from apps.shift.state import ShiftState
            from apps.zds import database as zdb
            from shared.db import insert_note, ensure_tm_profile_exists, lookup_entity_id_by_name
            from shared.state.capture_toast import CaptureToastState

            shift = await self.get_state(ShiftState)
            shift_date = shift.shift_date_iso
            event_id = shift.shift_log_event_id or None

            # Resolve tm_id — use picked, fall back to name lookup
            tm_id = self.picked_tm_id or ""
            if not tm_id:
                tm_id = shift.roster_name_to_id.get(self.picked_name, "")
            if not tm_id:
                tm_id = lookup_entity_id_by_name(self.picked_name) or ""

            # 1. Write call_off row (idempotent)
            if tm_id:
                try:
                    ensure_tm_profile_exists(tm_id, source="shift_hud_callout")
                    zdb.add_call_off(tm_id, shift_date, self.note or "")
                except Exception:
                    print(f"[CallOutModal] call_off write error:\n{traceback.format_exc()}")

            # 2. Parse points
            pts: float | None = None
            try:
                pts = float(self.points_str)
            except Exception:
                pass

            # 3. Write note to public.notes
            from apps.shift.state import _now_approx_label
            meta: dict = {"section": "Call-Outs", "approx_time": _now_approx_label()}
            if pts is not None:
                meta["points"] = pts
            if self.note:
                meta["note"] = self.note
            if event_id:
                meta["event_id"] = event_id

            insert_note(
                content=f"{self.picked_name} called off",
                content_type="flag",
                sentiment="flag",
                original_date=shift_date,
                author="brian",
                captured_via="shift-hud",
                metadata=meta,
                entity_ids=[tm_id] if tm_id else [],
                event_id=event_id,
            )

            # 4. Toast
            pts_str = f" ({pts:g}pts)" if pts is not None else ""
            ct = await self.get_state(CaptureToastState)
            ct.show(f"Logged {self.picked_name} callout{pts_str}")

            # 5. Close modal, refresh activity feed
            self.open = False
            shift2 = await self.get_state(ShiftState)
            await shift2._build_tasks()
            await shift2._build_activity()

        except Exception:
            print(f"[CallOutModal.confirm] error:\n{traceback.format_exc()}")
        finally:
            self.submitting = False
