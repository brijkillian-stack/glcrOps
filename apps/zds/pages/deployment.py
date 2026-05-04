"""
Zone Deployment Sheet page — /week/[week_id]
Shows the 5×2 zones grid, 5-card RR row, aux strip, and a flip-side break sheet.
"""

import reflex as rx
from ..state import ZdsState
from ..components import zone_card, rr_card, aux_card, tm_picker_drawer, night_tab_bar, save_banner


# ── Section header ────────────────────────────────────────────────────────────

def _section_header(icon: str, label: str, staffed: str = "") -> rx.Component:
    return rx.hstack(
        rx.icon(icon, size=13, color="#6b7280"),
        rx.text(label, size="1", weight="bold", color="#6b7280",
                letter_spacing="0.1em", text_transform="uppercase"),
        rx.spacer(),
        rx.cond(staffed != "", rx.text(staffed, size="1", color="#9ca3af"), rx.fragment()),
        width="100%", align="center", padding="4px 0 6px",
    )


# ── Deployment sheet (zones + RR + aux) ───────────────────────────────────────

def _zones_section() -> rx.Component:
    return rx.vstack(
        _section_header("map-pin", "Zones"),
        rx.grid(
            rx.foreach(ZdsState.zone_slots, zone_card),
            columns="5",
            gap="7px",
            width="100%",
        ),
        width="100%", gap="0",
    )


def _rr_section() -> rx.Component:
    return rx.vstack(
        _section_header("door-open", "Restrooms"),
        # RR cards are pre-grouped by slot_key (each has mens + womens data merged)
        rx.grid(
            rx.foreach(ZdsState.rr_slots, rr_card),
            columns="5",
            gap="7px",
            width="100%",
        ),
        width="100%", gap="0",
    )


def _aux_section() -> rx.Component:
    return rx.vstack(
        _section_header("star", "Auxiliary"),
        rx.grid(
            rx.foreach(ZdsState.aux_slots, aux_card),
            columns="7",
            gap="7px",
            width="100%",
        ),
        width="100%", gap="0",
    )


def deployment_body() -> rx.Component:
    return rx.vstack(
        _zones_section(),
        _rr_section(),
        _aux_section(),
        gap="20px",
        width="100%",
    )


# ── Break sheet (breaks + overlaps) ──────────────────────────────────────────

_WAVE_COLORS = {1: "#2563eb", 2: "#059669", 3: "#7c3aed"}


_LOCK_GOLD = "#b45309"


def _wave_buttons(row: dict) -> rx.Component:
    """Three compact wave-picker buttons [1][2][3] + a wave-lock toggle."""
    buttons = []
    for w in (1, 2, 3):
        active_bg = _WAVE_COLORS[w]
        buttons.append(
            rx.box(
                str(w),
                font_size="9px", font_weight="bold",
                width="15px", height="15px",
                display="flex", align_items="center", justify_content="center",
                border_radius="full",
                background=rx.cond(row["break_wave"] == w, active_bg, "#f3f4f6"),
                color=rx.cond(row["break_wave"] == w, "white", "#9ca3af"),
                cursor=rx.cond(row["is_wave_locked"], "not-allowed", "pointer"),
                opacity=rx.cond(row["is_wave_locked"], "0.4", "1"),
                _hover=rx.cond(row["is_wave_locked"], {}, {"opacity": "0.75"}),
                on_click=rx.cond(
                    row["is_wave_locked"],
                    rx.prevent_default,
                    ZdsState.update_break_wave(row["id"], w),
                ),
            )
        )
    lock_icon = rx.box(
        rx.icon(
            rx.cond(row["is_wave_locked"], "lock", "lock-open"),
            size=10,
            color=rx.cond(row["is_wave_locked"], _LOCK_GOLD, "#d1d5db"),
        ),
        cursor="pointer",
        on_click=ZdsState.toggle_wave_lock(row["id"]),
        _hover={"opacity": "0.7"},
        flex_shrink="0",
        title=rx.cond(row["is_wave_locked"], "Wave locked — click to unlock", "Click to lock wave"),
    )
    return rx.hstack(*buttons, lock_icon, gap="2px", flex_shrink="0", align="center")


