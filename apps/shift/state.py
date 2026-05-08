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
from apps.zds.database import ENGINE_SLOT_LABEL as _ENGINE_SLOT_LABEL
from shared.db import get_tonight_tasks, get_activity_feed, ensure_shift_log_event
from .utils import fmt_time
from .types import (
    HudZoneSlot,
    HudRRSlot,
    HudAuxSlot,
    BreakSlot,
    BreakGroup,
    ZoneCardData,
    HudRosterChip,
    HudCarryOverItem,
    HudTask,
    HudActivityEntry,
)

_ET = ZoneInfo("America/Detroit")

# Break wave base times (minutes past midnight for wave 1, 2, 3)
# Group offset = (group_num - 1) * 30 minutes; each wave window is 30 min.
#   Group 1, Wave 1: 1:00am–1:30am   Group 1, Wave 2: 3:00am–3:30am  ...
#   Group 2, Wave 1: 1:30am–2:00am   Group 2, Wave 2: 3:30am–4:00am  ...
#   Group 3, Wave 1: 2:00am–2:30am   Group 3, Wave 2: 4:00am–4:30am  ...
_WAVE_BASE_MINS = {1: 60, 2: 180, 3: 300}   # 1:00am, 3:00am, 5:00am

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


def _break_slot_times(group_num: int, wave_num: int) -> tuple[str, str]:
    """Return (start_time_str, end_time_str) for a break slot, e.g. ('1:00am', '1:30am')."""
    base_min   = _WAVE_BASE_MINS[wave_num]
    offset     = (group_num - 1) * 30
    start_min  = base_min + offset
    end_min    = start_min + 30
    sh, sm = divmod(start_min, 60)
    eh, em = divmod(end_min, 60)
    return fmt_time(datetime.time(sh, sm)), fmt_time(datetime.time(eh, em))


def _break_slot_status(group_num: int, wave_num: int) -> str:
    """Derive break slot status from current ET time vs the slot's window."""
    base_min  = _WAVE_BASE_MINS[wave_num]
    offset    = (group_num - 1) * 30
    start_min = base_min + offset
    end_min   = start_min + 30
    now       = datetime.datetime.now(tz=_ET)
    now_min   = now.hour * 60 + now.minute
    if now_min >= end_min:
        return "complete"
    if now_min >= start_min:
        return "active"
    return "upcoming"


