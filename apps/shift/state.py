"""
apps/shift/state.py — ShiftState for the Shift HUD (/shift).

Reads tonight's zone/rr/aux/break_rows from ZdsState (which already owns
the DB connection for ZDS) and tasks + activity from shared/db.py.

All DB access is synchronous (supabase-py).  State vars are JSON-serialisable.

Phase 3 ships read-only.  Write actions (call-out, kudos, BEO) land in the
thumb cluster and will be wired to capture() in a follow-on phase.
"""

from __future__ import annotations

import datetime
import traceback
from zoneinfo import ZoneInfo

import reflex as rx

from apps.zds.state import ZdsState
from shared.db import get_tonight_tasks, get_activity_feed, ensure_shift_log_event
from .types import (
    HudZoneSlot,
    HudRRSlot,
    HudAuxSlot,
    HudBreakWave,
    HudRosterChip,
    HudCarryOverItem,
    HudTask,
    HudActivityEntry,
)

_ET = ZoneInfo("America/Detroit")

_WAVE_TIMES = {1: "01:00", 2: "02:30", 3: "04:00"}
_WAVE_RANGES = {1: "01:00 – 01:30", 2: "02:30 – 03:00", 3: "04:00 – 04:30"}

# Category → short tag label for tonight tasks
_CAT_TAG = {
    "beo":      "BEO",
    "task":     "TASK",
    "walk":     "WALK",
    "meeting":  "MEET",
    "meet":     "MEET",
    "restock":  "TASK",
    "debrief":  "MEET",
}

# content_type / event_type → T2 color key for activity feed
_CT_COLOR = {
    "kudos":       "gold",
    "callout":     "red",
    "flag":        "red",
    "incident":    "red",
    "beo":         "blue",
    "floor_walk":  "blue",
    "huddle":      "blue",
    "observation": "ink2",
    "shift_recap": "ink3",
}


def _slot_status(slot: dict) -> str:
    if slot.get("is_locked"):
        return "lock"
    tm = (slot.get("display_name") or "").strip()
    if slot.get("is_called_off"):
        return "warn"
    if not tm:
        return "open"
    return "ok"


def _wave_state(wave_num: int) -> str:
    """Rough wave state based on current time (ET)."""
    now = datetime.datetime.now(tz=_ET)
    # Grave shift: starts 11 PM, waves at 01:00, 02:30, 04:00
    hour  = now.hour
    minute = now.minute
    minutes_since_midnight = hour * 60 + minute
    # Before 01:00 → W1 queued, W2/W3 queued
    wave_starts = {1: 60, 2: 150, 3: 240}    # minutes past midnight
    wave_ends   = {1: 90, 2: 180, 3: 270}
    start = wave_starts[wave_num]
    end   = wave_ends[wave_num]
    if minutes_since_midnight >= end:
        return "done"
    if minutes_since_midnight >= start:
        return "active"
    return "queue"


def _format_due(due_at: str | None) -> str:
    if not due_at:
        return "anytime"
    try:
        dt = datetime.datetime.fromisoformat(due_at.replace("Z", "+00:00")).astimezone(_ET)
        return dt.strftime("%-I:%M %p").lower()
    except Exception:
        return "anytime"


def _cat_tag(category: str | None) -> str:
    if not category:
        return "TASK"
    return _CAT_TAG.get(category.lower(), category.upper()[:4])


def _activity_color(content_type: str) -> str:
    return _CT_COLOR.get((content_type or "").lower(), "ink2")


def _now_approx_label() -> str:
    """Return a human-readable approx time label, e.g. '1:42am'."""
    now = datetime.datetime.now(tz=_ET)
    return now.strftime("%-I:%M%p").lower()


def _tonight_date_iso() -> str:
    """ISO date string for tonight's shift.

    Grave shift runs 11 PM → 7 AM. For the purpose of anchoring captures,
    we use 'today's date' as defined by the morning side of the shift:
    before 7 AM → use today's date (the shift is still running from last night);
    7 AM or later → shift hasn't started yet, use today's date as tomorrow's anchor.
    In practice: just use date.today() which is always correct for the log date.
    """
    return datetime.date.today().isoformat()


