"""
App-wide Reflex state.
All DB calls are synchronous (supabase-py sync client).
State vars must be JSON-serializable (dicts / lists / str / int / bool).
"""

from __future__ import annotations
import datetime
import uuid
from pathlib import Path
from typing import Optional

import reflex as rx

from . import database
from .database import ENGINE_SLOT_LABEL
from .styles import BG_ZONE, BG_RR_M, BG_RR_W, BG_AUX
from .types import (
    EMPTY_NIGHT,
    EMPTY_ENGINE_RESULT,
    BreakRow,
    ChangeLogEntry,
    EngineResult,
    Night,
    OverlapRow,
    RRSlot,
    TM,
    Week,
    ZoneSlot,
)

# Print-cache resolution:
#   - Dev (`reflex run --env dev`): Vite serves from .web/public/, so we write
#     there and the URL /print_cache/<file> hits Vite.
#   - Prod / Render (Caddy + static export): Caddy serves from .web/build/client/,
#     so we write the print HTML there instead. Same URL path, different dir.
# state.py lives at apps/zds/state.py → up 3 to reach project root.
_PROJ_ROOT = Path(__file__).parent.parent.parent
_PROD_STATIC = _PROJ_ROOT / ".web" / "build" / "client"
_PRINT_CACHE = (
    _PROD_STATIC / "print_cache"
    if _PROD_STATIC.exists()
    else _PROJ_ROOT / ".web" / "public" / "print_cache"
)


def _enrich_nights(nights: list[dict]) -> list[dict]:
    """Override day_name with the actual calendar weekday from night_date and add day_color.

    The DB stores day_name as the night the shift *starts* (11PM), but night_date
    is the morning the shift *ends* (7AM) — one day later. We show the calendar
    day that matches the date so labels and dates agree in the UI and print output.
    """
    for n in nights:
        date_str = n.get("night_date", "")
        if date_str:
            try:
                actual_day = datetime.date.fromisoformat(date_str).strftime("%A")
            except ValueError:
                actual_day = n.get("day_name", "")
        else:
            actual_day = n.get("day_name", "")
        n["day_name"]  = actual_day
        n["day_color"] = _DAY_COLORS.get(actual_day, "#6b7280")
    return nights


_DAY_COLORS: dict = {
    "Friday":    "#C13A14",
    "Saturday":  "#0065bf",
    "Sunday":    "#6A1B85",
    "Monday":    "#2E7D32",
    "Tuesday":   "#B89708",
    "Wednesday": "#B7679A",
    "Thursday":  "#313845",
}


def _mark_section_headers(rows: list[dict]) -> list[dict]:
    """Add show_section_header=True to the first row of each section within a wave column."""
    prev = ""
    result = []
    for row in rows:
        r = dict(row)
        sec = r.get("section", "")
        r["show_section_header"] = sec != prev
        prev = sec
        result.append(r)
    return result


