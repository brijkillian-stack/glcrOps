"""
apps/admin/pages/engine.py — Engine Configurator stub (Phase 4c placeholder).

Route: /admin/engine
Phase 4c will populate this with:
  • Weight sliders (zone priority weights)
  • Threshold editors (warn / lock thresholds)
  • Slot-difficulty editor (per-zone difficulty ratings)
  • Simulation pane (run a placement pass and preview output)
"""

import reflex as rx
from shared.components.admin_section_head import admin_breadcrumb


def admin_engine_page() -> rx.Component:
    return rx.el.div(
        admin_breadcrumb(section="Workflows", page_title="Engine Config"),
        rx.el.div(
            # Eyebrow
            rx.el.div(
                "ENGINE · CONFIGURATOR",
                style={
                    "fontSize": "10px",
                    "fontWeight": "700",
                    "letterSpacing": "0.14em",
                    "textTransform": "uppercase",
                    "color": "var(--gold)",
                    "fontFamily": "var(--font)",
                    "marginBottom": "8px",
                },
            ),
            # Heading
            rx.el.div(
                "Engine Configurator",
                style={
                    "fontFamily": "var(--serif)",
                    "fontSize": "26px",
                    "fontWeight": "400",
                    "fontStyle": "italic",
                    "letterSpacing": "-0.015em",
                    "color": "var(--ink)",
                    "marginBottom": "12px",
                },
            ),
            # Body
            rx.el.div(
                rx.el.div(
                    "⚙",
                    style={
                        "fontSize": "48px",
                        "color": "var(--line2)",
                        "marginBottom": "16px",
                    },
                ),
                rx.el.div(
                    "Phase 4c will populate this with weight sliders, threshold editors, "
                    "slot-difficulty editor, and the simulation pane.",
                    style={
                        "fontSize": "14px",
                        "color": "var(--ink3)",
                        "lineHeight": "1.6",
                        "maxWidth": "420px",
                        "marginBottom": "24px",
                    },
                ),
                # Coming soon chips
                rx.el.div(
                    *[
                        rx.el.span(
                            label,
                            style={
                                "display": "inline-flex",
                                "alignItems": "center",
                                "padding": "4px 12px",
                                "borderRadius": "999px",
                                "background": "var(--panel2)",
                                "border": "1px solid var(--line2)",
                                "fontSize": "11px",
                                "fontWeight": "600",
                                "color": "var(--ink3)",
                                "letterSpacing": "0.04em",
                                "fontFamily": "var(--font)",
                            },
                        )
                        for label in [
                            "Weight Sliders",
                            "Threshold Editors",
                            "Slot-Difficulty Editor",
                            "Simulation Pane",
                        ]
                    ],
                    style={
                        "display": "flex",
                        "flexWrap": "wrap",
                        "gap": "8px",
                    },
                ),
                style={
                    "display": "flex",
                    "flexDirection": "column",
                    "alignItems": "flex-start",
                },
            ),
            style={
                "padding": "40px 40px",
                "minHeight": "calc(100vh - 40px)",
                "background": "var(--bg)",
                "fontFamily": "var(--font)",
                "color": "var(--ink)",
            },
        ),
        class_name="admin-subpage-wrapper",
    )
