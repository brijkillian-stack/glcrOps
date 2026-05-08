"""
apps/admin/pages/tasks.py — Zone Task Manager (Phase 4k.1 rebuild)

Route: /admin/tasks
Three-tab view:
  Tab 0 — All Tasks: filter bar + table with code column + inline add
  Tab 1 — Neglect Ranking: zone/rr/aux tasks by days-since-last-assignment
Edit drawer:
  - Name / Code / Default Zone / Category / Active / Notes fields
  - Zone Affinity bar chart
  - Per-day overrides section (task_day_overrides CRUD)
"""

from __future__ import annotations

import reflex as rx

from apps.admin.tasks_state import (
    ZoneTasksState,
    CATEGORY_OPTIONS,
    CATEGORY_FILTER_OPTIONS,
    DEFAULT_ZONE_OPTIONS,
)
from shared.components.admin_section_head import admin_breadcrumb


# ── Style tokens ─────────────────────────────────────────────────────────────

_SURFACE  = "var(--surface-card)"
_BORDER   = "var(--border-subtle)"
_INK1     = "var(--ink1)"
_INK2     = "var(--ink2)"
_INK3     = "var(--ink3)"
_ACCENT   = "var(--accent-blue)"
_FONT     = "var(--font)"

_CAT_COLORS: dict[str, str] = {
    "zone":       "#2563eb",
    "rr":         "#7c3aed",
    "aux":        "#d97706",
    "overlap_pm": "#0891b2",
    "overlap_am": "#059669",
}


# ── Icon helper ───────────────────────────────────────────────────────────────

def _icon(name: str, size: int = 16) -> rx.Component:
    """Render a GLCR SVG icon from assets/icons/glcr/actions/<name>.svg."""
    return rx.image(
        src=f"/icons/glcr/actions/{name}.svg",
        width=f"{size}px",
        height=f"{size}px",
        style={"display": "inline-block", "verticalAlign": "middle", "flexShrink": "0"},
    )


# ── Category badge ────────────────────────────────────────────────────────────

def _cat_badge(category: rx.Var) -> rx.Component:
    # Use rx.match to select the background color per category value
    bg = rx.match(
        category,
        ("zone",       "#dbeafe"),
        ("rr",         "#ede9fe"),
        ("aux",        "#fef3c7"),
        ("overlap_pm", "#cffafe"),
        ("overlap_am", "#d1fae5"),
        "#f1f5f9",  # default
    )
    fg = rx.match(
        category,
        ("zone",       "#1d4ed8"),
        ("rr",         "#6d28d9"),
        ("aux",        "#92400e"),
        ("overlap_pm", "#0e7490"),
        ("overlap_am", "#065f46"),
        _INK2,
    )
    return rx.el.span(
        category,
        style={
            "fontSize":      "11px",
            "fontWeight":    "600",
            "padding":       "2px 8px",
            "borderRadius":  "4px",
            "background":    bg,
            "color":         fg,
            "textTransform": "uppercase",
            "letterSpacing": "0.04em",
            "whiteSpace":    "nowrap",
        },
    )


# ── Tab strip ─────────────────────────────────────────────────────────────────

def _tab_btn(label: str, idx: int) -> rx.Component:
    is_active = ZoneTasksState.active_tab == idx
    return rx.el.button(
        label,
        on_click=ZoneTasksState.set_tab(idx),
        style={
            "padding":      "7px 16px",
            "fontSize":     "13px",
            "fontWeight":   rx.cond(is_active, "700", "500"),
            "border":       "none",
            "borderBottom": rx.cond(is_active, f"2px solid {_ACCENT}", "2px solid transparent"),
            "background":   "transparent",
            "color":        rx.cond(is_active, _ACCENT, _INK2),
            "cursor":       "pointer",
            "fontFamily":   _FONT,
            "transition":   "all 0.12s",
        },
    )


