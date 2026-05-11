"""
pages/patterns.py — Patterns page

Three trend panels:
  1. Call-out frequency — TMs who call out most in the analysis window
  2. Zone flags — which zones / areas get flagged most during floor walks
  3. Score velocity — TMs with the biggest skill-score changes in the window
"""

import reflex as rx
from ..state.patterns import PatternsState
from shared.base import AppState
from ..state.people import PeopleState
from shared.components.ui import empty_state
from shared.components.palette import command_palette
from shared.components.capture import capture_modal
from ..components.tm_drawer import global_tm_drawer, tm_name_link


# ── Helpers ───────────────────────────────────────────────────────────────────

def _section_title(text: str, badge: rx.Component) -> rx.Component:
    return rx.el.div(
        rx.el.h2(text, class_name="section-title", style={"marginBottom": "0"}),
        badge,
        style={"display": "flex", "alignItems": "center",
               "gap": "8px", "marginBottom": "16px"},
    )


def _count_badge(count: rx.Var) -> rx.Component:
    return rx.el.span(
        count.to_string(),
        style={
            "fontSize": "11px", "fontWeight": "500",
            "color": "var(--fg-mute)",
            "background": "var(--surface-hover)",
            "borderRadius": "var(--r-pill)",
            "padding": "2px 8px",
        },
    )


def _skeleton_bars(n: int = 5) -> rx.Component:
    return rx.el.div(
        *[
            rx.el.div(
                rx.el.div(class_name="skeleton",
                          style={"height": "11px", "width": "80px", "marginBottom": "6px"}),
                rx.el.div(class_name="skeleton",
                          style={"height": "8px", "width": "100%", "borderRadius": "var(--r-pill)"}),
                style={"marginBottom": "12px"},
            )
            for _ in range(n)
        ],
    )


# ── Call-out panel ────────────────────────────────────────────────────────────

def callout_bar_row(item: dict) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            tm_name_link(item["name"], extra_class="pat-bar-name"),
            rx.el.span(
                item["count"].to_string(),
                " × · last ",
                item["last_display"],
                class_name="pat-bar-meta",
            ),
            class_name="pat-bar-label-row",
        ),
        rx.el.div(
            rx.el.div(
                style={
                    "height": "100%",
                    "width": item["pct"].to_string() + "%",
                    "background": "var(--accent-flag)",
                    "borderRadius": "var(--r-pill)",
                    "transition": "width 400ms var(--ease)",
                    "minWidth": "4px",
                },
            ),
            class_name="pat-bar-track",
        ),
        class_name="pat-bar-row",
    )


def callout_panel() -> rx.Component:
    return rx.el.div(
        _section_title("Call-outs", _count_badge(PatternsState.callout_count)),
        rx.cond(
            PatternsState.loading,
            _skeleton_bars(5),
            rx.cond(
                PatternsState.has_callouts,
                rx.el.div(
                    rx.foreach(PatternsState.callouts, callout_bar_row),
                    class_name="pat-bars",
                ),
                empty_state(
                    "No call-outs",
                    f"{PatternsState.window_label} — no call-out notes found.",
                ),
            ),
        ),
        class_name="pat-panel",
    )


# ── Zone flags panel ──────────────────────────────────────────────────────────

def zone_flag_row(item: dict) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(item["zone"], class_name="pat-bar-name"),
            rx.el.span(
                item["count"].to_string(),
                " flag",
                class_name="pat-bar-meta",
            ),
            class_name="pat-bar-label-row",
        ),
        rx.el.div(
            rx.el.div(
                style={
                    "height": "100%",
                    "width": item["pct"].to_string() + "%",
                    "background": "var(--accent-blue)",
                    "borderRadius": "var(--r-pill)",
                    "transition": "width 400ms var(--ease)",
                    "minWidth": "4px",
                },
            ),
            class_name="pat-bar-track",
        ),
        class_name="pat-bar-row",
    )


def zone_flags_panel() -> rx.Component:
    return rx.el.div(
        _section_title("Zone Flags", _count_badge(PatternsState.zone_flag_count)),
        rx.cond(
            PatternsState.loading,
            _skeleton_bars(6),
            rx.cond(
                PatternsState.has_zone_flags,
                rx.el.div(
                    rx.foreach(PatternsState.zone_flags, zone_flag_row),
                    class_name="pat-bars",
                ),
                empty_state(
                    "No zone flags",
                    f"{PatternsState.window_label} — no flagged areas found.",
                ),
            ),
        ),
        class_name="pat-panel",
    )


