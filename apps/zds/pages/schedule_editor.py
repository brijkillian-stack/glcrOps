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


# ── Unknown-name reconciler banner (Phase O.4) ───────────────────────────────

def _unresolved_row(item: dict) -> rx.Component:
    """One row inside the Unknown TMs banner — Phase Q: whole row is a button
    that opens the linker modal."""
    return rx.el.button(
        rx.hstack(
            rx.icon("user-round-search", size=14, color="#92400e"),
            rx.vstack(
                rx.text(item["display"], size="2", weight="bold", color="#7c2d12"),
                rx.text("Unknown — on the ", item["shift"],
                        " sheet · click to link",
                        size="1", color="#92400e"),
                gap="0", align="start", flex="1",
            ),
            rx.spacer(),
            rx.icon("chevron-right", size=14, color="#92400e"),
            width="100%", align="center", gap="10px",
        ),
        on_click=ScheduleEditorState.open_reconcile_picker(
            item["display"], item["first"], item["shift"],
        ),
        style={
            "padding": "8px 12px",
            "background": "#fffbeb",
            "border": "1px solid #fcd34d",
            "borderRadius": "6px",
            "cursor": "pointer",
            "width": "100%",
            "textAlign": "left",
        },
        _hover={"background": "#fef3c7", "borderColor": "#f59e0b"},
        title="Click to link this name to an existing TM or create a new one",
    )


def _link_option(opt: dict) -> rx.Component:
    """One row in the Match-to-existing list inside the linker modal.

    Reflex 0.9 chains event handlers when on_click is a list — first set
    the match target, then apply.
    """
    return rx.el.button(
        rx.hstack(
            rx.icon("user", size=12, color="#0065BF"),
            rx.text(opt["display_name"], size="2", weight="medium",
                    color="#111827"),
            rx.spacer(),
            rx.icon("link-2", size=11, color="#0065BF"),
            width="100%", align="center", gap="8px",
        ),
        on_click=[
            ScheduleEditorState.set_reconcile_match_tm_id(opt["id"]),
            ScheduleEditorState.reconcile_apply_match(
                ScheduleEditorState.reconcile_target_first,
            ),
        ],
        style={
            "padding": "8px 10px",
            "background": "white",
            "border": "1px solid #e5e7eb",
            "borderRadius": "6px",
            "cursor": "pointer",
            "width": "100%",
            "textAlign": "left",
        },
        _hover={"background": "#eaf4ff", "borderColor": "#0065BF"},
    )


