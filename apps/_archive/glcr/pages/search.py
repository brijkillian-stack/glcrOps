"""
pages/search.py — Search page

Full-text search across notes, tasks, and team members.
Results are grouped by kind (Tasks / Notes / People) with type chips.
"""

import reflex as rx
from ..state.search import SearchState
from shared.base import AppState
from ..state.people import PeopleState
from shared.components.palette import command_palette
from shared.components.capture import capture_modal
from ..components.tm_drawer import global_tm_drawer


# ── Page header ───────────────────────────────────────────────────────────────

def page_header() -> rx.Component:
    return rx.el.header(
        rx.el.div("Search", class_name="page-eyebrow"),
        rx.el.h1("Find anything", class_name="page-title"),
        class_name="page-head",
        style={"marginBottom": "20px"},
    )


# ── Search bar ────────────────────────────────────────────────────────────────

def search_bar() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span("⌕", class_name="search-icon"),
            rx.el.input(
                placeholder="Search notes, tasks, team members…",
                value=SearchState.query,
                on_change=SearchState.set_query,
                auto_focus=True,
                class_name="search-input",
            ),
            rx.cond(
                SearchState.query != "",
                rx.el.button(
                    "✕",
                    on_click=SearchState.clear_search,
                    class_name="search-clear",
                    title="Clear",
                ),
                rx.fragment(),
            ),
            class_name="search-bar",
        ),
        class_name="search-bar-wrap",
    )


# ── Kind filter tabs ──────────────────────────────────────────────────────────

def _filter_tab(label: str, value: str, count_var: rx.Var) -> rx.Component:
    return rx.el.button(
        label,
        rx.cond(
            count_var > 0,
            rx.el.span(
                count_var.to_string(),
                class_name="search-tab-count",
            ),
            rx.fragment(),
        ),
        on_click=SearchState.set_kind_filter(value),
        class_name=rx.cond(
            SearchState.kind_filter == value,
            "filter-tab active",
            "filter-tab",
        ),
    )


def kind_filters() -> rx.Component:
    return rx.cond(
        SearchState.has_searched,
        rx.el.div(
            _filter_tab("All",    "all",    SearchState.result_count),
            _filter_tab("Notes",  "notes",  SearchState.notes_count),
            _filter_tab("Tasks",  "tasks",  SearchState.tasks_count),
            _filter_tab("People", "people", SearchState.people_count),
            class_name="filter-tabs",
            style={"marginBottom": "20px"},
        ),
        rx.fragment(),
    )


# ── Status / empty state ──────────────────────────────────────────────────────

def status_line() -> rx.Component:
    return rx.el.p(
        SearchState.status_line,
        class_name="search-status",
    )


def empty_state() -> rx.Component:
    return rx.cond(
        SearchState.show_empty,
        rx.el.div(
            rx.el.span("⌕", style={"fontSize": "32px", "color": "var(--fg-mute)"}),
            rx.el.p(
                "Nothing found for ",
                rx.el.strong(SearchState.query, style={"color": "var(--fg-1)"}),
                ".",
                style={"margin": "8px 0 4px", "color": "var(--fg-2)", "fontSize": "15px"},
            ),
            rx.el.p(
                "Try a different word, or check the Logs page for archived entries.",
                style={"color": "var(--fg-3)", "fontSize": "13px", "margin": "0"},
            ),
            class_name="search-empty",
        ),
        rx.fragment(),
    )


# ── Loading skeleton ──────────────────────────────────────────────────────────

def _skeleton_row() -> rx.Component:
    return rx.el.div(
        rx.el.div(class_name="skel skel-sm", style={"width": "48px", "marginBottom": "6px"}),
        rx.el.div(class_name="skel skel-md", style={"width": "70%", "marginBottom": "6px"}),
        rx.el.div(class_name="skel skel-sm", style={"width": "90%"}),
        class_name="search-result-item",
        style={"pointerEvents": "none"},
    )


def loading_state() -> rx.Component:
    return rx.cond(
        SearchState.loading,
        rx.el.div(
            _skeleton_row(),
            _skeleton_row(),
            _skeleton_row(),
            class_name="search-results",
        ),
        rx.fragment(),
    )


# ── Result item ───────────────────────────────────────────────────────────────

def _kind_class(result: dict) -> rx.Var:
    """CSS class for the kind badge on the left."""
    return rx.cond(
        result["kind"] == "task",    "search-kind-badge search-kind-task",
        rx.cond(
            result["kind"] == "person", "search-kind-badge search-kind-person",
            "search-kind-badge search-kind-note",
        ),
    )


