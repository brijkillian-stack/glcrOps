"""
pages/floor.py — Floor Walk page

Zone-by-zone checklist for the grave shift floor walk.
Each area can be marked OK (green) or Flagged (red + inline note).
Flags are saved to Supabase immediately. Completing the walk saves
a floor_walk summary note that appears in Today's activity feed.
"""

import reflex as rx
from ..state.floor import FloorState
from shared.base import AppState
from shared.components.sidebar import sidebar
from shared.components.palette import command_palette
from shared.components.capture import capture_modal


# ── Page header ───────────────────────────────────────────────────────────────

def page_header() -> rx.Component:
    return rx.el.header(
        rx.el.div("Floor Walk", class_name="page-eyebrow"),
        rx.el.h1("Zone Checklist", class_name="page-title"),
        class_name="page-head",
        style={"marginBottom": "20px"},
    )


# ── Progress bar ──────────────────────────────────────────────────────────────

def progress_bar() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    FloorState.checked_count.to_string(),
                    " / ",
                    FloorState.total_items.to_string(),
                    " checked",
                    style={"fontWeight": "600", "color": "var(--fg-1)"},
                ),
                rx.el.span(
                    rx.cond(
                        FloorState.flag_count > 0,
                        rx.el.span(
                            "  ⚑ ",
                            FloorState.flag_count.to_string(),
                            " flag",
                            style={"color": "var(--accent-flag)"},
                        ),
                        rx.fragment(),
                    ),
                ),
                style={"display": "flex", "gap": "12px", "alignItems": "center",
                       "fontSize": "14px"},
            ),
            rx.cond(
                FloorState.walk_started,
                rx.el.span(
                    "~",
                    FloorState.duration_min.to_string(),
                    " min",
                    style={"fontSize": "12px", "color": "var(--fg-3)"},
                ),
                rx.fragment(),
            ),
            style={"display": "flex", "justifyContent": "space-between",
                   "marginBottom": "8px"},
        ),
        # Track
        rx.el.div(
            rx.el.div(
                style={
                    "height": "100%",
                    "borderRadius": "var(--r-pill)",
                    "background": rx.cond(
                        FloorState.flag_count > 0,
                        "var(--accent-flag)",
                        "var(--accent-positive)",
                    ),
                    "transition": "width 300ms ease",
                    "width": FloorState.progress_pct.to_string() + "%",
                },
            ),
            style={
                "height": "6px", "borderRadius": "var(--r-pill)",
                "background": "var(--border-subtle)", "overflow": "hidden",
                "marginBottom": "20px",
            },
        ),
        class_name="walk-progress",
    )


# ── Start / complete buttons ──────────────────────────────────────────────────

def walk_controls() -> rx.Component:
    return rx.cond(
        FloorState.walk_completed,
        # Done state
        rx.el.div(
            rx.el.div(
                rx.el.span("✓", style={"fontSize": "20px", "color": "var(--accent-positive)"}),
                rx.el.div(
                    rx.el.p("Walk complete", style={"fontWeight": "600", "margin": "0 0 2px"}),
                    rx.el.p(
                        FloorState.checked_count.to_string(),
                        " checked · ",
                        FloorState.flag_count.to_string(),
                        " flags · ~",
                        FloorState.duration_min.to_string(),
                        " min",
                        style={"fontSize": "12px", "color": "var(--fg-3)", "margin": "0"},
                    ),
                ),
                style={"display": "flex", "gap": "12px", "alignItems": "center"},
            ),
            rx.el.button(
                "New Walk",
                class_name="btn btn-ghost",
                on_click=FloorState.start_walk,
                style={"fontSize": "13px"},
            ),
            style={"display": "flex", "justifyContent": "space-between",
                   "alignItems": "center", "marginBottom": "28px",
                   "padding": "16px", "background": "var(--accent-positive-bg)",
                   "borderRadius": "var(--r-lg)", "border": "1px solid var(--accent-positive)"},
        ),
        rx.cond(
            FloorState.walk_started,
            # In-progress: show complete button
            rx.el.div(
                progress_bar(),
                rx.cond(
                    FloorState.all_checked,
                    rx.el.button(
                        rx.cond(FloorState.saving, "Saving…", "✓  Complete Walk"),
                        class_name="btn btn-primary",
                        on_click=FloorState.complete_walk,
                        disabled=FloorState.saving,
                        style={"marginBottom": "28px", "fontSize": "14px",
                               "padding": "10px 20px"},
                    ),
                    rx.el.p(
                        FloorState.total_items.__sub__(FloorState.checked_count).to_string(),
                        " areas remaining",
                        style={"fontSize": "12px", "color": "var(--fg-3)",
                               "marginBottom": "28px"},
                    ),
                ),
            ),
            # Not started: show start button
            rx.el.div(
                rx.el.p(
                    "Start a floor walk to check all zones and restrooms.",
                    style={"fontSize": "14px", "color": "var(--fg-2)",
                           "marginBottom": "16px"},
                ),
                rx.el.button(
                    "▶  Start Floor Walk",
                    class_name="btn btn-primary",
                    on_click=FloorState.start_walk,
                    style={"fontSize": "14px", "padding": "10px 20px",
                           "marginBottom": "28px"},
                ),
            ),
        ),
    )


