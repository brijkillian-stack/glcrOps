"""
apps/shift/types.py — TypedDicts for the Shift HUD state vars.

These mirror the dict shapes produced by ShiftState.on_load (which reads
ZdsState zone/rr/aux/break_rows for tonight's deployment, plus shared/db.py
for tasks and activity).  All fields are str / int / bool so Reflex can
infer them inside rx.foreach bodies without manual .to() casts.
"""

from __future__ import annotations

from typing import TypedDict


class HudZoneSlot(TypedDict):
    """Read-only snapshot of one zone slot for the HUD zone grid."""

    slot_key: str       # "Z1" … "Z10"
    tm_name: str        # Display name, or "—" when open
    position: str       # Slot descriptor, e.g. "Outdoor Smoking · Elevators"
    wave: int           # 1 | 2 | 3
    wave_time: str      # "01:00" | "02:30" | "04:00"
    status: str         # "ok" | "lock" | "warn" | "open"
    is_locked: bool
    is_called_off: bool


class HudRRSlot(TypedDict):
    """Read-only restroom slot for the HUD RR section."""

    slot_key: str       # "RR 1+2", "RR 6", …
    mens_name: str      # "—" when open
    womens_name: str
    status: str         # "ok" | "open"


class HudAuxSlot(TypedDict):
    """Read-only aux slot for the HUD Auxiliary section."""

    slot_key: str       # "Z9 SR", "Admin", "Trash 1", …
    tm_name: str        # "—" when open
    status: str         # "ok" | "open"


class BreakSlot(TypedDict):
    """One wave cell within a break group (Phase 4d 3×3 model)."""

    wave_num: int       # 1 | 2 | 3 (wave within the group)
    start_time: str     # formatted "1:00am"
    end_time: str       # formatted "1:30am"
    tms: list[str]      # TM display names assigned to this wave
    status: str         # "upcoming" | "active" | "complete"


class BreakGroup(TypedDict):
    """One break group, containing 3 waves (Phase 4d 3×3 model)."""

    group_num: int         # 1 | 2 | 3
    tm_count: int          # total unique TMs in this group (across all waves)
    waves: list[BreakSlot] # always 3 entries (wave 1, 2, 3)


class ZoneCardData(TypedDict):
    """Rich zone card data for the Shift HUD zone grid (Phase 4d)."""

    zone_id: str
    zone_label: str        # short label: "Z1", "Z3", "Z9 SR"
    zone_area: str         # descriptive area name: "Slot Bank A"
    tm_name: str           # display name, or "—" when open
    tm_id: str
    group_num: int         # 1 | 2 | 3 — drives the break-group badge (0 = unset)
    current_task: str      # first task in display_tasks, or ""
    status: str            # "ok" | "lock" | "warn" | "open"
    is_locked: bool
    is_called_off: bool


class HudRosterChip(TypedDict):
    """One chip in the roster strip on the right panel."""

    name: str
    tm_id: str          # entity id — "" if unknown
    kind: str           # "g" grave | "p" pm_ol | "a" am_ol | "x" off
    zone: str           # assigned zone label, or "—"


class HudCarryOverItem(TypedDict):
    """One line in the ⚑ Carried-over panel."""

    text: str
    from_label: str     # "Lopez · 6:42A"


class HudTask(TypedDict):
    """One tonight-task row."""

    id: str
    title: str
    due_label: str      # "by 03:00" | "anytime" | "06:45"
    tag: str            # "BEO" | "TASK" | "WALK" | "MEET" etc.
    is_overdue: bool


class HudActivityEntry(TypedDict):
    """One row in the activity feed."""

    ts_display: str     # "01:42"
    who: str            # "Joy" | "Brian" | "System"
    what: str           # one-line description
    color_key: str      # "gold" | "ink2" | "green" | "red" | "ink3"
