"""
state_schedule.py — Phase N.2

Dedicated state for the Week Schedule editor page at
/zds/week/[week_id]/schedule. Loads the linked xlsx, applies any
schedule_overrides, exposes shift filtering + name search, and provides
cell-level mutation handlers (Mark PTO / MDL / Called Off / Reset).
"""

from __future__ import annotations
from datetime import date as _date
from typing import Optional

import reflex as rx

from . import database
from . import schedule_parser
from .state import ZdsState
from .types import ScheduleCell, ScheduleRow


# Override values written to the schedule_overrides table. Match the
# parser's _classify_off_value categories so the grid recolors correctly.
OV_PTO        = "PTO Hourly"
OV_MDL        = "MDL"
OV_OFF        = "OFF"
OV_CALLED_OFF = "called_off"


class ScheduleEditorState(rx.State):
    """State for the dedicated Week Schedule editor."""

    # ── Context ────────────────────────────────────────────────────────────
    current_week_id: str = ""
    schedule_path: str = ""

    # ── Grid data ───────────────────────────────────────────────────────────
    # dates / weekdays are 7-element parallel arrays (Fri..Thu of the week).
    dates:        list[str] = []
    weekdays:     list[str] = []
    # rows: one entry per (TM, shift), with 7 cells each, built by parse_week_grid.
    rows: list[ScheduleRow] = []

    # ── Filters ─────────────────────────────────────────────────────────────
    shift_filter: str = "all"     # "all" | "days" | "swings" | "graves"
    search_query: str = ""

    # ── Cell popover ────────────────────────────────────────────────────────
    popover_open:    bool = False
    popover_tm_name: str  = ""
    popover_shift:   str  = ""
    popover_date:    str  = ""
    popover_value:   str  = ""    # current value (override or raw)
    popover_overridden: bool = False
    popover_note:    str  = ""

    loading: bool = True
    error:   str  = ""

    # ── Unknown-name reconciler (Phase O.4 / Q) ──────────────────────────────
    # Names from the xlsx that don't resolve to any entity. Each entry has
    # {first, last, display, shift}.
    unresolved_names: list[dict] = []
    # Per-row action state — Phase Q: clicking an unresolved name opens a
    # modal with search + Create-new + Match-to-existing.
    reconcile_target_display: str = ""
    reconcile_target_first:   str = ""
    reconcile_target_shift:   str = ""
    reconcile_match_tm_id:    str = ""
    reconcile_search:         str = ""
    reconcile_saving:         bool = False
    # All TMs available as match targets (display_name + id)
    reconcile_options: list[dict] = []

    # =========================================================================
    # Computed vars
    # =========================================================================

    @rx.var
    def week_label(self) -> str:
        if self.dates:
            return f"Week ending {self.dates[-1]}"
        return ""

    @rx.var
    def back_url(self) -> str:
        """Where the back arrow navigates — week overview for this week."""
        return f"/zds/week/{self.current_week_id}" if self.current_week_id else "/zds/"

    @rx.var
    def filtered_rows(self) -> list[ScheduleRow]:
        """Rows after applying shift_filter + search_query."""
        out = self.rows
        if self.shift_filter and self.shift_filter != "all":
            out = [r for r in out if r.get("shift") == self.shift_filter]
        q = (self.search_query or "").strip().lower()
        if q:
            out = [r for r in out if q in r.get("name", "").lower()]
        return out

    @rx.var
    def total_count(self) -> int:
        return len(self.rows)

    @rx.var
    def filtered_count(self) -> int:
        return len(self.filtered_rows)

    # =========================================================================
    # Lifecycle
    # =========================================================================

    @rx.event
    def on_load(self):
        """Page on_mount handler.

        Reflex auto-binds the [week_id] URL segment to self.current_week_id (since
        the field matches the dynamic route param name). We just read it.
        """
        try:
            wid = self.router.page.params.get("week_id", "")
            if wid:
                self.current_week_id = wid
        except Exception:
            pass
        self._load_grid()

    @rx.event
    def reload(self):
        """Reload grid (used after a cell write)."""
        self._load_grid()

    def _load_grid(self):
        """Fetch the schedule xlsx + overrides + entities, build the editor grid."""
        self.loading = True
        self.error = ""
        self.dates = []
        self.weekdays = []
        self.rows = []
        try:
            # 1. Resolve which xlsx is linked to this week
            week = database.fetch_week(self.current_week_id) if self.current_week_id else {}
            self.schedule_path = (week or {}).get("schedule_path") or ""

            # 2. Pull xlsx bytes from Storage (or local cache)
            blob = self._load_schedule_bytes()
            if not blob:
                self.error = "No schedule linked to this week. Upload + link one on /zds/."
                self.loading = False
                return

            # 3. Pull overrides for this schedule, build (name_lower, date) → value map
            overrides = database.fetch_schedule_overrides(self.schedule_path)
            entities = database.fetch_all_tms()
            id_to_name: dict[str, str] = {
                e["id"]: (e.get("display_name") or "").lower()
                for e in entities
                if e.get("id") and e.get("display_name")
            }
            ov_map: dict[tuple, str] = {}
            for o in overrides:
                name_lower = id_to_name.get(o.get("tm_id", ""), "")
                cell_date = o.get("cell_date", "")
                if name_lower and cell_date:
                    ov_map[(name_lower, cell_date)] = o.get("override_value", "")

            # 4. Parse grid — pass entities so the resolver can map xlsx
            # legal names to entity nicknames via metadata.aliases.
            grid = schedule_parser.parse_week_grid(
                blob,
                overrides_by_tm_date=ov_map,
                entities=entities,
            )
            self.dates    = grid.get("dates", [])
            self.weekdays = grid.get("weekdays", [])
            self.rows     = grid.get("rows", [])

            # 5. Phase O.4 — find names in the xlsx that don't resolve to any
            # entity, so the UI can offer to create-new or match-to-existing.
            try:
                self.unresolved_names = schedule_parser.find_unresolved_xlsx_names(
                    blob, entities
                )
            except Exception as exc:
                print(f"[_load_grid] unresolved scan: {exc}")
                self.unresolved_names = []
            # Build the dropdown options list (for "Match to existing")
            self.reconcile_options = sorted(
                ({"id": e["id"], "display_name": e.get("display_name", "")}
                 for e in entities if e.get("display_name")),
                key=lambda r: r["display_name"].lower(),
            )
        except Exception as e:
            self.error = f"Couldn't load schedule: {e}"
        finally:
            self.loading = False

    def _load_schedule_bytes(self) -> Optional[bytes]:
        """Try local Inputs/ first; fall back to Storage download."""
        if not self.schedule_path:
            return None
        local = schedule_parser.SCHEDULE_DIR / self.schedule_path
        try:
            if local.exists():
                return local.read_bytes()
        except Exception:
            pass
        try:
            from shared.db import get_client
            sb = get_client()
            return sb.storage.from_("schedules").download(self.schedule_path)
        except Exception:
            return None

    # =========================================================================
    # Filter / search setters
    # =========================================================================

    @rx.event
    def set_shift_filter(self, v: str):
        self.shift_filter = v or "all"

    @rx.event
    def set_search_query(self, v: str):
        self.search_query = v

    # =========================================================================
    # Cell popover
    # =========================================================================

    @rx.event
    def open_cell_popover(self, tm_name: str, shift: str, cell_date: str,
                          value: str, overridden: bool):
        self.popover_open       = True
        self.popover_tm_name    = tm_name
        self.popover_shift      = shift
        self.popover_date       = cell_date
        self.popover_value      = value
        self.popover_overridden = bool(overridden)
        self.popover_note       = ""

    @rx.event
    def close_cell_popover(self):
        self.popover_open = False

    @rx.event
    def set_popover_note(self, v: str):
        self.popover_note = v

    # =========================================================================
    # Cell writes
    # =========================================================================

    def _resolve_tm_id(self, display_name: str) -> str:
        """Look up tm_id by display_name."""
        try:
            for e in database.fetch_all_tms():
                if (e.get("display_name") or "").strip().lower() == display_name.strip().lower():
                    return e.get("id", "") or ""
        except Exception:
            pass
        return ""

    def _write_override(self, value: str):
        """Apply an override to the popover's targeted cell."""
        if not (self.schedule_path and self.popover_tm_name and self.popover_date):
            return
        tm_id = self._resolve_tm_id(self.popover_tm_name)
        if not tm_id:
            self.error = f"Couldn't find TM '{self.popover_tm_name}' in entities."
            return
        ok = database.upsert_schedule_override(
            schedule_path=self.schedule_path,
            tm_id=tm_id,
            shift=self.popover_shift or "graves",
            cell_date=self.popover_date,
            override_value=value,
            note=self.popover_note,
        )
        if not ok:
            self.error = "Failed to save override."
            return
        self.close_cell_popover()
        self._load_grid()

    @rx.event
    def mark_cell_pto(self):
        self._write_override(OV_PTO)

    @rx.event
    def mark_cell_mdl(self):
        self._write_override(OV_MDL)

    @rx.event
    def mark_cell_off(self):
        self._write_override(OV_OFF)

    @rx.event
    def mark_cell_called_off(self):
        """Phase N.4 — write override AND insert into call_offs so deployment
        slots flag the warning immediately."""
        if not self.popover_tm_name or not self.popover_date:
            return
        tm_id = self._resolve_tm_id(self.popover_tm_name)
        if tm_id:
            try:
                database.upsert_schedule_override(
                    schedule_path=self.schedule_path,
                    tm_id=tm_id,
                    shift=self.popover_shift or "graves",
                    cell_date=self.popover_date,
                    override_value=OV_CALLED_OFF,
                    note=self.popover_note,
                )
            except Exception as e:
                self.error = f"Override write failed: {e}"
                return
            try:
                from .database import add_call_off as _add_co
                _add_co(tm_id, self.popover_date, self.popover_note or "Marked from schedule editor")
            except Exception:
                # Non-fatal — override is persisted; call_offs sync best-effort
                pass
        self.close_cell_popover()
        self._load_grid()

    @rx.event
    def reset_cell(self):
        """Remove any override on this cell (back to xlsx value).
        Also removes any call_offs row for the same date if it was
        written by Mark Called Off."""
        if not (self.schedule_path and self.popover_tm_name and self.popover_date):
            return
        tm_id = self._resolve_tm_id(self.popover_tm_name)
        if tm_id:
            database.delete_schedule_override(self.schedule_path, tm_id, self.popover_date)
            try:
                from .database import remove_call_off as _rm_co
                _rm_co(tm_id, self.popover_date)
            except Exception:
                pass
        self.close_cell_popover()
        self._load_grid()

    # =========================================================================
    # Phase O.4 — Unknown-name reconciler
    # =========================================================================

    @rx.event
    def open_reconcile_picker(self, display: str, first: str, shift: str):
        """Phase Q — clicking an unresolved name opens the linker modal."""
        self.reconcile_target_display = display or ""
        self.reconcile_target_first   = first or ""
        self.reconcile_target_shift   = shift or ""
        self.reconcile_match_tm_id    = ""
        self.reconcile_search         = ""

    @rx.event
    def set_reconcile_target(self, display: str):
        """Backward-compat — still callable with just a display name."""
        self.reconcile_target_display = display or ""
        self.reconcile_match_tm_id = ""

    @rx.event
    def set_reconcile_match_tm_id(self, tm_id: str):
        self.reconcile_match_tm_id = tm_id or ""

    @rx.event
    def set_reconcile_search(self, v: str):
        self.reconcile_search = v

    @rx.event
    def cancel_reconcile(self):
        self.reconcile_target_display = ""
        self.reconcile_target_first   = ""
        self.reconcile_target_shift   = ""
        self.reconcile_match_tm_id    = ""
        self.reconcile_search         = ""

    @rx.var
    def filtered_reconcile_options(self) -> list[dict]:
        """Apply the search filter to the entity list for the linker modal."""
        q = (self.reconcile_search or "").strip().lower()
        if not q:
            return self.reconcile_options
        return [o for o in self.reconcile_options
                if q in (o.get("display_name") or "").lower()]

    @rx.event
    def reconcile_create_new(self, display: str, shift: str):
        """Create a new TM entity using the xlsx-derived display name."""
        if not display:
            return
        self.reconcile_saving = True
        try:
            grave_pool = (
                "Grave" if shift == "graves"
                else "PM" if shift == "swings"
                else "AM" if shift == "days"
                else "Grave"
            )
            database.insert_tm_entity(
                display_name=display.strip(),
                grave_pool=grave_pool,
                aliases=[],
            )
        except Exception as e:
            self.error = f"Couldn't create TM: {e}"
            self.reconcile_saving = False
            return
        self.reconcile_saving = False
        # Reload the grid so the new entity resolves and the unresolved list shrinks
        self._load_grid()

    @rx.event
    def reconcile_apply_match(self, first: str):
        """Add the xlsx first-name as an alias on the chosen entity, then
        reload so it resolves on the next pass."""
        if not (first and self.reconcile_match_tm_id):
            return
        self.reconcile_saving = True
        try:
            # Pull current aliases, append the new one
            res = (
                database._client()
                .table("entities")
                .select("metadata")
                .eq("id", self.reconcile_match_tm_id)
                .single()
                .execute()
            )
            meta = (res.data or {}).get("metadata") or {}
            aliases = list(meta.get("aliases") or [])
            new_alias = first.strip().lower()
            if new_alias and new_alias not in aliases:
                aliases.append(new_alias)
            ok = database.update_entity_aliases(self.reconcile_match_tm_id, aliases)
            if not ok:
                self.error = "Couldn't update aliases."
                self.reconcile_saving = False
                return
        except Exception as e:
            self.error = f"Match failed: {e}"
            self.reconcile_saving = False
            return
        self.reconcile_saving = False
        self.reconcile_target_display = ""
        self.reconcile_match_tm_id = ""
        self._load_grid()