def _break_col(wave: int, rows: list) -> rx.Component:
    color = _WAVE_COLORS.get(wave, "#6b7280")
    return rx.vstack(
        rx.text(
            f"Break {wave}",
            size="2", weight="bold", color=color,
            border_top=f"3px solid {color}",
            padding_top="10px",
        ),
        rx.vstack(
            rx.foreach(
                rows,
                lambda row: rx.vstack(
                    # Section divider — only shown for first row of each section
                    rx.cond(
                        row["show_section_header"],
                        rx.text(
                            row["section"],
                            size="1", color="#9ca3af",
                            letter_spacing="0.08em",
                            text_transform="uppercase",
                            font_weight="600",
                            padding_top="6px",
                            padding_bottom="2px",
                        ),
                        rx.fragment(),
                    ),
                    # Row: slot badge · TM name · wave buttons
                    rx.hstack(
                        rx.box(
                            row["slot_label"],
                            background=row["slot_color"],
                            color="white",
                            font_size="8px",
                            font_weight="bold",
                            padding="1px 5px",
                            border_radius="3px",
                            flex_shrink="0",
                            min_width="28px",
                            text_align="center",
                        ),
                        rx.text(
                            rx.cond(row["tm_name"] != "", row["tm_name"], "—"),
                            size="2", weight="medium", flex="1",
                            color=rx.cond(row["tm_name"] != "", "#111827", "#d1d5db"),
                            font_style=rx.cond(row["tm_name"] != "", "normal", "italic"),
                        ),
                        _wave_buttons(row),
                        width="100%", align="center", gap="5px",
                        padding="3px 0",
                        border_bottom="1px solid #f3f4f6",
                    ),
                    gap="0", width="100%",
                ),
            ),
            gap="0", width="100%",
        ),
        flex="1", gap="6px",
    )


def _overlap_row_comp(rows: list, label: str, time_range: str) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.vstack(
                rx.text(time_range, size="3", weight="bold"),
                rx.text(label, size="1", color="#6b7280",
                        letter_spacing="0.08em", text_transform="uppercase"),
                gap="0",
            ),
            rx.grid(
                rx.foreach(
                    rows,
                    lambda row: rx.box(
                        rx.text(
                            rx.cond(row["tm_name"] != "", row["tm_name"], "Unfilled"),
                            weight=rx.cond(row["is_filled"], "bold", "normal"),
                            color=rx.cond(row["is_filled"], "#111827", "#d1d5db"),
                            font_style=rx.cond(row["is_filled"], "normal", "italic"),
                            size="2",
                        ),
                        rx.text(
                            rx.cond(row["task"] != "", row["task"], "—"),
                            size="1", color="#6b7280",
                        ),
                        padding="6px 8px",
                        border="1px solid #e5e7eb",
                        border_radius="6px",
                        min_width="120px",
                    ),
                ),
                columns="6", gap="6px", flex="1",
            ),
            gap="16px", width="100%", align="start",
        ),
        width="100%",
    )


def break_sheet_body() -> rx.Component:
    return rx.vstack(
        # Break waves
        rx.hstack(
            _break_col(1, ZdsState.break_wave_1),
            rx.divider(orientation="vertical"),
            _break_col(2, ZdsState.break_wave_2),
            rx.divider(orientation="vertical"),
            _break_col(3, ZdsState.break_wave_3),
            gap="16px", width="100%", align="start",
        ),
        # Overlaps
        rx.box(
            rx.text("Overlaps", size="1", weight="bold", color="#6b7280",
                    letter_spacing="0.1em", text_transform="uppercase",
                    padding_bottom="8px"),
            _overlap_row_comp(ZdsState.pm_overlaps, "Late Evening", "11p – 1a"),
            _overlap_row_comp(ZdsState.am_overlaps, "Early AM",     "5a – 7a"),
            border_top="1px solid #e5e7eb",
            padding_top="12px",
            width="100%",
        ),
        gap="20px", width="100%",
    )


# ── Schedule tab ─────────────────────────────────────────────────────────────


