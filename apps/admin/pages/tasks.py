"""
apps/admin/pages/tasks.py — Zone Task Manager (Phase 4i.3)

Route: /admin/tasks
Two-tab view:
  Tab 0 — All Tasks: full table with inline add, row-click-to-edit drawer
  Tab 1 — Neglect Ranking: tasks sorted by days since last assignment
"""

from __future__ import annotations

import reflex as rx

from apps.admin.tasks_state import ZoneTasksState, CATEGORY_OPTIONS, DEFAULT_ZONE_OPTIONS
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
    "zone": "#2563eb",
    "rr":   "#7c3aed",
    "aux":  "#d97706",
}

def _cat_badge(category: rx.Var) -> rx.Component:
    return rx.el.span(
        category,
        style={
            "fontSize":      "11px",
            "fontWeight":    "600",
            "padding":       "2px 8px",
            "borderRadius":  "4px",
            "background":    "#f1f5f9",
            "color":         _INK2,
            "textTransform": "uppercase",
            "letterSpacing": "0.04em",
        },
    )


# ── Tab strip ────────────────────────────────────────────────────────────────

def _tab_btn(label: str, idx: int) -> rx.Component:
    is_active = ZoneTasksState.active_tab == idx
    return rx.el.button(
        label,
        on_click=ZoneTasksState.set_tab(idx),
        style={
            "padding":       "7px 16px",
            "fontSize":      "13px",
            "fontWeight":    rx.cond(is_active, "700", "500"),
            "border":        "none",
            "borderBottom":  rx.cond(is_active, f"2px solid {_ACCENT}", "2px solid transparent"),
            "background":    "transparent",
            "color":         rx.cond(is_active, _ACCENT, _INK2),
            "cursor":        "pointer",
            "fontFamily":    _FONT,
            "transition":    "all 0.12s",
        },
    )


def _tab_strip() -> rx.Component:
    return rx.el.div(
        _tab_btn("All Tasks", 0),
        _tab_btn("Neglect Ranking", 1),
        style={
            "display":    "flex",
            "gap":        "4px",
            "borderBottom": f"1px solid {_BORDER}",
            "marginBottom": "20px",
        },
    )


# ── Shared button helper ─────────────────────────────────────────────────────

def _btn(label: str, on_click, variant: str = "default", disabled: rx.Var | bool = False) -> rx.Component:
    base: dict = {
        "padding":      "7px 18px",
        "fontSize":     "13px",
        "fontWeight":   "600",
        "borderRadius": "6px",
        "border":       f"1px solid {_BORDER}",
        "cursor":       "pointer",
        "fontFamily":   _FONT,
        "transition":   "opacity 0.12s",
    }
    if variant == "primary":
        base.update({"background": _ACCENT, "color": "#fff", "border": "none"})
    elif variant == "danger":
        base.update({"background": "transparent", "color": "#ef4444", "border": f"1px solid #ef4444"})
    else:
        base.update({"background": _SURFACE, "color": _INK2})
    return rx.el.button(label, on_click=on_click, disabled=disabled, style=base)


# ── Select helper ────────────────────────────────────────────────────────────

def _select(value: rx.Var, on_change, options: list[dict]) -> rx.Component:
    """Simple native <select>."""
    return rx.el.select(
        *[
            rx.el.option(o["label"], value=o["value"])
            for o in options
        ],
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
            "width":        "100%",
        },
    )


# ── Add new task strip ───────────────────────────────────────────────────────

def _add_task_row() -> rx.Component:
    return rx.el.div(
        rx.el.div(
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
                        "flex": "1",
                        "padding": "6px 10px",
                        "fontSize": "13px",
                        "borderRadius": "6px",
                        "border": f"1px solid {_BORDER}",
                        "background": _SURFACE,
                        "color": _INK1,
                        "fontFamily": _FONT,
                    },
                ),
                _select(
                    ZoneTasksState.new_zone,
                    ZoneTasksState.set_new_zone,
                    DEFAULT_ZONE_OPTIONS,
                ),
                _select(
                    ZoneTasksState.new_category,
                    ZoneTasksState.set_new_category,
                    [{"label": c.upper(), "value": c} for c in CATEGORY_OPTIONS],
                ),
                _btn("Add", ZoneTasksState.add_task, variant="primary",
                     disabled=ZoneTasksState.adding),
                style={"display": "flex", "gap": "10px", "alignItems": "center"},
            ),
            rx.cond(
                ZoneTasksState.add_error != "",
                rx.el.span(ZoneTasksState.add_error,
                           style={"color": "#ef4444", "fontSize": "12px", "marginTop": "6px",
                                  "display": "block"}),
                rx.el.span(""),
            ),
        ),
        style={
            "padding":    "14px 16px",
            "background": "#f8fafc",
            "borderRadius": "8px",
            "border":     f"1px dashed {_BORDER}",
            "marginBottom": "16px",
        },
    )