class ShiftState(rx.State):
    """State for the Shift HUD page."""

    # ── Zone / RR / Aux / Break (read from ZdsState on load) ─────────────────
    zone_slots: list[HudZoneSlot] = []
    rr_slots:   list[HudRRSlot]  = []
    aux_slots:  list[HudAuxSlot] = []
    break_waves: list[HudBreakWave] = []

    # ── Roster chips (derived from zone/rr/aux slots) ─────────────────────────
    roster_chips: list[HudRosterChip] = []

    # Counts for roster legend
    roster_grave_count: int = 0
    roster_pmol_count:  int = 0
    roster_amol_count:  int = 0
    roster_off_count:   int = 0

    # ── Deployment summary bar ────────────────────────────────────────────────
    deploy_filled: int = 0
    deploy_total:  int = 0
    deploy_locked: int = 0
    deploy_warn:   int = 0
    deploy_open:   int = 0
    deploy_ok:     int = 0

    # ── Carried-over items ────────────────────────────────────────────────────
    carry_over_items: list[HudCarryOverItem] = []

    # ── Tonight tasks (from shared/db.py) ────────────────────────────────────
    tasks: list[HudTask] = []

    # ── Activity feed (from shared/db.py) ─────────────────────────────────────
    activity: list[HudActivityEntry] = []

    # ── Header pills ──────────────────────────────────────────────────────────
    shift_date_label: str = ""   # "Wed · May 7 · Grave shift"
    shift_date_iso: str = ""     # "2026-05-07" — used by capture writes
    greeting: str = ""           # "Good evening, Brian."
    live_label: str = ""         # "01:42 in"
    carry_count: int = 0

    # ── Shift log event anchor ─────────────────────────────────────────────────
    # Created once per shift_date; all captures attach to this event_id.
    shift_log_event_id: str = ""

    # ── Entity lookup (display_name → entity id) ───────────────────────────────
    # Populated from ZdsState.tm_name_to_id on load; used by capture modals.
    roster_name_to_id: dict = {}

    # ── Loading ───────────────────────────────────────────────────────────────
    loading: bool = False

    @rx.event
    async def on_load(self):
        self.loading = True
        try:
            await self._build_header()
            # Anchor shift_log event idempotently on first load each night
            if self.shift_date_iso and not self.shift_log_event_id:
                try:
                    eid = ensure_shift_log_event(self.shift_date_iso)
                    if eid:
                        self.shift_log_event_id = eid
                except Exception:
                    print(f"[ShiftState.on_load] shift_log anchor error:\n{traceback.format_exc()}")
            await self._build_from_zds()
            await self._build_tasks()
            await self._build_activity()
        except Exception:
            print(f"[ShiftState.on_load] error:\n{traceback.format_exc()}")
        finally:
            self.loading = False

    @rx.event
    async def refresh(self):
        """Lightweight refresh: tasks + activity only (no ZDS re-read).
        Called after captures to update the right-panel feed."""
        try:
            await self._build_tasks()
            await self._build_activity()
        except Exception:
            print(f"[ShiftState.refresh] error:\n{traceback.format_exc()}")

    async def _build_header(self):
        now = datetime.datetime.now(tz=_ET)
        day_abbr = now.strftime("%a")
        month_abbr = now.strftime("%b %-d")
        self.shift_date_label = f"{day_abbr} · {month_abbr} · Grave shift"
        self.shift_date_iso = _tonight_date_iso()
        hour = now.hour
        if 5 <= hour < 12:
            greeting_word = "Good morning"
        elif 12 <= hour < 17:
            greeting_word = "Good afternoon"
        else:
            greeting_word = "Good evening"
        self.greeting = f"{greeting_word}, Brian."

        # Minutes into shift (shift starts 11 PM = 23:00)
        shift_start = now.replace(hour=23, minute=0, second=0, microsecond=0)
        # If we're before 11 PM, shift started yesterday
        if now < shift_start:
            shift_start -= datetime.timedelta(days=1)
        elapsed = int((now - shift_start).total_seconds() // 60)
        h, m = divmod(elapsed, 60)
        if h > 0:
            self.live_label = f"{h:02d}:{m:02d} in"
        else:
            self.live_label = f"{m}m in"

    async def _build_from_zds(self):
        """Pull tonight's zone/rr/aux/break data from ZdsState."""
        zds = await self.get_state(ZdsState)
        # Copy the name→entity_id lookup so capture modals can resolve entity ids
        self.roster_name_to_id = dict(zds.tm_name_to_id or {})

        # ── Zone slots ────────────────────────────────────────────────────────
        zones: list[HudZoneSlot] = []
        for s in zds.zone_slots:
            tm = (s.get("display_name") or "").strip()
            st = _slot_status(s)
            wave_num = s.get("wave_num") or 1
            zones.append(HudZoneSlot(
                slot_key=s.get("slot_key", "?"),
                tm_name=tm or "—",
                position=s.get("slot_label") or s.get("position") or "",
                wave=wave_num,
                wave_time=_WAVE_TIMES.get(wave_num, "—"),
                status=st,
                is_locked=bool(s.get("is_locked")),
                is_called_off=bool(s.get("is_called_off")),
            ))
        self.zone_slots = zones

        # ── RR slots ──────────────────────────────────────────────────────────
        rrs: list[HudRRSlot] = []
        for s in zds.rr_slots:
            st = "open" if not (s.get("mens_name") or s.get("womens_name")) else "ok"
            rrs.append(HudRRSlot(
                slot_key=s.get("slot_key", ""),
                mens_name=(s.get("mens_name") or "").strip() or "—",
                womens_name=(s.get("womens_name") or "").strip() or "—",
                status=st,
            ))
        self.rr_slots = rrs

        # ── Aux slots ─────────────────────────────────────────────────────────
        auxs: list[HudAuxSlot] = []
        for s in zds.aux_slots:
            tm = (s.get("display_name") or "").strip()
            auxs.append(HudAuxSlot(
                slot_key=s.get("slot_key", ""),
                tm_name=tm or "—",
                status="ok" if tm else "open",
            ))
        self.aux_slots = auxs

        # ── Break waves ───────────────────────────────────────────────────────
        # ZdsState.break_rows is a list of BreakRow dicts with slot_key / names per wave
        waves: list[HudBreakWave] = []
        wave_names: dict[int, list[str]] = {1: [], 2: [], 3: []}
        for row in zds.break_rows:
            wave_num = int(row.get("wave_num") or 0)
            if wave_num in wave_names:
                nm = (row.get("display_name") or row.get("tm_name") or "").strip()
                if nm:
                    wave_names[wave_num].append(nm)

        for wn in [1, 2, 3]:
            names = wave_names[wn]
            st = _wave_state(wn)
            on_cnt = len(names) if st == "active" else (len(names) if st == "done" else 0)
            waves.append(HudBreakWave(
                wave_num=wn,
                wave_label=f"W{wn}",
                time_range=_WAVE_RANGES[wn],
                state=st,
                on_count=on_cnt,
                total_count=len(names),
                names=names,
            ))
        self.break_waves = waves

        # ── Deployment summary ────────────────────────────────────────────────
        statuses = [z["status"] for z in zones]
        self.deploy_total  = len(zones)
        self.deploy_filled = sum(1 for s in statuses if s != "open")
        self.deploy_locked = statuses.count("lock")
        self.deploy_warn   = statuses.count("warn")
        self.deploy_open   = statuses.count("open")
        self.deploy_ok     = statuses.count("ok")

        # ── Roster chips (from zone assignments only for simplicity) ──────────
        chips: list[HudRosterChip] = []
        called_off_names: set[str] = set(zds.night_called_off or [])
        grave_pool: set[str] = set(zds.night_grave_pool or [])
        pmol_pool:  set[str] = set(zds.night_pm_ol_pool or [])
        amol_pool:  set[str] = set(zds.night_am_ol_pool or [])

        name_to_id = dict(zds.tm_name_to_id or {})
        seen: set[str] = set()
        for z in zones:
            nm = z["tm_name"]
            if nm == "—" or nm in seen:
                continue
            seen.add(nm)
            if nm in called_off_names:
                kind = "x"
            elif nm in pmol_pool:
                kind = "p"
            elif nm in amol_pool:
                kind = "a"
            else:
                kind = "g"
            chips.append(HudRosterChip(
                name=nm, tm_id=name_to_id.get(nm, ""),
                kind=kind, zone=z["slot_key"],
            ))

        # Add called-off TMs not assigned anywhere
        for nm in called_off_names:
            if nm not in seen:
                chips.append(HudRosterChip(
                    name=nm, tm_id=name_to_id.get(nm, ""),
                    kind="x", zone="—",
                ))
                seen.add(nm)

        self.roster_chips = chips
        self.roster_grave_count = sum(1 for c in chips if c["kind"] == "g")
        self.roster_pmol_count  = sum(1 for c in chips if c["kind"] == "p")
        self.roster_amol_count  = sum(1 for c in chips if c["kind"] == "a")
        self.roster_off_count   = sum(1 for c in chips if c["kind"] == "x")

    async def _build_tasks(self):
        raw = get_tonight_tasks(limit=6)
        tasks: list[HudTask] = []
        for t in raw:
            tasks.append(HudTask(
                id=str(t.get("id", "")),
                title=t.get("title", ""),
                due_label=_format_due(t.get("due_at")),
                tag=_cat_tag(t.get("category")),
                is_overdue=bool(t.get("is_overdue")),
            ))
        self.tasks = tasks

        # Carry-over = overdue tasks surfaced as ⚑ items
        carry: list[HudCarryOverItem] = []
        for t in tasks:
            if t["is_overdue"]:
                carry.append(HudCarryOverItem(
                    text=t["title"],
                    from_label="overdue",
                ))
        self.carry_over_items = carry
        self.carry_count = len(carry)

    async def _build_activity(self):
        raw = get_activity_feed(since_days=2, limit=8)
        entries: list[HudActivityEntry] = []
        for r in raw:
            meta = r.get("metadata") or {}
            who = meta.get("author") or meta.get("who") or r.get("who") or "Brian"
            entries.append(HudActivityEntry(
                ts_display=r.get("timestamp_display", ""),
                who=str(who)[:12],
                what=r.get("text", "")[:80],
                color_key=_activity_color(r.get("content_type", "")),
            ))
        self.activity = entries
