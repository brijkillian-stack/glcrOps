"""
pages/tasks.py — Tasks page (Phase 1 UX rebuild)

Changes vs original:
  - Always-visible quick-add bar at the top (no button needed)
  - Priority dot on every task row — click to cycle normal→high→urgent→low
  - Collapsible group headers — click to fold/unfold
  - Full "add with details" form still accessible via "+ Details" link
"""

import reflex as rx
from ..state.tasks import TasksState
from shared.base import AppState
from shared.components.ui import empty_state, skeleton_card
from shared.components.palette import command_palette
from shared.components.capture import capture_modal


# ── Page header ───────────────────────────────────────────────────────────────

def page_header() -> rx.Component:
    return rx.el.header(
        rx.el.div(
            rx.el.div("Tasks", class_name="page-eyebrow"),
            rx.el.h1("Task List", class_name="page-title"),
            rx.el.p(TasksState.page_summary, class_name="page-summary"),
        ),
        class_name="page-head",
        style={"marginBottom": "16px"},
    )


# ── Filter tabs ───────────────────────────────────────────────────────────────

def _filter_tab(value: str, label: str) -> rx.Component:
    return rx.el.button(
        label,
        class_name=rx.cond(
            TasksState.status_filter == value,
            "filter-tab active",
            "filter-tab",
        ),
        on_click=TasksState.set_filter(value),
    )


def filter_tabs() -> rx.Component:
    return rx.el.div(
        _filter_tab("open",      "Open"),
        _filter_tab("completed", "Completed"),
        _filter_tab("all",       "All"),
        class_name="filter-tabs",
    )


# ── Always-visible quick-add bar ──────────────────────────────────────────────

def quick_add_bar() -> rx.Component:
    return rx.el.form(
        rx.el.input(
            placeholder="Quick-add a task…",
            value=TasksState.quick_title,
            on_change=TasksState.set_quick_title,
            class_name="quick-add-input",
        ),
        rx.el.button(
            rx.cond(TasksState.saving_quick, "…", "Add"),
            type="submit",
            class_name="quick-add-btn",
            disabled=TasksState.quick_title == "",
        ),
        rx.el.button(
            "+ Details",
            type="button",
            class_name="quick-add-details-btn",
            on_click=TasksState.open_form,
            title="Add task with full details",
        ),
        on_submit=TasksState.save_quick_task,
        class_name="quick-add-bar",
    )


# ── Full new-task form (expanded details) ─────────────────────────────────────

def new_task_form() -> rx.Component:
    return rx.cond(
        TasksState.form_open,
        rx.el.div(
            # Header row
            rx.el.div(
                rx.el.span(
                    "New Task — Full Details",
                    style={"fontSize": "14px", "fontWeight": "600", "color": "var(--fg-1)"},
                ),
                rx.el.button(
                    "✕",
                    on_click=TasksState.close_form,
                    class_name="btn btn-ghost",
                    style={"fontSize": "12px", "padding": "4px 8px"},
                ),
                style={
                    "display": "flex", "justifyContent": "space-between",
                    "alignItems": "center", "marginBottom": "14px",
                },
            ),
            rx.el.input(
                placeholder="Task title (required)…",
                value=TasksState.new_title,
                on_change=TasksState.set_new_title,
                auto_focus=True,
                class_name="nt-input",
                style={"marginBottom": "10px"},
            ),
            rx.el.input(
                placeholder="Description (optional)…",
                value=TasksState.new_description,
                on_change=TasksState.set_new_description,
                class_name="nt-input nt-input-sm",
                style={"marginBottom": "12px"},
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.label("Category", class_name="nt-label"),
                    rx.el.select(
                        rx.el.option("Tasks",      value="Tasks"),
                        rx.el.option("HR",         value="HR"),
                        rx.el.option("Scheduling", value="Scheduling"),
                        rx.el.option("Parts",      value="Parts"),
                        rx.el.option("Awareness",  value="Awareness"),
                        rx.el.option("Reminders",  value="Reminders"),
                        value=TasksState.new_category,
                        on_change=TasksState.set_new_category,
                        class_name="nt-select",
                    ),
                    class_name="nt-field",
                ),
                rx.el.div(
                    rx.el.label("Priority", class_name="nt-label"),
                    rx.el.select(
                        rx.el.option("Normal", value="normal"),
                        rx.el.option("High",   value="high"),
                        rx.el.option("Urgent", value="urgent"),
                        rx.el.option("Low",    value="low"),
                        value=TasksState.new_priority,
                        on_change=TasksState.set_new_priority,
                        class_name="nt-select",
                    ),
                    class_name="nt-field",
                ),
                rx.el.div(
                    rx.el.label("Due date", class_name="nt-label"),
                    rx.el.input(
                        type="date",
                        value=TasksState.new_due,
                        on_change=TasksState.set_new_due,
                        class_name="nt-input nt-date",
                    ),
                    class_name="nt-field",
                ),
                class_name="nt-row",
            ),
            rx.el.div(
                rx.el.button(
                    rx.cond(TasksState.saving_task, "Saving…", "Save Task"),
                    class_name="btn btn-primary",
                    on_click=TasksState.save_new_task,
                    disabled=~TasksState.can_save,
                    style={"fontSize": "13px", "padding": "8px 16px"},
                ),
                rx.el.button(
                    "Cancel",
                    class_name="btn btn-ghost",
                    on_click=TasksState.close_form,
                    style={"fontSize": "13px", "padding": "8px 12px"},
                ),
                style={"display": "flex", "gap": "8px", "marginTop": "14px"},
            ),
            class_name="new-task-form",
        ),
        rx.fragment(),
    )