# ── Score velocity panel ──────────────────────────────────────────────────────

def mover_row(item: dict) -> rx.Component:
    badge_cls = rx.cond(
        item["direction"] == "up",
        "pat-mover-badge up",
        "pat-mover-badge down",
    )
    arrow = rx.cond(item["direction"] == "up", "▲", "▼")
    return rx.el.div(
        # Name + entry count
        rx.el.div(
            tm_name_link(item["name"], extra_class="pat-mover-name"),
            rx.el.span(
                item["entries"].to_string(),
                " score change",
                rx.cond(item["entries"].to(int) > 1, "s", ""),
                class_name="pat-mover-entries",
            ),
            class_name="pat-mover-left",
        ),
        # Score track: before → now
        rx.el.div(
            rx.el.span(
                item["before_label"],
                style={"color": "var(--fg-3)", "fontSize": "12px"},
            ),
            rx.el.span("→", style={"color": "var(--fg-4)", "fontSize": "11px", "margin": "0 4px"}),
            rx.el.span(
                item["score_label"],
                style={"color": "var(--fg-1)", "fontWeight": "600", "fontSize": "13px"},
            ),
            class_name="pat-mover-scores",
        ),
        # Delta badge
        rx.el.div(
            arrow,
            " ",
            item["delta_str"],
            class_name=badge_cls,
        ),
        class_name="pat-mover-row",
    )


def score_velocity_panel() -> rx.Component:
    return rx.el.div(
        _section_title("Score Velocity", _count_badge(PatternsState.mover_count)),
        rx.cond(
            PatternsState.loading,
            # Skeleton mover rows
            rx.el.div(
                *[
                    rx.el.div(
                        rx.el.div(class_name="skeleton",
                                  style={"height": "13px", "width": "80px"}),
                        rx.el.div(class_name="skeleton",
                                  style={"height": "13px", "width": "60px", "marginLeft": "auto"}),
                        style={"display": "flex", "justifyContent": "space-between",
                               "marginBottom": "12px"},
                    )
                    for _ in range(6)
                ],
            ),
            rx.cond(
                PatternsState.has_movers,
                rx.el.div(
                    rx.foreach(PatternsState.score_movers, mover_row),
                    class_name="pat-movers",
                ),
                empty_state(
                    "No score changes",
                    f"{PatternsState.window_label} — all scores are stable.",
                ),
            ),
        ),
        class_name="pat-panel",
    )


# ── Page header ───────────────────────────────────────────────────────────────

def page_header() -> rx.Component:
    return rx.el.header(
        rx.el.div("Trends", class_name="page-eyebrow"),
        rx.el.div(
            rx.el.h1("Patterns", class_name="page-title", style={"marginBottom": "0"}),
            # Window selector
                rx.el.select(
                    rx.el.option("Last 30 days", value="30"),
                    rx.el.option("Last 60 days", value="60"),
                    rx.el.option("Last 90 days", value="90"),
                    value=PatternsState.window_days.to_string(),
                    on_change=PatternsState.set_window,
                    style={
                        "fontSize": "13px", "color": "var(--fg-2)",
                        "background": "var(--surface-card)",
                        "border": "1px solid var(--border-subtle)",
                        "borderRadius": "var(--r-md)", "padding": "5px 10px",
                        "outline": "none", "cursor": "pointer",
                    },
                ),
            style={"display": "flex", "alignItems": "center", "gap": "16px"},
        ),
        class_name="page-head",
        style={"marginBottom": "28px"},
    )


# ── Patterns page ─────────────────────────────────────────────────────────────

def patterns_page() -> rx.Component:
    return rx.el.div(
        rx.el.main(
            page_header(),
            # Row 1 — side by side panels
            rx.el.div(
                callout_panel(),
                zone_flags_panel(),
                class_name="pat-row",
            ),
            # Row 2 — full-width velocity panel
            score_velocity_panel(),
            class_name="main main-single",
            style={"maxWidth": "960px"},
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