def _tab_strip() -> rx.Component:
    return rx.el.div(
        _tab_btn("All Tasks", 0),
        _tab_btn("Neglect Ranking", 1),
        style={
            "display":      "flex",
            "gap":          "4px",
            "borderBottom": f"1px solid {_BORDER}",
            "marginBottom": "20px",
        },
    )


# ── Shared button ─────────────────────────────────────────────────────────────

def _btn(
    label: str | rx.Component,
    on_click,
    variant: str = "default",
    disabled: "rx.Var | bool" = False,
    icon: str = "",
) -> rx.Component:
    base: dict = {
        "display":      "inline-flex",
        "alignItems":   "center",
        "gap":          "6px",
        "padding":      "7px 14px",
        "fontSize":     "13px",
        "fontWeight":   "600",
        "borderRadius": "6px",
        "border":       f"1px solid {_BORDER}",
        "cursor":       "pointer",
        "fontFamily":   _FONT,
        "transition":   "opacity 0.12s",
        "whiteSpace":   "nowrap",
    }
    if variant == "primary":
        base.update({"background": _ACCENT, "color": "#fff", "border": "none"})
    elif variant == "danger":
        base.update({"background": "transparent", "color": "#ef4444",
                     "border": "1px solid #ef4444"})
    elif variant == "ghost":
        base.update({"background": "transparent", "color": _INK2, "border": "none",
                     "padding": "4px 6px"})
    else:
        base.update({"background": _SURFACE, "color": _INK2})
    children = [_icon(icon), label] if icon else [label]
    return rx.el.button(*children, on_click=on_click, disabled=disabled, style=base)


# ── Select helper ─────────────────────────────────────────────────────────────

def _select(value: rx.Var, on_change, options: list[dict], width: str = "100%") -> rx.Component:
    return rx.el.select(
        *[rx.el.option(o["label"], value=o["value"]) for o in options],
        value=value,
        on_change=on_change,
        style={
            "padding":      "6px 10px",
            "fontSize":     "13px",
            "borderRadius": "6px",
            "border":       f"1px solid {_BORDER}",
            "background":   _SURFACE,
            "color":        _INK1,
            "fontFamily":   _FONT,
            "width":        width,
        },
    )


# ── Filter bar ────────────────────────────────────────────────────────────────

def _filter_bar() -> rx.Component:
    return rx.el.div(
        # Search input
        rx.el.div(
            _icon("search", 14),
            rx.el.input(
                placeholder="Search by name or code …",
                value=ZoneTasksState.filter_search,
                on_change=ZoneTasksState.set_filter_search,
                style={
                    "border":     "none",
                    "outline":    "none",
                    "flex":       "1",
                    "fontSize":   "13px",
                    "background": "transparent",
                    "color":      _INK1,
                    "fontFamily": _FONT,
                },
            ),
            style={
                "display":      "flex",
                "alignItems":   "center",
                "gap":          "8px",
                "flex":         "1",
                "padding":      "7px 12px",
                "borderRadius": "6px",
                "border":       f"1px solid {_BORDER}",
                "background":   _SURFACE,
            },
        ),
        # Category filter
        _select(
            ZoneTasksState.filter_category,
            ZoneTasksState.set_filter_category,
            CATEGORY_FILTER_OPTIONS,
            width="160px",
        ),
        # Show archived toggle
        rx.el.label(
            rx.el.input(
                type="checkbox",
                checked=ZoneTasksState.show_archived,
                on_change=lambda _: ZoneTasksState.toggle_show_archived(),
                style={"marginRight": "6px"},
            ),
            "Archived",
            style={"fontSize": "13px", "color": _INK2, "cursor": "pointer",
                   "display": "flex", "alignItems": "center", "whiteSpace": "nowrap"},
        ),
        # Clear
        _btn("Clear", ZoneTasksState.clear_filters, variant="ghost"),
        style={
            "display":       "flex",
            "gap":           "10px",
            "alignItems":    "center",
            "marginBottom":  "16px",
            "flexWrap":      "wrap",
        },
    )


