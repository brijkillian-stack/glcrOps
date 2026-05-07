"""
pages/health.py — System Health page

Displays dashboard KPIs: capture velocity, embedding coverage, search activity,
and backend diagnostics.
"""

import reflex as rx
from ..state.health import HealthState
from shared.base import AppState
from shared.components.ui import kpi_card, empty_state, skeleton_card
import os


def page_header() -> rx.Component:
    return rx.el.header(
        rx.el.div(
            rx.el.h1("System Health", class_name="page-title"),
            rx.el.p("Backend diagnostics and data quality metrics",
                    class_name="page-summary"),
            class_name="page-head-content",
        ),
        class_name="page-head",
    )


def kpi_section() -> rx.Component:
    """Three KPI cards: Capture velocity, Embedding coverage, Search activity."""
    return rx.el.div(
        rx.el.div(
            kpi_card(
                "Capture velocity",
                HealthState.total_notes,
                HealthState.last_note_relative_time,
                "flat",
            ),
            kpi_card(
                "Embedding coverage",
                HealthState.embedding_coverage_pct,
                HealthState.embedding_entity_label,
                "flat",
            ),
            kpi_card(
                "Search activity",
                HealthState.search_log_total_rows,
                rx.cond(
                    HealthState.search_log_zero_hit_count > 0,
                    f"{HealthState.search_log_zero_hit_count} zero-hit",
                    "no blanks",
                ),
                "flat",
            ),
            class_name="kpi-stack",
        ),
    )


def backend_section() -> rx.Component:
    """Backend diagnostics panel."""
    supabase_url = os.environ.get("SUPABASE_URL", "—")

    return rx.el.div(
        rx.el.h2("Backend", class_name="section-title"),
        rx.el.div(
            rx.el.div(
                rx.el.div("Platform", class_name="backend-label"),
                rx.el.div("Supabase", class_name="backend-value"),
                class_name="backend-row",
            ),
            rx.el.div(
                rx.el.div("Schema version", class_name="backend-label"),
                rx.el.div(HealthState.schema_version, class_name="backend-value"),
                class_name="backend-row",
            ),
            rx.el.div(
                rx.el.div("Project URL", class_name="backend-label"),
                rx.el.div(
                    supabase_url[:50] + "…" if len(supabase_url) > 50 else supabase_url,
                    class_name="backend-value",
                    style={"fontSize": "11px", "color": "var(--fg-3)"},
                ),
                class_name="backend-row",
            ),
            rx.el.div(
                rx.el.div("Advisor warnings", class_name="backend-label"),
                rx.el.div(HealthState.advisor_warning_count, class_name="backend-value"),
                class_name="backend-row",
            ),
            rx.el.div(
                rx.el.div("Total counts", class_name="backend-label"),
                rx.el.div(
                    f"{HealthState.total_notes} notes · "
                    f"{HealthState.total_entities} entities · "
                    f"{HealthState.total_events} events · "
                    f"{HealthState.total_tasks} tasks",
                    class_name="backend-value",
                    style={"fontSize": "12px"},
                ),
                class_name="backend-row",
            ),
            class_name="backend-panel",
        ),
        rx.el.button(
            "↻ Refresh",
            on_click=HealthState.reload_health,
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


def health_page() -> rx.Component:
    return rx.el.div(
        rx.el.main(
            page_header(),
            rx.cond(
                HealthState.loading,
                rx.fragment(skeleton_card(), skeleton_card(), skeleton_card()),
                rx.cond(
                    HealthState.error == "",
                    rx.fragment(
                        kpi_section(),
                        backend_section(),
                    ),
                    rx.el.div(
                        rx.el.p(f"Error: {HealthState.error}",
                                style={"color": "var(--accent-flag)"}),
                        class_name="error-state",
                    ),
                ),
            ),
            class_name="main",
        ),
        class_name=AppState.app_class_name,
    )
