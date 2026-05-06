"""
Week Overview page — /week/[week_id]

Shows all 7 nights for the week.  Each card has:
  • day name + date
  • staffing summary (in-rotation + break-wave counts)
  • Edit button  → /week/[week_id]/day/[night_id]
  • Print Day    → /api/print/night/[night_id]  (new tab)

Header has a Print Week button → /api/print/week/[week_id]  (new tab).
"""

import reflex as rx
from ..state import ZdsState


# ── Single night card ─────────────────────────────────────────────────────────

def _night_card(night: dict) -> rx.Component:
    return rx.box(
        rx.vstack(
            # Day name + date
            rx.hstack(
                rx.heading(night["day_name"], size="4", color="#111827"),
                rx.spacer(),
                rx.text(
                    night["night_date"],
                    size="1", color="#9ca3af",
                    align_self="center",
                ),
                align="center", width="100%",
            ),

            # Staffing summary
            rx.hstack(
                rx.text(
                    night["in_rotation"], " in rotation",
                    size="2", color="#6b7280",
                ),
                rx.separator(orientation="vertical", height="14px"),
                rx.text(
                    "Breaks: ",
                    night["breaks_5"], " / ",
                    night["breaks_9"], " / ",
                    night["breaks_4"],
                    size="2", color="#6b7280",
                ),
                align="center", gap="8px",
            ),

            # Phase R — at-a-glance fill bar + status pills
            rx.cond(
                night["stat_total"] > 0,
                rx.vstack(
                    # Progress bar
                    rx.box(
                        rx.box(
                            background=night["day_color"],
                            height="100%",
                            border_radius="999px",
                            width=(
                                (night["stat_filled"] * 100 / night["stat_total"]).to_string()
                                + "%"
                            ),
                            transition="width 0.3s ease",
                        ),
                        background="#f3f4f6",
                        height="6px",
                        border_radius="999px",
                        width="100%",
                        class_name="night-tab-fill-track",
                    ),
                    # Pills row: filled / unfilled / locked / called-off
                    rx.hstack(
                        rx.text(
                            night["stat_filled"].to_string(), " / ",
                            night["stat_total"].to_string(), " filled",
                            size="1", color="#374151", weight="medium",
                            font_variant_numeric="tabular-nums",
                        ),
                        rx.cond(
                            night["stat_unfilled"] > 0,
                            rx.hstack(
                                rx.box(
                                    background="#9ca3af",
                                    width="6px", height="6px",
                                    border_radius="999px",
                                ),
                                rx.text(
                                    night["stat_unfilled"].to_string(), " open",
                                    size="1", color="#6b7280",
                                ),
                                gap="3px", align="center",
                            ),
                            rx.fragment(),
                        ),
                        rx.cond(
                            night["stat_locked"] > 0,
                            rx.hstack(
                                rx.icon("lock", size=10, color="#b45309"),
                                rx.text(
                                    night["stat_locked"].to_string(),
                                    size="1", color="#92400e", weight="medium",
                                ),
                                gap="2px", align="center",
                            ),
                            rx.fragment(),
                        ),
                        rx.cond(
                            night["stat_called_off"] > 0,
                            rx.hstack(
                                rx.icon("octagon-x", size=10, color="#dc2626"),
                                rx.text(
                                    night["stat_called_off"].to_string(), " call-off",
                                    size="1", color="#991b1b", weight="medium",
                                ),
                                gap="2px", align="center",
                            ),
                            rx.fragment(),
                        ),
                        gap="10px", align="center", flex_wrap="wrap",
                    ),
                    width="100%", gap="6px",
                ),
                rx.fragment(),
            ),

            # Action buttons
            rx.hstack(
                rx.button(
                    rx.icon("pencil", size=13),
                    "Edit",
                    variant="soft",
                    size="2",
                    color_scheme="blue",
                    on_click=ZdsState.select_night(night["id"]),
                    cursor="pointer",
                ),
                rx.button(
                    rx.icon("printer", size=13),
                    "Print Day",
                    variant="outline",
                    size="2",
                    on_click=ZdsState.open_print_night(night["id"]),
                    cursor="pointer",
                ),
                rx.button(
                    rx.icon("cpu", size=13),
                    "Run Engine",
                    variant="soft",
                    size="2",
                    color_scheme="amber",
                    on_click=ZdsState.run_zone_engine_from_overview(night["id"]),
                    cursor="pointer",
                    title="Auto-fill unlocked slots for this night using the deployment algorithm",
                ),
                rx.button(
                    rx.icon("waves", size=13),
                    "Break Waves",
                    variant="soft",
                    size="2",
                    color_scheme="violet",
                    on_click=ZdsState.run_engine_night(night["id"]),
                    cursor="pointer",
                    title="Reset break wave assignments for this night",
                ),
                gap="8px", flex_wrap="wrap",
            ),

            gap="10px",
            align="start",
        ),

        padding="16px",
        background="white",
        border="1px solid #e5e7eb",
        border_left=f"4px solid {night['day_color']}",
        border_radius="10px",
        _hover={
            "border_color": "#d1d5db",
            "box_shadow": "0 2px 6px rgba(0,0,0,0.06)",
        },
        transition="all 0.15s",
        class_name="week-night-card",
    )