# ── Add new task strip ────────────────────────────────────────────────────────

def _add_task_row() -> rx.Component:
    return rx.el.div(
        rx.el.span("+ New task", style={"fontSize": "12px", "fontWeight": "600",
                                        "color": _INK2, "textTransform": "uppercase",
                                        "letterSpacing": "0.06em", "marginBottom": "10px",
                                        "display": "block"}),
        rx.el.div(
            rx.el.input(
                placeholder="Task name …",
                value=ZoneTasksState.new_name,
                on_change=ZoneTasksState.set_new_name,
                style={
                    "flex": "1", "minWidth": "180px",
                    "padding": "6px 10px", "fontSize": "13px",
                    "borderRadius": "6px", "border": f"1px solid {_BORDER}",
                    "background": _SURFACE, "color": _INK1, "fontFamily": _FONT,
                },
            ),
            _select(ZoneTasksState.new_zone, ZoneTasksState.set_new_zone,
                    DEFAULT_ZONE_OPTIONS, width="140px"),
            _select(ZoneTasksState.new_category, ZoneTasksState.set_new_category,
                    [{"label": c.replace("_", " ").upper(), "value": c} for c in CATEGORY_OPTIONS],
                    width="130px"),
            _btn("Add", ZoneTasksState.add_task, variant="primary",
                 icon="add-new", disabled=ZoneTasksState.adding),
            style={"display": "flex", "gap": "10px", "alignItems": "center", "flexWrap": "wrap"},
        ),
        rx.cond(
            ZoneTasksState.add_error != "",
            rx.el.span(ZoneTasksState.add_error,
                       style={"color": "#ef4444", "fontSize": "12px", "marginTop": "6px",
                              "display": "block"}),
            rx.el.span(""),
        ),
        style={
            "padding":      "14px 16px",
            "background":   "#f8fafc",
            "borderRadius": "8px",
            "border":       f"1px dashed {_BORDER}",
            "marginBottom": "16px",
        },
    )


# ── Task table ────────────────────────────────────────────────────────────────

def _task_row(t: dict) -> rx.Component:
    is_archived = ~t["active"]
    return rx.el.tr(
        # Name
        rx.el.td(
            rx.el.span(
                t["name"],
                style={
                    "fontWeight":     "500",
                    "color":          rx.cond(is_archived, _INK3, _INK1),
                    "textDecoration": rx.cond(is_archived, "line-through", "none"),
                },
            ),
            style={"padding": "9px 12px"},
        ),
        # Code
        rx.el.td(
            rx.cond(
                t["code"] != None,
                rx.el.code(
                    t["code"],
                    style={"fontSize": "11px", "color": "#6366f1",
                           "background": "#eef2ff", "padding": "2px 6px",
                           "borderRadius": "3px"},
                ),
                rx.el.span("—", style={"color": _INK3, "fontSize": "12px"}),
            ),
            style={"padding": "9px 12px"},
        ),
        # Default zone
        rx.el.td(
            rx.el.code(
                rx.cond(t["default_zone"] != None, t["default_zone"], "—"),
                style={"fontSize": "11px", "color": _INK2},
            ),
            style={"padding": "9px 12px"},
        ),
        # Category
        rx.el.td(_cat_badge(t["category"]), style={"padding": "9px 12px"}),
        # Status
        rx.el.td(
            rx.cond(
                t["active"],
                rx.el.span("Active", style={"color": "#16a34a", "fontSize": "12px", "fontWeight": "600"}),
                rx.el.span("Archived", style={"color": _INK3, "fontSize": "12px"}),
            ),
            style={"padding": "9px 12px"},
        ),
        # Edit action
        rx.el.td(
            _btn("Edit", ZoneTasksState.open_drawer(t["id"]), icon="edit-pencil"),
            style={"padding": "9px 12px"},
        ),
        style={
            "borderBottom": f"1px solid {_BORDER}",
            "background":   rx.cond(is_archived, "#f8fafc", "transparent"),
            "_hover":       {"background": "#f0f9ff"},
        },
    )


