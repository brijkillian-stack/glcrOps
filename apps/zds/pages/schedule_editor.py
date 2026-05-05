"""
pages/schedule_editor.py — Phase N.2

Dedicated full-screen Week Schedule editor. Route:
    /zds/week/[week_id]/schedule

Design goals:
  - High-information density without feeling cluttered.
  - Click any cell → popover with cell-level actions.
  - Filter by shift, search by name. Both stay sticky during scroll.
  - Color-coded categories so the at-a-glance state of the week is obvious.
"""

from __future__ import annotations
import reflex as rx

from ..state import ZdsState
from ..state_schedule import ScheduleEditorState
from ..components.zds_header import zds_header
from shared.components.app_switcher import app_switcher


# ── Category styling ──────────────────────────────────────────────────────────
# Each cell is rendered with a background, accent border, and label color
# matching its category so the grid telegraphs the week's shape at a glance.
_CAT_STYLE: dict[str, dict] = {
    "working":       {"bg": "#ecfdf5", "border": "#a7f3d0", "fg": "#065f46"},
    "scheduled_off": {"bg": "#f3f4f6", "border": "#e5e7eb", "fg": "#9ca3af"},
    "pto":           {"bg": "#fef3c7", "border": "#fcd34d", "fg": "#92400e"},
    "mdl":           {"bg": "#fee2e2", "border": "#fca5a5", "fg": "#7f1d1d"},
    "called_off":    {"bg": "#fecaca", "border": "#dc2626", "fg": "#7f1d1d"},
    "other":         {"bg": "#e0f2fe", "border": "#7dd3fc", "fg": "#0369a1"},
    "blank":         {"bg": "transparent", "border": "transparent", "fg": "#d1d5db"},
}


def _shift_pill(label: str, value: str) -> rx.Component:
    """One pill in the shift filter row."""
    is_active = ScheduleEditorState.shift_filter == value
    return rx.el.button(
        label,
        on_click=ScheduleEditorState.set_shift_filter(value),
        background=rx.cond(is_active, "#0065BF", "white"),
        color=rx.cond(is_active, "white", "#374151"),
        border=rx.cond(is_active, "1px solid #0065BF", "1px solid #d1d5db"),
        style={
            "padding": "5px 14px",
            "borderRadius": "999px",
            "fontSize": "12px",
            "fontWeight": "600",
            "cursor": "pointer",
        },
    )


def _cell_chip(cell: dict, name: str, shift: str, date_iso: str) -> rx.Component:
    """One cell in the schedule grid — clickable to open the action popover."""
    cat = cell["category"]
    # Look up styles per category via rx.match — we can't index a dict with a Var.
    bg = rx.match(
        cat,
        ("working",       "#ecfdf5"),
        ("scheduled_off", "#f3f4f6"),
        ("pto",           "#fef3c7"),
        ("mdl",           "#fee2e2"),
        ("called_off",    "#fecaca"),
        ("other",         "#e0f2fe"),
        "transparent",
    )
    border = rx.match(
        cat,
        ("working",       "#a7f3d0"),
        ("scheduled_off", "#e5e7eb"),
        ("pto",           "#fcd34d"),
        ("mdl",           "#fca5a5"),
        ("called_off",    "#dc2626"),
        ("other",         "#7dd3fc"),
        "transparent",
    )
    fg = rx.match(
        cat,
        ("working",       "#065f46"),
        ("scheduled_off", "#9ca3af"),
        ("pto",           "#92400e"),
        ("mdl",           "#7f1d1d"),
        ("called_off",    "#7f1d1d"),
        ("other",         "#0369a1"),
        "#d1d5db",
    )
    short = rx.match(
        cat,
        ("working",       cell["value"]),
        ("scheduled_off", "OFF"),
        ("pto",           "PTO"),
        ("mdl",           "MDL"),
        ("called_off",    "CALL-OFF"),
        ("other",         cell["value"]),
        "—",
    )
    return rx.el.button(
        rx.cond(
            cell["overridden"],
            rx.hstack(
                rx.icon("pen-line", size=10, color=fg),
                rx.text(short, size="1", color=fg, weight="bold"),
                gap="2px", align="center",
            ),
            rx.text(short, size="1", color=fg, weight="bold"),
        ),
        on_click=ScheduleEditorState.open_cell_popover(
            name, shift, date_iso, cell["value"], cell["overridden"],
        ),
        background=bg,
        border_width="1px",
        border_style="solid",
        border_color=border,
        style={
            "padding": "6px 4px",
            "borderRadius": "6px",
            "fontSize": "10.5px",
            "minHeight": "30px",
            "width": "100%",
            "cursor": "pointer",
            "fontVariantNumeric": "tabular-nums",
            "lineHeight": "1.2",
            "whiteSpace": "nowrap",
            "overflow": "hidden",
            "textOverflow": "ellipsis",
        },
        title=cell["value"],
    )