# ── Full page ─────────────────────────────────────────────────────────────────

def week_overview() -> rx.Component:
    from shared.components.app_switcher import app_switcher
    return rx.box(
        # ── Sticky top bar ────────────────────────────────────────────────────
        rx.hstack(
            app_switcher(),
            rx.link(
                rx.icon("arrow-left", size=16),
                href="/zds/",
                color="#6b7280",
                _hover={"color": "#111827"},
            ),
            rx.vstack(
                rx.heading("Zone Deployment", size="5"),
                rx.text(
                    "GLCR · Grave  ·  11PM – 7AM",
                    size="1", color="#9ca3af", letter_spacing="0.06em",
                ),
                gap="0",
            ),
            rx.spacer(),
            # Phase N.2 — link to the dedicated Week Schedule editor
            rx.link(
                rx.button(
                    rx.icon("calendar-days", size=14),
                    "View Schedule",
                    variant="soft",
                    size="2",
                    cursor="pointer",
                ),
                href=ZdsState.current_week_schedule_url,
            ),
            # Print Week — generates HTML and opens in new tab
            rx.button(
                rx.icon("printer", size=14),
                "Print Week",
                variant="soft",
                size="2",
                on_click=ZdsState.open_print_current_week,
                cursor="pointer",
            ),
            # Run Deployment Engine for all nights
            rx.button(
                rx.icon("cpu", size=14),
                "Run Engine (Week)",
                variant="soft",
                size="2",
                color_scheme="amber",
                on_click=ZdsState.run_zone_engine_week,
                cursor="pointer",
                title="Auto-fill unlocked slots for all 7 nights using the deployment algorithm",
            ),
            # Set Break Waves for all nights in the week
            rx.button(
                rx.icon("waves", size=14),
                "Break Waves (Week)",
                variant="soft",
                size="2",
                color_scheme="violet",
                on_click=ZdsState.run_engine_week,
                cursor="pointer",
                title="Rebuild break wave assignments for every night this week",
            ),

            align="center",
            gap="12px",
            padding="16px 24px",
            border_bottom="1px solid #e5e7eb",
            background="white",
            position="sticky",
            top="0",
            z_index="10",
            width="100%",
            class_name="chip-header",
        ),

        # ── Week label ────────────────────────────────────────────────────────
        rx.box(
            rx.hstack(
                rx.icon("calendar-days", size=15, color="#6b7280"),
                rx.text(
                    ZdsState.week_label,
                    size="3", weight="medium", color="#374151",
                ),
                align="center", gap="6px",
            ),
            padding="20px 24px 4px",
        ),

        # ── Night cards grid ──────────────────────────────────────────────────
        rx.box(
            rx.foreach(ZdsState.nights, _night_card),
            display="grid",
            grid_template_columns="repeat(auto-fill, minmax(340px, 1fr))",
            gap="12px",
            padding="16px 24px 40px",
        ),

        # ── Loading overlay ───────────────────────────────────────────────────
        rx.cond(
            ZdsState.loading,
            rx.box(
                rx.spinner(size="3"),
                position="fixed",
                inset="0",
                display="flex",
                align_items="center",
                justify_content="center",
                background="rgba(255,255,255,0.7)",
                z_index="20",
            ),
            rx.fragment(),
        ),

        # Engine result dialog — Phase K.1
        _engine_dialog(),

        background="#f9fafb",
        min_height="100vh",
        on_mount=ZdsState.on_week_overview_load,
        class_name="zds-index-page",
    )


def _engine_dialog():
    from ..components.engine_result_dialog import engine_result_dialog
    return engine_result_dialog()
