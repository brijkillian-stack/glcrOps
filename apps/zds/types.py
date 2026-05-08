"""
Typed shapes for Reflex state vars.

Using TypedDict on `list[dict]` and `dict` state vars lets Reflex infer the
type of item access — e.g. `night["day_color"]` returns a `Var[str]`, so
f-strings, `+` concatenation, and equality checks work without manual
`.to(str)` casts inside `rx.foreach`.

These shapes mirror the dicts produced by `glcr_zone_app.database` (with a
few display fields layered on by `state.py`). Keep them in sync if a
database function adds, removes, or renames a field.
"""

from __future__ import annotations

from typing import TypedDict


class TaskItem(TypedDict):
    """One task in a slot's display_tasks list (Phase 4k.3).

    Upgrading from plain str so that annotation handlers have task UUIDs
    available for writes to `zds_annotations`. Custom tasks (from the
    custom_tasks JSONB column) and hardcoded fallbacks carry id="".
    """
    id:   str   # UUID from zone_tasks; "" for custom / hardcoded tasks
    name: str   # display label


class Week(TypedDict):
    """One row from the `weeks` table."""
    id: str
    week_ending: str
    label: str
    status: str  # "draft" | "published" | "archived"
    # Phase H — file in the schedules bucket this week is built from. Empty
    # string when not linked yet. Used by the index page card + ZDS engine.
    schedule_path: str
    # Phase R — pre-formatted "Fri May 1 – Thu May 7" range stamped by fetch_weeks
    date_range: str


class Night(TypedDict):
    """One row from the `nights` table, plus a `day_color` set in state.py."""
    id: str
    week_id: str
    night_date: str
    day_name: str
    day_num: int
    page_num: int
    in_rotation: int
    breaks_5: int
    breaks_9: int
    breaks_4: int
    day_color: str  # hex; injected in on_week_overview_load / on_day_load
    # Phase R — at-a-glance stats stamped by on_week_overview_load
    stat_filled: int
    stat_total: int
    stat_unfilled: int
    stat_locked: int
    stat_called_off: int
    # Phase D — night-level lock
    is_locked:  bool
    locked_by:  str
    locked_at:  str  # ISO timestamp string; "" when not locked


class Notice(TypedDict):
    """Phase E — per-slot notice surfaced via the NoticeDot affordance.

    Stored in the `notices` table; injected onto each ZoneSlot/RRSlot/AuxSlot
    by state._load_night. Fields are typed strings so Reflex Vars expose
    `.upper()`, string concat, etc. inside rx.foreach bodies — without the
    typed shape, compile fails with UntypedVarError on the second-level
    iteration inside _notice_dot.
    """
    id:         str
    type:       str   # "alert" | "info" | "training" | "meeting"
    text:       str
    created_by: str
    created_at: str   # ISO timestamp string


class ZoneSlot(TypedDict):
    """
    Generic slot row used for both zones and aux strip.
    Restroom slots use `RRSlot` because they merge mens + womens into one card.
    Shape matches `database.fetch_zone_assignments`.
    """
    id: str
    slot_type: str        # "zone" | "aux" (filtered before reaching state)
    slot_key: str
    rr_side: str          # "" for zones / aux
    is_filled: bool
    is_empty: bool
    sort_order: int
    # Group / sweeper / alert flags
    group_num: int
    has_group: bool
    has_alert: bool
    alert_target: str
    is_sweeper: bool
    sweeper_route: str
    is_crowded: bool
    is_extra_crowded: bool
    has_trainee: bool
    trainee_name: str
    # TM identity (joined from the `entities` table)
    tm_id: str
    tm_name: str
    tm_skill: int         # 0 when unset / unknown
    # Pre-computed display fields
    label: str
    color: str
    display_name: str
    name_color: str
    name_style: str
    name_size: str
    display_tasks: list[TaskItem]  # Phase 4k.3: {id, name} dicts; id="" for custom/hardcoded
    is_locked: bool            # position lock — protects TM from accidental clear
    has_duplicate: bool        # True when this TM is also assigned to another slot tonight
    # Phase J — call-off / scheduling warning
    # "ok"             → TM scheduled and present
    # "called_off"     → TM is in call_offs table for this night
    # "not_scheduled"  → TM is assigned but not in any schedule pool tonight
    # Empty string for unfilled slots.
    warning_status: str
    # Phase E — notices (injected in state._load_night from the notices table).
    # Typed via the Notice TypedDict above so rx.foreach inside _notice_dot
    # can resolve `n["type"].upper()` and similar string operations. A bare
    # `list` or even `list[dict]` (Var[Any] item) crashes compile with
    # UntypedVarError on second-level iteration.
    notices: list[Notice]


class RRSlot(TypedDict):
    """Restroom card — mens + womens slot data merged in `_load_night`."""
    slot_key: str
    label: str
    color: str
    has_alert: bool
    alert_target: str
    is_sweeper: bool
    sweeper_route: str
    mens_name: str
    mens_slot_id: str
    mens_tm_id: str            # raw tm_id (empty string when unfilled)
    mens_is_filled: bool
    mens_is_locked: bool
    mens_has_duplicate: bool
    mens_group: int            # break group (1/2/3); 0 = none
    womens_name: str
    womens_slot_id: str
    womens_tm_id: str
    womens_is_filled: bool
    womens_is_locked: bool
    womens_has_duplicate: bool
    womens_group: int          # break group (1/2/3); 0 = none
    display_tasks: list[TaskItem]  # Phase 4k.3: from mens slot, {id, name} dicts
    # Phase J — call-off / scheduling warning per side
    mens_warning_status: str   # "ok" | "called_off" | "not_scheduled" | ""
    womens_warning_status: str


