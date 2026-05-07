"""
shared/state/beo_modal.py — BeoModalState

Manages the ⊟ BEO (Business Early-Out) modal on the Shift HUD:
  1. Brian multi-selects TMs using toggle chips
  2. Enters or adjusts the BEO time (default = current time in "6am" format)
  3. On submit: one note per TM (content_type=observation, section=BEOs) + toast
"""

from __future__ import annotations

import datetime
import traceback
from typing import TypedDict
from zoneinfo import ZoneInfo

import reflex as rx

_ET = ZoneInfo("America/Detroit")


def _default_beo_time() -> str:
    """Return current hour in 'Xam'/'Xpm' format, e.g. '1am', '6pm'."""
    now = datetime.datetime.now(tz=_ET)
    return now.strftime("%-I%p").lower()


class _TmOption(TypedDict):
    name: str
    tm_id: str
    selected: bool


class BeoModalState(rx.State):
    open: bool = False
    avail_tms: list[_TmOption] = []
    beo_time: str = ""
    submitting: bool = False

    @property
    def selected_tms(self) -> list[_TmOption]:
        return [t for t in self.avail_tms if t["selected"]]

    @rx.event
    async def open_modal(self):
        from apps.shift.state import ShiftState
        shift = await self.get_state(ShiftState)
        self.avail_tms = [
            _TmOption(name=c["name"], tm_id=c["tm_id"], selected=False)
            for c in shift.roster_chips
            if c["kind"] != "x"   # don't offer already-called-off TMs
        ]
        self.beo_time = _default_beo_time()
        self.submitting = False
        self.open = True

    @rx.event
    def toggle_tm(self, name: str):
        self.avail_tms = [
            _TmOption(
                name=t["name"],
                tm_id=t["tm_id"],
                selected=not t["selected"] if t["name"] == name else t["selected"],
            )
            for t in self.avail_tms
        ]

    @rx.event
    def set_beo_time(self, val: str):
        self.beo_time = val

    @rx.event
    def close(self):
        self.open = False

    @rx.event
    async def submit(self):
        selected = [t for t in self.avail_tms if t["selected"]]
        if not selected:
            return
        self.submitting = True
        try:
            from apps.shift.state import ShiftState
            from shared.db import insert_note, lookup_entity_id_by_name
            from shared.state.capture_toast import CaptureToastState

            shift = await self.get_state(ShiftState)
            shift_date = shift.shift_date_iso
            event_id = shift.shift_log_event_id or None
            beo_time = self.beo_time or _default_beo_time()

            for tm in selected:
                tm_id = tm["tm_id"] or ""
                if not tm_id:
                    tm_id = shift.roster_name_to_id.get(tm["name"], "")
                if not tm_id:
                    tm_id = lookup_entity_id_by_name(tm["name"]) or ""

                meta: dict = {
                    "section":  "BEOs",
                    "beo_time": beo_time,
                }
                if event_id:
                    meta["event_id"] = event_id

                insert_note(
                    content=f"{tm['name']} took BEO",
                    content_type="observation",
                    sentiment="neutral",
                    original_date=shift_date,
                    author="brian",
                    captured_via="shift-hud",
                    metadata=meta,
                    entity_ids=[tm_id] if tm_id else [],
                    event_id=event_id,
                )

            names_str = ", ".join(t["name"] for t in selected)
            ct = await self.get_state(CaptureToastState)
            ct.show(f"Logged BEO: {names_str} at {beo_time}")

            self.open = False
            shift2 = await self.get_state(ShiftState)
            await shift2._build_tasks()
            await shift2._build_activity()

        except Exception:
            print(f"[BeoModal.submit] error:\n{traceback.format_exc()}")
        finally:
            self.submitting = False
