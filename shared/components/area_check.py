"""
components/area_check.py — Phase M

Quick Area Check overlay. Brian taps a FAB on Today (or any GLCR page where
this component is mounted), picks an area off a tile grid, sees the TM
assigned to that area on tonight's deployment, and rates the area 1-10.

The save writes a row to public.area_checks linking BOTH the area_key and
the assigned tm_id, so trends are queryable from either side.
"""

import reflex as rx
from shared.base import AppState
from shared.db import AREA_CHECK_AREAS


# ── Step 1: area picker ─────────────────────────────────────────────────────

def _area_tile(label: str, key: str, side: str) -> rx.Component:
    return rx.el.button(
        label,
        on_click=AppState.pick_area_check_area(key, side, label),
        style={
            "padding": "10px 8px",
            "fontSize": "13px",
            "fontWeight": "600",
            "color": "var(--fg-1)",
            "background": "var(--surface-card)",
            "border": "1px solid var(--border-subtle)",
            "borderRadius": "var(--r-md)",
            "cursor": "pointer",
            "textAlign": "center",
            "transition": "all 120ms ease",
        },
        _hover={
            "borderColor": "var(--accent-blue)",
            "background": "var(--accent-blue-bg)",
            "color": "var(--accent-blue)",
        },
    )


def _picker_step() -> rx.Component:
    """Tile grid of every area Brian can rate."""
    # Statically built from AREA_CHECK_AREAS — these don't change at runtime.
    tiles = [_area_tile(a["label"], a["key"], a["side"]) for a in AREA_CHECK_AREAS]
    return rx.el.div(
        rx.el.div(
            "Where did you check?",
            style={
                "fontSize": "13px", "fontWeight": "600",
                "color": "var(--fg-2)", "marginBottom": "12px",
            },
        ),
        rx.el.div(
            *tiles,
            style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fill, minmax(110px, 1fr))",
                "gap": "8px",
            },
        ),
    )


# ── Step 2: rate ─────────────────────────────────────────────────────────────

def _score_button(n: int) -> rx.Component:
    """One of the 10 score buttons."""
    return rx.el.button(
        n,
        on_click=AppState.set_area_check_score(n),
        style={
            "width": "40px", "height": "40px",
            "fontSize": "15px", "fontWeight": "700",
            "borderRadius": "var(--r-md)",
            "cursor": "pointer",
            "transition": "all 120ms ease",
        },
        # Highlight only the selected score.
        background=rx.cond(
            AppState.area_check_score == n,
            "var(--accent-blue)",
            "var(--surface-card)",
        ),
        color=rx.cond(
            AppState.area_check_score == n,
            "white",
            "var(--fg-2)",
        ),
        border=rx.cond(
            AppState.area_check_score == n,
            "1px solid var(--accent-blue)",
            "1px solid var(--border-subtle)",
        ),
    )