class ZdsState(rx.State):
    # ── Week list (index page) ────────────────────────────────────────────────
    weeks: list[Week] = []

    # ── Current week ─────────────────────────────────────────────────────────
    current_week_id: str = ""
    nights: list[Night] = []

    # ── Current night ─────────────────────────────────────────────────────────
    current_night_id: str = ""
    zone_slots:     list[ZoneSlot] = []   # slot_type == 'zone'
    rr_slots:       list[RRSlot]   = []   # slot_type == 'rr' (mens+womens merged)
    aux_slots:      list[ZoneSlot] = []   # slot_type == 'aux'
    break_rows:     list[BreakRow]   = []
    overlap_rows:   list[OverlapRow] = []

    # ── View toggle (deployment / break sheet / schedule) ────────────────────
    show_break_sheet: bool = False
    show_schedule:    bool = False
    active_tab:       str  = "deployment"  # "deployment" | "break" | "schedule"

    # ── Schedule pools (keyed by night_date ISO string) ───────────────────────
    # Raw pool data: {date_str: {"grave": [...], "pm_ol": [...], "am_ol": [...]}}
    schedule_pools:     dict = {}
    schedule_file_name: str  = ""
    # Pre-extracted pools for the CURRENTLY open night (set by _load_night)
    night_grave_pool: list[str] = []
    night_pm_ol_pool: list[str] = []
    night_am_ol_pool: list[str] = []

    # ── Call-offs for the CURRENTLY open night (Phase J) ──────────────────────
    # Display names of TMs marked as called off for this night. Drives:
    #   - Schedule tab strikethrough
    #   - Slot warning indicator on the deployment grid
    night_called_off: list[str] = []

    # display_name → tm_id lookup (populated alongside schedule pools).
    # The Schedule tab UI shows names from the parsed xlsx, but the call_offs
    # table is keyed by tm_id, so we need this bridge.
    tm_name_to_id: dict = {}

    # ── Engine result dialog (Phase K.1) ──────────────────────────────────────
    # Modal that pops up after Run Engine / Set Break Waves with a structured
    # summary of what changed.
    engine_result_open: bool = False
    engine_result: EngineResult = EMPTY_ENGINE_RESULT

    # ── TM Picker ─────────────────────────────────────────────────────────────
    show_picker:     bool = False
    picker_slot_id:  str = ""
    picker_slot_key: str = ""
    picker_rr_side:  str = ""
    picker_label:    str = ""
    eligible_tms:    list[TM] = []
    tm_search:       str = ""

    # ── Week overview ─────────────────────────────────────────────────────────
    week_info: Week = Week(id="", week_ending="", label="", status="")

    # ── New week modal ────────────────────────────────────────────────────────
    show_new_week:   bool = False
    new_week_ending: str = ""
    new_week_label:  str = ""

    # ── Unlinked schedules (Phase H) ──────────────────────────────────────────
    # Schedules in Storage that don't yet have a Week record (or whose Week
    # has no schedule_path linked yet). One-click "Create Zone Sheet" turns
    # them into a real week + 7 nights.
    unlinked_schedules: list[dict] = []

    # ── Task inline edit ──────────────────────────────────────────────────────
    task_edit_slot_id: str = ""
    task_edit_text:    str = ""

    # ── Loading / error ───────────────────────────────────────────────────────
    loading: bool = False
    error:   str = ""

    # ── Audit banner (tracks user-driven mutations for the session) ───────────
    # Newest-first; capped at 100 entries via _log_change.
    change_log:      list[ChangeLogEntry] = []
    banner_expanded: bool = False

    def set_error(self, msg: str):
        self.error = msg

    # =========================================================================
    # Computed vars
    # =========================================================================

    @rx.var
    def current_night(self) -> Night:
        for n in self.nights:
            if n["id"] == self.current_night_id:
                return n
        return EMPTY_NIGHT

    @rx.var
    def change_count(self) -> int:
        """Count of un-undone changes for the current night."""
        return sum(
            1 for c in self.change_log
            if not c["undone"] and c["night_id"] == self.current_night_id
        )

    @rx.var
    def has_changes(self) -> bool:
        return self.change_count > 0

    @rx.var
    def visible_changes(self) -> list[ChangeLogEntry]:
        """Changes for the current night, newest-first (already stored newest-first)."""
        return [c for c in self.change_log if c["night_id"] == self.current_night_id]

    @rx.var
    def filtered_tms(self) -> list[TM]:
        q = self.tm_search.strip().lower()
        if not q:
            return self.eligible_tms
        return [t for t in self.eligible_tms if q in t["display_name"].lower()]

    @rx.var
    def break_wave_1(self) -> list[BreakRow]:
        return _mark_section_headers(
            [r for r in self.break_rows if r["break_wave"] == 1]
        )

    @rx.var
    def break_wave_2(self) -> list[BreakRow]:
        return _mark_section_headers(
            [r for r in self.break_rows if r["break_wave"] == 2]
        )

    @rx.var
    def break_wave_3(self) -> list[BreakRow]:
        return _mark_section_headers(
            [r for r in self.break_rows if r["break_wave"] == 3]
        )

    @rx.var
    def schedule_loaded(self) -> bool:
        """True when schedule pool data has been parsed."""
        return bool(self.schedule_pools)

    @rx.var
    def schedule_file_label(self) -> str:
        """Filename for display, or a fallback prompt."""
        return self.schedule_file_name or "No schedule loaded"

    @rx.var
    def pm_overlaps(self) -> list[OverlapRow]:
        return [r for r in self.overlap_rows if r["overlap_window"] == "pm"]

    @rx.var
    def am_overlaps(self) -> list[OverlapRow]:
        return [r for r in self.overlap_rows if r["overlap_window"] == "am"]

    @rx.var
    def week_label(self) -> str:
        return (self.week_info.get("label")
                or self.week_info.get("week_ending")
                or "Week Overview")

    @rx.var
    def week_overview_url(self) -> str:
        return f"/zds/week/{self.current_week_id}"

    # =========================================================================
    # Week list
    # =========================================================================

    def load_weeks(self):
        self.loading = True
        self.error = ""
        try:
            self.weeks = database.fetch_weeks()
            # Phase H — also surface schedules that don't have a Zone Sheet yet
            try:
                self.unlinked_schedules = database.list_unlinked_schedules()
            except Exception as ex:
                # Storage may be unreachable in local dev — non-fatal
                print(f"[load_weeks] list_unlinked_schedules: {ex}")
                self.unlinked_schedules = []
        except Exception as e:
            self.error = str(e)
        finally:
            self.loading = False

    def create_week_from_schedule(self, filename: str):
        """Phase H — given a schedule xlsx in Storage, create a Week + 7 Nights
        for it and navigate to the new week's overview."""
        if not filename:
            return
        self.loading = True
        self.error = ""
        try:
            # Find the matching unlinked entry to grab its parsed dates.
            entry = next(
                (u for u in self.unlinked_schedules if u["filename"] == filename),
                None,
            )
            if not entry:
                self.error = f"Schedule {filename} not in unlinked list — refresh and retry."
                self.loading = False
                return

            # If the entry already has a matching_week (existing week with no
            # schedule_path), just link them. Otherwise create a new week.
            if entry.get("matching_week"):
                existing_week_id = entry["matching_week"]["id"]
                ok = database.update_week_schedule_path(existing_week_id, filename)
                if not ok:
                    self.error = "Failed to link schedule to existing week."
                    self.loading = False
                    return
                self.unlinked_schedules = database.list_unlinked_schedules()
                self.weeks = database.fetch_weeks()
                self.loading = False
                return rx.redirect(f"/zds/week/{existing_week_id}")

            # No existing week — create one.
            week = database.create_week_with_nights(
                week_ending=entry["week_ending"],
                dates=entry["dates"],
                schedule_path=filename,
                label=f"Week ending {entry['week_ending']}",
            )
            new_week_id = week.get("id", "")
            if not new_week_id:
                self.error = "Failed to create week."
                self.loading = False
                return
            # Refresh local state
            self.unlinked_schedules = database.list_unlinked_schedules()
            self.weeks = database.fetch_weeks()
            self.loading = False
            return rx.redirect(f"/zds/week/{new_week_id}")
        except Exception as e:
            self.error = str(e)
            self.loading = False

    def open_new_week_modal(self):
        self.show_new_week = True

    def close_new_week_modal(self):
        self.show_new_week = False
        self.new_week_ending = ""
        self.new_week_label = ""

    def set_new_week_ending(self, val: str):
        self.new_week_ending = val
        # Auto-generate label from date
        if val:
            self.new_week_label = f"Week of {val}"

    def set_new_week_label(self, val: str):
        self.new_week_label = val

    def create_week(self):
        if not self.new_week_ending:
            return
        try:
            database.create_week(self.new_week_ending, self.new_week_label)
            self.close_new_week_modal()
            self.load_weeks()
        except Exception as e:
            self.error = str(e)

    def update_week_status(self, week_id: str, status: str):
        try:
            database.update_week_status(week_id, status)
            self.load_weeks()
        except Exception as e:
            self.error = str(e)

    # =========================================================================
    # Navigation / night loading
    # =========================================================================

    def open_week(self, week_id: str):
        """From the index — navigate to the week overview."""
        self.current_week_id = week_id
        return rx.redirect(f"/zds/week/{week_id}")

    def on_week_overview_load(self):
        """Called on_mount for /week/[week_id] (week overview page)."""
        week_id = self.router.page.params.get("week_id", "")
        if not week_id:
            return
        if week_id != self.current_week_id:
            self.current_week_id = week_id
        self.week_info = database.fetch_week(week_id)
        self.nights = _enrich_nights(database.fetch_nights(week_id))
        self._reload_schedule()

    def on_day_load(self):
        """Called on_mount for /week/[week_id]/day/[night_id] (deployment editor)."""
        week_id  = self.router.page.params.get("week_id", "")
        night_id = self.router.page.params.get("night_id", "")
        if not week_id or not night_id:
            return
        if week_id != self.current_week_id:
            self.current_week_id = week_id
            self.week_info = database.fetch_week(week_id)
            self.nights = _enrich_nights(database.fetch_nights(week_id))
            self._reload_schedule()
        elif not self.schedule_pools:
            self._reload_schedule()
        if night_id != self.current_night_id:
            self._load_night(night_id)

    # =========================================================================
    # Schedule helpers
    # =========================================================================

    def _update_night_pools(self):
        """Extract the current night's schedule pools from schedule_pools into flat lists."""
        night_date = ""
        for n in self.nights:
            if n["id"] == self.current_night_id:
                night_date = n.get("night_date", "")
                break
        if not night_date or not self.schedule_pools:
            self.night_grave_pool = []
            self.night_pm_ol_pool = []
            self.night_am_ol_pool = []
            return
        day = self.schedule_pools.get(night_date, {})
        self.night_grave_pool = list(day.get("grave", []))
        self.night_pm_ol_pool = list(day.get("pm_ol", []))
        self.night_am_ol_pool = list(day.get("am_ol", []))

    def _reload_schedule(self):
        """Load/refresh schedule pool data from the latest schedule Excel file."""
        from . import schedule_parser
        try:
            entities = database.fetch_all_tms()
            pools = schedule_parser.parse_daily_pools(entities)
            self.schedule_pools = pools
            path = schedule_parser.get_latest_schedule_path()
            self.schedule_file_name = path.name if path else ""
            # Phase J — display_name → tm_id lookup so the Schedule tab can
            # call mark_called_off / unmark_called_off with just a name.
            self.tm_name_to_id = {
                e.get("display_name", ""): e["id"]
                for e in entities
                if e.get("display_name") and e.get("id")
            }
            if self.current_night_id:
                self._update_night_pools()
        except Exception as e:
            self.error = str(e)

    async def handle_schedule_upload(self, files: list[rx.UploadFile]):
        """
        Accept a dropped/selected schedule .xlsx, persist to BOTH the local
        Inputs/ dir (for immediate parser reload) AND Supabase Storage (so
        the schedule survives container restarts on Render), then refresh
        the pool data.

        Phase H: also auto-link the new file to an existing Week record if
        one already exists for the same week_ending and has no schedule_path.
        And refresh the unlinked-schedules list so the index page picks up
        any new "creatable" entries.
        """
        from . import schedule_parser
        from shared import storage
        if not files:
            return
        upload_dir = schedule_parser.SCHEDULE_DIR
        upload_dir.mkdir(parents=True, exist_ok=True)
        for file in files:
            upload_data = await file.read()
            # 1. Local copy — used immediately by the parser below.
            dest = upload_dir / file.filename
            dest.write_bytes(upload_data)
            # 2. Persist to Supabase Storage — survives container restarts.
            try:
                storage.upload_schedule(file.filename, upload_data)
            except Exception as exc:
                # Don't fail the UI on Storage error — just log and surface.
                self.error = f"Saved locally; Storage sync failed: {exc}"

            # 3. Phase H — auto-link to a matching week if there's an unlinked one.
            try:
                peek = schedule_parser.peek_schedule_dates(upload_data)
                if peek:
                    we = peek["week_ending"]
                    for w in database.fetch_weeks():
                        if w["week_ending"] == we and not w.get("schedule_path"):
                            database.update_week_schedule_path(w["id"], file.filename)
                            break
            except Exception as exc:
                print(f"[upload] auto-link failed: {exc}")

        self._reload_schedule()
        # Phase H — refresh the index page's unlinked + week lists
        try:
            self.unlinked_schedules = database.list_unlinked_schedules()
            self.weeks = database.fetch_weeks()
        except Exception:
            pass

    def select_night(self, night_id: str):
        """Navigate to a specific night's deployment editor."""
        self.show_break_sheet = False
        return rx.redirect(f"/zds/week/{self.current_week_id}/day/{night_id}")

    # =========================================================================
    # Print generation
    # =========================================================================

    def open_print_night(self, night_id: str):
        """Generate and open a 2-page print view for a specific night (week overview cards)."""
        _PRINT_CACHE.mkdir(parents=True, exist_ok=True)
        from .print_renderer import render_night_html
        try:
            html  = render_night_html(night_id)
            fname = f"night_{night_id}.html"
            (_PRINT_CACHE / fname).write_text(html, encoding="utf-8")
            url = f"/print_cache/{fname}"
            return rx.call_script(f"window.open('{url}', '_blank')")
        except Exception as e:
            self.error = f"Print error: {e}"

    def open_print_current_night(self):
        """Generate and open a 2-page print view for the currently-loaded night."""
        _PRINT_CACHE.mkdir(parents=True, exist_ok=True)
        from .print_renderer import render_night_html
        try:
            html  = render_night_html(self.current_night_id)
            fname = f"night_{self.current_night_id}.html"
            (_PRINT_CACHE / fname).write_text(html, encoding="utf-8")
            url = f"/print_cache/{fname}"
            return rx.call_script(f"window.open('{url}', '_blank')")
        except Exception as e:
            self.error = f"Print error: {e}"

    def open_print_current_week(self):
        """Generate and open a 14-page print view for the current week."""
        _PRINT_CACHE.mkdir(parents=True, exist_ok=True)
        from .print_renderer import render_week_html
        try:
            html  = render_week_html(self.current_week_id)
            fname = f"week_{self.current_week_id}.html"
            (_PRINT_CACHE / fname).write_text(html, encoding="utf-8")
            url = f"/print_cache/{fname}"
            return rx.call_script(f"window.open('{url}', '_blank')")
        except Exception as e:
            self.error = f"Print error: {e}"

    def _load_night(self, night_id: str):
        self.current_night_id = night_id
        self.loading = True
        try:
            # Phase J — fetch call-offs for this night BEFORE building slot dicts,
            # so we can stamp warning_status onto each filled slot.
            night_date = ""
            for n in self.nights:
                if n["id"] == night_id:
                    night_date = n.get("night_date", "")
                    break
            if night_date:
                try:
                    self.night_called_off = database.fetch_called_off_names_for_night(night_date)
                except Exception as exc:
                    print(f"[_load_night] call-offs fetch: {exc}")
                    self.night_called_off = []
            else:
                self.night_called_off = []

            all_slots = database.fetch_zone_assignments(night_id)
            self.zone_slots = [s for s in all_slots if s["slot_type"] == "zone"]
            self.aux_slots  = [s for s in all_slots if s["slot_type"] == "aux"]

            # Group RR slots into paired dicts (one dict per bank, with mens+womens merged)
            rr_raw = [s for s in all_slots if s["slot_type"] == "rr"]
            rr_order = ["rr_1_2", "rr_6", "rr_7", "rr_8", "rr_10"]
            rr_map: dict[str, dict] = {}
            for s in rr_raw:
                sk = s["slot_key"]
                if sk not in rr_map:
                    rr_map[sk] = {
                        "slot_key": sk, "label": s["label"], "color": s["color"],
                        "has_alert": False, "alert_target": "",
                        "is_sweeper": False, "sweeper_route": "",
                        "mens_name": "Unfilled", "mens_slot_id": "",
                        "mens_tm_id": "", "mens_is_filled": False,
                        "mens_is_locked": False, "mens_has_duplicate": False,
                        "mens_group": 0,
                        "womens_name": "Unfilled", "womens_slot_id": "",
                        "womens_tm_id": "", "womens_is_filled": False,
                        "womens_is_locked": False, "womens_has_duplicate": False,
                        "womens_group": 0,
                        "display_tasks": [],
                    }
                if s["rr_side"] == "mens":
                    rr_map[sk]["mens_name"]          = s["display_name"]
                    rr_map[sk]["mens_slot_id"]        = s["id"]
                    rr_map[sk]["mens_tm_id"]          = s.get("tm_id") or ""
                    rr_map[sk]["mens_is_filled"]      = s["is_filled"]
                    rr_map[sk]["mens_is_locked"]      = s.get("is_locked", False)
                    rr_map[sk]["mens_has_duplicate"]  = s.get("has_duplicate", False)
                    rr_map[sk]["mens_group"]          = s.get("group_num", 0)
                    rr_map[sk]["display_tasks"]       = s.get("display_tasks", [])
                else:
                    rr_map[sk]["womens_name"]         = s["display_name"]
                    rr_map[sk]["womens_slot_id"]      = s["id"]
                    rr_map[sk]["womens_tm_id"]        = s.get("tm_id") or ""
                    rr_map[sk]["womens_is_filled"]    = s["is_filled"]
                    rr_map[sk]["womens_is_locked"]    = s.get("is_locked", False)
                    rr_map[sk]["womens_has_duplicate"]= s.get("has_duplicate", False)
                    rr_map[sk]["womens_group"]        = s.get("group_num", 0)
                # Carry over alert / sweeper from either side
                if s["has_alert"]:
                    rr_map[sk]["has_alert"]     = True
                    rr_map[sk]["alert_target"]  = s["alert_target"]
                if s["is_sweeper"]:
                    rr_map[sk]["is_sweeper"]    = True
                    rr_map[sk]["sweeper_route"] = s["sweeper_route"]
            self.rr_slots = [rr_map[sk] for sk in rr_order if sk in rr_map]

            self.break_rows   = database.fetch_break_assignments(night_id)
            self.overlap_rows = database.fetch_overlap_assignments(night_id)
            # Extract schedule pool lists for this night
            self._update_night_pools()

            # Phase J — stamp warning_status on every filled slot.
            # "called_off"    if TM display_name is in self.night_called_off
            # "not_scheduled" if TM is assigned but not in any pool tonight
            #                 (and pools are populated — empty pools mean no
            #                 schedule uploaded yet, so suppress this warning)
            scheduled_set = (
                set(self.night_grave_pool)
                | set(self.night_pm_ol_pool)
                | set(self.night_am_ol_pool)
            )
            called_off_set = set(self.night_called_off)
            pools_known = bool(scheduled_set)

            def _classify(name: str) -> str:
                if not name or name == "Unfilled":
                    return ""
                if name in called_off_set:
                    return "called_off"
                if pools_known and name not in scheduled_set:
                    return "not_scheduled"
                return "ok"

            for s in self.zone_slots:
                s["warning_status"] = _classify(s.get("display_name") or s.get("tm_name", ""))
            for s in self.aux_slots:
                s["warning_status"] = _classify(s.get("display_name") or s.get("tm_name", ""))
            for rr in self.rr_slots:
                rr["mens_warning_status"]   = _classify(rr.get("mens_name", ""))
                rr["womens_warning_status"] = _classify(rr.get("womens_name", ""))
        except Exception as e:
            self.error = str(e)
        finally:
            self.loading = False

    def toggle_break_sheet(self):
        self.show_break_sheet = not self.show_break_sheet
        self.active_tab = "break" if self.show_break_sheet else "deployment"
        self.show_schedule = False

    def set_active_tab(self, tab: str | list[str]):
        """Switch between Deployment / Break Sheet / Schedule tabs.

        Radix's segmented control event spec is `str | list[str]` (the multi-
        select variant returns a list). We're single-select, so normalize.
        """
        if isinstance(tab, list):
            tab = tab[0] if tab else "deployment"
        self.active_tab      = tab
        self.show_break_sheet = (tab == "break")
        self.show_schedule    = (tab == "schedule")

    # =========================================================================
    # TM Picker
    # =========================================================================

    def open_picker(self, slot_id: str, slot_key: str, rr_side: str, label: str):
        self.picker_slot_id  = slot_id
        self.picker_slot_key = slot_key
        self.picker_rr_side  = rr_side
        self.picker_label    = label
        self.tm_search       = ""
        try:
            tms = database.fetch_eligible_tms_for_slot(
                slot_key, rr_side if rr_side else None
            )
            # Build a fast tm_id → (slot_label, slot_id, slot_locked) map for this night.
            # Phase I: Swap needs the source slot_id so we can rewrite the originating
            # placement. We also need to know if the source slot is locked — swap
            # must refuse if either side is locked.
            tm_slot_map: dict[str, tuple[str, str, bool]] = {}
            for s in self.zone_slots:
                if s.get("tm_id"):
                    tm_slot_map[s["tm_id"]] = (s["label"], s["id"], bool(s.get("is_locked")))
            for s in self.aux_slots:
                if s.get("tm_id"):
                    tm_slot_map[s["tm_id"]] = (s["label"], s["id"], bool(s.get("is_locked")))
            for rr in self.rr_slots:
                if rr.get("mens_tm_id"):
                    tm_slot_map[rr["mens_tm_id"]] = (
                        f"{rr['label']} M",
                        rr.get("mens_slot_id", ""),
                        bool(rr.get("mens_is_locked")),
                    )
                if rr.get("womens_tm_id"):
                    tm_slot_map[rr["womens_tm_id"]] = (
                        f"{rr['label']} W",
                        rr.get("womens_slot_id", ""),
                        bool(rr.get("womens_is_locked")),
                    )
            # Annotate each TM with their current assignment for this night
            for tm in tms:
                entry = tm_slot_map.get(tm["id"])
                if entry:
                    label, src_id, src_locked = entry
                    tm["is_assigned"]      = True
                    tm["assigned_to"]      = label
                    tm["assigned_slot_id"] = src_id
                    tm["assigned_locked"]  = src_locked
                else:
                    tm["is_assigned"]      = False
                    tm["assigned_to"]      = ""
                    tm["assigned_slot_id"] = ""
                    tm["assigned_locked"]  = False

            # Annotate each TM with their schedule pool for tonight
            # Phase J — also flag called-off TMs so the picker can warn
            grave_set     = set(self.night_grave_pool)
            pm_set        = set(self.night_pm_ol_pool)
            am_set        = set(self.night_am_ol_pool)
            called_off_set = set(self.night_called_off)
            for tm in tms:
                dn = tm["display_name"]
                if dn in grave_set:
                    tm["on_schedule"]   = True
                    tm["schedule_pool"] = "grave"
                elif dn in pm_set:
                    tm["on_schedule"]   = True
                    tm["schedule_pool"] = "pm_ol"
                elif dn in am_set:
                    tm["on_schedule"]   = True
                    tm["schedule_pool"] = "am_ol"
                else:
                    tm["on_schedule"]   = False
                    tm["schedule_pool"] = "off"
                tm["is_called_off"] = dn in called_off_set

            # Phase K.2 — batch-fetch recent placements for the eligible TMs.
            # Strictly before this night's date so we never show tonight's
            # in-progress placement as "history".
            current_night_date = ""
            for n in self.nights:
                if n["id"] == self.current_night_id:
                    current_night_date = n.get("night_date", "")
                    break
            if current_night_date:
                tm_ids = [t["id"] for t in tms]
                try:
                    history_map = database.fetch_recent_placements_bulk(
                        tm_ids, before_date=current_night_date, max_per_tm=3,
                    )
                except Exception as exc:
                    print(f"[open_picker] history fetch: {exc}")
                    history_map = {}
                for tm in tms:
                    hist = history_map.get(tm["id"], []) or []
                    # Pre-render the compact label string the UI will show.
                    # "Mon Z3 · Sun Z6 · Sat Z9 SR"  (newest first)
                    if hist:
                        tm["history_summary"] = " · ".join(
                            f"{h['weekday']} {h['slot_label']}".strip()
                            for h in hist
                        )
                    else:
                        tm["history_summary"] = ""
            else:
                for tm in tms:
                    tm["history_summary"] = ""

            # Sort: scheduled TMs first (grave → pm_ol → am_ol → off),
            #       already-assigned slots sink to the bottom within each group
            _pool_order = {"grave": 0, "pm_ol": 1, "am_ol": 2, "off": 3}
            tms.sort(key=lambda t: (
                _pool_order.get(t["schedule_pool"], 3),
                t["is_assigned"],
                t["display_name"].lower(),
            ))
            self.eligible_tms = tms
        except Exception as e:
            self.error = str(e)
            self.eligible_tms = []
        self.show_picker = True

    def close_picker(self):
        self.show_picker = False
        self.picker_slot_id = ""
        self.tm_search = ""

    def set_tm_search(self, val: str):
        self.tm_search = val

    # =========================================================================
    # Audit banner — change tracking + undo
    # =========================================================================

    def _describe_slot(self, slot_id: str) -> tuple[str, str, str]:
        """
        Resolve a slot_id to (target_label, current_tm_id, current_tm_name).
        Falls back to (slot_id, "", "") for unknown slots so the log still
        renders something rather than crashing.
        """
        for s in self.zone_slots:
            if s["id"] == slot_id:
                return s["label"], s["tm_id"], s["tm_name"]
        for s in self.aux_slots:
            if s["id"] == slot_id:
                return s["label"], s["tm_id"], s["tm_name"]
        for rr in self.rr_slots:
            if rr.get("mens_slot_id") == slot_id:
                return f"{rr['label']} Mens", rr.get("mens_tm_id", ""), rr["mens_name"]
            if rr.get("womens_slot_id") == slot_id:
                return f"{rr['label']} Women's", rr.get("womens_tm_id", ""), rr["womens_name"]
        return slot_id, "", ""

    def _log_change(
        self,
        *,
        kind: str,
        slot_id: str,
        target_label: str,
        detail: str,
        icon: str,
        accent: str,
        prev_tm_id: str = "",
        prev_lock: bool = False,
        task_text: str = "",
        # Phase K.4 — redo + swap-revert payload
        new_tm_id: str = "",
        new_lock: bool = False,
        source_slot_id: str = "",
    ) -> None:
        """Append a ChangeLogEntry, newest-first, capped at 100 entries."""
        entry: ChangeLogEntry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "kind": kind,
            "night_id": self.current_night_id,
            "slot_id": slot_id,
            "target_label": target_label,
            "detail": detail,
            "icon": icon,
            "accent": accent,
            "prev_tm_id": prev_tm_id,
            "prev_lock": prev_lock,
            "task_text": task_text,
            "undone": False,
            "new_tm_id": new_tm_id,
            "new_lock": new_lock,
            "source_slot_id": source_slot_id,
        }
        self.change_log = [entry] + self.change_log[:99]

    def revert_change(self, entry_id: str):
        """
        Reverse a logged mutation. Routes by `kind` back through the same
        DB functions the original mutation used; the engine re-runs after
        assign/clear undos so dependent slots reshuffle as expected.
        """
        entry: Optional[ChangeLogEntry] = None
        for c in self.change_log:
            if c["id"] == entry_id:
                entry = c
                break
        if entry is None or entry["undone"]:
            return
        try:
            kind = entry["kind"]
            slot_id = entry["slot_id"]
            if kind in ("assign", "clear"):
                prev = entry["prev_tm_id"] or None
                database.update_zone_assignment(slot_id, prev)
                self._do_engine_night(self.current_night_id)
            elif kind == "swap":
                # Phase K.4 — swap revert: put each TM back where they were.
                # entry.slot_id      = target slot (where new_tm_id ended up)
                # entry.source_slot_id = source slot (where prev_tm_id ended up after swap)
                # entry.prev_tm_id   = TM that was at target before the swap
                # entry.new_tm_id    = TM that was moved INTO target (came from source)
                src_slot = entry.get("source_slot_id", "") or ""
                # Restore: target slot back to prev_tm_id, source slot back to new_tm_id
                database.update_zone_assignment(slot_id, entry["prev_tm_id"] or None)
                if src_slot:
                    database.update_zone_assignment(src_slot, entry["new_tm_id"] or None)
                self._do_engine_night(self.current_night_id)
            elif kind == "lock_toggle":
                database.update_slot_lock(slot_id, entry["prev_lock"])
            elif kind == "task_add":
                tasks = [t for t in self._get_slot_tasks(slot_id) if t != entry["task_text"]]
                database.update_slot_tasks(slot_id, tasks)
            elif kind == "task_remove":
                tasks = self._get_slot_tasks(slot_id)
                if entry["task_text"] not in tasks:
                    tasks.append(entry["task_text"])
                database.update_slot_tasks(slot_id, tasks)
            else:
                return
            # Mark this entry undone — keep it in the log as an audit trail
            self.change_log = [
                {**c, "undone": True} if c["id"] == entry_id else c
                for c in self.change_log
            ]
            self._load_night(self.current_night_id)
        except Exception as e:
            self.error = str(e)

    def redo_change(self, entry_id: str):
        """Phase K.4 — Re-apply an undone mutation.

        Symmetric to revert_change. Walks the same kind switch but with the
        forward payload (new_tm_id / new_lock) instead of the prev payload.
        """
        entry: Optional[ChangeLogEntry] = None
        for c in self.change_log:
            if c["id"] == entry_id:
                entry = c
                break
        if entry is None or not entry["undone"]:
            return
        try:
            kind = entry["kind"]
            slot_id = entry["slot_id"]
            if kind == "assign":
                database.update_zone_assignment(slot_id, entry["new_tm_id"] or None)
                self._do_engine_night(self.current_night_id)
            elif kind == "clear":
                # A clear's "redo" is to clear again — write None.
                database.update_zone_assignment(slot_id, None)
                self._do_engine_night(self.current_night_id)
            elif kind == "swap":
                src_slot = entry.get("source_slot_id", "") or ""
                # Re-apply: target slot gets new_tm_id, source gets prev_tm_id
                database.update_zone_assignment(slot_id, entry["new_tm_id"] or None)
                if src_slot:
                    database.update_zone_assignment(src_slot, entry["prev_tm_id"] or None)
                self._do_engine_night(self.current_night_id)
            elif kind == "lock_toggle":
                database.update_slot_lock(slot_id, entry["new_lock"])
            elif kind == "task_add":
                tasks = self._get_slot_tasks(slot_id)
                if entry["task_text"] not in tasks:
                    tasks.append(entry["task_text"])
                database.update_slot_tasks(slot_id, tasks)
            elif kind == "task_remove":
                tasks = [t for t in self._get_slot_tasks(slot_id) if t != entry["task_text"]]
                database.update_slot_tasks(slot_id, tasks)
            else:
                return
            # Mark not-undone again
            self.change_log = [
                {**c, "undone": False} if c["id"] == entry_id else c
                for c in self.change_log
            ]
            self._load_night(self.current_night_id)
        except Exception as e:
            self.error = str(e)

    def clear_change_log(self):
        """'Mark all reviewed' — drop entries for the current night."""
        self.change_log = [
            c for c in self.change_log if c["night_id"] != self.current_night_id
        ]
        self.banner_expanded = False

    def toggle_banner(self):
        self.banner_expanded = not self.banner_expanded

    # =========================================================================
    # Slot mutations
    # =========================================================================

    def assign_tm(self, tm_id: str):
        if not self.picker_slot_id:
            return
        slot_id = self.picker_slot_id   # capture before close_picker resets it
        # Guard: refuse to overwrite a locked slot
        slot_is_locked = False
        for s in self.zone_slots + self.aux_slots:
            if s["id"] == slot_id:
                slot_is_locked = s.get("is_locked", False)
                break
        if slot_is_locked:
            self.error = "This slot is locked. Unlock it first before reassigning."
            self.close_picker()
            return
        # Capture before-state for the audit log
        target_label, prev_tm_id, prev_tm_name = self._describe_slot(slot_id)
        new_tm_name = next(
            (tm["display_name"] for tm in self.eligible_tms if tm["id"] == tm_id),
            "Unknown",
        )
        try:
            database.update_zone_assignment(slot_id, tm_id)
            self._do_engine_night(self.current_night_id)
            self._load_night(self.current_night_id)
            was = prev_tm_name if prev_tm_name and prev_tm_name != "Unfilled" else "Unfilled"
            self._log_change(
                kind="assign",
                slot_id=slot_id,
                target_label=target_label,
                detail=f"{new_tm_name} → {target_label} (was {was})",
                icon="user-plus",
                accent="#1d4ed8",
                prev_tm_id=prev_tm_id,
                new_tm_id=tm_id,
            )
        except Exception as e:
            self.error = str(e)
        self.close_picker()

    def swap_tms(self, target_tm_id: str):
        """Phase I — Swap a TM from their current slot into the picker's
        target slot, simultaneously moving whoever was in the target slot
        (if anyone) into the source's slot.

        Refuses if either side is locked. Logs both legs of the swap to the
        audit banner.
        """
        if not self.picker_slot_id:
            return
        target_slot_id = self.picker_slot_id  # the slot we tapped to open the picker

        # Resolve the source slot from the eligible_tms metadata
        tm_entry = next(
            (tm for tm in self.eligible_tms if tm["id"] == target_tm_id),
            None,
        )
        if not tm_entry:
            self.error = "TM not found in picker list — refresh the picker."
            self.close_picker()
            return
        source_slot_id = tm_entry.get("assigned_slot_id", "")
        if not source_slot_id:
            # Shouldn't happen — UI only shows Swap on currently-assigned TMs.
            self.error = "Cannot swap: TM has no current placement."
            self.close_picker()
            return

        # Lock guards on both legs
        if tm_entry.get("assigned_locked"):
            self.error = (
                f"Source slot ({tm_entry.get('assigned_to', '?')}) is locked. "
                "Unlock it first."
            )
            self.close_picker()
            return
        target_locked = False
        for s in self.zone_slots + self.aux_slots:
            if s["id"] == target_slot_id:
                target_locked = s.get("is_locked", False)
                break
        # RR slots
        if not target_locked:
            for rr in self.rr_slots:
                if rr.get("mens_slot_id") == target_slot_id and rr.get("mens_is_locked"):
                    target_locked = True
                if rr.get("womens_slot_id") == target_slot_id and rr.get("womens_is_locked"):
                    target_locked = True
        if target_locked:
            self.error = "Target slot is locked. Unlock it first before swapping."
            self.close_picker()
            return

        # Capture before-state for the audit log
        target_label, target_prev_tm_id, target_prev_tm_name = self._describe_slot(target_slot_id)
        source_label, _src_curr_id, _src_curr_name = self._describe_slot(source_slot_id)
        target_tm_name = tm_entry["display_name"]

        try:
            # Two writes, in order:
            #   1. Put target_tm into the picker's target slot
            #   2. Put whoever was previously in the target slot (if anyone)
            #      into the source slot. If the target was empty, just clear
            #      the source.
            database.update_zone_assignment(target_slot_id, target_tm_id)
            database.update_zone_assignment(source_slot_id, target_prev_tm_id or None)

            # Re-run break-wave engine + reload UI state for the night
            self._do_engine_night(self.current_night_id)
            self._load_night(self.current_night_id)

            # Audit log — two entries, one per leg, so undo can revert both.
            self._log_change(
                kind="swap",
                slot_id=target_slot_id,
                target_label=target_label,
                detail=(
                    f"{target_tm_name} → {target_label}  ⇄  "
                    f"{target_prev_tm_name or 'Unfilled'} → {source_label}"
                ),
                icon="arrow-left-right",
                accent="#7c3aed",   # violet — distinguishes swap from assign/clear
                prev_tm_id=target_prev_tm_id,
                new_tm_id=target_tm_id,
                source_slot_id=source_slot_id,
            )
        except Exception as e:
            self.error = f"Swap failed: {e}"
        self.close_picker()

    # =========================================================================
    # Call-offs (Phase J)
    # =========================================================================

    def toggle_call_off_by_name(self, display_name: str):
        """Toggle call-off status for a TM identified by display_name.

        Used by the Schedule tab where we only know the parsed name from the
        xlsx, not the tm_id. Looks up the tm_id, then marks or unmarks based
        on current state.
        """
        if not display_name:
            return
        tm_id = self.tm_name_to_id.get(display_name, "")
        if not tm_id:
            self.error = f"Couldn't find TM '{display_name}' in entities."
            return
        if display_name in self.night_called_off:
            self.unmark_called_off(tm_id)
        else:
            self.mark_called_off(tm_id)

    def mark_called_off(self, tm_id: str, reason: str = ""):
        """Mark a TM as called off for the currently-open night."""
        night_date = ""
        for n in self.nights:
            if n["id"] == self.current_night_id:
                night_date = n.get("night_date", "")
                break
        if not night_date or not tm_id:
            return
        try:
            ok = database.add_call_off(tm_id, night_date, reason)
            if not ok:
                self.error = "Failed to mark called off."
                return
            # Refresh — will recompute warning_status on every slot too
            self._load_night(self.current_night_id)
        except Exception as e:
            self.error = str(e)

    def unmark_called_off(self, tm_id: str):
        """Remove a call-off mark for the currently-open night."""
        night_date = ""
        for n in self.nights:
            if n["id"] == self.current_night_id:
                night_date = n.get("night_date", "")
                break
        if not night_date or not tm_id:
            return
        try:
            database.remove_call_off(tm_id, night_date)
            self._load_night(self.current_night_id)
        except Exception as e:
            self.error = str(e)

    def clear_slot(self, slot_id: str):
        # Guard: refuse to clear a locked slot
        for s in self.zone_slots + self.aux_slots:
            if s["id"] == slot_id and s.get("is_locked", False):
                self.error = "This slot is locked. Unlock it first before clearing."
                return
        target_label, prev_tm_id, prev_tm_name = self._describe_slot(slot_id)
        try:
            database.update_zone_assignment(slot_id, None)
            self._do_engine_night(self.current_night_id)
            self._load_night(self.current_night_id)
            if prev_tm_id:   # don't log no-op clears
                self._log_change(
                    kind="clear",
                    slot_id=slot_id,
                    target_label=target_label,
                    detail=f"Cleared {prev_tm_name} from {target_label}",
                    icon="user-minus",
                    accent="#b45309",
                    prev_tm_id=prev_tm_id,
                )
        except Exception as e:
            self.error = str(e)

    def toggle_slot_lock(self, slot_id: str):
        """Toggle the position lock on a zone/RR/aux slot."""
        target_label, _tm_id, tm_name = self._describe_slot(slot_id)
        # Find current lock state
        current = False
        for s in self.zone_slots + self.aux_slots:
            if s["id"] == slot_id:
                current = s.get("is_locked", False)
                break
        # Check RR slots too
        for rr in self.rr_slots:
            if rr.get("mens_slot_id") == slot_id:
                current = rr.get("mens_is_locked", False)
                break
            if rr.get("womens_slot_id") == slot_id:
                current = rr.get("womens_is_locked", False)
                break
        try:
            database.update_slot_lock(slot_id, not current)
            self._load_night(self.current_night_id)
            new_state = not current
            who = f" ({tm_name})" if tm_name and tm_name != "Unfilled" else ""
            self._log_change(
                kind="lock_toggle",
                slot_id=slot_id,
                target_label=target_label,
                detail=(f"Locked {target_label}{who}" if new_state
                        else f"Unlocked {target_label}"),
                icon="lock" if new_state else "lock_open",
                accent="#a16207" if new_state else "#6b7280",
                prev_lock=current,
                new_lock=new_state,
            )
        except Exception as e:
            self.error = str(e)

    def toggle_wave_lock(self, assignment_id: str):
        """Toggle the wave lock on a break assignment."""
        current = False
        for r in self.break_rows:
            if r["id"] == assignment_id:
                current = r.get("is_wave_locked", False)
                break
        try:
            database.update_wave_lock(assignment_id, not current)
            self._load_night(self.current_night_id)
        except Exception as e:
            self.error = str(e)

    # =========================================================================
    # Task inline edit
    # =========================================================================

    def open_task_input(self, slot_id: str):
        self.task_edit_slot_id = slot_id
        self.task_edit_text    = ""

    def close_task_input(self):
        self.task_edit_slot_id = ""
        self.task_edit_text    = ""

    def set_task_edit_text(self, val: str):
        self.task_edit_text = val

    def submit_task(self, slot_id: str):
        text = self.task_edit_text.strip()
        if not text or not slot_id:
            self.close_task_input()
            return
        target_label, _tm_id, _tm_name = self._describe_slot(slot_id)
        current = self._get_slot_tasks(slot_id)
        already_present = text in current
        if not already_present:
            current.append(text)
        try:
            database.update_slot_tasks(slot_id, current)
            self._load_night(self.current_night_id)
            if not already_present:
                self._log_change(
                    kind="task_add",
                    slot_id=slot_id,
                    target_label=target_label,
                    detail=f'Added "{text}" to {target_label}',
                    icon="list-plus",
                    accent="#059669",
                    task_text=text,
                )
        except Exception as e:
            self.error = str(e)
        self.close_task_input()

    def remove_task(self, slot_id: str, task: str):
        target_label, _tm_id, _tm_name = self._describe_slot(slot_id)
        current = self._get_slot_tasks(slot_id)
        if task not in current:
            return
        current = [t for t in current if t != task]
        try:
            database.update_slot_tasks(slot_id, current)
            self._load_night(self.current_night_id)
            self._log_change(
                kind="task_remove",
                slot_id=slot_id,
                target_label=target_label,
                detail=f'Removed "{task}" from {target_label}',
                icon="list-minus",
                accent="#9ca3af",
                task_text=task,
            )
        except Exception as e:
            self.error = str(e)

    def _get_slot_tasks(self, slot_id: str) -> list[str]:
        """Return the current display_tasks list for a given slot_id."""
        for s in self.zone_slots:
            if s["id"] == slot_id:
                return list(s.get("display_tasks", []))
        for s in self.aux_slots:
            if s["id"] == slot_id:
                return list(s.get("display_tasks", []))
        for rr in self.rr_slots:
            if rr.get("mens_slot_id") == slot_id:
                return list(rr.get("display_tasks", []))
        return []

    # =========================================================================
    # Break wave editing
    # =========================================================================

    def update_break_wave(self, assignment_id: str, new_wave: int):
        try:
            database.update_break_wave(assignment_id, new_wave)
            self._load_night(self.current_night_id)
        except Exception as e:
            self.error = str(e)

    # =========================================================================
    # Engine — regenerate break assignments from current slot placements
    # =========================================================================

    def _do_engine_night(self, night_id: str):
        """
        Rebuild break_assignments for one night from current zone placements.
        Uses BG_* defaults for wave assignment.
        Only filled slots are inserted — break_assignments.tm_id is NOT NULL.
        """
        all_slots = database.fetch_zone_assignments(night_id)
        rows: list[dict] = []
        sort_order = 0

        # ── Zones (zone_1 … zone_10 in order) ──
        zone_order = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        zone_map = {
            int(s["slot_key"].rsplit("_", 1)[-1]): s
            for s in all_slots if s["slot_type"] == "zone"
        }
        for n in zone_order:
            s = zone_map.get(n)
            if s is None or not s.get("tm_id"):
                continue  # skip unfilled — tm_id NOT NULL
            sort_order += 1
            label = ENGINE_SLOT_LABEL.get(s["slot_key"], s["slot_key"])
            rows.append({
                "night_id":   night_id,
                "tm_id":      s["tm_id"],
                "break_wave": BG_ZONE.get(n, 1),
                "slot_ref":   label,
                "sort_order": sort_order,
            })

        # ── Restrooms (mens side then womens side) ──
        rr_order = ["rr_1_2", "rr_6", "rr_7", "rr_8", "rr_10"]
        rr_num = {"rr_1_2": 1, "rr_6": 6, "rr_7": 7, "rr_8": 8, "rr_10": 10}
        rr_slots = [s for s in all_slots if s["slot_type"] == "rr"]
        for side, tbl in [("mens", BG_RR_M), ("womens", BG_RR_W)]:
            for sk in rr_order:
                slot = next(
                    (s for s in rr_slots
                     if s["slot_key"] == sk and s["rr_side"] == side), None
                )
                if slot is None or not slot.get("tm_id"):
                    continue  # skip unfilled — tm_id NOT NULL
                num = rr_num[sk]
                sort_order += 1
                label = ENGINE_SLOT_LABEL.get(f"{sk}_{side}", f"{sk} {side}")
                rows.append({
                    "night_id":   night_id,
                    "tm_id":      slot["tm_id"],
                    "break_wave": tbl.get(num, 1),
                    "slot_ref":   label,
                    "sort_order": sort_order,
                })

        # ── Auxiliary ──
        aux_order = [
            "z9_sr", "admin",
            "trash_1", "trash_2",
            "support_1", "support_2", "support_3",
        ]
        aux_map = {s["slot_key"]: s for s in all_slots if s["slot_type"] == "aux"}
        for sk in aux_order:
            s = aux_map.get(sk)
            if s is None or not s.get("tm_id"):
                continue  # skip unfilled — tm_id NOT NULL
            sort_order += 1
            label = ENGINE_SLOT_LABEL.get(sk, sk)
            rows.append({
                "night_id":   night_id,
                "tm_id":      s["tm_id"],
                "break_wave": BG_AUX.get(sk, 1),
                "slot_ref":   label,
                "sort_order": sort_order,
            })

        database.replace_break_assignments(night_id, rows)

    def run_engine_night(self, night_id: str):
        """Run the break engine for a specific night (used from week overview)."""
        self.loading = True
        self.error = ""
        try:
            self._do_engine_night(night_id)
            # If this is also the currently-loaded night, refresh the break data
            if night_id == self.current_night_id:
                self._load_night(night_id)
        except Exception as e:
            self.error = str(e)
        finally:
            self.loading = False

    def run_engine_current_night(self):
        """Run the break engine for the currently-open deployment page."""
        if not self.current_night_id:
            return
        self.loading = True
        self.error = ""
        try:
            self._do_engine_night(self.current_night_id)
            self._load_night(self.current_night_id)
        except Exception as e:
            self.error = str(e)
        finally:
            self.loading = False

    def run_engine_week(self):
        """Run the break engine for every night in the current week."""
        if not self.current_week_id:
            return
        self.loading = True
        self.error = ""
        try:
            for night in self.nights:
                self._do_engine_night(night["id"])
            # Refresh break data if a night is currently loaded
            if self.current_night_id:
                self._load_night(self.current_night_id)
        except Exception as e:
            self.error = str(e)
        finally:
            self.loading = False

    # =========================================================================
    # Zone Deployment Engine — auto-fill zone/RR/aux assignments from schedule
    # =========================================================================

    def _do_zone_engine(self, target_night_id: str | None = None) -> dict:
        """
        Run the full GLCR fill_engine for the current week and sync results to
        Supabase zone_assignments.

        Locked slots are preserved.  If target_night_id is provided, only that
        night's unlocked slots are updated (the full week still runs for correct
        cross-day rotation).

        Returns a structured result dict (Phase K.1):
            {
              "success":      bool,
              "scope":        "night" | "week",
              "updated":      int,        # slots written
              "locked_skipped": int,      # slots preserved due to lock
              "unresolved_cleared": int,  # slots the engine couldn't fill that we cleared
              "unresolved":   list[dict], # full engine.unresolved list
              "week_ending":  str,
              "error":        str | "",
              "message":      str,        # human-readable one-liner
            }
        """
        from .engine_bridge import run_fill_engine
        from . import database

        # Phase H: prefer the schedule_path explicitly linked to this week.
        # Falls back to mtime auto-pick (legacy behavior) only when no link exists.
        linked_path = (self.week_info or {}).get("schedule_path") or ""
        if linked_path:
            result = run_fill_engine(schedule_file=linked_path)
        else:
            result = run_fill_engine()

        scope = "night" if target_night_id else "week"

        if result.get("error"):
            return {
                "success": False, "scope": scope,
                "updated": 0, "locked_skipped": 0, "unresolved_cleared": 0,
                "unresolved": [], "week_ending": result.get("week_ending", ""),
                "error":  f"Engine error: {result['error']}",
                "message": f"Engine error: {result['error']}",
            }

        # Sync placements to Supabase
        summary = database.sync_engine_to_week(
            self.current_week_id,
            result,
            target_night_id=target_night_id,
        )

        if summary.get("error"):
            return {
                "success": False, "scope": scope,
                "updated": 0, "locked_skipped": 0, "unresolved_cleared": 0,
                "unresolved": [], "week_ending": result.get("week_ending", ""),
                "error":  f"Sync error: {summary['error']}",
                "message": f"Sync error: {summary['error']}",
            }

        updated   = summary.get("updated", 0)
        locked    = summary.get("skipped_locked", 0)
        cleared   = summary.get("unresolved_cleared", 0)
        unresolved = result.get("unresolved", []) or []

        # Compose human-readable summary
        bits = [f"{updated} slot(s) filled"]
        if cleared:
            bits.append(f"{cleared} cleared (no eligible TM)")
        if locked:
            bits.append(f"{locked} locked preserved")
        if unresolved:
            bits.append(f"{len(unresolved)} unresolved")
        msg = f"Deployment engine ran ({scope}): " + ", ".join(bits) + "."

        return {
            "success":            True,
            "scope":              scope,
            "updated":            updated,
            "locked_skipped":     locked,
            "unresolved_cleared": cleared,
            "unresolved":         unresolved,
            "week_ending":        result.get("week_ending", ""),
            "error":              "",
            "message":            msg,
        }

    def run_zone_engine_current_night(self):
        """
        Run the full deployment engine and apply results to the currently-open night only.
        Locked slots on this night are not touched.
        """
        if not self.current_night_id or not self.current_week_id:
            return
        self.loading = True
        self.error = ""
        try:
            result = self._do_zone_engine(target_night_id=self.current_night_id)
            # Re-run break wave engine to keep break sheet in sync
            self._do_engine_night(self.current_night_id)
            self._load_night(self.current_night_id)
            self._open_engine_result(result)
        except Exception as e:
            self.error = str(e)
        finally:
            self.loading = False

    def run_zone_engine_from_overview(self, night_id: str):
        """
        Run the full deployment engine targeted at a specific night (from week overview).
        """
        if not night_id or not self.current_week_id:
            return
        self.loading = True
        self.error = ""
        try:
            result = self._do_zone_engine(target_night_id=night_id)
            # Re-run break wave engine for this night too
            self._do_engine_night(night_id)
            self._open_engine_result(result)
        except Exception as e:
            self.error = str(e)
        finally:
            self.loading = False

    def run_zone_engine_week(self):
        """
        Run the full deployment engine for the entire week.
        All unlocked slots across all 7 nights are auto-filled.
        """
        if not self.current_week_id:
            return
        self.loading = True
        self.error = ""
        try:
            result = self._do_zone_engine(target_night_id=None)
            # Re-run break wave engine for all nights
            for night in self.nights:
                self._do_engine_night(night["id"])
            if self.current_night_id:
                self._load_night(self.current_night_id)
            self._open_engine_result(result)
        except Exception as e:
            self.error = str(e)
        finally:
            self.loading = False

    # ── Bulk operations on the current night (Phase K.3) ──────────────────────

    def bulk_clear_unlocked(self):
        """Clear every UNLOCKED filled slot on the current night.
        Locked slots are preserved.
        """
        if not self.current_night_id:
            return
        cleared_count = 0
        try:
            for s in self.zone_slots + self.aux_slots:
                if s.get("is_filled") and not s.get("is_locked"):
                    database.update_zone_assignment(s["id"], None)
                    cleared_count += 1
            for rr in self.rr_slots:
                if rr.get("mens_is_filled") and not rr.get("mens_is_locked"):
                    database.update_zone_assignment(rr["mens_slot_id"], None)
                    cleared_count += 1
                if rr.get("womens_is_filled") and not rr.get("womens_is_locked"):
                    database.update_zone_assignment(rr["womens_slot_id"], None)
                    cleared_count += 1
            self._do_engine_night(self.current_night_id)
            self._load_night(self.current_night_id)
            if cleared_count:
                self._log_change(
                    kind="bulk_clear",
                    slot_id="",
                    target_label="all unlocked",
                    detail=f"Cleared {cleared_count} unlocked slot(s)",
                    icon="brush-cleaning",
                    accent="#9ca3af",
                )
        except Exception as e:
            self.error = str(e)

    def bulk_lock_filled(self):
        """Lock every filled slot on the current night.
        Useful once you're happy with a night and want to freeze it before
        iterating on others."""
        if not self.current_night_id:
            return
        locked_count = 0
        try:
            for s in self.zone_slots + self.aux_slots:
                if s.get("is_filled") and not s.get("is_locked"):
                    database.update_slot_lock(s["id"], True)
                    locked_count += 1
            for rr in self.rr_slots:
                if rr.get("mens_is_filled") and not rr.get("mens_is_locked"):
                    database.update_slot_lock(rr["mens_slot_id"], True)
                    locked_count += 1
                if rr.get("womens_is_filled") and not rr.get("womens_is_locked"):
                    database.update_slot_lock(rr["womens_slot_id"], True)
                    locked_count += 1
            self._load_night(self.current_night_id)
            if locked_count:
                self._log_change(
                    kind="bulk_lock",
                    slot_id="",
                    target_label="all filled",
                    detail=f"Locked {locked_count} filled slot(s)",
                    icon="lock",
                    accent="#a16207",
                )
        except Exception as e:
            self.error = str(e)

    def bulk_copy_from_previous_night(self):
        """Copy filled placements from the previous night in this week into
        the corresponding unlocked slots on the current night.

        Locks on the target slots are preserved (won't overwrite). Walks by
        slot_key + rr_side so the mapping is unambiguous.
        """
        if not self.current_night_id or not self.current_week_id:
            return
        # Find current night's day_num and the previous night
        current_day_num = 0
        for n in self.nights:
            if n["id"] == self.current_night_id:
                current_day_num = int(n.get("day_num", 0) or 0)
                break
        if current_day_num <= 1:
            self.error = "No previous night in this week to copy from."
            return
        prev_night_id = ""
        for n in self.nights:
            if int(n.get("day_num", 0) or 0) == current_day_num - 1:
                prev_night_id = n["id"]
                break
        if not prev_night_id:
            self.error = "Previous night not found in this week."
            return

        try:
            prev_slots = database.fetch_zone_assignments(prev_night_id)
            # Index prev by (slot_key, rr_side)
            prev_by_key: dict[tuple, str] = {}
            for s in prev_slots:
                if s.get("tm_id"):
                    key = (s["slot_key"], s.get("rr_side") or "")
                    prev_by_key[key] = s["tm_id"]

            copied = 0
            # Walk current zone + aux slots
            for s in self.zone_slots + self.aux_slots:
                if s.get("is_locked"):
                    continue
                key = (s["slot_key"], s.get("rr_side") or "")
                src_tm = prev_by_key.get(key)
                if src_tm:
                    database.update_zone_assignment(s["id"], src_tm)
                    copied += 1
            # Walk current RR slots (per side)
            for rr in self.rr_slots:
                if not rr.get("mens_is_locked") and rr.get("mens_slot_id"):
                    src_tm = prev_by_key.get((rr["slot_key"], "mens"))
                    if src_tm:
                        database.update_zone_assignment(rr["mens_slot_id"], src_tm)
                        copied += 1
                if not rr.get("womens_is_locked") and rr.get("womens_slot_id"):
                    src_tm = prev_by_key.get((rr["slot_key"], "womens"))
                    if src_tm:
                        database.update_zone_assignment(rr["womens_slot_id"], src_tm)
                        copied += 1

            self._do_engine_night(self.current_night_id)
            self._load_night(self.current_night_id)
            self._log_change(
                kind="bulk_copy",
                slot_id="",
                target_label="from previous night",
                detail=f"Copied {copied} placement(s) from previous night",
                icon="copy",
                accent="#0ea5e9",
            )
        except Exception as e:
            self.error = str(e)

    # ── Engine result dialog (Phase K.1) ──────────────────────────────────────

    def _open_engine_result(self, result: dict):
        """Surface the structured engine result in a modal (and as self.error
        if it was a failure)."""
        self.engine_result = result or {}
        self.engine_result_open = True
        if not result.get("success"):
            self.error = result.get("error", "") or result.get("message", "")

    def close_engine_result(self):
        self.engine_result_open = False

    def set_engine_result_open(self, open_: bool):
        """Two-way bind for rx.dialog's on_open_change."""
        self.engine_result_open = bool(open_)