def _shift_badge(shift: str) -> rx.Component:
    """Tiny shift pill next to TM names so users know which sheet they're from."""
    color_scheme = rx.match(
        shift,
        ("days", "amber"),
        ("swings", "violet"),
        ("graves", "blue"),
        "gray",
    )
    label = rx.match(
        shift,
        ("days", "D"),
        ("swings", "S"),
        ("graves", "G"),
        "?",
    )
    return rx.badge(
        label,
        color_scheme=color_scheme,
        variant="soft",
        size="1",
        style={"fontSize": "9px", "padding": "1px 5px", "minWidth": "16px"},
    )


def _row(item: dict) -> rx.Component:
    """One row in the editor grid — sticky-left name + 7 cell columns."""
    name  = item["name"]
    shift = item["shift"]
    cells = item["cells"]
    return rx.box(
        rx.hstack(
            # Sticky left: name + shift badge
            rx.hstack(
                _shift_badge(shift),
                rx.text(name, size="2", weight="medium",
                        white_space="nowrap", overflow="hidden",
                        text_overflow="ellipsis"),
                gap="6px", align="center",
                style={
                    "minWidth": "160px", "maxWidth": "160px",
                    "padding": "0 12px 0 8px",
                },
            ),
            # 7 cells (one per date) — all in a flex row that scrolls horizontally
            rx.foreach(
                cells,
                lambda cell, idx: rx.box(
                    _cell_chip(
                        cell,
                        name,
                        shift,
                        ScheduleEditorState.dates[idx],
                    ),
                    style={"flex": "1 1 0", "minWidth": "92px"},
                ),
            ),
            gap="4px", width="100%", align="center",
        ),
        padding="4px 0",
        border_bottom="1px solid #f3f4f6",
    )


# ── Header rows ──────────────────────────────────────────────────────────────

def _grid_header() -> rx.Component:
    """Day-name + date header strip, sticky to the top of the scroll area."""
    return rx.box(
        rx.hstack(
            # Left spacer matching the name column
            rx.box(style={"minWidth": "160px", "maxWidth": "160px"}),
            rx.foreach(
                ScheduleEditorState.dates,
                lambda iso, idx: rx.box(
                    rx.vstack(
                        rx.text(
                            ScheduleEditorState.weekdays[idx],
                            size="1", color="#6b7280", weight="bold",
                            letter_spacing="0.06em", text_transform="uppercase",
                        ),
                        rx.text(iso, size="1", color="#9ca3af",
                                font_variant_numeric="tabular-nums"),
                        gap="0", align="center",
                    ),
                    style={"flex": "1 1 0", "minWidth": "92px",
                           "padding": "6px 0", "textAlign": "center"},
                ),
            ),
            gap="4px", width="100%",
        ),
        position="sticky",
        top="0",
        z_index="5",
        background="#f9fafb",
        border_bottom="1px solid #e5e7eb",
    )


# ── Cell action popover ──────────────────────────────────────────────────────

