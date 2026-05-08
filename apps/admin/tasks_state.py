"""
apps/admin/tasks_state.py — ZoneTasksState (Phase 4k.1 rebuild)

Manages the /admin/tasks page:
  - Table of all zone_tasks with filter bar (search + category)
  - Drawer: edit name / code / default_zone / category / active flag + notes
  - Per-day override sub-section in drawer (task_day_overrides)
  - Neglect ranking: tasks sorted by last zone_task_assignment
  - Zone affinity %: per-task breakdown of where assignments landed
"""

from __future__ import annotations

import reflex as rx

CATEGORY_OPTIONS: list[str] = [
    "zone", "rr", "aux", "overlap_pm", "overlap_am",
]

CATEGORY_FILTER_OPTIONS: list[dict] = [
    {"label": "All",        "value": ""},
    {"label": "Zone",       "value": "zone"},
    {"label": "RR",         "value": "rr"},
    {"label": "Aux",        "value": "aux"},
    {"label": "Overlap PM", "value": "overlap_pm"},
    {"label": "Overlap AM", "value": "overlap_am"},
]

# Zone slot options for the default_zone picker
DEFAULT_ZONE_OPTIONS: list[dict] = [
    {"label": "Zone 1",      "value": "zone_1"},
    {"label": "Zone 2",      "value": "zone_2"},
    {"label": "Zone 3",      "value": "zone_3"},
    {"label": "Zone 4",      "value": "zone_4"},
    {"label": "Zone 5",      "value": "zone_5"},
    {"label": "Zone 6",      "value": "zone_6"},
    {"label": "Zone 7",      "value": "zone_7"},
    {"label": "Zone 8",      "value": "zone_8"},
    {"label": "Zone 9",      "value": "zone_9"},
    {"label": "Zone 10",     "value": "zone_10"},
    {"label": "RR 1",        "value": "rr_1"},
    {"label": "RR 6",        "value": "rr_6"},
    {"label": "RR 7",        "value": "rr_7"},
    {"label": "RR 8",        "value": "rr_8"},
    {"label": "RR 10",       "value": "rr_10"},
    {"label": "Admin",       "value": "admin"},
    {"label": "Trash 1",     "value": "trash_1"},
    {"label": "Trash 2",     "value": "trash_2"},
    {"label": "Z9 SR",       "value": "z9_sr"},
    {"label": "Z9 SR Buddy", "value": "z9_sr_buddy"},
    {"label": "Support 1",   "value": "support_1"},
    {"label": "Support 2",   "value": "support_2"},
    {"label": "Support 3",   "value": "support_3"},
    {"label": "PMOL1",       "value": "PMOL1"},
    {"label": "PMOL2",       "value": "PMOL2"},
    {"label": "PMOL3",       "value": "PMOL3"},
    {"label": "PMOL4",       "value": "PMOL4"},
    {"label": "PMOL5",       "value": "PMOL5"},
    {"label": "PMOL6",       "value": "PMOL6"},
    {"label": "AMOL1",       "value": "AMOL1"},
    {"label": "AMOL2",       "value": "AMOL2"},
    {"label": "AMOL3",       "value": "AMOL3"},
    {"label": "AMOL4",       "value": "AMOL4"},
    {"label": "AMOL5",       "value": "AMOL5"},
    {"label": "AMOL6",       "value": "AMOL6"},
    {"label": "Floating",    "value": ""},
]