# ── Priority dot (clickable cycle) ────────────────────────────────────────────

def _priority_dot(item: dict) -> rx.Component:
    dot_cls = rx.cond(
        item["is_overdue"],
        "priority-dot urgent",
        rx.cond(
            item["priority"] == "urgent",
            "priority-dot urgent",
            rx.cond(
                item["priority"] == "high",
                "priority-dot high",
                rx.cond(
                    item["priority"] == "low",
                    "priority-dot low",
                    "priority-dot normal",
                ),
            ),
        ),
    )
    title_str = rx.cond(
        item["is_overdue"],
        "OVERDUE — click to cycle priority",
        rx.cond(
            item["priority"] == "urgent",
            "Urgent — click to cycle to Low",
            rx.cond(
                item["priority"] == "high",
                "High — click to cycle to Urgent",
                rx.cond(
                    item["priority"] == "low",
                    "Low — click to cycle to Normal",
                    "Normal — click to cycle to High",
                ),
            ),
        ),
    )
    return rx.el.button(
        class_name=dot_cls,
        on_click=TasksState.cycle_priority(item["id"]),
        title=title_str,
    )


# ── Bulk action bar ───────────────────────────────────────────────────────────

def bulk_action_bar() -> rx.Component:
    return rx.cond(
        TasksState.has_selection,
        rx.el.div(
            rx.el.span(
                TasksState.selected_count.to_string(),
                " selected",
                style={"fontSize": "13px", "color": "var(--fg-2)", "fontWeight": "500"},
            ),
            rx.el.button(
                rx.cond(TasksState.bulk_completing, "Completing…", "✓  Complete Selected"),
                class_name="btn btn-primary",
                on_click=TasksState.complete_selected,
                disabled=TasksState.bulk_completing,
                style={"fontSize": "12px", "padding": "6px 14px"},
            ),
            rx.el.button(
                "✕  Clear",
                class_name="btn btn-ghost",
                on_click=TasksState.clear_selection,
                style={"fontSize": "12px", "padding": "6px 10px"},
            ),
            class_name="bulk-action-bar",
        ),
        rx.fragment(),
    )


# ── Select-all row ────────────────────────────────────────────────────────────

def select_all_row() -> rx.Component:
    return rx.cond(
        TasksState.task_count > 0,
        rx.el.div(
            rx.el.div(
                rx.cond(
                    TasksState.all_selected,
                    rx.el.span("☑", class_name="task-checkbox checked"),
                    rx.el.span("☐", class_name="task-checkbox"),
                ),
                rx.el.span(
                    rx.cond(
                        TasksState.all_selected,
                        "Deselect all",
                        "Select all",
                    ),
                    style={"fontSize": "12px", "color": "var(--fg-3)"},
                ),
                on_click=TasksState.toggle_select_all,
                style={"display": "flex", "alignItems": "center", "gap": "6px",
                       "cursor": "pointer", "padding": "4px 0"},
            ),
            style={"padding": "0 0 4px 2px"},
        ),
        rx.fragment(),
    )


# ── Task row ──────────────────────────────────────────────────────────────────