_TABLE_HEADERS = ["Name", "Code", "Default Zone", "Category", "Status", ""]


def _tasks_tab() -> rx.Component:
    return rx.el.div(
        _filter_bar(),
        _add_task_row(),
        rx.cond(
            ZoneTasksState.loading,
            rx.el.div("Loading…", style={"color": _INK3, "fontSize": "14px", "padding": "24px 0"}),
            rx.el.div(
                rx.el.table(
                    rx.el.thead(
                        rx.el.tr(
                            *[
                                rx.el.th(
                                    h,
                                    style={
                                        "padding":       "8px 12px",
                                        "textAlign":     "left",
                                        "fontSize":      "11px",
                                        "fontWeight":    "600",
                                        "textTransform": "uppercase",
                                        "letterSpacing": "0.06em",
                                        "color":         _INK3,
                                        "borderBottom":  f"1px solid {_BORDER}",
                                        "whiteSpace":    "nowrap",
                                    },
                                )
                                for h in _TABLE_HEADERS
                            ]
                        )
                    ),
                    rx.el.tbody(rx.foreach(ZoneTasksState.visible_tasks, _task_row)),
                    style={"width": "100%", "borderCollapse": "collapse", "fontSize": "13px"},
                ),
                style={
                    "background":   _SURFACE,
                    "border":       f"1px solid {_BORDER}",
                    "borderRadius": "8px",
                    "overflow":     "hidden",
                },
            ),
        ),
    )


# ── Neglect ranking tab ───────────────────────────────────────────────────────

def _neglect_row(r: dict) -> rx.Component:
    many_days = r["days_idle"].to(int) > 14
    never     = r["days_idle"].to(int) == 9999
    idle_color = rx.cond(never, "#ef4444", rx.cond(many_days, "#d97706", "#16a34a"))
    idle_label = rx.cond(never, "Never assigned", r["days_idle"].to_string() + " days ago")
    return rx.el.tr(
        rx.el.td(r["name"], style={"padding": "10px 12px", "fontWeight": "500"}),
        rx.el.td(
            rx.el.code(r["default_zone"], style={"fontSize": "12px", "color": _INK2}),
            style={"padding": "10px 12px"},
        ),
        rx.el.td(_cat_badge(r["category"]), style={"padding": "10px 12px"}),
        rx.el.td(r["last_assigned"], style={"padding": "10px 12px", "color": _INK2, "fontSize": "12px"}),
        rx.el.td(
            rx.el.span(idle_label, style={"color": idle_color, "fontWeight": "600", "fontSize": "12px"}),
            style={"padding": "10px 12px"},
        ),
        style={"borderBottom": f"1px solid {_BORDER}", "_hover": {"background": "#f0f9ff"}},
    )


def _neglect_tab() -> rx.Component:
    return rx.el.div(
        rx.el.p(
            "Zone/RR/aux tasks sorted by longest time since last assignment. "
            "Red = never assigned · Orange = > 14 days idle.",
            style={"fontSize": "13px", "color": _INK2, "marginBottom": "16px"},
        ),
        rx.el.div(
            rx.el.table(
                rx.el.thead(
                    rx.el.tr(
                        *[
                            rx.el.th(h, style={
                                "padding": "8px 12px", "textAlign": "left",
                                "fontSize": "11px", "fontWeight": "600",
                                "textTransform": "uppercase", "letterSpacing": "0.06em",
                                "color": _INK3, "borderBottom": f"1px solid {_BORDER}",
                            })
                            for h in ["Name", "Default Zone", "Category", "Last Assigned", "Idle"]
                        ]
                    )
                ),
                rx.el.tbody(rx.foreach(ZoneTasksState.neglect_rows, _neglect_row)),
                style={"width": "100%", "borderCollapse": "collapse", "fontSize": "13px"},
            ),
            style={
                "background":   _SURFACE,
                "border":       f"1px solid {_BORDER}",
                "borderRadius": "8px",
                "overflow":     "hidden",
            },
        ),
    )