def _rate_step() -> rx.Component:
    return rx.el.div(
        # Area + assigned TM banner
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    "Checking",
                    style={"fontSize": "10px", "fontWeight": "700",
                           "letterSpacing": "0.08em", "textTransform": "uppercase",
                           "color": "var(--fg-3)"},
                ),
                rx.el.div(
                    AppState.area_check_area_label,
                    style={"fontSize": "20px", "fontWeight": "700",
                           "color": "var(--fg-1)", "lineHeight": "1.1",
                           "marginTop": "2px"},
                ),
                style={"flex": "1"},
            ),
            rx.cond(
                AppState.area_check_tm_name != "",
                rx.el.div(
                    rx.el.div(
                        "Assigned",
                        style={"fontSize": "10px", "fontWeight": "700",
                               "letterSpacing": "0.08em", "textTransform": "uppercase",
                               "color": "var(--fg-3)", "textAlign": "right"},
                    ),
                    rx.el.div(
                        AppState.area_check_tm_name,
                        style={"fontSize": "16px", "fontWeight": "600",
                               "color": "var(--accent-blue)", "marginTop": "2px",
                               "textAlign": "right"},
                    ),
                ),
                rx.el.div(
                    "Unassigned",
                    style={"fontSize": "12px", "color": "var(--fg-mute)",
                           "fontStyle": "italic"},
                ),
            ),
            style={
                "display": "flex", "alignItems": "center", "gap": "12px",
                "padding": "12px 14px",
                "background": "var(--surface-canvas)",
                "border": "1px solid var(--border-subtle)",
                "borderRadius": "var(--r-md)",
                "marginBottom": "16px",
            },
        ),
        # Score 1-10
        rx.el.div(
            "Score (1 = poor, 10 = perfect)",
            style={"fontSize": "12px", "fontWeight": "600",
                   "color": "var(--fg-3)", "marginBottom": "8px"},
        ),
        rx.el.div(
            *[_score_button(n) for n in range(1, 11)],
            style={
                "display": "grid",
                "gridTemplateColumns": "repeat(10, 1fr)",
                "gap": "6px",
                "marginBottom": "14px",
            },
        ),
        # Note
        rx.el.textarea(
            value=AppState.area_check_note,
            on_change=AppState.set_area_check_note,
            placeholder="Optional note — what stood out?",
            spellcheck=False,
            style={
                "width": "100%", "fontSize": "13px",
                "padding": "8px 10px",
                "border": "1px solid var(--border-subtle)",
                "borderRadius": "var(--r-md)",
                "background": "var(--surface-card)",
                "color": "var(--fg-1)",
                "outline": "none",
                "minHeight": "60px", "resize": "vertical",
                "marginBottom": "14px",
                "fontFamily": "inherit",
            },
        ),
        # Error
        rx.cond(
            AppState.area_check_error != "",
            rx.el.div(
                AppState.area_check_error,
                style={"fontSize": "12px", "color": "var(--accent-flag)",
                       "marginBottom": "8px"},
            ),
            rx.fragment(),
        ),
        # Actions
        rx.el.div(
            rx.el.button(
                "← Pick different area",
                on_click=AppState.back_to_area_picker,
                class_name="btn btn-ghost",
                style={"fontSize": "12px"},
            ),
            rx.el.div(style={"flex": "1"}),
            rx.el.button(
                rx.cond(AppState.area_check_saving, "Saving…", "Save check"),
                on_click=AppState.save_area_check,
                disabled=AppState.area_check_saving,
                class_name="btn btn-primary",
                style={"fontSize": "13px"},
            ),
            style={"display": "flex", "alignItems": "center", "gap": "8px"},
        ),
    )


# ── Public component ─────────────────────────────────────────────────────────

def area_check_modal() -> rx.Component:
    """The full overlay. Renders only when AppState.area_check_open is True."""
    return rx.cond(
        AppState.area_check_open,
        rx.el.div(
            # Backdrop
            rx.el.div(
                on_click=AppState.close_area_check,
                style={
                    "position": "fixed", "inset": "0",
                    "background": "rgba(0,0,0,0.45)",
                    "zIndex": "60",
                },
            ),
            # Centered panel
            rx.el.div(
                # Header
                rx.el.div(
                    rx.el.div(
                        "Area Check",
                        style={"fontSize": "16px", "fontWeight": "700",
                               "color": "var(--fg-1)"},
                    ),
                    rx.el.button(
                        "✕",
                        on_click=AppState.close_area_check,
                        style={
                            "background": "transparent", "border": "none",
                            "fontSize": "18px", "color": "var(--fg-3)",
                            "cursor": "pointer", "padding": "0 4px",
                        },
                    ),
                    style={
                        "display": "flex", "alignItems": "center",
                        "justifyContent": "space-between",
                        "marginBottom": "12px",
                    },
                ),
                # Step content
                rx.cond(
                    AppState.area_check_step == "pick",
                    _picker_step(),
                    _rate_step(),
                ),
                style={
                    "position": "fixed",
                    "top": "50%", "left": "50%",
                    "transform": "translate(-50%, -50%)",
                    "width": "min(560px, calc(100vw - 32px))",
                    "maxHeight": "calc(100vh - 32px)",
                    "overflowY": "auto",
                    "background": "var(--surface-card)",
                    "border": "1px solid var(--border-subtle)",
                    "borderRadius": "var(--r-lg)",
                    "padding": "16px",
                    "boxShadow": "0 24px 64px rgba(0,0,0,0.32)",
                    "zIndex": "61",
                },
            ),
        ),
        rx.fragment(),
    )


def area_check_fab() -> rx.Component:
    """Floating action button — opens the overlay. Drop into any GLCR page
    that should expose Quick Area Check from the floor."""
    return rx.el.button(
        "★",
        on_click=AppState.open_area_check,
        title="Area Check",
        aria_label="Open quick area check",
        style={
            "position": "fixed",
            "bottom": "20px",
            "left": "20px",
            "width": "44px", "height": "44px",
            "borderRadius": "50%",
            "background": "var(--accent-blue)",
            "color": "white",
            "border": "none",
            "fontSize": "20px",
            "fontWeight": "700",
            "cursor": "pointer",
            "boxShadow": "0 8px 24px rgba(0,101,191,0.32)",
            "zIndex": "30",
        },
    )
