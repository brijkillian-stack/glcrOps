"""
pages/today.py — Today page (Phase 1 command center rebuild)

Additions vs original:
  - Quick-log chip bar: one-click chips for Call-out, Late, BEO, Kudos, Note
  - Completable tonight-task rows: ✓ button marks complete without leaving page
  - Shift context in header (day label already in AppState)
"""

import reflex as rx
from ..state.today import TodayState
from shared.base import AppState
from shared.components.sidebar import sidebar
from shared.components.ui import kpi_card, brewing_card, feed_row, empty_state, skeleton_card
from shared.components.palette import command_palette
from shared.components.capture import capture_modal
from ..components.tm_drawer import global_tm_drawer


# ── Page header ───────────────────────────────────────────────────────────────

def privacy_toggle() -> rx.Component:
    return rx.el.button(
        rx.cond(
            AppState.privacy_mode,
            rx.el.span("◉  Live view", style={"color": "var(--accent-positive)"}),
            rx.el.span("◎  Private",   style={"color": "var(--fg-3)"}),
        ),
        on_click=AppState.toggle_privacy,
        class_name="privacy-toggle-btn",
        title=rx.cond(
            AppState.privacy_mode,
            "Click to show team info",
            "Click to hide team info",
        ),
    )


def page_header() -> rx.Component:
    return rx.el.header(
        rx.el.div(
            rx.el.div(
                rx.el.div(TodayState.today_label, class_name="page-eyebrow"),
                rx.el.h1("Good evening, Brian.", class_name="page-title"),
                rx.el.p(TodayState.page_summary, class_name="page-summary"),
            ),
            privacy_toggle(),
            style={"display": "flex", "justifyContent": "space-between",
                   "alignItems": "flex-start"},
        ),
        class_name="page-head",
    )


# ── Capture bar ───────────────────────────────────────────────────────────────

def capture_bar() -> rx.Component:
    return rx.el.div(
        rx.el.input(
            class_name="capture-bar-input",
            placeholder="Capture a note — Joy nailed Z9 SR tonight…",
            read_only=True,
        ),
        rx.el.span("⌘N", class_name="kbd"),
        class_name="capture-bar",
        on_click=AppState.open_capture,
    )


# ── Quick-log chips ───────────────────────────────────────────────────────────

def _quick_chip(icon: str, label: str, content_type: str, prefix: str) -> rx.Component:
    return rx.el.button(
        rx.el.span(icon, style={"fontSize": "13px", "marginRight": "4px"}),
        label,
        on_click=AppState.open_capture_typed(content_type, prefix),
        class_name="quick-chip",
        title=f"Log a {label.lower()}",
    )


def quick_log_bar() -> rx.Component:
    return rx.el.div(
        rx.el.span("Quick log:", class_name="quick-log-label"),
        _quick_chip("⚑",  "Call-out",    "callout",     "Call-out: "),
        _quick_chip("⏰",  "Late",        "observation", "Late arrival: "),
        _quick_chip("⊟",  "BEO",         "beo",         "BEO: "),
        _quick_chip("★",  "Kudos",       "kudos",       "Kudos — "),
        _quick_chip("⚠",  "Incident",    "incident",    "Incident: "),
        _quick_chip("◐",  "Observation", "observation", ""),
        class_name="quick-log-bar",
    )


# ── Tonight task row (with complete button) ───────────────────────────────────

def _tonight_priority_dot(item: dict) -> rx.Component:
    dot_cls = rx.cond(
        item["is_overdue"],
        "priority-dot urgent",
        rx.cond(
            item["priority"] == "urgent", "priority-dot urgent",
            rx.cond(
                item["priority"] == "high",   "priority-dot high",
                rx.cond(
                    item["priority"] == "low", "priority-dot low",
                    "priority-dot normal",
                ),
            ),
        ),
    )
    return rx.el.span(class_name=dot_cls,
                      style={"display": "inline-block", "marginRight": "6px",
                             "flexShrink": "0"})


def tonight_task_row(item: dict) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            _tonight_priority_dot(item),
            rx.el.div(
                rx.el.p(item["title"], class_name="card-title"),
                rx.el.div(
                    rx.el.span(
                        rx.cond(item["is_overdue"], "overdue", item["category"]),
                        class_name=rx.cond(
                            item["is_overdue"], "chip chip-flag", "chip chip-blue"
                        ),
                    ),
                    rx.cond(
                        item["due_date"] != "",
                        rx.el.span(item["due_date"],
                                   style={"fontSize": "11px", "color": "var(--fg-3)"}),
                        rx.fragment(),
                    ),
                    class_name="card-meta",
                ),
                class_name="card-body",
            ),
            rx.el.button(
                "✓",
                class_name="complete-btn",
                on_click=TodayState.mark_complete_tonight(item["id"]),
                title="Mark complete",
            ),
            class_name="card-row",
            style={"alignItems": "center"},
        ),
        class_name="card",
    )


# ── Tonight column ────────────────────────────────────────────────────────────