# ── Edit drawer ───────────────────────────────────────────────────────────────

def _field_label(text: str) -> rx.Component:
    return rx.el.label(
        text,
        style={
            "display":       "block",
            "fontSize":      "11px",
            "fontWeight":    "600",
            "textTransform": "uppercase",
            "letterSpacing": "0.06em",
            "color":         _INK3,
            "marginBottom":  "5px",
        },
    )


def _affinity_bar(r: dict) -> rx.Component:
    return rx.el.div(
        rx.el.span(r["zone_slot"], style={"fontSize": "12px", "color": _INK2,
                                          "width": "72px", "display": "inline-block",
                                          "flexShrink": "0"}),
        rx.el.div(
            rx.el.div(style={
                "height": "8px", "borderRadius": "4px", "background": _ACCENT,
                "width": r["pct"].to_string() + "%", "minWidth": "4px",
            }),
            style={"flex": "1", "background": "#e2e8f0", "borderRadius": "4px",
                   "height": "8px", "overflow": "hidden"},
        ),
        rx.el.span(
            r["pct"].to_string() + "% (" + r["count"].to_string() + ")",
            style={"fontSize": "11px", "color": _INK3, "width": "80px",
                   "textAlign": "right", "display": "inline-block", "flexShrink": "0"},
        ),
        style={"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "6px"},
    )


def _override_row(r: dict) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(r["override_date"], style={"fontSize": "12px", "fontWeight": "600",
                                                   "color": _INK1, "minWidth": "90px"}),
            rx.el.span(r["description"], style={"fontSize": "13px", "color": _INK1, "flex": "1"}),
            rx.el.button(
                _icon("delete-trash", 13),
                on_click=ZoneTasksState.delete_override(r["id"]),
                style={"background": "none", "border": "none", "cursor": "pointer",
                       "color": "#ef4444", "padding": "2px", "display": "flex", "alignItems": "center"},
            ),
            style={"display": "flex", "alignItems": "center", "gap": "10px"},
        ),
        style={
            "padding":      "7px 10px",
            "borderRadius": "5px",
            "background":   "#f1f5f9",
            "marginBottom": "5px",
        },
    )


def _overrides_section() -> rx.Component:
    return rx.el.div(
        # Section header
        rx.el.div(
            "Per-Day Overrides",
            style={
                "fontSize": "11px", "fontWeight": "600", "textTransform": "uppercase",
                "letterSpacing": "0.06em", "color": _INK3, "marginBottom": "10px",
            },
        ),
        # Existing overrides
        rx.cond(
            ZoneTasksState.has_overrides,
            rx.foreach(ZoneTasksState.override_rows, _override_row),
            rx.el.p("No overrides yet.", style={"fontSize": "12px", "color": _INK3,
                                                 "marginBottom": "8px"}),
        ),
        # Add override form
        rx.el.div(
            rx.el.input(
                type="date",
                value=ZoneTasksState.new_override_date,
                on_change=ZoneTasksState.set_new_override_date,
                style={
                    "padding": "5px 8px", "fontSize": "13px", "borderRadius": "5px",
                    "border": f"1px solid {_BORDER}", "background": _SURFACE,
                    "color": _INK1, "fontFamily": _FONT, "width": "130px",
                },
            ),
            rx.el.input(
                placeholder="Description for this date …",
                value=ZoneTasksState.new_override_desc,
                on_change=ZoneTasksState.set_new_override_desc,
                style={
                    "flex": "1", "padding": "5px 8px", "fontSize": "13px",
                    "borderRadius": "5px", "border": f"1px solid {_BORDER}",
                    "background": _SURFACE, "color": _INK1, "fontFamily": _FONT,
                },
            ),
            _btn("Add", ZoneTasksState.add_override, variant="primary",
                 icon="add-new", disabled=ZoneTasksState.adding_override),
            style={"display": "flex", "gap": "8px", "alignItems": "center", "marginTop": "8px"},
        ),
        rx.cond(
            ZoneTasksState.override_error != "",
            rx.el.span(ZoneTasksState.override_error,
                       style={"color": "#ef4444", "fontSize": "12px",
                              "marginTop": "5px", "display": "block"}),
            rx.el.span(""),
        ),
        style={
            "background": "#f8fafc", "borderRadius": "6px",
            "padding": "12px", "marginBottom": "20px",
        },
    )