def _result_inner(result: dict) -> rx.Component:
    """Shared inner layout for all result kinds."""
    return rx.fragment(
        # Left: icon + kind badge
        rx.el.div(
            rx.el.span(result["icon"], class_name="result-icon"),
            rx.el.span(result["type_label"], class_name=_kind_class(result)),
            class_name="result-left",
        ),
        # Right: title + excerpt + timestamp
        rx.el.div(
            rx.el.div(
                rx.el.span(result["title"], class_name="result-title"),
                rx.el.span(result["timestamp_display"], class_name="result-ts"),
                class_name="result-title-row",
            ),
            rx.cond(
                result["excerpt"] != "",
                rx.el.p(result["excerpt"], class_name="result-excerpt"),
                rx.fragment(),
            ),
            class_name="result-body",
        ),
    )


def result_item(result: dict) -> rx.Component:
    # Person results are clickable — open the global TM quick-peek drawer.
    # Tasks and notes are styled as plain cards (links could be added later).
    return rx.cond(
        result["kind"] == "person",
        rx.el.div(
            _result_inner(result),
            on_click=PeopleState.open_drawer_by_name(result["title"]),
            class_name="search-result-item search-result-person",
        ),
        rx.el.div(
            _result_inner(result),
            class_name="search-result-item",
        ),
    )


# ── Results list ──────────────────────────────────────────────────────────────

def results_list() -> rx.Component:
    return rx.cond(
        SearchState.show_results,
        rx.el.div(
            rx.foreach(SearchState.results, result_item),
            class_name="search-results",
        ),
        rx.fragment(),
    )


# ── Recent search chip ───────────────────────────────────────────────────────

def recent_chip(term: str) -> rx.Component:
    return rx.el.div(
        rx.el.span(
            "↺",
            style={"fontSize": "11px", "marginRight": "5px", "color": "var(--fg-3)"},
        ),
        rx.el.span(term, class_name="recent-chip-text"),
        rx.el.button(
            "✕",
            on_click=SearchState.remove_recent(term),
            class_name="recent-chip-remove",
            title="Remove",
        ),
        on_click=SearchState.apply_recent(term),
        class_name="recent-chip",
    )


def recent_searches_row() -> rx.Component:
    return rx.cond(
        SearchState.show_recent,
        rx.el.div(
            rx.el.div(
                rx.el.span("Recent", class_name="recent-label"),
                rx.el.button(
                    "Clear all",
                    on_click=SearchState.clear_recent,
                    class_name="recent-clear-btn",
                ),
                class_name="recent-header",
            ),
            rx.el.div(
                rx.foreach(SearchState.recent_searches, recent_chip),
                class_name="recent-chips-row",
            ),
            class_name="recent-searches",
        ),
        rx.fragment(),
    )


# ── Hero prompt (pre-search state) ────────────────────────────────────────────

def hero_prompt() -> rx.Component:
    return rx.cond(
        ~SearchState.has_searched & ~SearchState.loading,
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.el.span("◐", style={"marginRight": "8px", "color": "var(--fg-mute)"}),
                    "Notes",
                    class_name="hero-chip",
                ),
                rx.el.div(
                    rx.el.span("☐", style={"marginRight": "8px", "color": "var(--fg-mute)"}),
                    "Tasks",
                    class_name="hero-chip",
                ),
                rx.el.div(
                    rx.el.span("◍", style={"marginRight": "8px", "color": "var(--fg-mute)"}),
                    "Team Members",
                    class_name="hero-chip",
                ),
                class_name="hero-chips",
            ),
            rx.el.p(
                "Search across everything in GLCR Memory.",
                style={
                    "color": "var(--fg-3)", "fontSize": "13px",
                    "textAlign": "center", "margin": "12px 0 0",
                },
            ),
            class_name="search-hero",
        ),
        rx.fragment(),
    )


# ── Search page ───────────────────────────────────────────────────────────────

def search_page() -> rx.Component:
    return rx.el.div(
        rx.el.main(
            page_header(),
            search_bar(),
            recent_searches_row(),
            kind_filters(),
            status_line(),
            loading_state(),
            empty_state(),
            results_list(),
            hero_prompt(),
            class_name="main main-single",
            style={"maxWidth": "720px"},
        ),
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
