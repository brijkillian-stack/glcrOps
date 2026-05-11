"""
pages/logs.py — Logs page

Full browsable history of all captured notes.
Type-filter tabs keep different categories of content separate so the
Shift Recap timeline stays clean with only operational entries.
"""

import reflex as rx
from ..state.logs import LogsState
from shared.base import AppState
from shared.components.ui import empty_state
from shared.components.palette import command_palette
from shared.components.capture import capture_modal
from ..components.tm_drawer import global_tm_drawer


# ── Page header ───────────────────────────────────────────────────────────────

def page_header() -> rx.Component:
    return rx.el.header(
        rx.el.div("History", class_name="page-eyebrow"),
        rx.el.h1("Logs", class_name="page-title"),
        rx.el.p(LogsState.page_summary, class_name="page-summary"),
        class_name="page-head",
    )


# ── Controls row ──────────────────────────────────────────────────────────────

def _type_tab(value: str, label: str) -> rx.Component:
    return rx.el.button(
        label,
        class_name=rx.cond(
            LogsState.type_filter == value,
            "filter-tab active",
            "filter-tab",
        ),
        on_click=LogsState.set_type_filter(value),
    )


def controls_row() -> rx.Component:
    return rx.el.div(
        # Type filter tabs
        rx.el.div(
            _type_tab("all",          "All"),
            _type_tab("observations", "Observations"),
            _type_tab("flags",        "Flags"),
            _type_tab("kudos",        "Kudos"),
            _type_tab("reference",    "Reference"),
            class_name="filter-tabs",
            style={"marginBottom": "0", "flex": "1"},
        ),
        # Right controls: days selector + search + view toggle
        rx.el.div(
            rx.el.select(
                rx.el.option("Today",        value="1"),
                rx.el.option("Last 7 days",  value="7"),
                rx.el.option("Last 30 days", value="30"),
                rx.el.option("Last 90 days", value="90"),
                rx.el.option("All time",     value="0"),
                value=LogsState.days_back.to_string(),
                on_change=LogsState.set_days_back,
                style={
                    "fontSize": "13px", "color": "var(--fg-2)",
                    "background": "var(--surface-card)",
                    "border": "1px solid var(--border-subtle)",
                    "borderRadius": "var(--r-md)", "padding": "6px 10px",
                    "outline": "none", "cursor": "pointer",
                },
            ),
            rx.el.input(
                placeholder="Search…",
                value=LogsState.search,
                on_change=LogsState.set_search,
                style={
                    "fontSize": "13px", "color": "var(--fg-1)",
                    "background": "var(--surface-card)",
                    "border": "1px solid var(--border-subtle)",
                    "borderRadius": "var(--r-md)", "padding": "6px 12px",
                    "outline": "none", "width": "180px",
                    "transition": "border-color 160ms var(--ease)",
                },
            ),
            # View toggle
            rx.el.div(
                rx.el.button(
                    "≡",
                    on_click=LogsState.set_view_mode("feed"),
                    class_name=rx.cond(
                        LogsState.view_mode == "feed",
                        "view-toggle-btn active", "view-toggle-btn",
                    ),
                    title="Feed view",
                ),
                rx.el.button(
                    "◎",
                    on_click=LogsState.set_view_mode("timeline"),
                    class_name=rx.cond(
                        LogsState.view_mode == "timeline",
                        "view-toggle-btn active", "view-toggle-btn",
                    ),
                    title="Timeline view",
                ),
                class_name="view-toggle-group",
            ),
            style={"display": "flex", "gap": "8px", "alignItems": "center"},
        ),
        style={
            "display": "flex", "gap": "16px",
            "alignItems": "center", "flexWrap": "wrap",
            "marginBottom": "24px",
        },
    )


# ── Log item ──────────────────────────────────────────────────────────────────