# ── Task table ───────────────────────────────────────────────────────────────

def _task_row(t: dict) -> rx.Component:
    is_archived = ~t["active"]
    return rx.el.tr(
        rx.el.td(
            rx.el.span(
                t["name"],
                style={
                    "fontWeight":      "500",
                    "color":           rx.cond(is_archived, _INK3, _INK1),
                    "textDecoration":  rx.cond(is_archived, "line-through", "none"),
                },
            ),
            style={"padding": "10px 12px"},
        ),
        rx.el.td(
            rx.el.code(
                t["default_zone"],
                style={"fontSize": "12px", "color": _INK2},
            ),
            style={"padding": "10px 12px"},
        ),
        rx.el.td(_cat_badge(t["category"]), style={"padding": "10px 12px"}),
        rx.el.td(
            rx.cond(
                t["active"],
                rx.el.span("Active", style={"color": "#16a34a", "fontSize": "12px", "fontWeight": "600"}),
                rx.el.span("Archived", style={"color": _INK3, "fontSize": "12px"}),
            ),
            style={"padding": "10px 12px"},
        ),
        rx.el.td(
            _btn("Edit", ZoneTasksState.open_drawer(t["id"]), variant="default"),
            style={"padding": "10px 12px"},
        ),
        style={
            "borderBottom": f"1px solid {_BORDER}",
            "background":   rx.cond(is_archived, "#f8fafc", "transparent"),
            "_hover":       {"background": "#f0f9ff"},
        },
    )


def _tasks_tab() -> rx.Component:
    return rx.el.div(
        _add_task_row(),
        # Show archived toggle
        rx.el.div(
            rx.el.label(
                rx.el.input(
                    type="checkbox",
                    checked=ZoneTasksState.show_archived,
                    on_change=lambda _: ZoneTasksState.toggle_show_archived(),
                    style={"marginRight": "6px"},
                ),
                "Show archived",
                style={"fontSize": "13px", "color": _INK2, "cursor": "pointer",
                       "display": "flex", "alignItems": "center"},
            ),
            style={"marginBottom": "12px"},
        ),
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
                                        "padding":      "8px 12px",
                                        "textAlign":    "left",
                                        "fontSize":     "11px",
                                        "fontWeight":   "600",
                                        "textTransform":"uppercase",
                                        "letterSpacing":"0.06em",
                                        "color":        _INK3,
                                        "borderBottom": f"1px solid {_BORDER}",
                                    },
                                )
                                for h in ["Name", "Default Zone", "Category", "Status", ""]
                            ]
                        )
                    ),
                    rx.el.tbody(
                        rx.foreach(ZoneTasksState.visible_tasks, _task_row)
                    ),
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


# ── Neglect ranking tab ──────────────────────────────────────────────────────