_POOL_COLORS = {
    "grave": "#065f46",   # dark green
    "pm_ol": "#92400e",   # amber-dark
    "am_ol": "#1e3a8a",   # navy
    "off":   "#9ca3af",   # grey
}
_POOL_BG = {
    "grave": "#d1fae5",
    "pm_ol": "#fef3c7",
    "am_ol": "#dbeafe",
    "off":   "#f3f4f6",
}
_POOL_LABEL = {
    "grave": "GRAVE",
    "pm_ol": "PM OL",
    "am_ol": "AM OL",
    "off":   "OFF",
}


def _schedule_pool_section(
    names: list,
    pool_key: str,
    icon_name: str,
    heading: str,
    time_range: str,
) -> rx.Component:
    """One pool section (Grave / PM OL / AM OL) inside the Schedule tab."""
    color  = _POOL_COLORS[pool_key]
    bg     = _POOL_BG[pool_key]
    label  = _POOL_LABEL[pool_key]
    return rx.vstack(
        # Header row
        rx.hstack(
            rx.icon(icon_name, size=13, color=color),
            rx.text(heading, size="1", weight="bold",
                    color=color, text_transform="uppercase", letter_spacing="0.08em"),
            rx.spacer(),
            rx.text(time_range, size="1", color="#9ca3af"),
            width="100%", align="center", padding="4px 0 6px",
        ),
        # Name chips
        rx.cond(
            names.length() == 0,
            rx.text("None scheduled", size="1", color="#d1d5db",
                    font_style="italic", padding="4px 0"),
            rx.flex(
                rx.foreach(
                    names,
                    lambda name: rx.box(
                        rx.text(name, size="2", weight="medium", color=color),
                        background=bg,
                        border="1px solid",
                        border_color=color,
                        border_radius="full",
                        padding="3px 10px",
                    ),
                ),
                wrap="wrap",
                gap="6px",
            ),
        ),
        width="100%", gap="4px",
    )


def schedule_body() -> rx.Component:
    return rx.cond(
        ZdsState.schedule_loaded,
        # Schedule loaded — show the three pools
        rx.vstack(
            # File name banner
            rx.hstack(
                rx.icon("file-spreadsheet", size=13, color="#6b7280"),
                rx.text(ZdsState.schedule_file_label, size="1", color="#6b7280"),
                gap="5px", align="center",
                padding="2px 0 10px",
            ),
            _schedule_pool_section(
                ZdsState.night_grave_pool,
                "grave",
                "moon",
                "Grave Shift",
                "11PM – 7AM",
            ),
            rx.separator(),
            _schedule_pool_section(
                ZdsState.night_pm_ol_pool,
                "pm_ol",
                "sunset",
                "PM Overlap",
                "11PM – 1AM",
            ),
            rx.separator(),
            _schedule_pool_section(
                ZdsState.night_am_ol_pool,
                "am_ol",
                "sunrise",
                "AM Overlap",
                "5AM – 7AM",
            ),
            gap="14px", width="100%",
        ),
        # No schedule loaded
        rx.vstack(
            rx.icon("calendar-off", size=40, color="#d1d5db"),
            rx.text("No schedule loaded", size="3", weight="medium", color="#6b7280"),
            rx.text(
                "Upload a weekly schedule Excel on the home page to see who is scheduled for each night.",
                size="2", color="#9ca3af", text_align="center", max_width="360px",
            ),
            rx.link(
                rx.button(
                    rx.icon("home", size=13), "Go to Home",
                    variant="soft", size="2",
                ),
                href="/",
            ),
            align="center", gap="12px", padding="40px 0",
        ),
    )


# ── Full page ─────────────────────────────────────────────────────────────────

