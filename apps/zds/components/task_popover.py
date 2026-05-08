"""task_popover.py — inline annotation popover for task lines (Phase 4k.6).

Renders directly inside each task <li> as an absolute-positioned child.
Visibility is controlled by ZdsState.task_popover_task_id == task["id"].

Views:
  root       — color swatches + symbol pills + action rows
  note       — textarea + save/cancel for task note
  edit_text  — input + save/cancel to rename the task

Outside-click dismiss is handled by a full-page transparent overlay
(task-popover-overlay) that fires close_task_popover on click.
"""

import reflex as rx
from ..state import ZdsState
from .glcr_icons import glcr_icon

# ── Annotation constants ─────────────────────────────────────────────────────

_HL_COLORS = [
    ("yellow",  "var(--c-yellow,  #d97706)"),
    ("red",     "var(--c-red,     #dc2626)"),
    ("blue",    "var(--c-blue,    #2563eb)"),
    ("green",   "var(--c-green,   #16a34a)"),
    ("orange",  "var(--c-orange,  #ea580c)"),
    ("purple",  "var(--c-purple,  #7c3aed)"),
]

# (section, slug, label) — section MUST match the directory the SVG
# lives in under assets/icons/glcr/. Verified against the canonical GLCR
# icon pack; section directories are: ops, maint, porter, uniform,
# casino, clean, zds, controls, nav, actions, status, ui, people.
# (No 'alerts' directory; alerts.svg lives in ops/.)
_SYMBOLS = [
    ("ui",     "star-favorite",  "Priority"),
    ("ui",     "pin-bookmark",   "Remember"),
    ("status", "warning",        "Watch"),
    ("status", "info",           "Note attached"),
    ("status", "clock-pending",  "Time-sensitive"),
    ("ops",    "alerts",         "Alert"),
    ("maint",  "inspection",     "Inspect"),
    ("maint",  "safety-check",   "Safety priority"),
]


# ── Overlay (outside-click dismiss) ──────────────────────────────────────────

def task_popover_overlay() -> rx.Component:
    """Full-page transparent overlay shown only when a popover is open.
    Clicking anywhere outside the popover fires close_task_popover.
    The popover itself stops propagation on click so inner interactions
    don't bubble to the overlay.
    """
    return rx.cond(
        ZdsState.task_popover_open,
        rx.box(
            class_name="task-popover-overlay",
            on_click=ZdsState.close_task_popover,
            z_index="150",
        ),
        rx.fragment(),
    )


# ── Root view ────────────────────────────────────────────────────────────────

def _color_swatch(color_name: str, css_val: str) -> rx.Component:
    is_active = ZdsState.task_popover_existing_highlight == color_name
    return rx.box(
        width="18px", height="18px",
        border_radius="50%",
        background=css_val,
        cursor="pointer",
        border=rx.cond(is_active, "2px solid #111", "2px solid transparent"),
        on_click=ZdsState.set_task_highlight(color_name),
        title=color_name,
        flex_shrink="0",
    )


def _symbol_pill(section: str, slug: str, label: str) -> rx.Component:
    existing = ZdsState.task_popover_existing_symbol
    is_active = (existing["section"] == section) & (existing["slug"] == slug)
    icon_html = glcr_icon(section, slug, size=13)
    return rx.box(
        rx.html(icon_html),
        padding="3px 5px",
        border_radius="4px",
        cursor="pointer",
        background=rx.cond(is_active, "var(--c-blue-light, #dbeafe)", "transparent"),
        border=rx.cond(is_active, "1px solid var(--c-blue, #2563eb)",
                       "1px solid var(--c-border, #e5e7eb)"),
        on_click=ZdsState.set_task_symbol(section, slug),
        title=label,
        flex_shrink="0",
    )


