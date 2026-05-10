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
    CardAdhocTask,
    ChangeLogEntry,
    EngineResult,
    Night,
    OverlapRow,
    RRSlot,
    TM,
    Week,
    ZoneSlot,
)

# Print-cache resolution (2026-05-06 — fixed 404):
# Previously we tried to land print HTML inside Reflex's build output
# (.web/build/client/print_cache/) so Caddy's catch-all file_server would
# serve it. That path depended on `reflex export` succeeding AND on Caddy's
# layout matching, which broke in production: when the export failed the
# fallback path (.web/public/) wasn't served at all → 404.
#
# Stable fix: write to <project_root>/print_cache and add an explicit
# Caddyfile handler that serves /print_cache/* from /app/print_cache/.
# Decouples the print output from Reflex's build dir entirely.
# state.py lives at apps/zds/state.py → up 3 to reach project root.
_PROJ_ROOT   = Path(__file__).parent.parent.parent
_PRINT_CACHE = _PROJ_ROOT / "print_cache"


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


def _collapse_card_annotations(raw: dict) -> dict:
    """Collapse raw card-kind annotation rows into a per-card dict.

    The raw grouped data has two ref shapes:
      - "Z9"        → direct card-level annotations (note, priority, …)
      - "Z9:abc123" → composite ref for a single adhoc task

    Returns {card_code: {note?, priority?, adhoc_tasks: [{ref, name}, ...]}}
    so the UI and print renderer never have to know about composite refs.
    """
    out: dict[str, dict] = {}
    for ref, anns in (raw or {}).items():
        if ":" in ref:
            # Composite adhoc task ref
            card_code = ref.split(":", 1)[0]
            adhoc_val = anns.get("adhoc", {})
            if adhoc_val:
                card = out.setdefault(card_code, {})
                tasks = card.setdefault("adhoc_tasks", [])
                tasks.append({"ref": ref, "name": adhoc_val.get("name", "")})
        else:
            # Direct card-level annotation(s)
            card = out.setdefault(ref, {})
            for k, v in anns.items():
                card[k] = v
    # Ensure every entry has the adhoc_tasks key
    for anns in out.values():
        anns.setdefault("adhoc_tasks", [])
    return out


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

    # ── Phase 4i.4 — Task list panel (collapsible, below zone grid) ─────────────
    tasks_panel_open: bool = False          # default collapsed
    night_task_assignments: list[dict] = [] # zone_task_assignments for current night

    def toggle_tasks_panel(self):
        self.tasks_panel_open = not self.tasks_panel_open
        if self.tasks_panel_open and self.current_night_id:
            return ZdsState._load_night_tasks()

    async def _load_night_tasks(self):
        try:
            from shared.db import get_client
            sb = get_client()
            res = (
                sb.table("zone_task_assignments")
                .select(
                    "id,zone_slot,assigned_by,source,"
                    "zone_tasks(name,category,default_zone),"
                    "tm_profiles(display_name)"
                )
                .eq("night_id", self.current_night_id)
                .order("zone_slot")
                .execute()
            )
            rows = []
            for r in (res.data or []):
                task  = r.get("zone_tasks") or {}
                tm    = r.get("tm_profiles") or {}
                rows.append({
                    "id":           r["id"],
                    "zone_slot":    r.get("zone_slot") or "—",
                    "task_name":    task.get("name", ""),
                    "category":     task.get("category", "zone"),
                    "tm_name":      tm.get("display_name") or "Unassigned",
                    "assigned_by":  r.get("assigned_by", "engine"),
                })
            self.night_task_assignments = rows
        except Exception as e:
            print(f"[ZdsState] _load_night_tasks error: {e}")

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
    # Canonical tasks for the currently-open slot (read from overlap_tasks via DB).
    # Read-only side panel in the picker shows these before Brian picks a TM.
    # Empty for zone / RR / aux slots; populated for PMOL / AMOL slots.
    picker_tasks:    list[str] = []

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

    # ── Schedule management panel (Phase N.1) ─────────────────────────────────
    # Full listing of every xlsx in Storage with size + week_ending + linkage.
    managed_schedules: list[dict] = []
    # Two-step delete confirmation
    delete_target_filename: str = ""
    # Replace upload — targets a specific existing filename
    replace_target_filename: str = ""

    # ── Task inline edit ──────────────────────────────────────────────────────
    task_edit_slot_id: str = ""
    task_edit_text:    str = ""

    # ── Task popover (Phase 4k.6) ─────────────────────────────────────────────
    # Click on a task line opens an inline popover anchored below the row.
    # Replaces the right-click JS context menu (4k.3–4k.5).
    task_popover_open:          bool = False
    task_popover_annot_id:      str  = ""      # stable annot_id (UUID or "custom:{lbl}:{hash}")
    task_popover_card_code:     str  = ""      # card code the task lives in
    task_popover_view:          str  = "root"  # root | note | edit_text
    task_popover_note_text:     str  = ""      # live text for note/edit-text subviews
    task_popover_existing_name: str  = ""      # current task name (for edit-text pre-fill)

    # ── Extended picker state — drawer annotation sections (Phase 4k.6) ──────
    # Set by open_picker alongside the existing picker_slot_* vars.
    picker_card_code: str = ""   # card code (= slot label) of the currently open slot
    picker_tm_id:     str = ""   # tm_id of TM currently assigned to that slot ("" if empty)
    picker_tm_name:   str = ""   # display name of that TM
    # Three separate input vars — previously a single shared picker_note_text
    # caused silent cross-contamination between card note, TM note, and adhoc
    # task inputs (bug fixed 2026-05-10).
    picker_card_note_input: str = ""  # card note textarea in picker drawer
    picker_tm_note_input:   str = ""  # TM pre-shift note textarea in picker drawer
    picker_adhoc_input:     str = ""  # ad-hoc task name input in picker drawer

    # Task pool picker (2026-05-10) — inline panel inside zone cards
    task_pool_slot_id:   str = ""       # slot whose pool panel is open ("" = closed)
    task_pool_category:  str = "porter" # "porter" | "am_ol" | "pm_ol"
    # Annotation data for current night: {task_uuid: {annotation_kind: value_dict}}
    # Reloaded each time _load_night runs or after any annotation write.
    task_annotation_data: dict = {}
    # TM annotation data for current night: {tm_id: {annotation_kind: value_dict}}
    # Phase 4k.4 — pre-shift notes + profile-log markers.
    tm_annotation_data: dict = {}
    # Card annotation data for current night.
    # Phase 4k.5 — collapsed from raw "card" grouped annotations.
    # Structure: {card_code: {note?, priority?, adhoc_tasks: [{ref, name}, ...]}}
    card_annotation_data: dict = {}

    @rx.var
    def picker_card_adhoc_tasks(self) -> list[CardAdhocTask]:
        """Adhoc task list for the card currently open in the picker drawer.

        Avoids chained Var subscripts in the component — returns a plain list
        of {ref, name} dicts for the active card_code.

        Typed return matters: Reflex 0.9 needs the TypedDict shape to resolve
        task["name"] / task["ref"] inside rx.foreach lambdas without crashing
        with UntypedVarError.
        """
        if not self.picker_card_code:
            return []
        return self.card_annotation_data.get(self.picker_card_code, {}).get(
            "adhoc_tasks", []
        )

    @rx.var
    def picker_card_has_note(self) -> bool:
        """True when the currently open picker card has a note annotation."""
        if not self.picker_card_code:
            return False
        return bool(
            self.card_annotation_data.get(self.picker_card_code, {}).get("note")
        )

    @rx.var
    def picker_card_saved_note_text(self) -> str:
        """Saved note text for the currently open picker card.

        Returned as a typed `str` so the textarea fallback in tm_picker.py
        doesn't have to chain-subscript card_annotation_data (bare `dict`
        return type → Reflex 0.9 UntypedVarError on nested ["note"]["text"]).
        """
        if not self.picker_card_code:
            return ""
        entry = self.card_annotation_data.get(self.picker_card_code, {})
        note = entry.get("note") or {}
        return note.get("text", "") or ""

    @rx.var
    def picker_card_has_priority(self) -> bool:
        """True when the currently open picker card has a priority annotation."""
        if not self.picker_card_code:
            return False
        return bool(
            self.card_annotation_data.get(self.picker_card_code, {}).get("priority")
        )

    @rx.var
    def picker_tm_has_note(self) -> bool:
        """True when the TM in the open picker slot has a pre-shift note."""
        if not self.picker_tm_id:
            return False
        return bool(
            self.tm_annotation_data.get(self.picker_tm_id, {}).get("note")
        )

    @rx.var
    def picker_tm_note_text(self) -> str:
        """Existing pre-shift note text for the TM in the open picker slot."""
        if not self.picker_tm_id:
            return ""
        return (
            self.tm_annotation_data.get(self.picker_tm_id, {})
            .get("note", {})
            .get("text", "")
        )

    @rx.var
    def task_popover_is_adhoc(self) -> bool:
        """True when the open popover is on an adhoc card-annotation task.

        Adhoc tasks have a composite ref like "Zone 9:abc123" (stored as a
        card annotation). Custom slot tasks use "custom:{label}:{hash}" and
        are NOT adhoc — they're stored in the slot's custom_tasks column and
        can't be deleted via the card-annotation path.
        """
        aid = self.task_popover_annot_id
        return ":" in aid and not aid.startswith("custom:")

    @rx.var
    def task_popover_is_canonical(self) -> bool:
        """True when the open popover is on a canonical zone_task (UUID-keyed).

        Canonical tasks live in the zone_tasks table — editing their text
        changes the name permanently for ALL weeks. Used to show a warning
        in the edit-text subview.
        """
        aid = self.task_popover_annot_id
        return bool(aid) and ":" not in aid

    @rx.var
    def task_popover_is_skipped(self) -> bool:
        """True when the task open in the popover has an active skip annotation."""
        if not self.task_popover_annot_id:
            return False
        return bool(
            self.task_annotation_data.get(self.task_popover_annot_id, {}).get("skip")
        )

    @rx.var
    def task_pool_slot_task_names(self) -> list[str]:
        """Task names currently on the pool-open slot.
        Used to show 'already added' indicators in the task pool panel.
        """
        if not self.task_pool_slot_id:
            return []
        sid = self.task_pool_slot_id
        for s in self.zone_slots + self.aux_slots:
            if s.get("id") == sid:
                return [t.get("name", "") for t in (s.get("display_tasks") or [])]
        for rr in self.rr_slots:
            if rr.get("mens_slot_id") == sid or rr.get("womens_slot_id") == sid:
                return [t.get("name", "") for t in (rr.get("display_tasks") or [])]
        return []

    @rx.var
    def duplicate_task_slots(self) -> dict[str, list[str]]:
        """Map task-name (lowercased) → list of slot labels that have it.
        Only entries with 2+ slots are included.
        Used to build duplicate warning badges.
        """
        name_to_slots: dict[str, list[str]] = {}
        for slot in list(self.zone_slots) + list(self.aux_slots):
            label = slot.get("label") or ""
            for t in (slot.get("display_tasks") or []):
                name = (t.get("name") or "").strip().lower()
                if name:
                    name_to_slots.setdefault(name, []).append(label)
        for rr in self.rr_slots:
            label = rr.get("label") or ""
            for t in (rr.get("display_tasks") or []):
                name = (t.get("name") or "").strip().lower()
                if name:
                    name_to_slots.setdefault(name, []).append(label)
        return {k: v for k, v in name_to_slots.items() if len(v) > 1}

    @rx.var
    def cards_with_duplicate_tasks(self) -> list[str]:
        """Slot labels that have at least one task also assigned to another slot."""
        result: set[str] = set()
        for slots in self.duplicate_task_slots.values():
            for s in slots:
                result.add(s)
        return list(result)

    @rx.var
    def task_popover_existing_note(self) -> str:
        """Existing note text for the task currently open in the popover."""
        if not self.task_popover_annot_id:
            return ""
        return (
            self.task_annotation_data.get(self.task_popover_annot_id, {})
            .get("note", {})
            .get("text", "")
        )

    @rx.var
    def task_popover_existing_highlight(self) -> str:
        """Existing highlight color for the task open in the popover ('' = none)."""
        if not self.task_popover_annot_id:
            return ""
        ann = self.task_annotation_data.get(self.task_popover_annot_id, {})
        return ann.get("highlight", {}).get("color", "")

    @rx.var
    def task_popover_existing_symbol_section(self) -> str:
        """Existing symbol section for the task open in the popover ('' = none).

        Split from a single dict return into two `-> str` computed vars
        because Reflex 0.9 can't reliably subscript a bare-`dict:` Var
        in a component body (renders as raw object → React error #31).
        """
        if not self.task_popover_annot_id:
            return ""
        ann = self.task_annotation_data.get(self.task_popover_annot_id, {})
        return (ann.get("symbol") or {}).get("section", "")

    @rx.var
    def task_popover_existing_symbol_slug(self) -> str:
        """Existing symbol slug for the task open in the popover ('' = none)."""
        if not self.task_popover_annot_id:
            return ""
        ann = self.task_annotation_data.get(self.task_popover_annot_id, {})
        return (ann.get("symbol") or {}).get("slug", "")

    @rx.var
    def card_badge_classes(self) -> dict[str, str]:
        """Map card_code → space-separated CSS badge class string.

        Used by zone_card.py to apply .card-priority / .card-has-note /
        .card-has-adhoc classes to the outer card wrapper.
        Only entries with at least one badge are included.

        Typed return matters: Reflex 0.9 needs dict[str, str] so that
        `tm_badge_classes[tm_id] + " "` resolves cleanly (a bare `dict`
        return crashes with TypeError on the + concat).
        """
        out: dict[str, str] = {}
        for code, anns in (self.card_annotation_data or {}).items():
            parts = []
            if anns.get("priority"):
                parts.append("card-priority")
            if anns.get("note"):
                parts.append("card-has-note")
            if anns.get("adhoc_tasks"):
                parts.append("card-has-adhoc")
            if parts:
                out[code] = " ".join(parts)
        return out

    @rx.var
    def tm_badge_classes(self) -> dict[str, str]:
        """Map tm_id → space-separated CSS badge class string.

        Used by zone_card.py to apply .tm-has-note / .tm-has-profile-log chips.
        Only entries with at least one badge are included (missing key → no badge).

        Typed return matters: Reflex 0.9 needs dict[str, str] so that
        `tm_badge_classes[tm_id] + " "` in zone_card.py resolves cleanly
        (bare `dict` return crashes with TypeError on the + concat).
        """
        out: dict[str, str] = {}
        for tm_id, anns in (self.tm_annotation_data or {}).items():
            parts = []
            if "note" in anns:
                parts.append("tm-has-note")
            if "profile_log" in anns:
                parts.append("tm-has-profile-log")
            if parts:
                out[tm_id] = " ".join(parts)
        return out

    @rx.var
    def task_class_map(self) -> dict[str, str]:
        """Map task_id → space-separated CSS class string for live-page rendering.

        Emits task-hl-{color} when a highlight annotation is present, and
        task-skip when a skip annotation is present. Only annotated tasks appear
        in the map; missing key means no extra classes.

        Phase 4k.6 hotfix: restores annotation visibility on the live page
        (zone_card.py foreach consumes this via .contains() guard).
        """
        out: dict[str, str] = {}
        for task_id, anns in (self.task_annotation_data or {}).items():
            parts = []
            hl = (anns.get("highlight") or {}).get("color", "")
            if hl:
                parts.append(f"task-hl-{hl}")
            if anns.get("skip"):
                parts.append("task-skip")
            if parts:
                out[task_id] = " ".join(parts)
        return out

    @rx.var
    def task_symbol_url(self) -> dict[str, str]:
        """Map annot_id → static asset URL for the task symbol icon SVG.

        Returns the pre-existing SVG path under /assets/icons/glcr/{section}/{slug}.svg.
        Using a static URL with rx.image is more reliable in Reflex 0.9 than
        rx.html(Var) with dict-subscript content (which drops dangerouslySetInnerHTML
        silently). Icons render as <img> — no currentColor inheritance, so they
        appear in default black stroke; acceptable for v1.

        Phase 4k.7: replaces task_symbol_html.
        """
        out: dict[str, str] = {}
        for annot_id, anns in (self.task_annotation_data or {}).items():
            sym     = anns.get("symbol") or {}
            section = sym.get("section", "")
            slug    = sym.get("slug", "")
            if section and slug:
                out[annot_id] = f"/assets/icons/glcr/{section}/{slug}.svg"
        return out

    @rx.var
    def task_note_text_map(self) -> dict[str, str]:
        """Map task_id → note text for tasks that have a note annotation.

        Used by zone_card.py to show a brief italic note preview inline.
        Only tasks with non-empty note text appear in the map.

        Phase 4k.6 hotfix: note text now renders inline on the live page.
        """
        out: dict[str, str] = {}
        for task_id, anns in (self.task_annotation_data or {}).items():
            text = (anns.get("note") or {}).get("text", "")
            if text:
                out[task_id] = text
        return out

    # ── Loading / error ───────────────────────────────────────────────────────
    loading: bool = False
    error:   str = ""

    # ── Theme (dark/light toggle) ─────────────────────────────────────────────
    # "dark" → dark mode. "light" → light mode (default).
    # data-theme is set on <html> by _THEME_INIT_SCRIPT and kept in sync by
    # toggle_theme via rx.call_script — no Reflex DOM binding needed on the
    # page wrapper. LocalStorage key: "glcr-theme" (migrated from "theme").
    theme: str = rx.LocalStorage("light", name="glcr-theme")

    # ── Audit strip ───────────────────────────────────────────────────────────
    # ISO timestamp of the last successful write this session; drives the
    # audit strip's "Saved {time}" indicator.
    last_saved_at: str = ""

    # ── Night-level lock (Phase D) ────────────────────────────────────────────
    # True while the unlock-confirm dialog is shown.
    night_lock_confirm_open: bool = False

    # ── Notices form (Phase E) ────────────────────────────────────────────────
    # Add-notice dialog state — opened via the context menu "Add Notice" item.
    notice_form_open:     bool = False
    notice_form_slot_key: str  = ""
    notice_form_type:     str  = "alert"   # "alert"|"info"|"training"|"meeting"
    notice_form_text:     str  = ""

    # ── Audit banner (tracks user-driven mutations for the session) ───────────
    # Newest-first; capped at 100 entries via _log_change.
    change_log:      list[ChangeLogEntry] = []
    banner_expanded: bool = False

    def set_error(self, msg: str):
        self.error = msg

    def toggle_theme(self):
        """Toggle between dark and light mode.

        Updates the Python state (which Reflex persists via LocalStorage
        key "glcr-theme") and emits a script to stamp data-theme on <html>
        immediately so CSS token selectors re-resolve without a page reload.
        """
        new_theme = "light" if self.theme == "dark" else "dark"
        self.theme = new_theme
        return rx.call_script(
            f"document.documentElement.setAttribute('data-theme', '{new_theme}');"
        )

    # ── Night-level lock handlers (Phase D) ───────────────────────────────────

    @rx.event
    async def toggle_night_lock(self):
        """Lock or unlock the current night.

        Requires zds_editor role.
        • Locking is immediate.
        • Unlocking opens the confirm dialog (night_lock_confirm_open = True).
        """
        from shared.auth import AuthState
        auth = await self.get_state(AuthState)
        if auth.editor_role not in ("zds_editor", "editor"):
            self.error = "You need editor access to lock/unlock nights."
            return
        night = next(
            (n for n in self.nights if n["id"] == self.current_night_id), {}
        )
        if not night:
            return
        if night.get("is_locked", False):
            # Unlocking — ask for confirmation first
            self.night_lock_confirm_open = True
        else:
            # Locking — apply immediately
            try:
                database.update_night_lock(
                    self.current_night_id, True, auth.editor_email
                )
                updated = database.fetch_nights(self.current_week_id)
                self.nights = _enrich_nights(updated)
            except Exception as e:
                self.error = str(e)

    @rx.event
    async def confirm_night_unlock(self):
        """Called from the unlock confirm dialog — actually clears the lock."""
        from shared.auth import AuthState
        auth = await self.get_state(AuthState)
        try:
            database.update_night_lock(
                self.current_night_id, False, auth.editor_email
            )
            updated = database.fetch_nights(self.current_week_id)
            self.nights = _enrich_nights(updated)
        except Exception as e:
            self.error = str(e)
        self.night_lock_confirm_open = False

    @rx.event
    def cancel_night_unlock(self):
        """Dismiss the unlock confirm dialog without making changes."""
        self.night_lock_confirm_open = False

    # ── Notice handlers (Phase E) ─────────────────────────────────────────────

    @rx.event
    def open_notice_form(self, slot_key: str):
        """Open the Add Notice dialog pre-filled for `slot_key`."""
        self.notice_form_slot_key = slot_key
        self.notice_form_type     = "alert"
        self.notice_form_text     = ""
        self.notice_form_open     = True

    @rx.event
    def close_notice_form(self):
        self.notice_form_open = False

    @rx.event
    def set_notice_type(self, t: str):
        self.notice_form_type = t

    @rx.event
    def set_notice_text(self, t: str):
        self.notice_form_text = t

    @rx.event
    async def submit_notice(self):
        """Persist the notice and reload slot data for the current night."""
        if not self.notice_form_slot_key:
            self.notice_form_open = False
            return
        from shared.auth import AuthState
        auth = await self.get_state(AuthState)
        if auth.editor_role not in ("zds_editor", "editor"):
            self.error = "You need editor access to add notices."
            self.notice_form_open = False
            return
        try:
            database.create_notice(
                night_id    = self.current_night_id,
                slot_key    = self.notice_form_slot_key,
                notice_type = self.notice_form_type,
                text        = self.notice_form_text,
                created_by  = auth.editor_email,
            )
            self._load_night(self.current_night_id)
        except Exception as e:
            self.error = str(e)
        self.notice_form_open = False

    @rx.event
    async def delete_notice(self, notice_id: str):
        """Remove a notice by ID and reload."""
        from shared.auth import AuthState
        auth = await self.get_state(AuthState)
        if auth.editor_role not in ("zds_editor", "editor"):
            self.error = "You need editor access to remove notices."
            return
        try:
            database.delete_notice(notice_id)
            self._load_night(self.current_night_id)
        except Exception as e:
            self.error = str(e)

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
    def current_night_is_locked(self) -> bool:
        """True when the active night has a night-level lock set."""
        for n in self.nights:
            if n["id"] == self.current_night_id:
                return bool(n.get("is_locked", False))
        return False

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
        # Hotfix: filter on group_num (sourced from BG_ZONE/BG_RR_M/BG_RR_W/BG_AUX maps).
        # break_wave is intentionally hardcoded to 1 in _do_engine_night() as Phase 4d
        # scaffolding for future sub-wave subdivision — do NOT read it here.
        return _mark_section_headers(
            [r for r in self.break_rows if r["group_num"] == 1]
        )

    @rx.var
    def break_wave_2(self) -> list[BreakRow]:
        return _mark_section_headers(
            [r for r in self.break_rows if r["group_num"] == 2]
        )

    @rx.var
    def break_wave_3(self) -> list[BreakRow]:
        return _mark_section_headers(
            [r for r in self.break_rows if r["group_num"] == 3]
        )

    @rx.var
    def schedule_loaded(self) -> bool:
        """True when schedule pool data has been parsed."""
        return bool(self.schedule_pools)

    # ── Phase R — at-a-glance summary stats for the open night ───────────────

    @rx.var
    def night_filled_count(self) -> int:
        n = 0
        for s in self.zone_slots + self.aux_slots:
            if s.get("is_filled"):
                n += 1
        for rr in self.rr_slots:
            if rr.get("mens_is_filled"):
                n += 1
            if rr.get("womens_is_filled"):
                n += 1
        return n

    @rx.var
    def night_total_count(self) -> int:
        # Each RR slot contributes 2 (mens + womens)
        return len(self.zone_slots) + len(self.aux_slots) + (len(self.rr_slots) * 2)

    @rx.var
    def night_locked_count(self) -> int:
        n = 0
        for s in self.zone_slots + self.aux_slots:
            if s.get("is_locked"):
                n += 1
        for rr in self.rr_slots:
            if rr.get("mens_is_locked"):
                n += 1
            if rr.get("womens_is_locked"):
                n += 1
        return n

    @rx.var
    def night_warning_count(self) -> int:
        """Slots with called-off, not-scheduled, or duplicate flags."""
        n = 0
        for s in self.zone_slots + self.aux_slots:
            ws = s.get("warning_status") or ""
            if ws in ("called_off", "not_scheduled"):
                n += 1
            if s.get("has_duplicate"):
                n += 1
        for rr in self.rr_slots:
            for side in ("mens", "womens"):
                ws = rr.get(f"{side}_warning_status") or ""
                if ws in ("called_off", "not_scheduled"):
                    n += 1
                if rr.get(f"{side}_has_duplicate"):
                    n += 1
        return n

    @rx.var
    def night_fill_pct(self) -> int:
        """Filled percentage 0-100 for the progress bar."""
        total = self.night_total_count
        if total <= 0:
            return 0
        return int((self.night_filled_count * 100) / total)

    @rx.var
    def unplaced_scheduled_tms(self) -> list[str]:
        """Phase Q.5 — TMs scheduled tonight (any pool) who aren't yet assigned
        to any zone/RR/aux slot. Surfaces as a banner above the deployment grid
        so Brian can see who still needs a spot.

        Excludes TMs marked called-off for this night.
        """
        scheduled: set[str] = set()
        for name in self.night_grave_pool:
            if name:
                scheduled.add(name)
        for name in self.night_pm_ol_pool:
            if name:
                scheduled.add(name)
        for name in self.night_am_ol_pool:
            if name:
                scheduled.add(name)
        # Drop call-offs — they're not expected to be placed
        called_off = set(self.night_called_off)
        scheduled -= called_off

        # Subtract anyone already deployed
        deployed: set[str] = set()
        for s in self.zone_slots + self.aux_slots:
            n = (s.get("display_name") or s.get("tm_name") or "").strip()
            if n and n != "Unfilled":
                deployed.add(n)
        for rr in self.rr_slots:
            for side in ("mens", "womens"):
                n = (rr.get(f"{side}_name") or "").strip()
                if n and n != "Unfilled":
                    deployed.add(n)
        # Also exclude PM/AM overlap TMs if they're placed in overlap_assignments
        for ol in self.overlap_rows:
            n = (ol.get("tm_name") or "").strip()
            if n:
                deployed.add(n)

        return sorted(scheduled - deployed, key=lambda s: s.lower())

    @rx.var
    def unplaced_scheduled_count(self) -> int:
        return len(self.unplaced_scheduled_tms)

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

    @rx.var
    def current_week_schedule_url(self) -> str:
        """Phase N.2 — Link to the dedicated Week Schedule editor."""
        return f"/zds/week/{self.current_week_id}/schedule"

    @rx.var
    def active_week_id(self) -> str:
        """Return the id of whichever week in self.weeks contains today's date.

        Used by the index page to highlight the current-shift week with a
        'current' badge. Returns "" if no week covers today (e.g. between
        scheduled weeks or if weeks haven't loaded yet).

        Week cadence is Fri–Thu ending on Thursday (week_ending). A week
        starting on a given Friday ends 6 days later on Thursday.
        """
        from datetime import date, timedelta
        today = date.today().isoformat()
        for w in self.weeks:
            we = (w.get("week_ending") or "")
            if not we:
                continue
            try:
                end   = date.fromisoformat(we)
                start = (end - timedelta(days=6)).isoformat()
                if start <= today <= we:
                    return w.get("id") or ""
            except Exception:
                pass
        return ""

    @rx.var
    def today_iso(self) -> str:
        """Today's date as YYYY-MM-DD string.

        Used by night_tabs to show a dot indicator on the tab that
        corresponds to tonight's shift.
        """
        from datetime import date
        return date.today().isoformat()

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
            # Phase N.1 — managed schedules panel
            try:
                self.load_managed_schedules()
            except Exception as ex:
                print(f"[load_weeks] load_managed_schedules: {ex}")
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

    # ── Schedule management (Phase N.1) ───────────────────────────────────────

    def load_managed_schedules(self):
        """Refresh the Manage Schedules panel — pulls Storage list, joins
        each filename with any week record that links to it, and parses
        week_ending from the xlsx where possible."""
        from shared import storage
        from . import schedule_parser
        try:
            files = storage.list_schedules()
        except Exception as exc:
            self.error = f"Couldn't list schedules: {exc}"
            return

        # Index existing weeks by schedule_path so we can show which file
        # is linked to which week.
        try:
            weeks = database.fetch_weeks()
        except Exception:
            weeks = []
        weeks_by_path: dict[str, dict] = {
            w["schedule_path"]: w for w in weeks if w.get("schedule_path")
        }

        sb_client = None
        try:
            from shared.db import get_client
            sb_client = get_client()
        except Exception:
            pass

        rows = []
        for f in files:
            name = f.get("name", "")
            if not name or name.startswith("."):
                continue
            size_bytes = (f.get("metadata") or {}).get("size", 0)
            updated_at = f.get("updated_at", "") or f.get("created_at", "")

            # Best-effort parse of the week_ending from the xlsx (peek only)
            week_ending = ""
            try:
                if sb_client is not None:
                    blob: bytes = sb_client.storage.from_("schedules").download(name)
                    peek = schedule_parser.peek_schedule_dates(blob)
                    if peek:
                        week_ending = peek["week_ending"]
            except Exception:
                pass

            linked_week = weeks_by_path.get(name)
            rows.append({
                "filename":     name,
                "size_bytes":   int(size_bytes or 0),
                "updated_at":   updated_at[:10] if updated_at else "",
                "week_ending":  week_ending,
                "linked_week_id":    (linked_week or {}).get("id", ""),
                "linked_week_label": (linked_week or {}).get("label", "") or week_ending,
            })

        # Sort by week_ending desc, then filename
        rows.sort(key=lambda r: (r["week_ending"] or "", r["filename"]), reverse=True)
        self.managed_schedules = rows

    def request_delete_schedule(self, filename: str):
        """Open the delete confirmation by setting the target filename."""
        self.delete_target_filename = filename or ""

    def cancel_delete_schedule(self):
        self.delete_target_filename = ""

    def confirm_delete_schedule(self):
        """Actually delete: drop from Storage, clear any week.schedule_path
        pointing at it, wipe schedule_overrides for the file."""
        filename = self.delete_target_filename
        if not filename:
            return
        from shared import storage
        try:
            storage.delete_schedule(filename)
        except Exception as exc:
            self.error = f"Storage delete failed: {exc}"
            self.delete_target_filename = ""
            return

        # Clear linkages
        try:
            for w in database.fetch_weeks():
                if w.get("schedule_path") == filename:
                    database.update_week_schedule_path(w["id"], "")
        except Exception:
            pass
        try:
            database.delete_overrides_for_schedule(filename)
        except Exception:
            pass

        self.delete_target_filename = ""
        # Refresh both lists so the UI reflects reality
        self.load_managed_schedules()
        try:
            self.unlinked_schedules = database.list_unlinked_schedules()
            self.weeks = database.fetch_weeks()
        except Exception:
            pass

    def request_replace_schedule(self, filename: str):
        """Stage a replace-upload targeting a specific filename. The actual
        upload widget reads this; if set, the next upload OVERWRITES this
        filename instead of using the dropped file's own name."""
        self.replace_target_filename = filename or ""

    def cancel_replace_schedule(self):
        self.replace_target_filename = ""

    # ── Unlink + Reset (Phase P) ──────────────────────────────────────────────

    def unlink_schedule_from_week(self, week_id: str):
        """Clear the schedule_path link on a week."""
        if not week_id:
            return
        try:
            database.unlink_schedule_from_week(week_id)
        except Exception as e:
            self.error = f"Couldn't unlink: {e}"
            return
        # Refresh both lists so badges update
        try:
            self.weeks = database.fetch_weeks()
            self.unlinked_schedules = database.list_unlinked_schedules()
            self.load_managed_schedules()
        except Exception:
            pass

    # State for the "Reset from new schedule upload" modal
    reset_week_open:        bool = False
    reset_week_target_id:   str  = ""
    reset_week_target_label: str = ""

    def open_reset_week_modal(self, week_id: str, label: str = ""):
        """Open the modal for replacing a week's schedule with a fresh upload."""
        if not week_id:
            return
        self.reset_week_open = True
        self.reset_week_target_id = week_id
        self.reset_week_target_label = label or week_id[:8]
        # The next upload will OVERWRITE / link to this week. We re-purpose
        # replace_target_filename below if the week already had a file.
        for w in self.weeks:
            if w["id"] == week_id:
                self.replace_target_filename = w.get("schedule_path") or ""
                break

    def close_reset_week_modal(self):
        self.reset_week_open = False
        self.reset_week_target_id = ""
        self.reset_week_target_label = ""
        self.replace_target_filename = ""

    async def handle_reset_week_upload(self, files: list[rx.UploadFile]):
        """Phase P — drop a new xlsx onto the reset modal:
          1. Save to Storage (overwrites if same filename, else creates)
          2. Link the week to this new filename
          3. Clear all zone_assignments + overrides on the week
        """
        from . import schedule_parser
        from shared import storage

        if not files or not self.reset_week_target_id:
            return

        upload_dir = schedule_parser.SCHEDULE_DIR
        upload_dir.mkdir(parents=True, exist_ok=True)
        new_filename = ""
        for file in files:
            data = await file.read()
            new_filename = file.filename
            (upload_dir / new_filename).write_bytes(data)
            try:
                storage.upload_schedule(new_filename, data)
            except Exception as exc:
                self.error = f"Storage upload failed: {exc}"
                return

        # Old schedule_path so we can wipe its overrides
        old_path = ""
        for w in self.weeks:
            if w["id"] == self.reset_week_target_id:
                old_path = w.get("schedule_path") or ""
                break

        try:
            # 1. Link week to new file
            database.update_week_schedule_path(self.reset_week_target_id, new_filename)
            # 2. Wipe overrides for the OLD schedule_path
            if old_path and old_path != new_filename:
                database.delete_overrides_for_schedule(old_path)
            # 3. Clear all zone_assignments on this week
            cleared = database.reset_week_placements(self.reset_week_target_id)
            self.error = ""  # success — clear any previous error banner
            print(f"[reset_week] linked {new_filename}, cleared {cleared} slots")
        except Exception as e:
            self.error = f"Reset failed: {e}"
            return

        # Refresh + close modal
        self._reload_schedule()
        try:
            self.weeks = database.fetch_weeks()
            self.unlinked_schedules = database.list_unlinked_schedules()
            self.load_managed_schedules()
        except Exception:
            pass
        self.close_reset_week_modal()

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
        # Phase R — stamp at-a-glance stats on each night so the overview
        # cards can render fill / locked / warnings without separate fetches.
        try:
            stats_by_id = database.fetch_week_night_stats(week_id)
            for n in self.nights:
                s = stats_by_id.get(n["id"], {})
                n["stat_filled"]     = int(s.get("filled", 0))
                n["stat_total"]      = int(s.get("total", 0))
                n["stat_unfilled"]   = int(s.get("unfilled", 0))
                n["stat_locked"]     = int(s.get("locked", 0))
                n["stat_called_off"] = int(s.get("called_off", 0))
        except Exception as exc:
            print(f"[on_week_overview_load] stats: {exc}")
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
        """Load/refresh schedule pool data for the current week's schedule file.

        Uses get_active_schedule_path() (week-id-aware, Phase A fix) instead of
        the legacy mtime-newest get_latest_schedule_path().  Opening a new week
        no longer pulls in last week's file and produces empty pools for tonight.
        """
        from . import schedule_parser
        try:
            entities = database.fetch_all_tms()
            # Phase A fix: resolve the correct xlsx for THIS week, not just the
            # most-recently-modified file on disk.
            path = schedule_parser.get_active_schedule_path(self.current_week_id)
            pools = schedule_parser.parse_daily_pools(entities, schedule_path=path)
            self.schedule_pools = pools
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
        replace_name = self.replace_target_filename
        for file in files:
            upload_data = await file.read()
            # If the user clicked Replace on a specific row, use THAT filename
            # for the upload — overwrites the existing xlsx in Storage.
            target_name = replace_name if replace_name else file.filename
            # 1. Local copy — used immediately by the parser below.
            dest = upload_dir / target_name
            dest.write_bytes(upload_data)
            # 2. Persist to Supabase Storage — survives container restarts.
            try:
                storage.upload_schedule(target_name, upload_data)
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
                            database.update_week_schedule_path(w["id"], target_name)
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
        # Phase N.1 — refresh managed schedules + clear any active replace target
        self.replace_target_filename = ""
        try:
            self.load_managed_schedules()
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
        import traceback, time as _t
        _PRINT_CACHE.mkdir(parents=True, exist_ok=True)
        from .print_renderer import render_night_html
        ts = int(_t.time())
        fname = f"night_{night_id}_{ts}.html"
        try:
            html = render_night_html(night_id)
            (_PRINT_CACHE / fname).write_text(html, encoding="utf-8")
            url = f"/print_cache/{fname}"
            return rx.call_script(f"window.open('{url}', '_blank')")
        except Exception as e:
            traceback.print_exc()
            err_msg = str(e).replace("'", "\\'")
            self.error = f"Print error: {e}"
            err_html = (f"<html><body style='font-family:monospace;padding:2em'>"
                        f"<h2 style='color:#dc2626'>Print render failed</h2>"
                        f"<pre>{err_msg}</pre></body></html>")
            (_PRINT_CACHE / fname).write_text(err_html, encoding="utf-8")
            return rx.call_script(f"window.open('/print_cache/{fname}', '_blank')")

    def open_print_current_night(self):
        """Generate and open a 2-page print view for the currently-loaded night."""
        import traceback, time as _t
        _PRINT_CACHE.mkdir(parents=True, exist_ok=True)
        from .print_renderer import render_night_html
        night_id = self.current_night_id
        ts = int(_t.time())
        fname = f"night_{night_id}_{ts}.html"
        try:
            html = render_night_html(night_id)
            (_PRINT_CACHE / fname).write_text(html, encoding="utf-8")
            url = f"/print_cache/{fname}"
            return rx.call_script(f"window.open('{url}', '_blank')")
        except Exception as e:
            traceback.print_exc()
            err_msg = str(e).replace("'", "\\'")
            self.error = f"Print error: {e}"
            err_html = (f"<html><body style='font-family:monospace;padding:2em'>"
                        f"<h2 style='color:#dc2626'>Print render failed</h2>"
                        f"<pre>{err_msg}</pre></body></html>")
            (_PRINT_CACHE / fname).write_text(err_html, encoding="utf-8")
            return rx.call_script(f"window.open('/print_cache/{fname}', '_blank')")

    def open_print_current_week(self):
        """Generate and open a 14-page print view for the current week."""
        import traceback, time as _t
        _PRINT_CACHE.mkdir(parents=True, exist_ok=True)
        from .print_renderer import render_week_html
        week_id = self.current_week_id
        ts = int(_t.time())
        fname = f"week_{week_id}_{ts}.html"
        try:
            html = render_week_html(week_id)
            (_PRINT_CACHE / fname).write_text(html, encoding="utf-8")
            url = f"/print_cache/{fname}"
            return rx.call_script(f"window.open('{url}', '_blank')")
        except Exception as e:
            traceback.print_exc()
            err_msg = str(e).replace("'", "\\'")
            self.error = f"Print error: {e}"
            err_html = (f"<html><body style='font-family:monospace;padding:2em'>"
                        f"<h2 style='color:#dc2626'>Print render failed</h2>"
                        f"<pre>{err_msg}</pre></body></html>")
            (_PRINT_CACHE / fname).write_text(err_html, encoding="utf-8")
            return rx.call_script(f"window.open('/print_cache/{fname}', '_blank')")

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
            # Phase E — enrich slots with their notices
            _raw_notices = database.fetch_notices(night_id)
            _notices_by_key: dict[str, list] = {}
            for _n in _raw_notices:
                _notices_by_key.setdefault(_n["slot_key"], []).append(_n)
            for _s in all_slots:
                _s["notices"] = _notices_by_key.get(_s["slot_key"], [])
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

            # ── Hotfix: guarantee all 12 canonical overlap slots are present ─────
            # fetch_overlap_assignments only returns rows the engine wrote; unfilled
            # slots are absent, so PMOL/AMOL cards never render for empty positions.
            # Source canonical slots from zone_tasks (Phase 4k.1) and pad any missing
            # positions with clickable placeholder rows.
            from shared.db import list_tasks as _list_tasks
            _canonical: list[dict] = []
            for _cat, _win in (("overlap_pm", "pm"), ("overlap_am", "am")):
                for _t in _list_tasks(category=_cat):
                    # Extract trailing digit(s) from code (e.g. "PMOL3" → 3, "AMOL6" → 6)
                    _digits = "".join(c for c in _t.get("code", "") if c.isdigit())
                    _pos = int(_digits) if _digits else 0
                    if _pos:
                        _canonical.append({
                            "window":   _win,
                            "position": _pos,
                            "task":     _t.get("name") or "",
                        })
            _filled = {
                (r["overlap_window"], r["position"]): r
                for r in self.overlap_rows
            }
            _padded: list[OverlapRow] = []
            for _c in sorted(_canonical, key=lambda x: (x["window"], x["position"])):
                _key = (_c["window"], _c["position"])
                if _key in _filled:
                    # Engine-placed row — keep it; backfill task text if blank
                    _row = dict(_filled[_key])
                    if not _row.get("task"):
                        _row["task"] = _c["task"]
                    _padded.append(_row)  # type: ignore[arg-type]
                else:
                    # Empty slot — placeholder that opens the picker on click
                    _padded.append({             # type: ignore[arg-type]
                        "id":             "",
                        "overlap_window": _c["window"],
                        "position":       _c["position"],
                        "is_filled":      False,
                        "task":           _c["task"],
                        "tm_id":          "",
                        "tm_name":        "",
                    })
            if _padded:
                self.overlap_rows = _padded
            # ─────────────────────────────────────────────────────────────────────

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
            # Phase 4k.3 — load task annotations for this night's day
            self._load_task_annotations()
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
        self.tm_search            = ""
        self.picker_card_note_input = ""
        self.picker_tm_note_input   = ""
        self.picker_adhoc_input     = ""
        # Phase 4k.6 — resolve card code (= slot label) and currently-assigned TM.
        # The card code is the label itself (e.g. "Zone 1", "RR 1 + 2", "Admin").
        # For RR sides the label is e.g. "RR 1 + 2 M" — strip the side suffix so
        # it matches the card annotation key from ZONE_LABELS.
        import re as _re
        card_code = _re.sub(r"\s+[MWmw]$", "", label).strip()
        self.picker_card_code = card_code
        # Look up the TM currently in this slot from loaded slot data.
        assigned_tm_id   = ""
        assigned_tm_name = ""
        for s in self.zone_slots:
            if s.get("id") == slot_id:
                assigned_tm_id   = s.get("tm_id", "")
                assigned_tm_name = s.get("display_name", "")
                break
        if not assigned_tm_id:
            for s in self.aux_slots:
                if s.get("id") == slot_id:
                    assigned_tm_id   = s.get("tm_id", "")
                    assigned_tm_name = s.get("display_name", "")
                    break
        if not assigned_tm_id:
            for rr in self.rr_slots:
                if rr.get("mens_slot_id") == slot_id:
                    assigned_tm_id   = rr.get("mens_tm_id", "")
                    assigned_tm_name = rr.get("mens_name", "")
                    break
                if rr.get("womens_slot_id") == slot_id:
                    assigned_tm_id   = rr.get("womens_tm_id", "")
                    assigned_tm_name = rr.get("womens_name", "")
                    break
        # Filter out placeholder "Unfilled" display names
        if assigned_tm_name in ("Unfilled", ""):
            assigned_tm_id   = ""
            assigned_tm_name = ""
        self.picker_tm_id   = assigned_tm_id
        self.picker_tm_name = assigned_tm_name
        # Load canonical tasks for the slot (overlap_tasks table).
        # Non-fatal: zone / RR / aux slots return [] which shows the empty state.
        try:
            from shared.db import get_canonical_tasks_for_slot
            self.picker_tasks = get_canonical_tasks_for_slot(slot_key)
        except Exception:
            self.picker_tasks = []
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

    def open_overlap_picker(self, slot_id: str, window: str, position: int):
        """Phase 4g convenience handler — open the TM picker for a PM/AM overlap slot.
        Derives slot_key from window ('pm'|'am') + position (1–6) and delegates to open_picker."""
        prefix    = "PMOL" if window == "pm" else "AMOL"
        slot_key  = f"{prefix}{position}"
        win_label = "PM Overlap" if window == "pm" else "AM Overlap"
        label     = f"{win_label} {position}"
        self.open_picker(slot_id, slot_key, "", label)

    def close_picker(self):
        self.show_picker = False
        self.picker_slot_id   = ""
        self.picker_card_code = ""
        self.picker_tm_id           = ""
        self.picker_tm_name         = ""
        self.picker_card_note_input = ""
        self.picker_tm_note_input   = ""
        self.picker_adhoc_input     = ""
        self.tm_search              = ""
        self.picker_tasks           = []

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
        # Stamp last_saved_at for the audit strip — "Saved {HH:MM}" indicator
        self.last_saved_at = datetime.datetime.now().strftime("%I:%M %p").lstrip("0")

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
        # Night-level lock guard (Phase D)
        if self.current_night_is_locked:
            self.error = "This night is locked. Unlock it before making changes."
            self.close_picker()
            return
        slot_id = self.picker_slot_id   # capture before close_picker resets it
        # Guard: refuse to overwrite a slot-locked slot
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
        # Night-level lock guard (Phase D)
        if self.current_night_is_locked:
            self.error = "This night is locked. Unlock it before making changes."
            self.close_picker()
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
        """Mark a TM as called off for the currently-open night.

        Writes to two tables:
          - call_offs (Phase J) — drives UI warning badges and Schedule tab strikethrough
          - engine_overrides (Phase C.2) — type='unavailable'; consumed by fill_engine
            so the TM is hard-filtered from the candidate pool when the engine runs.
        """
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
            # Phase C.2 — mirror to engine_overrides so fill_engine hard-filters this TM.
            # Guard: ensure a tm_profiles row exists first. The call-off UI is
            # entity-driven (anyone in entities can be called off), but
            # engine_overrides.tm_id has an FK to tm_profiles. Without this
            # guard, calling off any entity-only TM silently fails the engine
            # mirror (caught here, logged, but engine never excluded the TM).
            # ensure_tm_profile_exists is idempotent — no-op if profile exists.
            if self.current_week_id:
                try:
                    from shared.db import ensure_tm_profile_exists, set_engine_override
                    ensure_tm_profile_exists(tm_id, source="mark_called_off")
                    set_engine_override(
                        week_id=self.current_week_id,
                        tm_id=tm_id,
                        override_date=night_date,
                        override_type="unavailable",
                        payload={"reason": reason or "called_off"},
                        note=reason or None,
                        created_by="supervisor",
                    )
                except Exception as oe:
                    # Non-fatal — call_off is already written; log and continue.
                    print(f"[mark_called_off] engine_overrides write failed: {oe}")
            # Refresh — will recompute warning_status on every slot too
            self._load_night(self.current_night_id)
        except Exception as e:
            self.error = str(e)

    def unmark_called_off(self, tm_id: str):
        """Remove a call-off mark for the currently-open night.

        Removes from both call_offs and engine_overrides (unavailable).
        """
        night_date = ""
        for n in self.nights:
            if n["id"] == self.current_night_id:
                night_date = n.get("night_date", "")
                break
        if not night_date or not tm_id:
            return
        try:
            database.remove_call_off(tm_id, night_date)
            # Phase C.2 — remove the matching engine_overrides row
            if self.current_week_id:
                try:
                    from shared.db import clear_engine_override
                    clear_engine_override(
                        week_id=self.current_week_id,
                        tm_id=tm_id,
                        override_date=night_date,
                        override_type="unavailable",
                    )
                except Exception as oe:
                    print(f"[unmark_called_off] engine_overrides clear failed: {oe}")
            self._load_night(self.current_night_id)
        except Exception as e:
            self.error = str(e)

    @rx.event
    async def clear_slot(self, slot_id: str):
        # Night-level lock guard (Phase D)
        if self.current_night_is_locked:
            self.error = "This night is locked. Unlock it before making changes."
            return
        # Guard: refuse to clear a slot-locked slot
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
                # Queue undo — lets the toast restore the cleared TM
                from shared.state.undo import UndoState
                undo = await self.get_state(UndoState)
                undo.queue(
                    f"Cleared {prev_tm_name} from {target_label}",
                    "restore_assignment",
                    {
                        "slot_id": slot_id,
                        "tm_id":   prev_tm_id,
                        "night_id": self.current_night_id,
                    },
                )
        except Exception as e:
            self.error = str(e)

    @rx.event
    async def toggle_slot_lock(self, slot_id: str):
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
            # Queue undo — lets the toast restore the previous lock state
            from shared.state.undo import UndoState
            undo = await self.get_state(UndoState)
            undo.queue(
                f"{'Locked' if new_state else 'Unlocked'} {target_label}",
                "restore_lock",
                {
                    "slot_id":   slot_id,
                    "prev_lock": current,
                    "night_id":  self.current_night_id,
                },
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

    # =========================================================================
    # Task annotation menu (Phase 4k.3)
    # =========================================================================

    def _current_day_key(self) -> str:
        """Return the 3-letter lowercase day key for the current night (fri/sat/…)."""
        _day_map = {
            "Friday": "fri", "Saturday": "sat", "Sunday": "sun",
            "Monday": "mon", "Tuesday": "tue", "Wednesday": "wed", "Thursday": "thu",
        }
        for n in self.nights:
            if n["id"] == self.current_night_id:
                day_name = n.get("day_name", "")
                return _day_map.get(day_name, day_name[:3].lower() if day_name else "fri")
        return "fri"

    def _load_task_annotations(self):
        """Load zds_annotations for the current night into task_annotation_data,
        tm_annotation_data (Phase 4k.4), and card_annotation_data (Phase 4k.5).
        """
        from shared.db import list_annotations_grouped
        week_ending = self.week_info.get("week_ending", "")
        day = self._current_day_key()
        if not week_ending:
            self.task_annotation_data = {}
            self.tm_annotation_data   = {}
            self.card_annotation_data = {}
            return
        try:
            grouped = list_annotations_grouped(week_ending, day)
            # grouped = {target_kind: {target_ref: {annotation_kind: value}}}
            self.task_annotation_data = grouped.get("task", {})
            self.tm_annotation_data   = grouped.get("tm",   {})
            self.card_annotation_data = _collapse_card_annotations(
                grouped.get("card", {})
            )
        except Exception as exc:
            print(f"[ZdsState] _load_task_annotations error: {exc}")
            self.task_annotation_data = {}
            self.tm_annotation_data   = {}
            self.card_annotation_data = {}

    # =========================================================================
    # Phase 4k.6 — Task popover handlers (click-based, replaces right-click)
    # =========================================================================

    @rx.event
    def open_task_popover(self, annot_id: str, card_code: str):
        """Open the inline task popover when a task line is clicked.

        annot_id is the TaskItem.annot_id (UUID for canonical tasks,
        "custom:{label}:{hash}" for custom/hardcoded tasks).
        """
        self.task_popover_annot_id  = annot_id or ""
        self.task_popover_card_code = card_code or ""
        self.task_popover_view      = "root"
        self.task_popover_note_text = (
            self.task_annotation_data.get(annot_id, {}).get("note", {}).get("text", "")
            if annot_id else ""
        )
        # Pre-populate the edit-text field with the current task display name.
        self.task_popover_existing_name = self._find_task_name_by_annot_id(annot_id)
        self.task_popover_open = True

    @rx.event
    def close_task_popover(self):
        """Dismiss the task popover (also fired by the overlay click)."""
        self.task_popover_open          = False
        self.task_popover_view          = "root"
        self.task_popover_note_text     = ""
        self.task_popover_existing_name = ""

    def _find_task_name_by_annot_id(self, annot_id: str) -> str:
        """Scan all loaded slots to find a task's current display name by annot_id.
        Returns "" if not found (e.g. popover opened before night data loaded).
        """
        if not annot_id:
            return ""
        all_slots = list(self.zone_slots) + list(self.aux_slots)
        for slot in all_slots:
            for t in (slot.get("display_tasks") or []):
                if t.get("annot_id") == annot_id:
                    return t.get("name", "")
        for rr in self.rr_slots:
            for t in (rr.get("display_tasks") or []):
                if t.get("annot_id") == annot_id:
                    return t.get("name", "")
        return ""

    @rx.event
    def set_task_popover_view(self, view: str):
        self.task_popover_view = view

    # =========================================================================
    # Task pool handlers (2026-05-10)
    # =========================================================================

    @rx.event
    def open_task_pool(self, slot_id: str):
        """Open the inline task pool panel for a given slot. Always resets to porter tab."""
        self.task_pool_slot_id  = slot_id
        self.task_pool_category = "porter"

    @rx.event
    def close_task_pool(self):
        """Close the task pool panel."""
        self.task_pool_slot_id = ""

    @rx.event
    def toggle_task_pool(self, slot_id: str):
        """Toggle the pool panel for a slot — open if closed, close if already open."""
        if self.task_pool_slot_id == slot_id:
            self.task_pool_slot_id = ""
        else:
            self.task_pool_slot_id  = slot_id
            self.task_pool_category = "porter"

    @rx.event
    def set_task_pool_category(self, cat: str):
        self.task_pool_category = cat

    @rx.event
    def add_task_from_pool(self, task_name: str):
        """Add a predefined pool task to the currently open pool slot. Skips duplicates."""
        slot_id = self.task_pool_slot_id
        text = task_name.strip()
        if not text or not slot_id:
            return
        current = self._get_slot_tasks(slot_id)
        if text in current:
            return  # already on this card — pool item shows check state
        new_tasks = current + [text]
        database.update_slot_tasks(slot_id, new_tasks)
        # _load_night requires a night_id arg — every other call site passes
        # self.current_night_id. Without it, this throws TypeError and Reflex
        # surfaces "Contact admin" while silently completing the DB write.
        if self.current_night_id:
            self._load_night(self.current_night_id)

    @rx.event
    def set_task_popover_note_text(self, val: str):
        self.task_popover_note_text = val

    @rx.event
    def set_picker_card_note(self, val: str):
        """Live update for the card note textarea in the picker drawer."""
        self.picker_card_note_input = val

    @rx.event
    def set_picker_tm_note(self, val: str):
        """Live update for the TM pre-shift note textarea in the picker drawer."""
        self.picker_tm_note_input = val

    @rx.event
    def set_picker_adhoc_input(self, val: str):
        """Live update for the ad-hoc task name input in the picker drawer."""
        self.picker_adhoc_input = val

    @rx.event
    def set_task_highlight(self, color: str):
        """Toggle a highlight annotation on the current task (same color → clears it)."""
        from shared.db import upsert_annotation, delete_annotation
        if not self.task_popover_annot_id:
            self.task_popover_open = False
            return
        week_ending = self.week_info.get("week_ending", "")
        day         = self._current_day_key()
        existing    = self.task_annotation_data.get(self.task_popover_annot_id, {}).get("highlight")
        if existing and existing.get("color") == color:
            delete_annotation(week_ending, day, "task", self.task_popover_annot_id, "highlight")
        else:
            upsert_annotation(week_ending, day, "task", self.task_popover_annot_id, "highlight",
                              {"color": color})
        self._load_task_annotations()

    @rx.event
    def set_task_symbol(self, section: str, slug: str):
        """Toggle a GLCR icon symbol annotation on the current task.

        Same section+slug → clears the annotation (toggle behavior).
        Stores JSONB {"section": section, "slug": slug} for the PDF renderer
        to look up via glcr_icon(section, slug).
        """
        from shared.db import upsert_annotation, delete_annotation
        if not self.task_popover_annot_id:
            self.task_popover_open = False
            return
        week_ending = self.week_info.get("week_ending", "")
        day         = self._current_day_key()
        existing    = self.task_annotation_data.get(self.task_popover_annot_id, {}).get("symbol")
        if (existing
                and existing.get("section") == section
                and existing.get("slug") == slug):
            delete_annotation(week_ending, day, "task", self.task_popover_annot_id, "symbol")
        else:
            upsert_annotation(week_ending, day, "task", self.task_popover_annot_id, "symbol",
                              {"section": section, "slug": slug})
        self._load_task_annotations()

    @rx.event
    def save_task_note(self):
        """Save (or delete if blank) a note annotation on the current task."""
        from shared.db import upsert_annotation, delete_annotation
        if not self.task_popover_annot_id:
            self.task_popover_open = False
            return
        week_ending = self.week_info.get("week_ending", "")
        day         = self._current_day_key()
        text        = self.task_popover_note_text.strip()
        if text:
            upsert_annotation(week_ending, day, "task", self.task_popover_annot_id, "note",
                              {"text": text})
        else:
            delete_annotation(week_ending, day, "task", self.task_popover_annot_id, "note")
        self._load_task_annotations()
        self.task_popover_view = "root"

    @rx.event
    def toggle_task_skip(self):
        """Toggle the skip-tonight annotation on the current task."""
        from shared.db import upsert_annotation, delete_annotation
        if not self.task_popover_annot_id:
            self.task_popover_open = False
            return
        week_ending = self.week_info.get("week_ending", "")
        day         = self._current_day_key()
        existing    = self.task_annotation_data.get(self.task_popover_annot_id, {}).get("skip")
        if existing is not None:
            delete_annotation(week_ending, day, "task", self.task_popover_annot_id, "skip")
        else:
            upsert_annotation(week_ending, day, "task", self.task_popover_annot_id, "skip",
                              {"skipped": True})
        self._load_task_annotations()

    @rx.event
    def clear_task_annotation(self):
        """Remove ALL annotations for the current task."""
        from shared.db import list_annotations, delete_annotation
        if not self.task_popover_annot_id:
            self.task_popover_open = False
            return
        week_ending = self.week_info.get("week_ending", "")
        day         = self._current_day_key()
        rows = list_annotations(week_ending, day, target_kind="task",
                                target_ref=self.task_popover_annot_id)
        for row in rows:
            delete_annotation(week_ending, day, "task",
                              self.task_popover_annot_id, row["annotation_kind"])
        self._load_task_annotations()
        self.task_popover_open = False

    @rx.event
    def edit_task_text(self, form_data: dict):
        """Update a task's display text.

        For canonical tasks (UUID in zone_tasks), calls upsert_task to update
        the zone_tasks row — this is a canonical change that carries to all weeks.
        For adhoc tasks (composite ref with ':'), updates the annotation's name field.
        """
        from shared.db import upsert_annotation, get_task_by_id
        new_text = (form_data.get("text") or "").strip()
        if not new_text or not self.task_popover_annot_id:
            self.task_popover_view = "root"
            return
        annot_id    = self.task_popover_annot_id
        week_ending = self.week_info.get("week_ending", "")
        day         = self._current_day_key()
        # Adhoc card-annotation tasks have ":" but don't start with "custom:"
        # Custom slot tasks ("custom:...") are stored in slot's custom_tasks column
        # — editing them is not yet supported (close popover silently).
        if annot_id.startswith("custom:"):
            self.task_popover_view = "root"
            return
        elif ":" in annot_id:
            # Adhoc composite ref — update the annotation value only (this week)
            upsert_annotation(week_ending, day, "card", annot_id, "adhoc", {"name": new_text})
        else:
            # Canonical zone_tasks row (UUID) — update the name for all weeks
            try:
                from shared.db import upsert_task
                upsert_task({"id": annot_id, "name": new_text})
            except Exception as exc:
                self.error = f"Edit task error: {exc}"
        self._load_task_annotations()
        # Force a night reload so the task name refreshes in display_tasks
        # (_load_night requires night_id; the bare-arg version threw silently
        # under the try/except, leaving display_tasks stale until next reload)
        if self.current_night_id:
            try:
                self._load_night(self.current_night_id)
            except Exception:
                pass
        self.task_popover_view = "root"

    @rx.event
    def delete_adhoc_task_from_popover(self):
        """Delete an adhoc card-annotation task currently open in the popover.

        Only deletes real adhoc tasks (composite ref, no "custom:" prefix).
        Custom slot tasks would need a separate slot-edit flow — bail silently.
        """
        from shared.db import delete_annotation
        annot_id = self.task_popover_annot_id
        if ":" not in annot_id or annot_id.startswith("custom:"):
            self.task_popover_open = False
            return
        week_ending = self.week_info.get("week_ending", "")
        day         = self._current_day_key()
        delete_annotation(week_ending, day, "card", annot_id, "adhoc")
        self._load_task_annotations()
        self.task_popover_open = False

    # =========================================================================
    # Phase 4k.6 — TM annotation handlers (now read from picker_tm_id)
    # =========================================================================

    @rx.event
    def save_tm_preshift_note(self):
        """Save (or delete if blank) a pre-shift note annotation on the TM open
        in the picker drawer. The note prints as an italic line below the TM name."""
        from shared.db import upsert_annotation, delete_annotation
        if not self.picker_tm_id:
            return
        week_ending = self.week_info.get("week_ending", "")
        day         = self._current_day_key()
        text        = self.picker_tm_note_input.strip()
        if text:
            upsert_annotation(week_ending, day, "tm", self.picker_tm_id,
                              "note", {"text": text})
        else:
            delete_annotation(week_ending, day, "tm", self.picker_tm_id, "note")
        self._load_task_annotations()
        self.picker_tm_note_input = ""

    @rx.event
    def log_tm_to_profile(self):
        """Capture an observation to the GLCR Memory Backend (public.notes table),
        then mirror a profile_log annotation so the deployment renderer can drop a
        pin-bookmark marker next to this TM's name without re-querying the backend.
        """
        from shared.db import upsert_annotation, insert_note
        if not self.picker_tm_id:
            return
        week_ending = self.week_info.get("week_ending", "")
        day         = self._current_day_key()
        text        = self.picker_tm_note_input.strip()
        if not text:
            return
        note_id = insert_note(
            content       = text,
            content_type  = "observation",
            sentiment     = "neutral",
            original_date = str(self.week_info.get("week_ending", "")),
            author        = "brian",
            captured_via  = "zds_preshift_log",
            entity_ids    = [self.picker_tm_id],
        )
        upsert_annotation(
            week_ending, day, "tm", self.picker_tm_id,
            "profile_log",
            {"note_id": note_id or "", "preview": text[:80]},
        )
        self._load_task_annotations()
        self.picker_tm_note_input = ""

    @rx.event
    def navigate_to_tm_profile(self):
        """Navigate to the TM's admin profile page (uses picker_tm_id)."""
        tm_id = self.picker_tm_id
        if tm_id:
            return rx.redirect(f"/admin/people/{tm_id}")

    @rx.event
    def clear_tm_note(self):
        """Delete the pre-shift note annotation for the TM open in the picker."""
        from shared.db import delete_annotation
        if not self.picker_tm_id:
            return
        week_ending = self.week_info.get("week_ending", "")
        day         = self._current_day_key()
        delete_annotation(week_ending, day, "tm", self.picker_tm_id, "note")
        self._load_task_annotations()

    # =========================================================================
    # Phase 4k.6 — Card annotation handlers (now read from picker_card_code)
    # =========================================================================

    @rx.event
    def add_card_adhoc_task(self):
        """Save picker_adhoc_input as a new adhoc task annotation on the open card.

        Uses a composite target_ref = "{card_code}:{8-hex}" to allow multiple
        adhoc tasks per card while satisfying the DB unique constraint.
        """
        from shared.db import upsert_annotation
        if not self.picker_card_code:
            return
        text = self.picker_adhoc_input.strip()
        if not text:
            return
        week_ending = self.week_info.get("week_ending", "")
        day         = self._current_day_key()
        task_ref    = f"{self.picker_card_code}:{uuid.uuid4().hex[:8]}"
        upsert_annotation(week_ending, day, "card", task_ref, "adhoc", {"name": text})
        self.picker_adhoc_input = ""
        self._load_task_annotations()

    @rx.event
    def delete_card_adhoc_task(self, task_ref: str):
        """Delete one adhoc task by composite ref (card_code:hexsuffix)."""
        from shared.db import delete_annotation
        week_ending = self.week_info.get("week_ending", "")
        day         = self._current_day_key()
        delete_annotation(week_ending, day, "card", task_ref, "adhoc")
        self._load_task_annotations()

    @rx.event
    def save_card_note(self):
        """Save (or delete if blank) a note annotation on the currently open card."""
        from shared.db import upsert_annotation, delete_annotation
        if not self.picker_card_code:
            return
        week_ending = self.week_info.get("week_ending", "")
        day         = self._current_day_key()
        text        = self.picker_card_note_input.strip()
        if text:
            upsert_annotation(week_ending, day, "card", self.picker_card_code,
                              "note", {"text": text})
        else:
            delete_annotation(week_ending, day, "card", self.picker_card_code, "note")
        self._load_task_annotations()
        self.picker_card_note_input = ""

    @rx.event
    def clear_card_note(self):
        """Delete the note annotation for the currently open card."""
        from shared.db import delete_annotation
        if not self.picker_card_code:
            return
        week_ending = self.week_info.get("week_ending", "")
        day         = self._current_day_key()
        delete_annotation(week_ending, day, "card", self.picker_card_code, "note")
        self._load_task_annotations()

    @rx.event
    def toggle_card_priority(self):
        """Toggle the priority annotation on the currently open card."""
        from shared.db import upsert_annotation, delete_annotation
        if not self.picker_card_code:
            return
        week_ending = self.week_info.get("week_ending", "")
        day         = self._current_day_key()
        existing    = self.card_annotation_data.get(self.picker_card_code, {}).get("priority")
        if existing is not None:
            delete_annotation(week_ending, day, "card", self.picker_card_code, "priority")
        else:
            upsert_annotation(week_ending, day, "card", self.picker_card_code,
                              "priority", {"level": "high"})
        self._load_task_annotations()

    @rx.event
    def print_single_card(self):
        """Generate and open a single-card print view for the currently open card.

        Uses the print-cache mechanism — writes HTML to /print_cache/ and opens
        in a new tab. No new Reflex route needed.
        """
        from .print_renderer import render_single_card_html
        code     = self.picker_card_code
        night_id = self.current_night_id
        if not code or not night_id:
            return
        import traceback, time as _t
        _PRINT_CACHE.mkdir(parents=True, exist_ok=True)
        safe  = code.lower().replace(" ", "_").replace("+", "").replace("/", "")
        fname = f"card_{safe}_{night_id[:8]}_{int(_t.time())}.html"
        try:
            html = render_single_card_html(night_id, code)
            (_PRINT_CACHE / fname).write_text(html, encoding="utf-8")
            url = f"/print_cache/{fname}"
            return rx.call_script(f"window.open('{url}', '_blank')")
        except Exception as exc:
            traceback.print_exc()
            err_msg = str(exc).replace("'", "\\'")
            self.error = f"Print card error: {exc}"
            err_html = (f"<html><body style='font-family:monospace;padding:2em'>"
                        f"<h2 style='color:#dc2626'>Card print failed</h2>"
                        f"<pre>{err_msg}</pre></body></html>")
            (_PRINT_CACHE / fname).write_text(err_html, encoding="utf-8")
            return rx.call_script(f"window.open('/print_cache/{fname}', '_blank')")

    # =========================================================================
    # Private slot-task helpers
    # =========================================================================

    def _get_slot_tasks(self, slot_id: str) -> list[str]:
        """Return the current task-name list for a given slot_id.

        Phase 4k.3: display_tasks is now list[{id, name}] dicts. This helper
        still returns list[str] (names only) because DB writes (custom_tasks)
        remain list[str]. Handles both the new dict format and the legacy
        plain-string format gracefully.
        """
        def _names(tasks):
            return [t["name"] if isinstance(t, dict) else t for t in tasks]

        for s in self.zone_slots:
            if s["id"] == slot_id:
                return _names(s.get("display_tasks", []))
        for s in self.aux_slots:
            if s["id"] == slot_id:
                return _names(s.get("display_tasks", []))
        for rr in self.rr_slots:
            if rr.get("mens_slot_id") == slot_id:
                return _names(rr.get("display_tasks", []))
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
                "group_num":  BG_ZONE.get(n, 1),   # Phase 4d: group_num = old break_wave
                "break_wave": 1,                    # Phase 4d: wave within group
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
                    "group_num":  tbl.get(num, 1),  # Phase 4d: group_num = old break_wave
                    "break_wave": 1,                # Phase 4d: wave within group
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
                "group_num":  BG_AUX.get(sk, 1),   # Phase 4d: group_num = old break_wave
                "break_wave": 1,                    # Phase 4d: wave within group
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