def _cell_popover() -> rx.Component:
    """Modal-style popover with the cell action buttons."""
    return rx.cond(
        ScheduleEditorState.popover_open,
        rx.box(
            # Backdrop
            rx.box(
                on_click=ScheduleEditorState.close_cell_popover,
                style={"position": "fixed", "inset": "0",
                       "background": "rgba(0,0,0,0.45)", "zIndex": "60"},
            ),
            # Centered panel
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.text("Schedule Cell", size="1", color="#6b7280",
                                letter_spacing="0.06em", text_transform="uppercase",
                                weight="bold"),
                        rx.spacer(),
                        rx.icon_button(
                            rx.icon("x", size=14),
                            variant="ghost",
                            on_click=ScheduleEditorState.close_cell_popover,
                            cursor="pointer",
                        ),
                        width="100%", align="center",
                    ),
                    rx.heading(ScheduleEditorState.popover_tm_name, size="5"),
                    rx.text(
                        ScheduleEditorState.popover_date, " · ",
                        ScheduleEditorState.popover_shift,
                        size="2", color="#6b7280",
                    ),
                    rx.box(
                        rx.text("Current value", size="1", color="#9ca3af",
                                weight="bold", letter_spacing="0.05em"),
                        rx.text(
                            ScheduleEditorState.popover_value,
                            size="3", weight="medium",
                        ),
                        rx.cond(
                            ScheduleEditorState.popover_overridden,
                            rx.badge("Overridden", color_scheme="violet",
                                     variant="soft", size="1"),
                            rx.fragment(),
                        ),
                        padding="10px 12px",
                        background="#f9fafb",
                        border="1px solid #e5e7eb",
                        border_radius="8px",
                        width="100%",
                    ),
                    # Optional note
                    rx.el.input(
                        type="text",
                        placeholder="Optional note (saved with the override)",
                        value=ScheduleEditorState.popover_note,
                        on_change=ScheduleEditorState.set_popover_note,
                        style={
                            "width": "100%", "padding": "6px 10px",
                            "fontSize": "13px",
                            "border": "1px solid #d1d5db",
                            "borderRadius": "6px",
                            "outline": "none",
                        },
                    ),
                    # Actions — quick toggles
                    rx.grid(
                        rx.button(
                            rx.icon("calendar-clock", size=14),
                            "Mark PTO",
                            on_click=ScheduleEditorState.mark_cell_pto,
                            variant="soft", color_scheme="amber",
                            cursor="pointer",
                        ),
                        rx.button(
                            rx.icon("heart-pulse", size=14),
                            "Mark MDL",
                            on_click=ScheduleEditorState.mark_cell_mdl,
                            variant="soft", color_scheme="red",
                            cursor="pointer",
                        ),
                        rx.button(
                            rx.icon("octagon-x", size=14),
                            "Mark Called Off",
                            on_click=ScheduleEditorState.mark_cell_called_off,
                            color_scheme="red",
                            cursor="pointer",
                        ),
                        rx.button(
                            rx.icon("user-x", size=14),
                            "Mark OFF",
                            on_click=ScheduleEditorState.mark_cell_off,
                            variant="soft", color_scheme="gray",
                            cursor="pointer",
                        ),
                        columns="2", gap="6px", width="100%",
                    ),
                    rx.button(
                        rx.icon("rotate-ccw", size=14),
                        "Reset to xlsx value",
                        on_click=ScheduleEditorState.reset_cell,
                        variant="ghost", color_scheme="gray",
                        cursor="pointer",
                        width="100%",
                    ),
                    gap="10px", width="100%", align="stretch",
                ),
                style={
                    "position": "fixed",
                    "top": "50%", "left": "50%",
                    "transform": "translate(-50%, -50%)",
                    "width": "min(440px, calc(100vw - 32px))",
                    "background": "white",
                    "border": "1px solid #e5e7eb",
                    "borderRadius": "12px",
                    "padding": "16px",
                    "boxShadow": "0 24px 64px rgba(0,0,0,0.32)",
                    "zIndex": "61",
                },
            ),
        ),
        rx.fragment(),
    )


# ── Page ─────────────────────────────────────────────────────────────────────

def schedule_editor_page() -> rx.Component:
    """The /zds/week/[week_id]/schedule page."""
    return rx.box(
        # Top header (app switcher + back arrow + title)
        rx.hstack(
            app_switcher(),
            rx.link(
                rx.icon("arrow-left", size=16),
                href=ScheduleEditorState.back_url,
                color="#6b7280",
            ),
            rx.vstack(
                rx.heading("Week Schedule", size="5"),
                rx.text(ScheduleEditorState.week_label, size="1",
                        color="#9ca3af", letter_spacing="0.06em"),
                gap="0",
            ),
            rx.spacer(),
            # Filter row — shift pills + search
            _shift_pill("All",     "all"),
            _shift_pill("Days",    "days"),
            _shift_pill("Swings",  "swings"),
            _shift_pill("Graves",  "graves"),
            rx.el.input(
                type="text",
                placeholder="Search by name…",
                value=ScheduleEditorState.search_query,
                on_change=ScheduleEditorState.set_search_query,
                style={
                    "padding": "6px 10px", "fontSize": "13px",
                    "border": "1px solid #d1d5db", "borderRadius": "999px",
                    "minWidth": "180px", "outline": "none",
                },
            ),
            align="center", gap="10px",
            padding="14px 24px",
            border_bottom="1px solid #e5e7eb",
            background="white",
            position="sticky", top="0", z_index="10",
            width="100%",
        ),
        # Body
        rx.cond(
            ScheduleEditorState.loading,
            rx.center(rx.spinner(size="3"), padding="80px 0"),
            rx.cond(
                ScheduleEditorState.error != "",
                rx.box(
                    rx.callout(ScheduleEditorState.error,
                               color_scheme="amber", icon="triangle-alert"),
                    padding="20px 24px",
                ),
                rx.box(
                    _grid_header(),
                    rx.box(
                        rx.foreach(ScheduleEditorState.filtered_rows, _row),
                        padding="0 8px",
                    ),
                    rx.text(
                        "Showing ", ScheduleEditorState.filtered_count.to_string(),
                        " of ", ScheduleEditorState.total_count.to_string(),
                        " TMs",
                        size="1", color="#9ca3af",
                        padding="14px 24px",
                    ),
                ),
            ),
        ),
        _cell_popover(),
        background="#f9fafb",
        min_height="100vh",
        on_mount=ScheduleEditorState.on_load,
    )