def _root_view() -> rx.Component:
    has_note     = ZdsState.task_popover_existing_note != ""
    is_skipped   = ZdsState.task_annotation_data.contains(ZdsState.task_popover_task_id)
    is_adhoc     = ZdsState.task_popover_is_adhoc

    return rx.vstack(
        # ── Highlight color row ──────────────────────────────────────────
        rx.hstack(
            *[_color_swatch(name, css) for name, css in _HL_COLORS],
            rx.box(
                "×",
                font_size="12px", color="#9ca3af",
                cursor="pointer",
                padding="0 2px",
                on_click=ZdsState.set_task_highlight(""),
                title="Clear highlight",
            ),
            gap="4px", align="center",
        ),
        # ── Symbol pills ─────────────────────────────────────────────────
        rx.flex(
            *[_symbol_pill(sec, slug, lbl) for sec, slug, lbl in _SYMBOLS],
            rx.box(
                "×",
                font_size="12px", color="#9ca3af",
                cursor="pointer",
                padding="0 2px",
                on_click=ZdsState.set_task_symbol("", ""),
                title="Clear symbol",
            ),
            gap="4px", wrap="wrap", align="center",
        ),
        rx.separator(width="100%", margin="4px 0"),
        # ── Note row ─────────────────────────────────────────────────────
        rx.hstack(
            rx.html(glcr_icon("actions", "edit-pencil", size=13)),
            rx.text(
                rx.cond(has_note, "Edit note", "Add note"),
                size="2",
            ),
            cursor="pointer",
            on_click=ZdsState.set_task_popover_view("note"),
            gap="6px", align="center", width="100%",
            padding="3px 0",
            _hover={"background": "#f3f4f6"},
            border_radius="4px",
        ),
        # ── Skip tonight row ─────────────────────────────────────────────
        rx.hstack(
            rx.html(glcr_icon("actions", "clock-pending", size=13)),
            rx.text("Skip tonight", size="2"),
            cursor="pointer",
            on_click=ZdsState.toggle_task_skip,
            gap="6px", align="center", width="100%",
            padding="3px 0",
            _hover={"background": "#f3f4f6"},
            border_radius="4px",
        ),
        # ── Edit text row ─────────────────────────────────────────────────
        rx.hstack(
            rx.html(glcr_icon("ui", "menu-list", size=13)),
            rx.text("Edit text", size="2"),
            cursor="pointer",
            on_click=ZdsState.set_task_popover_view("edit_text"),
            gap="6px", align="center", width="100%",
            padding="3px 0",
            _hover={"background": "#f3f4f6"},
            border_radius="4px",
        ),
        # ── Delete (adhoc only) ───────────────────────────────────────────
        rx.cond(
            is_adhoc,
            rx.hstack(
                rx.html(glcr_icon("actions", "delete-trash", size=13)),
                rx.text("Delete task", size="2", color="#dc2626"),
                cursor="pointer",
                on_click=ZdsState.delete_adhoc_task_from_popover,
                gap="6px", align="center", width="100%",
                padding="3px 0",
                _hover={"background": "#fef2f2"},
                border_radius="4px",
            ),
            rx.fragment(),
        ),
        # ── Clear all ────────────────────────────────────────────────────
        rx.hstack(
            rx.html(glcr_icon("ui", "close-x", size=13)),
            rx.text("Clear all", size="2", color="#9ca3af"),
            cursor="pointer",
            on_click=ZdsState.clear_task_annotation,
            gap="6px", align="center", width="100%",
            padding="3px 0",
            _hover={"background": "#f3f4f6"},
            border_radius="4px",
        ),
        gap="4px", align="start", width="100%",
    )


# ── Note sub-view ─────────────────────────────────────────────────────────────

def _note_view() -> rx.Component:
    return rx.vstack(
        rx.text("Task note", weight="bold", size="2"),
        rx.text_area(
            value=ZdsState.task_popover_note_text,
            on_change=ZdsState.set_task_popover_note_text,
            placeholder="Note about this task tonight…",
            rows="3",
            width="100%",
            auto_focus=True,
        ),
        rx.hstack(
            rx.button(
                "Save",
                size="1", color_scheme="blue",
                on_click=ZdsState.save_task_note,
            ),
            rx.button(
                "Cancel",
                size="1", variant="ghost",
                on_click=ZdsState.set_task_popover_view("root"),
            ),
            gap="6px",
        ),
        gap="6px", width="100%",
    )


# ── Edit-text sub-view ────────────────────────────────────────────────────────

def _edit_text_view() -> rx.Component:
    return rx.el.form(
        rx.vstack(
            rx.text("Edit task text", weight="bold", size="2"),
            rx.input(
                name="text",
                placeholder="Task name…",
                size="2",
                width="100%",
                auto_focus=True,
            ),
            rx.hstack(
                rx.button(
                    "Save",
                    type="submit",
                    size="1", color_scheme="blue",
                ),
                rx.button(
                    "Cancel",
                    type="button",
                    size="1", variant="ghost",
                    on_click=ZdsState.set_task_popover_view("root"),
                ),
                gap="6px",
            ),
            gap="6px", width="100%",
        ),
        on_submit=ZdsState.edit_task_text,
    )


# ── Main popover body ─────────────────────────────────────────────────────────

def task_popover_body() -> rx.Component:
    """The popover panel itself. Rendered inside the task <li> as an
    absolute-positioned div. Clicks inside stop propagation so they don't
    bubble to the overlay and close the popover."""
    return rx.box(
        rx.match(
            ZdsState.task_popover_view,
            ("root",      _root_view()),
            ("note",      _note_view()),
            ("edit_text", _edit_text_view()),
            _root_view(),
        ),
        class_name="task-popover",
        on_click=rx.stop_propagation,  # prevent overlay from catching inner clicks
        z_index="200",
    )


# ── Per-task inline popover (rendered inside each <li>) ───────────────────────

def task_popover(task_id_var) -> rx.Component:
    """Render the popover only when this task's ID matches the open popover ID."""
    return rx.cond(
        ZdsState.task_popover_open & (ZdsState.task_popover_task_id == task_id_var),
        task_popover_body(),
        rx.fragment(),
    )