class BreakRow(TypedDict):
    """One row from `break_assignments`, joined with the TM display name."""
    id: str
    group_num: int            # 1 | 2 | 3 — break group (Phase 4d)
    break_wave: int           # 1 | 2 | 3 — wave within the group
    sort_order: int
    slot_ref: str             # canonical key stored in DB (e.g. "Z1", "RR6 M")
    slot_label: str           # same as slot_ref (alias for display)
    slot_color: str           # hex badge color
    section: str              # "Zones" | "Restrooms" | "Auxiliary"
    show_section_header: bool  # True for first row of each section in a wave column
    is_wave_locked: bool       # wave survives engine re-runs when True
    tm_id: str
    tm_name: str


class OverlapRow(TypedDict):
    """One row from `overlap_assignments`, joined with the TM display name."""
    id: str
    overlap_window: str   # "pm" | "am"
    position: int
    is_filled: bool
    task: str
    tm_id: str
    tm_name: str


class TM(TypedDict):
    """A team member row used by the picker."""
    id: str
    display_name: str
    skill_score: int
    skill_str: str
    skill_color: str
    grave_pool: str
    eligibility: dict[str, bool]
    preferences: list[str]
    is_assigned: bool    # already placed in another slot this night
    assigned_to: str     # label of that slot, e.g. "Zone 3" (empty when not assigned)
    on_schedule: bool    # True if TM is in grave / PM OL / AM OL pool for this night
    schedule_pool: str   # "grave" | "pm_ol" | "am_ol" | "off"
    # Phase I — swap support
    assigned_slot_id: str  # zone_assignments.id of the source slot (for Swap action)
    assigned_locked: bool  # True if the source slot is locked (swap forbidden)
    # Phase J — call-off awareness
    is_called_off: bool  # True if TM is in the call_offs table for this night
    # Phase K.2 — recent placement history badge
    history_summary: str   # pre-rendered "Mon Z3 · Sun Z6 · Sat Z9 SR" string


class ChangeLogEntry(TypedDict):
    """One tracked mutation in the audit banner.

    Carries enough payload to undo the user's *intent*. (After undo, the
    engine re-runs and may re-shuffle dependent slots — this is intentional
    and matches how the original mutation worked.)
    """
    id: str               # uuid for keying in the foreach + undo lookup
    timestamp: str        # ISO-8601, used for "5 min ago"
    kind: str             # "assign" | "clear" | "lock_toggle" | "task_add" | "task_remove"
    night_id: str         # so we can ignore changes from other nights if user navigates
    slot_id: str          # the affected zone_assignments row
    target_label: str     # human-readable slot, e.g. "Zone 9", "RR 6 Mens", "MP 1"
    detail: str           # one-line summary, e.g. "Joy Smith → Zone 9 (was Unfilled)"
    icon: str             # lucide icon name for the row
    accent: str           # hex color tint for the icon
    # Undo / redo payload — kind-specific; unused fields default to "" / False.
    prev_tm_id: str       # for assign / clear / swap (TM that was at slot before)
    prev_lock: bool       # for lock_toggle (lock state before)
    task_text: str        # for task_add / task_remove
    undone: bool          # marked True after revert (banner can grey it out)
    # Phase K.4 — redo support
    new_tm_id: str        # for assign / swap (TM placed at the target slot)
    new_lock: bool        # for lock_toggle (the new lock state)
    source_slot_id: str   # for swap (the slot the TM came FROM; primary slot is `slot_id`)


# Default `Night` value used when `current_night` can't find a match.
# Matches every key in `Night` so item access never returns undefined.
EMPTY_NIGHT: Night = {
    "id": "",
    "week_id": "",
    "night_date": "",
    "day_name": "",
    "day_num": 0,
    "page_num": 0,
    "in_rotation": 0,
    "breaks_5": 0,
    "breaks_9": 0,
    "breaks_4": 0,
    "day_color": "#6b7280",
    "stat_filled": 0,
    "stat_total": 0,
    "stat_unfilled": 0,
    "stat_locked": 0,
    "stat_called_off": 0,
    # Phase D — night-level lock defaults
    "is_locked": False,
    "locked_by": "",
    "locked_at": "",
}


# Phase K.1 — Engine result modal payload.

class UnresolvedSlot(TypedDict):
    """One unresolved slot from the engine's audit JSON."""
    date: str
    zone_slot: str
    priority: int


class EngineResult(TypedDict):
    """Structured payload returned by ZdsState._do_zone_engine."""
    success: bool
    scope: str                     # "night" | "week"
    updated: int
    locked_skipped: int
    unresolved_cleared: int
    unresolved: list[UnresolvedSlot]
    week_ending: str
    error: str
    message: str


EMPTY_ENGINE_RESULT: EngineResult = {
    "success": False,
    "scope": "",
    "updated": 0,
    "locked_skipped": 0,
    "unresolved_cleared": 0,
    "unresolved": [],
    "week_ending": "",
    "error": "",
    "message": "",
}


# Phase N.2 — Week Schedule editor grid shapes.

class ScheduleCell(TypedDict):
    """One cell in the editor grid (TM × date)."""
    raw: str           # original xlsx cell value
    value: str         # effective value (override or raw)
    category: str      # "working" | "scheduled_off" | "pto" | "mdl"
                       # | "called_off" | "other" | "blank"
    overridden: bool


class ScheduleRow(TypedDict):
    """One row in the editor grid — a TM on a specific shift, with their
    seven cells (one per date in the week)."""
    name: str
    first: str
    last: str
    shift: str         # "days" | "swings" | "graves"
    cells: list[ScheduleCell]