def _format_due(due_at: str | None) -> str:
    if not due_at:
        return "anytime"
    try:
        dt = datetime.datetime.fromisoformat(due_at.replace("Z", "+00:00")).astimezone(_ET)
        return fmt_time(dt)
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
    return fmt_time(datetime.datetime.now(tz=_ET))


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
    zone_slots: list[HudZoneSlot] = []    # kept for deploy stats + roster chips
    zone_cards: list[ZoneCardData] = []   # Phase 4d: rich zone cards for HUD grid
    rr_slots:   list[HudRRSlot]  = []
    aux_slots:  list[HudAuxSlot] = []
    break_groups: list[BreakGroup] = []   # Phase 4d: 3 groups × 3 waves = 9 cells

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

    # ── Phase 4i.5 — Zone Tasks floating drawer ───────────────────────────────
    zone_tasks_drawer_open: bool = False
    zone_task_rows: list[dict] = []    # [{zone_slot, task_name, category, tm_name, assigned_by}]

    def open_zone_tasks_drawer(self):
        self.zone_tasks_drawer_open = True
        return ShiftState._load_zone_tasks()

    def close_zone_tasks_drawer(self):
        self.zone_tasks_drawer_open = False

    async def _load_zone_tasks(self):
        """Load zone_task_assignments for tonight's night via ZdsState.current_night_id."""
        try:
            from apps.zds.state import ZdsState
            zds = await self.get_state(ZdsState)
            night_id = zds.current_night_id
            if not night_id:
                self.zone_task_rows = []
                return
            from shared.db import get_client
            sb = get_client()
            res = (
                sb.table("zone_task_assignments")
                .select(
                    "zone_slot,assigned_by,"
                    "zone_tasks(name,category),"
                    "tm_profiles(display_name)"
                )
                .eq("night_id", night_id)
                .order("zone_slot")
                .execute()
            )
            rows = []
            for r in (res.data or []):
                task = r.get("zone_tasks") or {}
                tm   = r.get("tm_profiles") or {}
                rows.append({
                    "zone_slot":   r.get("zone_slot") or "—",
                    "task_name":   task.get("name", ""),
                    "category":    task.get("category", "zone"),
                    "tm_name":     tm.get("display_name") or "Unassigned",
                    "assigned_by": r.get("assigned_by", "engine"),
                })
            self.zone_task_rows = rows
        except Exception as e:
            print(f"[ShiftState._load_zone_tasks] error: {e}")
            self.zone_task_rows = []

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
            self.live_label = f"{h}h {m}m in"
        else:
            self.live_label = f"{m}m in"

    async def _build_from_zds(self):
        """Pull tonight's zone/rr/aux/break data from ZdsState.

        ZdsState's slot lists (zone_slots / rr_slots / aux_slots) are only
        populated by its own loaders, which fire on /zds/* routes that have
        week_id + night_id URL params. /shift has neither, so we have to
        explicitly resolve tonight's night and ask ZdsState to load it
        before reading the slot data. Without this bootstrap step the HUD
        renders 0/0 because zds.zone_slots is the empty default.
        """
        zds = await self.get_state(ZdsState)

        # ── Bootstrap: ensure ZdsState has tonight's data loaded ─────────────
        # Resolve tonight's night_id by date-range query on the nights table.
        # We pick the night whose night_date is the closest match to today —
        # accounting for whether Brian's data convention indexes the shift
        # by start-date or end-date (different at midnight). Two candidates:
        # today and tomorrow; pick whichever has a row.
        from shared.db import get_client as _get_client
        from apps.zds import database as _zds_db
        try:
            sb = _get_client()
            today = datetime.date.today().isoformat()
            tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
            yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
            # Try in order of likelihood: today (shift-start convention),
            # tomorrow (shift-end convention), yesterday (mid-shift before 7am).
            night_id = ""
            week_id = ""
            for candidate in (today, tomorrow, yesterday):
                row = (
                    sb.table("nights")
                    .select("id, week_id")
                    .eq("night_date", candidate)
                    .limit(1)
                    .execute()
                    .data
                )
                if row:
                    night_id = row[0]["id"]
                    week_id  = row[0]["week_id"]
                    break

            if night_id and week_id:
                # If ZdsState isn't already focused on tonight, focus it
                # and load. _load_night needs self.nights populated first.
                if zds.current_week_id != week_id:
                    zds.current_week_id = week_id
                    zds.nights = _zds_db.fetch_nights(week_id)
                if zds.current_night_id != night_id:
                    zds._load_night(night_id)
        except Exception:
            print(f"[ShiftState._build_from_zds] bootstrap error:\n{traceback.format_exc()}")

        # Copy the name→entity_id lookup so capture modals can resolve entity ids
        self.roster_name_to_id = dict(zds.tm_name_to_id or {})

        # ── Zone slots + Zone cards ───────────────────────────────────────────
        zones: list[HudZoneSlot] = []
        cards: list[ZoneCardData] = []
        for s in zds.zone_slots:
            tm   = (s.get("display_name") or "").strip()
            sk   = s.get("slot_key", "")
            st   = _slot_status(s)
            gn   = int(s.get("group_num") or 0)
            tasks = list(s.get("display_tasks") or [])
            # Short zone label ("Z1") and area name ("Slot Bank A")
            zone_label = _ENGINE_SLOT_LABEL.get(sk, sk)
            zone_area  = s.get("label") or ""
            is_co = s.get("warning_status") == "called_off"
            # HudZoneSlot kept for deploy stats + roster chips
            zones.append(HudZoneSlot(
                slot_key=zone_label,          # use short label ("Z1") for roster chip zone
                tm_name=tm or "—",
                position=zone_area,
                wave=gn,                      # repurpose wave field as group_num
                wave_time="",
                status=st,
                is_locked=bool(s.get("is_locked")),
                is_called_off=is_co,
            ))
            # ZoneCardData — used by the HUD zone grid
            cards.append(ZoneCardData(
                zone_id=s.get("id") or "",
                zone_label=zone_label,
                zone_area=zone_area,
                tm_name=tm or "—",
                tm_id=s.get("tm_id") or "",
                group_num=gn,
                current_task=tasks[0] if tasks else "",
                status=st,
                is_locked=bool(s.get("is_locked")),
                is_called_off=is_co,
            ))
        self.zone_slots = zones
        self.zone_cards = cards

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

        # ── Break groups (3 groups × 3 waves = 9 slots) ──────────────────────
        # build group_tm_map: {group_num: {wave_num: [tm_names]}}
        group_tm_map: dict[int, dict[int, list[str]]] = {
            1: {1: [], 2: [], 3: []},
            2: {1: [], 2: [], 3: []},
            3: {1: [], 2: [], 3: []},
        }
        for row in zds.break_rows:
            gn = int(row.get("group_num") or 1)
            wn = int(row.get("break_wave") or 1)
            if gn in group_tm_map and wn in group_tm_map.get(gn, {}):
                nm = (row.get("tm_name") or "").strip()
                if nm:
                    group_tm_map[gn][wn].append(nm)

        grps: list[BreakGroup] = []
        for gn in [1, 2, 3]:
            all_tms: set[str] = set()
            wave_slots: list[BreakSlot] = []
            for wn in [1, 2, 3]:
                tms = group_tm_map[gn][wn]
                all_tms.update(tms)
                st_str, et_str = _break_slot_times(gn, wn)
                status = _break_slot_status(gn, wn)
                wave_slots.append(BreakSlot(
                    wave_num=wn,
                    start_time=st_str,
                    end_time=et_str,
                    tms=list(tms),
                    status=status,
                ))
            grps.append(BreakGroup(
                group_num=gn,
                tm_count=len(all_tms),
                waves=wave_slots,
            ))
        self.break_groups = grps

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