def _neglect_row(r: dict) -> rx.Component:
    many_days = r["days_idle"] > 14
    never     = r["days_idle"] == 9999
    idle_color = rx.cond(never, "#ef4444", rx.cond(many_days, "#d97706", "#16a34a"))
    idle_label = rx.cond(never, "Never assigned", rx.el.span(r["days_idle"].to_string() + " days ago"))
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
            "Tasks sorted by longest time since last zone_task_assignment. "
            "Red = never assigned. Orange = > 14 days idle.",
            style={"fontSize": "13px", "color": _INK2, "marginBottom": "16px"},
        ),
        rx.el.div(
            rx.el.table(
                rx.el.thead(
                    rx.el.tr(
                        *[
                            rx.el.th(
                                h,
                                style={
                                    "padding": "8px 12px",
                                    "textAlign": "left",
                                    "fontSize": "11px",
                                    "fontWeight": "600",
                                    "textTransform": "uppercase",
                                    "letterSpacing": "0.06em",
                                    "color": _INK3,
                                    "borderBottom": f"1px solid {_BORDER}",
                                },
                            )
                            for h in ["Name", "Default Zone", "Category", "Last Assigned", "Idle"]
                        ]
                    )
                ),
                rx.el.tbody(
                    rx.foreach(ZoneTasksState.neglect_rows, _neglect_row)
                ),
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


# ── Edit drawer ──────────────────────────────────────────────────────────────

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
        rx.el.div(
            rx.el.span(r["zone_slot"], style={"fontSize": "12px", "color": _INK2, "width": "80px",
                                              "display": "inline-block"}),
            rx.el.div(
                rx.el.div(
                    style={
                        "height":     "8px",
                        "borderRadius": "4px",
                        "background": _ACCENT,
                        "width":      r["pct"].to_string() + "%",
                        "minWidth":   "4px",
                    }
                ),
                style={"flex": "1", "background": "#e2e8f0", "borderRadius": "4px", "height": "8px",
                       "display": "flex", "alignItems": "center"},
            ),
            rx.el.span(
                r["pct"].to_string() + "% (" + r["count"].to_string() + ")",
                style={"fontSize": "11px", "color": _INK3, "width": "80px",
                       "textAlign": "right", "display": "inline-block"},
            ),
            style={"display": "flex", "alignItems": "center", "gap": "10px"},
        ),
        style={"marginBottom": "6px"},
    )


def _edit_drawer() -> rx.Component:
    return rx.cond(
        ZoneTasksState.drawer_open,
        # Overlay
        rx.el.div(
            # Backdrop
            rx.el.div(
                on_click=ZoneTasksState.close_drawer,
                style={
                    "position": "fixed", "inset": "0",
                    "background": "rgba(0,0,0,0.35)",
                    "zIndex": "1000",
                },
            ),
            # Drawer panel
            rx.el.div(
                # Header
                rx.el.div(
                    rx.el.span(
                        ZoneTasksState.drawer_title,
                        style={"fontSize": "16px", "fontWeight": "700", "color": _INK1},
                    ),
                    rx.el.button(
                        "✕",
                        on_click=ZoneTasksState.close_drawer,
                        style={
                            "background": "none", "border": "none", "cursor": "pointer",
                            "fontSize": "18px", "color": _INK3, "lineHeight": "1",
                        },
                    ),
                    style={
                        "display": "flex", "justifyContent": "space-between",
                        "alignItems": "center", "paddingBottom": "16px",
                        "borderBottom": f"1px solid {_BORDER}", "marginBottom": "20px",
                    },
                ),
                # Fields
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
                    style={"marginBottom": "16px"},
                ),
                rx.el.div(
                    _field_label("Default Zone"),
                    _select(ZoneTasksState.edit_zone, ZoneTasksState.set_edit_zone, DEFAULT_ZONE_OPTIONS),
                    style={"marginBottom": "16px"},
                ),
                rx.el.div(
                    _field_label("Category"),
                    _select(
                        ZoneTasksState.edit_category,
                        ZoneTasksState.set_edit_category,
                        [{"label": c.upper(), "value": c} for c in CATEGORY_OPTIONS],
                    ),
                    style={"marginBottom": "16px"},
                ),
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
                    style={"marginBottom": "16px"},
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
                # Zone affinity section
                rx.cond(
                    ZoneTasksState.affinity_rows.length() > 0,
                    rx.el.div(
                        rx.el.div(
                            "Zone Affinity",
                            style={
                                "fontSize": "11px", "fontWeight": "600",
                                "textTransform": "uppercase", "letterSpacing": "0.06em",
                                "color": _INK3, "marginBottom": "10px",
                            },
                        ),
                        rx.foreach(ZoneTasksState.affinity_rows, _affinity_bar),
                        style={
                            "background": "#f8fafc", "borderRadius": "6px",
                            "padding": "12px", "marginBottom": "20px",
                        },
                    ),
                    rx.el.span(""),
                ),
                # Error
                rx.cond(
                    ZoneTasksState.save_error != "",
                    rx.el.div(
                        ZoneTasksState.save_error,
                        style={"color": "#ef4444", "fontSize": "12px", "marginBottom": "12px"},
                    ),
                    rx.el.span(""),
                ),
                # Action row
                rx.el.div(
                    _btn("Save", ZoneTasksState.save_edit, variant="primary",
                         disabled=ZoneTasksState.saving),
                    _btn(
                        "Archive",
                        ZoneTasksState.archive_task(ZoneTasksState.editing_id),
                        variant="danger",
                    ),
                    _btn("Cancel", ZoneTasksState.close_drawer),
                    style={"display": "flex", "gap": "10px", "alignItems": "center"},
                ),
                style={
                    "position": "fixed", "top": "0", "right": "0",
                    "width": "420px", "height": "100vh",
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


# ── Page ─────────────────────────────────────────────────────────────────────

def admin_tasks_page() -> rx.Component:
    return rx.el.div(
        # Breadcrumb — admin_breadcrumb takes (section, page_title) keyword args.
        admin_breadcrumb(section="Workflows", page_title="Zone Tasks"),
        # Header
        rx.el.div(
            rx.el.div(
                rx.el.h1(
                    "Zone Tasks",
                    style={"fontSize": "22px", "fontWeight": "700",
                           "color": _INK1, "margin": "0"},
                ),
                rx.el.p(
                    "Manage canonical task lists for each zone slot. "
                    "Changes take effect on the next deployment book render.",
                    style={"fontSize": "13px", "color": _INK2, "marginTop": "4px"},
                ),
            ),
            style={"marginBottom": "24px"},
        ),
        # Tab strip
        _tab_strip(),
        # Tab content
        rx.cond(
            ZoneTasksState.active_tab == 0,
            _tasks_tab(),
            _neglect_tab(),
        ),
        # Edit drawer (rendered globally, always present)
        _edit_drawer(),
        style={
            "padding":    "28px 32px",
            "maxWidth":   "960px",
            "fontFamily": _FONT,
        },
    )