class ZoneTasksState(rx.State):
    """State for /admin/tasks."""

    # ── Page-level ───────────────────────────────────────────────────────────
    loading: bool = False
    active_tab: int = 0          # 0=All Tasks, 1=Neglect Ranking

    # ── Filter bar ───────────────────────────────────────────────────────────
    filter_search: str = ""
    filter_category: str = ""   # "" = all

    # ── Task list ────────────────────────────────────────────────────────────
    tasks: list[dict] = []       # zone_tasks rows (all categories)
    show_archived: bool = False

    # ── Drawer ───────────────────────────────────────────────────────────────
    drawer_open: bool = False
    editing_id: str = ""
    edit_name: str = ""
    edit_code: str = ""
    edit_zone: str = ""
    edit_category: str = "zone"
    edit_active: bool = True
    edit_notes: str = ""
    saving: bool = False
    save_error: str = ""

    # ── Per-day overrides (shown in drawer) ──────────────────────────────────
    override_rows: list[dict] = []       # [{id, override_date, description, notes}]
    new_override_date: str = ""
    new_override_desc: str = ""
    adding_override: bool = False
    override_error: str = ""

    # ── Neglect ranking ──────────────────────────────────────────────────────
    neglect_rows: list[dict] = []

    # ── Zone affinity (for drawer) ───────────────────────────────────────────
    affinity_rows: list[dict] = []

    # ── New task inline form ─────────────────────────────────────────────────
    new_name: str = ""
    new_zone: str = "zone_1"
    new_category: str = "zone"
    adding: bool = False
    add_error: str = ""

    # ── Computed helpers ─────────────────────────────────────────────────────
    @rx.var
    def visible_tasks(self) -> list[dict]:
        rows = self.tasks
        # Archive filter
        if not self.show_archived:
            rows = [t for t in rows if t.get("active", True)]
        # Category filter
        if self.filter_category:
            rows = [t for t in rows if t.get("category") == self.filter_category]
        # Search filter (name or code)
        if self.filter_search:
            q = self.filter_search.lower()
            rows = [
                t for t in rows
                if q in (t.get("name") or "").lower()
                or q in (t.get("code") or "").lower()
            ]
        return rows

    @rx.var
    def drawer_title(self) -> str:
        if not self.editing_id:
            return "Task"
        t = next((x for x in self.tasks if x["id"] == self.editing_id), {})
        return t.get("name", "Task")

    @rx.var
    def has_overrides(self) -> bool:
        return len(self.override_rows) > 0

    # ── Load ─────────────────────────────────────────────────────────────────
    async def load_tasks(self):
        self.loading = True
        yield
        try:
            from shared.db import list_tasks
            # Include archived so state has all rows; visible_tasks filters on display
            all_rows = list_tasks(active_only=False, include_overlap=True)
            self.tasks = all_rows
            yield ZoneTasksState._load_neglect()
        except Exception as e:
            print(f"[ZoneTasksState] load_tasks error: {e}")
        finally:
            self.loading = False

    async def _load_neglect(self):
        """Load neglect ranking: tasks sorted by last assignment date (oldest idle first)."""
        try:
            from shared.db import get_client
            import datetime as dt
            sb = get_client()
            res = (
                sb.table("zone_task_assignments")
                .select("task_id,assigned_at")
                .order("assigned_at", desc=True)
                .execute()
            )
            last_by_task: dict[str, str] = {}
            for row in (res.data or []):
                tid = row["task_id"]
                if tid not in last_by_task:
                    last_by_task[tid] = row["assigned_at"]

            today = dt.date.today()
            rows = []
            for t in self.tasks:
                if not t.get("active", True):
                    continue
                # Only include zone/rr categories in neglect (not overlaps)
                if t.get("category") not in ("zone", "rr", "aux"):
                    continue
                tid = t["id"]
                last = last_by_task.get(tid)
                if last:
                    d = dt.date.fromisoformat(last[:10])
                    idle = (today - d).days
                    last_str = last[:10]
                else:
                    idle = 9999
                    last_str = "Never"
                rows.append({
                    "id":           tid,
                    "name":         t["name"],
                    "default_zone": t.get("default_zone") or "—",
                    "category":     t.get("category", "zone"),
                    "last_assigned": last_str,
                    "days_idle":    idle,
                })
            rows.sort(key=lambda r: r["days_idle"], reverse=True)
            self.neglect_rows = rows
        except Exception as e:
            print(f"[ZoneTasksState] _load_neglect error: {e}")

    # ── Filter setters ────────────────────────────────────────────────────────
    def set_filter_search(self, v: str):    self.filter_search = v
    def set_filter_category(self, v: str):  self.filter_category = v
    def clear_filters(self):
        self.filter_search = ""
        self.filter_category = ""

    # ── Tab ──────────────────────────────────────────────────────────────────
    def set_tab(self, idx: int):
        self.active_tab = idx

    def toggle_show_archived(self):
        self.show_archived = not self.show_archived

    # ── Drawer open / close ──────────────────────────────────────────────────
    async def open_drawer(self, task_id: str):
        t = next((x for x in self.tasks if x["id"] == task_id), {})
        if not t:
            return
        self.editing_id    = task_id
        self.edit_name     = t.get("name", "")
        self.edit_code     = t.get("code") or ""
        self.edit_zone     = t.get("default_zone") or ""
        self.edit_category = t.get("category", "zone")
        self.edit_active   = bool(t.get("active", True))
        self.edit_notes    = t.get("notes") or ""
        self.save_error    = ""
        self.affinity_rows = []
        self.override_rows = []
        self.new_override_date = ""
        self.new_override_desc = ""
        self.override_error = ""
        self.drawer_open   = True
        yield ZoneTasksState._load_affinity(task_id)
        yield ZoneTasksState._load_overrides(task_id)

    def close_drawer(self):
        self.drawer_open   = False
        self.editing_id    = ""
        self.affinity_rows = []
        self.override_rows = []
        self.save_error    = ""
        self.override_error = ""

    # ── Affinity ─────────────────────────────────────────────────────────────
    async def _load_affinity(self, task_id: str):
        try:
            from shared.db import get_client
            from collections import Counter
            sb = get_client()
            res = (
                sb.table("zone_task_assignments")
                .select("zone_slot")
                .eq("task_id", task_id)
                .execute()
            )
            slots = [r["zone_slot"] for r in (res.data or []) if r.get("zone_slot")]
            total = len(slots)
            if total == 0:
                self.affinity_rows = []
                return
            counts = Counter(slots)
            rows = [
                {
                    "zone_slot": slot,
                    "count": cnt,
                    "pct": round(cnt / total * 100),
                }
                for slot, cnt in sorted(counts.items(), key=lambda x: -x[1])
            ]
            self.affinity_rows = rows
        except Exception as e:
            print(f"[ZoneTasksState] _load_affinity error: {e}")

    # ── Per-day overrides ─────────────────────────────────────────────────────
    async def _load_overrides(self, task_id: str):
        try:
            from shared.db import get_client
            sb = get_client()
            res = (
                sb.table("task_day_overrides")
                .select("id,override_date,description,notes")
                .eq("task_id", task_id)
                .order("override_date")
                .execute()
            )
            self.override_rows = res.data or []
        except Exception as e:
            print(f"[ZoneTasksState] _load_overrides error: {e}")

    def set_new_override_date(self, v: str): self.new_override_date = v
    def set_new_override_desc(self, v: str): self.new_override_desc = v

    async def add_override(self):
        if not self.new_override_date or not self.new_override_desc.strip():
            self.override_error = "Date and description are required."
            return
        self.adding_override = True
        self.override_error = ""
        yield
        try:
            from shared.db import upsert_task_override
            upsert_task_override(
                task_id=self.editing_id,
                override_date=self.new_override_date,
                description=self.new_override_desc.strip(),
            )
            self.new_override_date = ""
            self.new_override_desc = ""
            yield ZoneTasksState._load_overrides(self.editing_id)
        except Exception as e:
            self.override_error = str(e)
        finally:
            self.adding_override = False

    async def delete_override(self, override_id: str):
        try:
            from shared.db import get_client
            sb = get_client()
            sb.table("task_day_overrides").delete().eq("id", override_id).execute()
            yield ZoneTasksState._load_overrides(self.editing_id)
        except Exception as e:
            print(f"[ZoneTasksState] delete_override error: {e}")

    # ── Setters ──────────────────────────────────────────────────────────────
    def set_edit_name(self, v: str):     self.edit_name = v
    def set_edit_code(self, v: str):     self.edit_code = v
    def set_edit_zone(self, v: str):     self.edit_zone = v
    def set_edit_category(self, v: str): self.edit_category = v
    def set_edit_active(self, v: bool):  self.edit_active = v
    def set_edit_notes(self, v: str):    self.edit_notes = v
    def set_new_name(self, v: str):      self.new_name = v
    def set_new_zone(self, v: str):      self.new_zone = v
    def set_new_category(self, v: str):  self.new_category = v

    # ── Save edit ────────────────────────────────────────────────────────────
    async def save_edit(self):
        if not self.edit_name.strip():
            self.save_error = "Name is required."
            return
        self.saving = True
        self.save_error = ""
        yield
        try:
            from shared.db import upsert_task
            upsert_task({
                "id":           self.editing_id,
                "name":         self.edit_name.strip(),
                "code":         self.edit_code.strip() or None,
                "default_zone": self.edit_zone or None,
                "category":     self.edit_category,
                "active":       self.edit_active,
                "notes":        self.edit_notes.strip() or None,
            })
            self.close_drawer()
            yield ZoneTasksState.load_tasks()
        except Exception as e:
            self.save_error = str(e)
        finally:
            self.saving = False

    # ── Archive / restore ────────────────────────────────────────────────────
    async def archive_task(self, task_id: str):
        try:
            from shared.db import deactivate_task
            deactivate_task(task_id)
            self.close_drawer()
            yield ZoneTasksState.load_tasks()
        except Exception as e:
            self.save_error = str(e)

    async def restore_task(self, task_id: str):
        try:
            from shared.db import get_client
            sb = get_client()
            sb.table("zone_tasks").update({
                "active":      True,
                "archived_at": None,
            }).eq("id", task_id).execute()
            yield ZoneTasksState.load_tasks()
        except Exception as e:
            print(f"[ZoneTasksState] restore_task error: {e}")

    # ── Add new task ─────────────────────────────────────────────────────────
    async def add_task(self):
        if not self.new_name.strip():
            self.add_error = "Name is required."
            return
        self.adding = True
        self.add_error = ""
        yield
        try:
            from shared.db import upsert_task
            upsert_task({
                "name":         self.new_name.strip(),
                "default_zone": self.new_zone or None,
                "category":     self.new_category,
                "active":       True,
            })
            self.new_name = ""
            yield ZoneTasksState.load_tasks()
        except Exception as e:
            self.add_error = str(e)
        finally:
            self.adding = False