def _edit_drawer() -> rx.Component:
    return rx.cond(
        ZoneTasksState.drawer_open,
        rx.el.div(
            # Backdrop
            rx.el.div(
                on_click=ZoneTasksState.close_drawer,
                style={
                    "position": "fixed", "inset": "0",
                    "background": "rgba(0,0,0,0.35)", "zIndex": "1000",
                },
            ),
            # Drawer panel
            rx.el.div(
                # Header
                rx.el.div(
                    rx.el.span(ZoneTasksState.drawer_title,
                               style={"fontSize": "16px", "fontWeight": "700", "color": _INK1}),
                    rx.el.button(
                        "✕",
                        on_click=ZoneTasksState.close_drawer,
                        style={"background": "none", "border": "none", "cursor": "pointer",
                               "fontSize": "18px", "color": _INK3, "lineHeight": "1"},
                    ),
                    style={
                        "display": "flex", "justifyContent": "space-between",
                        "alignItems": "center", "paddingBottom": "16px",
                        "borderBottom": f"1px solid {_BORDER}", "marginBottom": "20px",
                    },
                ),
                # Name
                rx.el.div(
                    _field_label("Name"),
                    rx.el.input(
                        value=ZoneTasksState.edit_name,
                        on_change=ZoneTasksState.set_edit_name,
                        style={
                            "width": "100%", "padding": "8px 10px", "fontSize": "14px",
                            "borderRadius": "6px", "border": f"1px solid {_BORDER}",
                            "background": _SURFACE, "color": _INK1, "fontFamily": _FONT,
                            "boxSizing": "border-box",
                        },
                    ),
                    style={"marginBottom": "14px"},
                ),
                # Code
                rx.el.div(
                    _field_label("Code (stable identifier)"),
                    rx.el.input(
                        value=ZoneTasksState.edit_code,
                        on_change=ZoneTasksState.set_edit_code,
                        placeholder="e.g. Z1_OUTDOOR_SMOKE",
                        style={
                            "width": "100%", "padding": "8px 10px", "fontSize": "13px",
                            "fontFamily": "monospace", "borderRadius": "6px",
                            "border": f"1px solid {_BORDER}", "background": _SURFACE,
                            "color": "#6366f1", "boxSizing": "border-box",
                        },
                    ),
                    style={"marginBottom": "14px"},
                ),
                # Default Zone
                rx.el.div(
                    _field_label("Default Zone"),
                    _select(ZoneTasksState.edit_zone, ZoneTasksState.set_edit_zone,
                            DEFAULT_ZONE_OPTIONS),
                    style={"marginBottom": "14px"},
                ),
                # Category
                rx.el.div(
                    _field_label("Category"),
                    _select(
                        ZoneTasksState.edit_category,
                        ZoneTasksState.set_edit_category,
                        [{"label": c.replace("_", " ").upper(), "value": c}
                         for c in CATEGORY_OPTIONS],
                    ),
                    style={"marginBottom": "14px"},
                ),
                # Notes
                rx.el.div(
                    _field_label("Notes"),
                    rx.el.textarea(
                        value=ZoneTasksState.edit_notes,
                        on_change=ZoneTasksState.set_edit_notes,
                        rows=2,
                        style={
                            "width": "100%", "padding": "8px 10px", "fontSize": "13px",
                            "borderRadius": "6px", "border": f"1px solid {_BORDER}",
                            "background": _SURFACE, "color": _INK1, "fontFamily": _FONT,
                            "boxSizing": "border-box", "resize": "vertical",
                        },
                    ),
                    style={"marginBottom": "14px"},
                ),
                # Active toggle
                rx.el.div(
                    rx.el.label(
                        rx.el.input(
                            type="checkbox",
                            checked=ZoneTasksState.edit_active,
                            on_change=ZoneTasksState.set_edit_active,
                            style={"marginRight": "8px"},
                        ),
                        "Active",
                        style={"display": "flex", "alignItems": "center",
                               "fontSize": "13px", "color": _INK1, "cursor": "pointer"},
                    ),
                    style={"marginBottom": "20px"},
                ),
                # Zone affinity
                rx.cond(
                    ZoneTasksState.affinity_rows.length() > 0,
                    rx.el.div(
                        rx.el.div("Zone Affinity", style={
                            "fontSize": "11px", "fontWeight": "600",
                            "textTransform": "uppercase", "letterSpacing": "0.06em",
                            "color": _INK3, "marginBottom": "10px",
                        }),
                        rx.foreach(ZoneTasksState.affinity_rows, _affinity_bar),
                        style={"background": "#f8fafc", "borderRadius": "6px",
                               "padding": "12px", "marginBottom": "20px"},
                    ),
                    rx.el.span(""),
                ),
                # Per-day overrides section
                _overrides_section(),
                # Error
                rx.cond(
                    ZoneTasksState.save_error != "",
                    rx.el.div(ZoneTasksState.save_error,
                              style={"color": "#ef4444", "fontSize": "12px", "marginBottom": "12px"}),
                    rx.el.span(""),
                ),
                # Action row
                rx.el.div(
                    _btn("Save", ZoneTasksState.save_edit, variant="primary",
                         icon="edit-pencil", disabled=ZoneTasksState.saving),
                    _btn("Archive", ZoneTasksState.archive_task(ZoneTasksState.editing_id),
                         variant="danger", icon="archive"),
                    _btn("Cancel", ZoneTasksState.close_drawer),
                    style={"display": "flex", "gap": "10px", "alignItems": "center",
                           "flexWrap": "wrap"},
                ),
                style={
                    "position": "fixed", "top": "0", "right": "0",
                    "width": "460px", "height": "100vh",
                    "background": "#fff",
                    "boxShadow": "-4px 0 24px rgba(0,0,0,0.12)",
                    "zIndex": "1001",
                    "padding": "28px 24px",
                    "overflowY": "auto",
                    "boxSizing": "border-box",
                },
            ),
            style={"position": "fixed", "inset": "0", "zIndex": "1000"},
        ),
        rx.el.span(""),
    )


# ── Page ──────────────────────────────────────────────────────────────────────

def admin_tasks_page() -> rx.Component:
    return rx.el.div(
        admin_breadcrumb(section="Workflows", page_title="Zone Tasks"),
        rx.el.div(
            rx.el.h1("Zone Tasks",
                     style={"fontSize": "22px", "fontWeight": "700",
                            "color": _INK1, "margin": "0"}),
            rx.el.p(
                "Manage canonical task lists for each zone slot. "
                "Changes take effect on the next deployment book render.",
                style={"fontSize": "13px", "color": _INK2, "marginTop": "4px"},
            ),
            style={"marginBottom": "24px"},
        ),
        _tab_strip(),
        rx.cond(
            ZoneTasksState.active_tab == 0,
            _tasks_tab(),
            _neglect_tab(),
        ),
        _edit_drawer(),
        style={
            "padding":    "28px 32px",
            "maxWidth":   "1100px",
            "fontFamily": _FONT,
        },
    )