def deployment() -> rx.Component:
    from shared.components.app_switcher import app_switcher
    night = ZdsState.current_night

    return rx.box(
        # Top nav
        rx.hstack(
            app_switcher(),
            rx.link(
                rx.icon("arrow-left", size=16),
                href=ZdsState.week_overview_url,
                color="#6b7280",
                _hover={"color": "#111827"},
            ),
            rx.vstack(
                rx.heading("Zone Deployment", size="5"),
                rx.text("GLCR · Grave  ·  11PM – 7AM",
                        size="1", color="#9ca3af", letter_spacing="0.06em"),
                gap="0",
            ),
            rx.spacer(),
            # Print Day — generates HTML and opens in new tab
            rx.button(
                rx.icon("printer", size=14),
                "Print Day",
                variant="outline",
                size="2",
                on_click=ZdsState.open_print_current_night,
                cursor="pointer",
            ),
            # Run Deployment Engine — auto-fill unlocked zone/RR/aux slots from schedule
            rx.button(
                rx.icon("cpu", size=14),
                "Run Engine",
                variant="soft",
                size="2",
                color_scheme="amber",
                on_click=ZdsState.run_zone_engine_current_night,
                cursor="pointer",
                title="Auto-fill unlocked slots using the deployment algorithm (respects locks)",
            ),
            # Set Break Waves — rebuild wave assignments from BG_* defaults
            rx.button(
                rx.icon("waves", size=14),
                "Set Break Waves",
                variant="soft",
                size="2",
                color_scheme="violet",
                on_click=ZdsState.run_engine_current_night,
                cursor="pointer",
                title="Reset break wave assignments from defaults (respects locked waves)",
            ),
            # Deployment / Break Sheet / Schedule toggle
            rx.segmented_control.root(
                rx.segmented_control.item("Deployment", value="deployment"),
                rx.segmented_control.item("Break Sheet", value="break"),
                rx.segmented_control.item("Schedule", value="schedule"),
                value=ZdsState.active_tab,
                on_change=ZdsState.set_active_tab,
            ),
            align="center", gap="12px",
            padding="16px 24px",
            border_bottom="1px solid #e5e7eb",
            background="white",
            position="sticky", top="0", z_index="10",
            width="100%",
        ),

        # Night tabs (clicking a tab navigates to that day's route)
        rx.box(
            night_tab_bar(),
            padding="0 24px",
            background="white",
            border_bottom="1px solid #f3f4f6",
        ),

        # Night header — use subscript access, not .get(); no f-strings with Vars
        rx.hstack(
            rx.heading(night["day_name"], size="6", color="#1d4ed8"),
            rx.text(night["night_date"], size="2", color="#9ca3af",
                    align_self="flex-end", padding_bottom="2px"),
            rx.spacer(),
            rx.hstack(
                rx.text(night["in_rotation"], " in rotation",
                        size="2", color="#6b7280"),
                rx.separator(orientation="vertical"),
                rx.text(
                    "Breaks ", night["breaks_5"], " / ",
                    night["breaks_9"], " / ", night["breaks_4"],
                    size="2", color="#6b7280",
                ),
                gap="8px", align="center",
            ),
            align="center", padding="16px 24px 0",
        ),

        # Error banner (print errors, etc.)
        rx.cond(
            ZdsState.error != "",
            rx.box(
                rx.hstack(
                    rx.icon("triangle-alert", size=14, color="#b91c1c"),
                    rx.text(ZdsState.error, size="2", color="#b91c1c", flex="1"),
                    rx.icon_button(
                        rx.icon("x", size=12),
                        size="1", variant="ghost",
                        on_click=ZdsState.set_error(""),
                    ),
                    align="center", gap="8px",
                ),
                background="#fef2f2",
                border="1px solid #fecaca",
                border_radius="8px",
                padding="10px 16px",
                margin="8px 24px 0",
            ),
            rx.fragment(),
        ),

        # Main content — toggled between deployment / break sheet / schedule
        rx.box(
            rx.cond(
                ZdsState.active_tab == "schedule",
                schedule_body(),
                rx.cond(
                    ZdsState.show_break_sheet,
                    break_sheet_body(),
                    deployment_body(),
                ),
            ),
            padding="16px 24px 32px",
        ),

        # Loading spinner overlay
        rx.cond(
            ZdsState.loading,
            rx.box(
                rx.spinner(size="3"),
                position="fixed", inset="0",
                display="flex", align_items="center", justify_content="center",
                background="rgba(255,255,255,0.7)",
                z_index="20",
            ),
            rx.fragment(),
        ),

        # TM Picker drawer (always mounted, controlled by show_picker)
        tm_picker_drawer(),

        # Audit banner — sticky bottom-right, hidden until first change
        save_banner(),

        background="#f9fafb",
        min_height="100vh",
        on_mount=ZdsState.on_day_load,
    )