def task_row(item: dict) -> rx.Component:
    checkbox_cls = rx.cond(
        item["is_selected"],
        "task-checkbox checked",
        "task-checkbox",
    )
    checkbox_icon = rx.cond(item["is_selected"], "☑", "☐")
    return rx.el.div(
        rx.el.div(
            # Selection checkbox (only shown on open tasks)
            rx.cond(
                TasksState.status_filter != "completed",
                rx.el.span(
                    checkbox_icon,
                    class_name=checkbox_cls,
                    on_click=TasksState.toggle_select(item["id"]),
                    title="Select",
                ),
                rx.fragment(),
            ),
            # Priority dot
            _priority_dot(item),
            rx.el.div(
                rx.el.p(item["title"], class_name="card-title"),
                rx.el.div(
                    rx.el.span(
                        rx.cond(item["is_overdue"], "overdue", item["category"]),
                        class_name=rx.cond(
                            item["is_overdue"],
                            "chip chip-flag",
                            "chip chip-blue",
                        ),
                    ),
                    rx.cond(
                        item["due_date"] != "",
                        rx.el.span(
                            item["due_date"],
                            style={"fontSize": "11px", "color": "var(--fg-3)"},
                        ),
                        rx.fragment(),
                    ),
                    class_name="card-meta",
                ),
                class_name="card-body",
            ),
            # Complete button (or checkmark for completed)
            rx.cond(
                TasksState.status_filter == "completed",
                rx.el.span(
                    "✓",
                    style={
                        "fontSize": "13px",
                        "color": "var(--accent-positive)",
                        "marginLeft": "auto",
                        "paddingRight": "4px",
                    },
                ),
                rx.cond(
                    TasksState.completing_id == item["id"],
                    rx.el.button("…", class_name="complete-btn completing"),
                    rx.el.button(
                        "✓",
                        class_name="complete-btn",
                        on_click=TasksState.mark_complete(item["id"]),
                        title="Mark complete",
                    ),
                ),
            ),
            class_name="card-row",
            style={"alignItems": "center"},
        ),
        class_name=rx.cond(item["is_selected"], "card card-selected", "card"),
    )


# ── Group header (collapsible) ────────────────────────────────────────────────

def group_header(item: dict) -> rx.Component:
    chevron_cls = rx.cond(
        item["is_collapsed"],
        "task-group-chevron collapsed",
        "task-group-chevron",
    )
    return rx.el.div(
        rx.el.span("▾", class_name=chevron_cls),
        rx.el.span(item["name"], class_name="task-group-name"),
        rx.el.span(item["count"], class_name="task-group-count"),
        on_click=TasksState.toggle_group(item["name"]),
        class_name="task-group-header",
    )


# ── Dispatcher ────────────────────────────────────────────────────────────────

def render_flat_item(item: dict) -> rx.Component:
    return rx.cond(
        item["_type"] == "header",
        group_header(item),
        task_row(item),
    )


# ── Skeleton loader ───────────────────────────────────────────────────────────

def tasks_skeleton() -> rx.Component:
    return rx.fragment(
        rx.el.div(
            rx.el.div(class_name="skeleton", style={"height": "11px", "width": "60px"}),
            class_name="task-group-header",
        ),
        *[skeleton_card() for _ in range(4)],
        rx.el.div(
            rx.el.div(class_name="skeleton", style={"height": "11px", "width": "80px"}),
            class_name="task-group-header",
            style={"marginTop": "8px"},
        ),
        *[skeleton_card() for _ in range(3)],
    )


# ── Tasks page ────────────────────────────────────────────────────────────────

def tasks_page() -> rx.Component:
    return rx.el.div(
        rx.el.main(
            page_header(),
            filter_tabs(),
            quick_add_bar(),
            new_task_form(),
            bulk_action_bar(),
            rx.cond(
                TasksState.loading,
                tasks_skeleton(),
                rx.cond(
                    TasksState.task_count > 0,
                    rx.el.div(
                        select_all_row(),
                        rx.foreach(TasksState.visible_items, render_flat_item),
                        class_name="task-list",
                    ),
                    empty_state(
                        rx.cond(
                            TasksState.status_filter == "completed",
                            "No completed tasks",
                            "No open tasks",
                        ),
                        rx.cond(
                            TasksState.status_filter == "completed",
                            "Nothing has been marked complete yet.",
                            "All clear — nothing pending for tonight.",
                        ),
                    ),
                ),
            ),
            class_name="main main-single",
        ),
        rx.el.button(
            "+",
            class_name="fab",
            on_click=AppState.open_capture,
            title="Capture (⌘N)",
            aria_label="Quick capture",
        ),
        command_palette(),
        capture_modal(),
        class_name=AppState.app_class_name,
    )