def _link_picker_modal() -> rx.Component:
    """Phase Q — search + create modal for linking an unresolved xlsx name."""
    return rx.cond(
        ScheduleEditorState.reconcile_target_display != "",
        rx.box(
            rx.box(
                on_click=ScheduleEditorState.cancel_reconcile,
                style={
                    "position": "fixed", "inset": "0",
                    "background": "rgba(0,0,0,0.45)",
                    "zIndex": "60",
                },
            ),
            rx.box(
                # Header
                rx.hstack(
                    rx.vstack(
                        rx.text("Link unknown TM", size="1", color="#9ca3af",
                                weight="bold", letter_spacing="0.06em",
                                text_transform="uppercase"),
                        rx.heading(
                            ScheduleEditorState.reconcile_target_display,
                            size="5",
                        ),
                        rx.text("Found on the ",
                                ScheduleEditorState.reconcile_target_shift,
                                " sheet · resolve by matching to an existing "
                                "TM (recommended) or creating a new one.",
                                size="1", color="#6b7280"),
                        gap="2px", align="start",
                    ),
                    rx.spacer(),
                    rx.icon_button(
                        rx.icon("x", size=14),
                        variant="ghost",
                        on_click=ScheduleEditorState.cancel_reconcile,
                        cursor="pointer",
                    ),
                    width="100%", align="start",
                ),
                # Create-new shortcut
                rx.button(
                    rx.icon("user-plus", size=14),
                    "Create new TM as “",
                    ScheduleEditorState.reconcile_target_display,
                    "”",
                    on_click=ScheduleEditorState.reconcile_create_new(
                        ScheduleEditorState.reconcile_target_display,
                        ScheduleEditorState.reconcile_target_shift,
                    ),
                    color_scheme="green",
                    size="2",
                    width="100%",
                    cursor="pointer",
                ),
                rx.divider(margin="14px 0 10px"),
                # Search
                rx.text("Or match to an existing TM:",
                        size="1", color="#6b7280", weight="medium"),
                rx.el.input(
                    type="text",
                    placeholder="Search by display name…",
                    value=ScheduleEditorState.reconcile_search,
                    on_change=ScheduleEditorState.set_reconcile_search,
                    style={
                        "width": "100%", "padding": "8px 10px",
                        "fontSize": "13px",
                        "border": "1px solid #d1d5db",
                        "borderRadius": "6px",
                        "outline": "none",
                        "marginTop": "6px",
                        "marginBottom": "8px",
                    },
                ),
                # Filtered list
                rx.scroll_area(
                    rx.vstack(
                        rx.foreach(
                            ScheduleEditorState.filtered_reconcile_options,
                            _link_option,
                        ),
                        gap="4px", width="100%",
                    ),
                    max_height="320px",
                    width="100%",
                ),
                style={
                    "position": "fixed",
                    "top": "50%", "left": "50%",
                    "transform": "translate(-50%, -50%)",
                    "width": "min(520px, calc(100vw - 32px))",
                    "background": "white",
                    "border": "1px solid #e5e7eb",
                    "borderRadius": "12px",
                    "padding": "16px",
                    "boxShadow": "0 24px 64px rgba(0,0,0,0.32)",
                    "zIndex": "61",
                    "display": "flex",
                    "flexDirection": "column",
                    "gap": "10px",
                },
            ),
        ),
        rx.fragment(),
    )


def _unresolved_banner() -> rx.Component:
    """Surface xlsx names that don't resolve to any entity."""
    return rx.cond(
        ScheduleEditorState.unresolved_names.length() > 0,
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.icon("triangle-alert", size=15, color="#b45309"),
                    rx.text(
                        "Unknown TMs in this schedule",
                        size="2", weight="bold", color="#7c2d12",
                    ),
                    rx.spacer(),
                    rx.badge(
                        ScheduleEditorState.unresolved_names.length(),
                        color_scheme="amber", variant="soft",
                    ),
                    width="100%", align="center",
                ),
                rx.text(
                    "These xlsx names don't match any TM. Create a new entry "
                    "for them, or alias to an existing TM (saves the alias to "
                    "their People profile so future imports resolve cleanly).",
                    size="1", color="#92400e",
                ),
                rx.vstack(
                    rx.foreach(ScheduleEditorState.unresolved_names, _unresolved_row),
                    gap="6px", width="100%",
                ),
                gap="8px", width="100%",
            ),
            padding="14px 16px",
            margin="14px 24px",
            background="#fef3c7",
            border="1px solid #fbbf24",
            border_radius="10px",
        ),
        rx.fragment(),
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
                        rx.button(
                            rx.icon("shield-check", size=14),
                            "Mark PDL",
                            on_click=ScheduleEditorState.mark_cell_pdl,
                            variant="soft", color_scheme="blue",
                            cursor="pointer",
                        ),
                        rx.button(
                            rx.icon("circle-ellipsis", size=14),
                            "Mark Other",
                            on_click=ScheduleEditorState.mark_cell_other,
                            variant="soft", color_scheme="cyan",
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
                    # Phase O.4 — surface unknown TMs from the xlsx
                    _unresolved_banner(),
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
        # Phase Q — Click-to-link picker for unknown xlsx names
        _link_picker_modal(),
        background="#f9fafb",
        min_height="100vh",
        on_mount=ScheduleEditorState.on_load,
    )
