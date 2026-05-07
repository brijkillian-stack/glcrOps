"""apps/admin/pages/index.py — Sudo Admin stub (Phase 2).

Phase 4 will populate this hub with long-tail Memory features:
Logs, Threads, Health, Floor Walk, Areas, Write-Ups, Deployment,
Engine Configurator.
"""

import reflex as rx


def admin_page() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.p(
                "ADMIN",
                style={
                    "fontSize": "10px",
                    "fontWeight": "700",
                    "letterSpacing": "0.14em",
                    "textTransform": "uppercase",
                    "color": "var(--zds-gold, #e0cbb6)",
                    "marginBottom": "8px",
                },
            ),
            rx.el.h1(
                "Sudo Admin",
                style={
                    "fontSize": "28px",
                    "fontWeight": "600",
                    "letterSpacing": "-0.02em",
                    "color": "var(--fg-1, #f0f4f8)",
                    "marginBottom": "12px",
                },
            ),
            rx.el.p(
                "Coming soon. Phase 4 will populate this hub with the long-tail "
                "Memory features (Logs, Threads, Health, Floor Walk, Areas, "
                "Write-Ups, Deployment, Engine Configurator).",
                style={
                    "color": "var(--fg-2, #8ba4be)",
                    "fontSize": "15px",
                    "lineHeight": "1.6",
                    "maxWidth": "480px",
                },
            ),
            style={
                "padding": "48px 40px",
            },
        ),
        style={
            "minHeight": "100vh",
            "background": "var(--zds-bg-1, #080e14)",
        },
    )
