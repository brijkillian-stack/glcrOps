"""
apps/admin/tasks_state.py — ZoneTasksState (Phase 4i.3)

Manages the /admin/tasks page:
  - Table of all zone_tasks (active + archived)
  - Drawer: edit name / default_zone / category / active flag
  - Neglect ranking: tasks sorted by last zone_task_assignment
  - Zone affinity %: per-task breakdown of where assignments landed
"""

from __future__ import annotations

import reflex as rx

CATEGORY_OPTIONS: list[str] = ["zone", "rr", "aux"]

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
    {"label": "Floating",    "value": ""},
]


class ZoneTasksState(rx.State):
    """State for /admin/tasks."""

    # ── Page-level ───────────────────────────────────────────────────────────
    loading: bool = False
    active_tab: int = 0          # 0=All Tasks, 1=Neglect Ranking

    # ── Task list ────────────────────────────────────────────────────────────
    tasks: list[dict] = []       # zone_tasks rows
    show_archived: bool = False  # toggle to include archived rows

    # ── Drawer ───────────────────────────────────────────────────────────────
    drawer_open: bool = False
    editing_id: str = ""
    edit_name: str = ""
    edit_zone: str = ""
    edit_category: str = "zone"
    edit_active: bool = True
    edit_notes: str = ""
    saving: bool = False
    save_error: str = ""

    # ── Neglect ranking ──────────────────────────────────────────────────────
    neglect_rows: list[dict] = []   # [{id, name, default_zone, category, last_assigned, days_idle}]

    # ── Zone affinity (for drawer) ───────────────────────────────────────────
    affinity_rows: list[dict] = []  # [{zone_slot, count, pct}] for editing_id

    # ── New task inline form ─────────────────────────────────────────────────
    new_name: str = ""
    new_zone: str = "zone_1"
    new_category: str = "zone"
    adding: bool = False
    add_error: str = ""

    # ── Computed helpers ─────────────────────────────────────────────────────
    @rx.var
    def visible_tasks(self) -> list[dict]:
        return [
            t for t in self.tasks
            if self.show_archived or t.get("active", True)
        ]

    @rx.var
    def drawer_title(self) -> str:
        if not self.editing_id:
            return "Task"
        t = next((x for x in self.tasks if x["id"] == self.editing_id), {})
        return t.get("name", "Task")

    # ── Load ─────────────────────────────────────────────────────────────────
    async def load_tasks(self):
        self.loading = True
        yield
        try:
            from shared.db import get_client
            sb = get_client()
            res = (
                sb.table("zone_tasks")
                .select("id,name,description,default_zone,category,active,notes,created_at,updated_at")
                .order("category")
                .order("default_zone")
                .order("name")
                .execute()
            )
            self.tasks = res.data or []
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
            # Get last assigned_at per task_id
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
        self.editing_id   = task_id
        self.edit_name     = t.get("name", "")
        self.edit_zone     = t.get("default_zone") or ""
        self.edit_category = t.get("category", "zone")
        self.edit_active   = bool(t.get("active", True))
        self.edit_notes    = t.get("notes") or ""
        self.save_error    = ""
        self.affinity_rows = []
        self.drawer_open   = True
        yield ZoneTasksState._load_affinity(task_id)

    def close_drawer(self):
        self.drawer_open   = False
        self.editing_id    = ""
        self.affinity_rows = []
        self.save_error    = ""

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

    # ── Setters ──────────────────────────────────────────────────────────────
    def set_edit_name(self, v: str):     self.edit_name = v
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
            from shared.db import get_client
            sb = get_client()
            sb.table("zone_tasks").update({
                "name":         self.edit_name.strip(),
                "default_zone": self.edit_zone or None,
                "category":     self.edit_category,
                "active":       self.edit_active,
                "notes":        self.edit_notes.strip() or None,
            }).eq("id", self.editing_id).execute()
            self.close_drawer()
            yield ZoneTasksState.load_tasks()
        except Exception as e:
            self.save_error = str(e)
        finally:
            self.saving = False

    # ── Archive / restore ────────────────────────────────────────────────────
    async def archive_task(self, task_id: str):
        try:
            from shared.db import get_client
            import datetime as dt
            sb = get_client()
            sb.table("zone_tasks").update({
                "active":      False,
                "archived_at": dt.datetime.utcnow().isoformat(),
            }).eq("id", task_id).execute()
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
            from shared.db import get_client
            sb = get_client()
            sb.table("zone_tasks").insert({
                "name":         self.new_name.strip(),
                "default_zone": self.new_zone or None,
                "category":     self.new_category,
                "active":       True,
            }).execute()
            self.new_name = ""
            yield ZoneTasksState.load_tasks()
        except Exception as e:
            self.add_error = str(e)
        finally:
            self.adding = False