# ── Single checklist card (tablet grid) ──────────────────────────────────────

def checklist_item(item: dict) -> rx.Component:
    card_cls = rx.cond(
        item["status"] == "ok",   "walk-card walk-card-ok",
        rx.cond(
            item["status"] == "flag", "walk-card walk-card-flag",
            rx.cond(
                item["status"] == "skipped", "walk-card walk-card-skipped",
                "walk-card",
            ),
        ),
    )
    status_icon = rx.cond(
        item["status"] == "ok",   "✓",
        rx.cond(item["status"] == "flag", "⚑",
                rx.cond(item["status"] == "skipped", "—", "")),
    )
    return rx.el.div(
        # Card top: name + status icon
        rx.el.div(
            rx.el.span(item["name"], class_name="walk-card-name"),
            rx.el.span(status_icon, class_name=rx.cond(
                item["status"] == "ok",   "walk-card-status ok",
                rx.cond(item["status"] == "flag", "walk-card-status flag", "walk-card-status"),
            )),
            class_name="walk-card-top",
        ),
        # Flag note
        rx.cond(
            item["status"] == "flag",
            rx.el.p(item["note"], class_name="walk-card-note"),
            rx.fragment(),
        ),
        # Skipped label
        rx.cond(
            item["status"] == "skipped",
            rx.el.p("Skipped", class_name="walk-card-skipped-label"),
            rx.fragment(),
        ),
        # Flagging inline input (when note entry open)
        rx.cond(
            FloorState.flagging_id == item["id"],
            rx.el.div(
                rx.el.input(
                    placeholder="Describe the issue…",
                    value=FloorState.flag_note,
                    on_change=FloorState.set_flag_note,
                    auto_focus=True,
                    class_name="walk-flag-input",
                ),
                rx.el.div(
                    rx.el.button("Save", on_click=FloorState.confirm_flag,
                                 class_name="walk-flag-save"),
                    rx.el.button("✕", on_click=FloorState.cancel_flag,
                                 class_name="walk-flag-cancel"),
                    style={"display": "flex", "gap": "6px", "marginTop": "6px"},
                ),
                class_name="walk-flag-inset",
                on_click=rx.stop_propagation,
            ),
            rx.fragment(),
        ),
        # Action area (only during active walk, not flagging)
        rx.cond(
            FloorState.walk_started & ~FloorState.walk_completed
            & (FloorState.flagging_id != item["id"]),
            rx.el.div(
                rx.cond(
                    item["status"] == "pending",
                    rx.el.div(
                        rx.el.button("✓", class_name="walk-tap-ok",
                                     on_click=FloorState.mark_ok(item["id"]),
                                     title="All clear"),
                        rx.el.button("⚑", class_name="walk-tap-flag",
                                     on_click=FloorState.start_flag(item["id"]),
                                     title="Flag issue"),
                        rx.el.button("—", class_name="walk-tap-skip",
                                     on_click=FloorState.skip_item(item["id"]),
                                     title="Skip (N/A)"),
                        class_name="walk-tap-row",
                    ),
                    rx.el.button(
                        rx.cond(item["status"] == "ok", "Undo OK",
                                rx.cond(item["status"] == "flag", "Undo Flag", "Undo Skip")),
                        class_name="walk-tap-undo",
                        on_click=rx.cond(
                            item["status"] == "ok",
                            FloorState.start_flag(item["id"]),
                            rx.cond(
                                item["status"] == "skipped",
                                FloorState.mark_ok(item["id"]),
                                FloorState.mark_ok(item["id"]),
                            ),
                        ),
                    ),
                ),
                class_name="walk-card-actions",
            ),
            rx.fragment(),
        ),
        class_name=card_cls,
    )


# ── Section renderer ──────────────────────────────────────────────────────────

def section_items(section_name: str) -> rx.Component:
    return rx.el.div(
        rx.el.h3(section_name, class_name="walk-section-title"),
        rx.el.div(
            rx.foreach(
                FloorState.walk_items,
                lambda item: rx.cond(
                    item["section"] == section_name,
                    checklist_item(item),
                    rx.fragment(),
                ),
            ),
            class_name="walk-grid",
        ),
        class_name="walk-section",
    )


# ── Floor Walk page ───────────────────────────────────────────────────────────

def floor_page() -> rx.Component:
    return rx.el.div(
        sidebar(),
        rx.el.main(
            page_header(),
            walk_controls(),
            # Three sections — rendered by filtering the same flat list
            section_items("Main Floor"),
            section_items("Men's Restrooms"),
            section_items("Women's Restrooms"),
            class_name="main main-single",
            style={"maxWidth": "900px"},
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