def tonight_column() -> rx.Component:
    return rx.el.div(
        rx.el.h2(
            "Tonight",
            rx.link("All tasks →", href="/tasks", class_name="section-title-action"),
            class_name="section-title",
        ),
        rx.cond(
            TodayState.loading,
            rx.fragment(skeleton_card(), skeleton_card(), skeleton_card()),
            rx.cond(
                TodayState.tonight_tasks.length() > 0,
                rx.foreach(TodayState.tonight_tasks, tonight_task_row),
                empty_state("No open tasks", "Nothing pending for tonight."),
            ),
        ),
        # Brewing
        rx.el.h2(
            "Brewing",
            rx.link("Patterns →", href="/patterns", class_name="section-title-action"),
            class_name="section-title",
            style={"marginTop": "28px"},
        ),
        rx.cond(
            TodayState.loading,
            rx.fragment(skeleton_card(), skeleton_card()),
            rx.cond(
                TodayState.brewing_items.length() > 0,
                rx.foreach(TodayState.brewing_items, brewing_card),
                empty_state("Nothing brewing", "No recurring patterns in the last 14 days."),
            ),
        ),
    )


# ── Activity column ───────────────────────────────────────────────────────────

def activity_column() -> rx.Component:
    return rx.el.div(
        rx.el.h2(
            "Recent",
            rx.link("All Logs →", href="/logs", class_name="section-title-action"),
            class_name="section-title",
        ),
        rx.cond(
            TodayState.loading,
            rx.el.div(
                *[rx.el.div(
                    rx.el.div(class_name="skeleton",
                              style={"height": "11px", "width": "40px"}),
                    rx.el.div(class_name="skeleton",
                              style={"height": "11px", "flex": "1", "marginLeft": "8px"}),
                    class_name="feed-item",
                    style={"gap": "12px"},
                ) for _ in range(3)],
                class_name="feed",
            ),
            rx.cond(
                TodayState.activity_feed.length() > 0,
                rx.el.div(
                    rx.foreach(TodayState.activity_feed, feed_row),
                    rx.link(
                        "View full log →",
                        href="/logs",
                        style={
                            "display": "block",
                            "textAlign": "right",
                            "fontSize": "12px",
                            "color": "var(--accent-blue)",
                            "marginTop": "8px",
                            "padding": "4px 0",
                        },
                    ),
                    class_name="feed",
                ),
                empty_state("No activity yet",
                            "Captures will appear here as the shift progresses."),
            ),
        ),
    )


# ── Numbers column ────────────────────────────────────────────────────────────

def numbers_column() -> rx.Component:
    return rx.el.div(
        rx.el.h2("Numbers", class_name="section-title"),
        rx.el.div(
            kpi_card(
                "Captures today",
                TodayState.kpi_captures_today,
                TodayState.kpi_captures_delta,
                TodayState.kpi_captures_direction,
            ),
            kpi_card(
                "Open tasks",
                TodayState.kpi_open_tasks,
                TodayState.overdue_label,
                TodayState.overdue_direction,
            ),
            kpi_card(
                "Active flags",
                TodayState.kpi_active_flags,
                TodayState.flags_delta_label,
                rx.cond(TodayState.kpi_active_flags > 0, "down", "flat"),
                value_color=rx.cond(
                    TodayState.kpi_active_flags > 0, "var(--accent-flag)", ""
                ),
            ),
            kpi_card(
                "Backend",
                rx.cond(TodayState.kpi_backend_ok, "●", "○"),
                rx.cond(
                    TodayState.kpi_backend_ok,
                    TodayState.kpi_backend_latency,
                    "unreachable",
                ),
                rx.cond(TodayState.kpi_backend_ok, "flat", "down"),
                value_color=rx.cond(
                    TodayState.kpi_backend_ok,
                    "var(--accent-positive)",
                    "var(--accent-flag)",
                ),
            ),
            class_name="kpi-stack",
        ),
        rx.el.button(
            "↻ Refresh",
            on_click=TodayState.reload_today,
            style={
                "marginTop": "16px",
                "fontSize": "12px",
                "color": "var(--fg-3)",
                "padding": "6px 0",
                "display": "block",
                "width": "100%",
                "textAlign": "right",
            },
        ),
    )


# ── Today page ────────────────────────────────────────────────────────────────

def today_page() -> rx.Component:
    return rx.el.div(
        sidebar(),
        rx.el.main(
            page_header(),
            capture_bar(),
            quick_log_bar(),
            rx.el.section(
                tonight_column(),
                activity_column(),
                numbers_column(),
                class_name=rx.cond(
                    AppState.privacy_mode,
                    "section-row privacy-shield",
                    "section-row",
                ),
            ),
            class_name="main",
        ),
        rx.el.button(
            "+",
            class_name="fab",
            on_click=AppState.open_capture,
            title="Capture (⌘N)",
            aria_label="Quick capture",
        ),
        # Area Check overlay is mounted globally via _with_grok in
        # brijkillian_stack.py and triggered from the sidebar nav.
        global_tm_drawer(),
        command_palette(),
        capture_modal(),
        class_name=AppState.app_class_name,
    )
