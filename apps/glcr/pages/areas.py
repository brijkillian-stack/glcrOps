"""
pages/areas.py — Areas quick-note page

Grid of area tiles (zones, restrooms, other areas). Tap a tile to open
an inline form for dropping a sentiment-tagged note without doing a full floor walk.
"""

import reflex as rx
from ..state.areas import AreasState
from shared.base import AppState
from shared.components.palette import command_palette
from shared.components.capture import capture_modal


def page_header() -> rx.Component:
    return rx.el.header(
        rx.el.div("Quick Notes", class_name="page-eyebrow"),
        rx.el.h1("Areas", class_name="page-title"),
        class_name="page-head",
        style={"marginBottom": "20px"},
    )


def sentiment_chip(label: str, value: str) -> rx.Component:
    is_selected = AreasState.note_sentiment == value
    return rx.el.button(
        label,
        on_click=AreasState.set_sentiment(value),
        class_name=rx.cond(
            is_selected,
            "sentiment-chip sentiment-chip-selected",
            "sentiment-chip",
        ),
        style={
            "padding": "6px 12px",
            "borderRadius": "var(--r-pill)",
            "border": "1px solid var(--border-subtle)",
            "background": rx.cond(
                is_selected,
                rx.cond(value == "positive", "var(--accent-positive-bg)",
                        rx.cond(value == "negative", "var(--accent-flag-bg)",
                                "var(--surface-card)")),
                "transparent",
            ),
            "color": rx.cond(
                is_selected,
                rx.cond(value == "positive", "var(--accent-positive)",
                        rx.cond(value == "negative", "var(--accent-flag)",
                                "var(--fg-1)")),
                "var(--fg-2)",
            ),
            "cursor": "pointer",
            "fontSize": "12px",
            "fontWeight": "500",
            "transition": "all 150ms ease",
        },
    )


def note_form() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.h3("Add Note", style={"margin": "0 0 12px", "fontSize": "14px",
                                       "fontWeight": "600"}),
            class_name="area-note-title",
        ),
        rx.el.textarea(
            placeholder="What did you observe?",
            value=AreasState.note_content,
            on_change=AreasState.set_note_content,
            style={
                "width": "100%",
                "minHeight": "80px",
                "padding": "8px 12px",
                "borderRadius": "var(--r-md)",
                "border": "1px solid var(--border-subtle)",
                "background": "var(--surface-card)",
                "color": "var(--fg-1)",
                "fontSize": "13px",
                "fontFamily": "inherit",
                "resize": "vertical",
            },
        ),
        rx.el.div(
            rx.el.span("Sentiment", style={"fontSize": "11px", "color": "var(--fg-3)",
                                           "textTransform": "uppercase",
                                           "fontWeight": "500"}),
            rx.el.div(
                sentiment_chip("Positive", "positive"),
                sentiment_chip("Neutral", "neutral"),
                sentiment_chip("Negative", "negative"),
                sentiment_chip("Flag", "flag"),
                style={"display": "flex", "gap": "8px", "flexWrap": "wrap",
                       "marginTop": "6px"},
            ),
            style={"marginTop": "12px", "marginBottom": "12px"},
        ),
        rx.el.div(
            rx.el.button(
                rx.cond(AreasState.saving, "Saving…", "✓ Save"),
                on_click=AreasState.save_area_note,
                disabled=AreasState.saving | (AreasState.note_content.length() == 0),
                class_name="btn btn-primary",
                style={"fontSize": "13px", "padding": "8px 16px"},
            ),
            rx.el.button(
                "Cancel",
                on_click=AreasState.cancel_note,
                class_name="btn btn-ghost",
                style={"fontSize": "13px"},
            ),
            style={"display": "flex", "gap": "8px"},
        ),
        class_name="area-note-form",
        style={
            "padding": "12px",
            "background": "var(--surface-card)",
            "borderRadius": "var(--r-md)",
            "border": "1px solid var(--border-subtle)",
        },
    )


def area_tile(area: dict) -> rx.Component:
    is_selected = AreasState.selected_area_id == area["id"]
    is_flashing = AreasState.just_saved_id == area["id"]

    return rx.el.div(
        # Tile button
        rx.el.button(
            rx.el.div(
                rx.el.div(
                    area["name"],
                    style={
                        "fontSize": "14px",
                        "fontWeight": "600",
                        "color": "var(--fg-1)",
                        "marginBottom": "4px",
                    },
                ),
                rx.cond(
                    area["recent_count"].to(int) > 0,
                    rx.el.span(
                        rx.text(area["recent_count"], " recent"),
                        style={
                            "fontSize": "11px",
                            "color": "var(--fg-3)",
                        },
                    ),
                    rx.fragment(),
                ),
                style={
                    "display": "flex",
                    "flexDirection": "column",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "width": "100%",
                    "height": "100%",
                    "padding": "16px",
                    "textAlign": "center",
                },
            ),
            on_click=AreasState.select_area(area["id"]),
            class_name=rx.cond(
                is_selected,
                "area-tile area-tile-active",
                rx.cond(is_flashing, "area-tile area-tile-flash", "area-tile"),
            ),
            style={
                "width": "100%",
                "aspectRatio": "1",
                "padding": "0",
                "border": "1px solid var(--border-subtle)",
                "borderRadius": "var(--r-md)",
                "background": rx.cond(
                    is_flashing,
                    "var(--accent-positive-bg)",
                    rx.cond(is_selected, "var(--surface-card)", "var(--surface)"),
                ),
                "cursor": "pointer",
                "transition": "all 150ms ease",
            },
        ),
        # Inline form (when selected)
        rx.cond(
            is_selected,
            rx.el.div(
                note_form(),
                style={
                    "gridColumn": "1 / -1",
                    "marginTop": "12px",
                },
            ),
            rx.fragment(),
        ),
        class_name="area-tile-wrapper",
    )


def section_grid(section_name: str, section_var) -> rx.Component:
    """Render a grid of areas for a given section."""
    return rx.el.div(
        rx.el.h2(section_name, style={
            "fontSize": "16px",
            "fontWeight": "600",
            "color": "var(--fg-1)",
            "marginBottom": "12px",
            "marginTop": "24px",
        }),
        rx.el.div(
            rx.foreach(
                section_var,
                lambda a: area_tile(a),
            ),
            class_name="areas-grid",
            style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fill, minmax(120px, 1fr))",
                "gap": "12px",
            },
        ),
        class_name="area-section",
    )


def areas_page() -> rx.Component:
    return rx.el.div(
        rx.el.main(
            page_header(),
            rx.cond(
                AreasState.loading,
                rx.el.p("Loading areas…", style={"color": "var(--fg-2)",
                                                 "textAlign": "center",
                                                 "paddingTop": "40px"}),
                rx.el.div(
                    section_grid("Main Floor", AreasState.main_floor_areas),
                    section_grid("Men's Restrooms", AreasState.mens_restroom_areas),
                    section_grid("Women's Restrooms", AreasState.womens_restroom_areas),
                    section_grid("Other Areas", AreasState.other_areas_list),
                    style={"marginBottom": "40px"},
                ),
            ),
            class_name="main main-single",
            style={"maxWidth": "1000px"},
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