def _icon_cls(item: dict):
    return rx.cond(
        item["note_type"] == "kudos",     "feed-icon feed-icon-gold",
        rx.cond(
            item["note_type"] == "flag",      "feed-icon feed-icon-flag",
            rx.cond(
                item["note_type"] == "incident",  "feed-icon feed-icon-flag",
                rx.cond(
                    item["note_type"] == "callout",   "feed-icon feed-icon-flag",
                    rx.cond(
                        item["note_type"] == "beo",       "feed-icon feed-icon-flag",
                        rx.cond(
                            item["note_type"] == "floor_walk","feed-icon feed-icon-blue",
                            rx.cond(
                                item["note_type"] == "huddle",    "feed-icon feed-icon-blue",
                                rx.cond(
                                    item["note_type"] == "reference", "feed-icon",
                                    "feed-icon",  # dispatch, observation, etc.
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def log_item(item: dict) -> rx.Component:
    return rx.el.div(
        rx.el.div(item["timestamp_display"], class_name="feed-time"),
        rx.el.div(item["icon"], class_name=_icon_cls(item)),
        rx.el.div(
            item["text"],
            rx.el.span(
                item["note_type"],
                class_name="chip",
                style={"marginLeft": "8px", "fontSize": "10px", "verticalAlign": "middle"},
            ),
            class_name="feed-text log-text",
        ),
        class_name="feed-item log-item",
    )


# ── Timeline item ─────────────────────────────────────────────────────────────

def _tl_dot_cls(item: dict) -> rx.Component:
    """Color-coded dot class based on note_type."""
    return rx.cond(
        item["note_type"] == "kudos",       "tl-dot tl-dot-gold",
        rx.cond(
            item["note_type"] == "flag",        "tl-dot tl-dot-flag",
            rx.cond(
                item["note_type"] == "incident",    "tl-dot tl-dot-flag",
                rx.cond(
                    item["note_type"] == "callout",     "tl-dot tl-dot-flag",
                    rx.cond(
                        item["note_type"] == "beo",         "tl-dot tl-dot-flag",
                        rx.cond(
                            item["note_type"] == "floor_walk",  "tl-dot tl-dot-blue",
                            rx.cond(
                                item["note_type"] == "huddle",      "tl-dot tl-dot-blue",
                                "tl-dot",   # observation, reference, dispatch → gray
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def timeline_item(item: dict) -> rx.Component:
    return rx.el.div(
        rx.el.div(class_name=_tl_dot_cls(item)),
        rx.el.div(
            rx.el.div(
                rx.el.span(item["timestamp_display"], class_name="tl-time"),
                rx.el.span(item["note_type"], class_name="chip",
                           style={"fontSize": "10px"}),
                class_name="tl-meta",
            ),
            rx.el.p(item["text"], class_name="tl-text"),
            class_name="tl-body",
        ),
        class_name="tl-item",
    )


# ── Skeleton feed ─────────────────────────────────────────────────────────────

def logs_skeleton() -> rx.Component:
    return rx.el.div(
        *[rx.el.div(
            rx.el.div(class_name="skeleton", style={"height": "11px", "width": "40px"}),
            rx.el.div(class_name="skeleton", style={"height": "16px", "width": "16px", "borderRadius": "4px"}),
            rx.el.div(
                rx.el.div(class_name="skeleton", style={"height": "11px", "width": "85%", "marginBottom": "4px"}),
                rx.el.div(class_name="skeleton", style={"height": "11px", "width": "60%"}),
                style={"flex": "1"},
            ),
            class_name="feed-item", style={"gap": "12px"},
        ) for _ in range(10)],
        class_name="feed",
    )


# ── Logs page ─────────────────────────────────────────────────────────────────

def logs_page() -> rx.Component:
    return rx.el.div(
        rx.el.main(
            page_header(),
            controls_row(),
            rx.cond(
                LogsState.loading,
                logs_skeleton(),
                rx.cond(
                    LogsState.item_count > 0,
                    rx.cond(
                        LogsState.view_mode == "timeline",
                        # Timeline view
                        rx.el.div(
                            rx.foreach(LogsState.items, timeline_item),
                            class_name="tl-feed",
                        ),
                        # Feed view (default)
                        rx.el.div(
                            rx.foreach(LogsState.items, log_item),
                            class_name="feed logs-feed",
                        ),
                    ),
                    empty_state(
                        "No entries found",
                        rx.cond(
                            LogsState.search != "",
                            "Try a broader search or different filter.",
                            "Nothing captured in this time range.",
                        ),
                    ),
                ),
            ),
            class_name="main main-single",
            style={"maxWidth": "760px"},
        ),
        # FAB
        rx.el.button(
            "+",
            class_name="fab",
            on_click=AppState.open_capture,
            title="Capture (⌘N)",
            aria_label="Quick capture",
        ),
        global_tm_drawer(),
        command_palette(),
        capture_modal(),
        class_name=AppState.app_class_name,
    )
