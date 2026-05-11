"""
state/tasks.py — TasksState

Manages the Tasks page. Loads all tasks from Supabase as a flat list
(group-header sentinels + task rows) for use with rx.foreach.

Phase 1 UX additions:
  - always-visible quick-add bar (quick_title + save_quick_task)
  - priority cycle: click a task's priority dot → normal→high→urgent→low→normal
  - collapsible groups: click a group header → toggle visibility
"""

import reflex as rx
from shared.base import AppState
from shared.db import get_tasks_flat, complete_task, create_task, update_task_priority


_PRIORITY_CYCLE = {"normal": "high", "high": "urgent", "urgent": "low", "low": "normal"}


class TasksState(AppState):
    # Flat list: header sentinels interleaved with task dicts (from DB)
    flat_items: list[dict] = []

    # Active filter tab
    status_filter: str = "open"

    # Page loading spinner
    loading: bool = True

    # ID of the task currently being marked complete (for button feedback)
    completing_id: str = ""

    # Group names that are currently collapsed
    collapsed_groups: list[str] = []

    # ── Multi-select ──────────────────────────────────────────────────────────
    selected_ids: list[str] = []
    bulk_completing: bool = False

    # ── Quick-add bar ─────────────────────────────────────────────────────────
    quick_title: str = ""
    saving_quick: bool = False

    # ── Full new-task form ────────────────────────────────────────────────────
    form_open:       bool = False
    new_title:       str  = ""
    new_category:    str  = "Tasks"
    new_priority:    str  = "normal"
    new_due:         str  = ""
    new_description: str  = ""
    saving_task:     bool = False

    # ── Computed vars ─────────────────────────────────────────────────────────

    @rx.var
    def visible_items(self) -> list[dict]:
        """
        flat_items filtered by collapsed_groups.
        Header items get an extra `is_collapsed` bool key.
        Task items get `is_collapsed: False` and `is_selected` bool so every row shares the same schema.
        """
        sel = set(self.selected_ids)
        result: list[dict] = []
        current_collapsed = False
        for item in self.flat_items:
            if item.get("_type") == "header":
                current_collapsed = item.get("name", "") in self.collapsed_groups
                result.append({**item, "is_collapsed": current_collapsed, "is_selected": False})
            elif not current_collapsed:
                result.append({**item, "is_collapsed": False,
                                "is_selected": item.get("id", "") in sel})
        return result

    @rx.var
    def task_count(self) -> int:
        return sum(1 for item in self.flat_items if item.get("_type") == "task")

    @rx.var
    def overdue_count(self) -> int:
        return sum(
            1 for item in self.flat_items
            if item.get("_type") == "task" and item.get("is_overdue")
        )

    @rx.var
    def page_summary(self) -> str:
        n  = self.task_count
        od = self.overdue_count
        if self.status_filter == "completed":
            return f"{n} completed task{'s' if n != 1 else ''}."
        if self.status_filter == "all":
            return f"{n} task{'s' if n != 1 else ''} total."
        if od > 0:
            return (
                f"{n} open task{'s' if n != 1 else ''}, "
                f"{od} overdue."
            )
        return f"{n} open task{'s' if n != 1 else ''}."

    @rx.var
    def can_save(self) -> bool:
        return bool(self.new_title.strip()) and not self.saving_task

    @rx.var
    def visible_count(self) -> int:
        return sum(1 for item in self.visible_items if item.get("_type") == "task")

    @rx.var
    def selected_count(self) -> int:
        return len(self.selected_ids)

    @rx.var
    def has_selection(self) -> bool:
        return len(self.selected_ids) > 0

    @rx.var
    def all_open_ids(self) -> list[str]:
        """IDs of all visible open tasks (for select-all)."""
        return [
            item.get("id", "")
            for item in self.flat_items
            if item.get("_type") == "task"
            and item.get("status") not in ("completed",)
            and item.get("id", "")
        ]

    @rx.var
    def all_selected(self) -> bool:
        if not self.all_open_ids:
            return False
        sel = set(self.selected_ids)
        return all(tid in sel for tid in self.all_open_ids)

    # ── Events ────────────────────────────────────────────────────────────────

    @rx.event
    async def load_tasks(self):
        self.loading = True
        yield
        self.flat_items = get_tasks_flat(self.status_filter)
        self.loading = False

    @rx.event
    async def set_filter(self, f: str):
        self.status_filter = f
        yield TasksState.load_tasks

    @rx.event
    async def mark_complete(self, task_id: str):
        self.completing_id = task_id
        yield
        ok = complete_task(task_id)
        self.completing_id = ""
        if ok:
            yield TasksState.load_tasks

    # ── Multi-select ─────────────────────────────────────────────────────────

    @rx.event
    def toggle_select(self, task_id: str):
        """Toggle a single task in/out of the selection."""
        if task_id in self.selected_ids:
            self.selected_ids = [tid for tid in self.selected_ids if tid != task_id]
        else:
            self.selected_ids = [*self.selected_ids, task_id]

    @rx.event
    def toggle_select_all(self):
        """Select all open tasks if not all selected; otherwise clear selection."""
        if self.all_selected:
            self.selected_ids = []
        else:
            self.selected_ids = list(self.all_open_ids)

    @rx.event
    def clear_selection(self):
        self.selected_ids = []

    @rx.event
    async def complete_selected(self):
        """Bulk-complete all selected tasks."""
        if not self.selected_ids:
            return
        self.bulk_completing = True
        yield
        ids_to_complete = list(self.selected_ids)
        for task_id in ids_to_complete:
            complete_task(task_id)
        self.selected_ids = []
        self.bulk_completing = False
        yield TasksState.load_tasks

    # ── Priority cycle ────────────────────────────────────────────────────────

    @rx.event
    async def cycle_priority(self, task_id: str):
        """Optimistically flip priority in state, then persist to Supabase."""
        new_priority = "normal"
        new_flat: list[dict] = []
        for item in self.flat_items:
            if item.get("id") == task_id and item.get("_type") == "task":
                current = item.get("priority", "normal")
                new_priority = _PRIORITY_CYCLE.get(current, "normal")
                new_flat.append({**item, "priority": new_priority})
            else:
                new_flat.append(item)
        self.flat_items = new_flat
        yield
        update_task_priority(task_id, new_priority)

    # ── Group collapse ────────────────────────────────────────────────────────

    @rx.event
    def toggle_group(self, name: str):
        if name in self.collapsed_groups:
            self.collapsed_groups = [g for g in self.collapsed_groups if g != name]
        else:
            self.collapsed_groups = [*self.collapsed_groups, name]

    # ── Quick-add ─────────────────────────────────────────────────────────────

    @rx.event
    def set_quick_title(self, value: str):
        self.quick_title = value

    @rx.event
    async def save_quick_task(self):
        if not self.quick_title.strip():
            return
        self.saving_quick = True
        yield
        ok = create_task(title=self.quick_title)
        self.saving_quick = False
        if ok:
            self.quick_title  = ""
            self.status_filter = "open"
            yield TasksState.load_tasks

    # ── Full form ─────────────────────────────────────────────────────────────

    @rx.event
    def open_form(self):
        self.form_open       = True
        self.new_title       = ""
        self.new_category    = "Tasks"
        self.new_priority    = "normal"
        self.new_due         = ""
        self.new_description = ""
        self.saving_task     = False

    @rx.event
    def close_form(self):
        self.form_open = False

    @rx.event
    def set_new_title(self, value: str):
        self.new_title = value

    @rx.event
    def set_new_category(self, value: str):
        self.new_category = value

    @rx.event
    def set_new_priority(self, value: str):
        self.new_priority = value

    @rx.event
    def set_new_due(self, value: str):
        self.new_due = value

    @rx.event
    def set_new_description(self, value: str):
        self.new_description = value

    @rx.event
    async def save_new_task(self):
        if not self.new_title.strip():
            return
        self.saving_task = True
        yield
        ok = create_task(
            title       = self.new_title,
            category    = self.new_category,
            priority    = self.new_priority,
            due_date    = self.new_due,
            description = self.new_description,
        )
        self.saving_task = False
        if ok:
            self.form_open     = False
            self.status_filter = "open"
            yield TasksState.load_tasks
