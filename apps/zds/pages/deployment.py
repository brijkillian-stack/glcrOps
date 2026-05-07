"""
Zone Deployment Sheet page — /week/[week_id]
Shows the 5×2 zones grid, 5-card RR row, aux strip, and a flip-side break sheet.
"""

import reflex as rx
from ..state import ZdsState
from ..components import zone_card, rr_card, aux_card, tm_picker_drawer, night_tab_bar, save_banner
from ..components.engine_result_dialog import engine_result_dialog
from shared.components.section_head import section_head


# ── Phase R — Skeleton scaffold ───────────────────────────────────────────────
# Pulse-animated placeholder cards that mimic the real grid layout so the page
# doesn't jump when data arrives. Used while ZdsState.loading is True.

def _skel_block(*, width="100%", height="14px", radius="6px",
                opacity=1.0) -> rx.Component:
    return rx.box(
        background="#e5e7eb",
        height=height,
        border_radius=radius,
        width=width,
        opacity=str(opacity),
    )


def _skel_zone_card() -> rx.Component:
    return rx.box(
        _skel_block(width="40%", height="10px"),
        rx.box(height="6px"),
        _skel_block(width="70%", height="22px"),
        rx.box(height="14px"),
        _skel_block(width="55%", height="10px", opacity=0.7),
        background="white",
        border="1px solid #e5e7eb",
        border_radius="8px",
        padding="14px",
        display="flex",
        flex_direction="column",
        height="120px",
    )


def _skel_rr_card() -> rx.Component:
    return rx.box(
        _skel_block(width="35%", height="10px"),
        rx.box(height="6px"),
        rx.hstack(
            rx.vstack(
                _skel_block(width="40%", height="9px"),
                _skel_block(width="80%", height="18px"),
                gap="4px", align="start", flex="1",
            ),
            rx.divider(orientation="vertical"),
            rx.vstack(
                _skel_block(width="50%", height="9px"),
                _skel_block(width="80%", height="18px"),
                gap="4px", align="start", flex="1",
            ),
            gap="8px", width="100%",
        ),
        background="white",
        border="1px solid #e5e7eb",
        border_radius="8px",
        padding="14px",
        height="92px",
    )


def _skel_aux_card() -> rx.Component:
    return rx.box(
        _skel_block(width="50%", height="9px"),
        rx.box(height="4px"),
        _skel_block(width="80%", height="14px"),
        background="white",
        border="1px solid #e5e7eb",
        border_radius="6px",
        padding="10px",
        height="60px",
    )


def _deployment_skeleton() -> rx.Component:
    """Skeleton view of the deployment grid — matches real layout
    (10 zones in 2 rows of 5, 5 RR cards, 7 aux strip)."""
    return rx.box(
        # Make the skeleton sit BELOW the sticky top bars (top ~140px)
        rx.box(height="140px"),
        rx.vstack(
            # Section: ZONES (2 rows of 5)
            _skel_block(width="120px", height="11px", opacity=0.8),
            rx.grid(
                *[_skel_zone_card() for _ in range(10)],
                columns="5", gap="10px", width="100%",
            ),
            # Section: RESTROOMS (5)
            rx.box(height="6px"),
            _skel_block(width="100px", height="11px", opacity=0.8),
            rx.grid(
                *[_skel_rr_card() for _ in range(5)],
                columns="5", gap="10px", width="100%",
            ),
            # Section: AUX (7)
            rx.box(height="6px"),
            _skel_block(width="80px", height="11px", opacity=0.8),
            rx.grid(
                *[_skel_aux_card() for _ in range(7)],
                columns="7", gap="8px", width="100%",
            ),
            gap="10px",
            padding="16px 24px 32px",
            width="100%",
        ),
        # Use the existing .skeleton CSS class (defined in styles.css) for
        # the pulse animation if present. Static otherwise — still a calm
        # placeholder.
        class_name="zds-skeleton-overlay zds-index-page",
        position="absolute",
        inset="0",
        z_index="3",
        background="#f9fafb",
        overflow="hidden",
    )


# ── Phase E — Notice type colors ──────────────────────────────────────────────

_NOTICE_TYPE_OPTS = [
    ("alert",    "⚠ Alert",    "#fbbf24", "rgba(251,191,36,0.12)"),
    ("info",     "ℹ Info",     "#30b2ff", "rgba(48,178,255,0.12)"),
    ("training", "🎓 Training", "#34d399", "rgba(52,211,153,0.12)"),
    ("meeting",  "📅 Meeting",  "#a78bfa", "rgba(167,139,250,0.12)"),
]


def _notice_form_dialog() -> rx.Component:
    """Add-notice dialog opened from the context menu 'Add notice' item.

    Type picker: four color-coded buttons.
    Text input: one-line description.
    Submit → ZdsState.submit_notice(); Cancel → ZdsState.close_notice_form().
    """
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Add Notice"),
            rx.dialog.description(
                "Choose a type and enter a short description.",
                size="2", color="#6b7280",
            ),
            rx.vstack(
                # ── Type selector ────────────────────────────────────────────
                rx.text("Type", size="1", weight="bold", color="#6b7280",
                        text_transform="uppercase", letter_spacing="0.06em"),
                rx.hstack(
                    *[
                        rx.button(
                            label,
                            variant=rx.cond(
                                ZdsState.notice_form_type == t,
                                "solid", "outline",
                            ),
                            size="1",
                            on_click=ZdsState.set_notice_type(t),
                            cursor="pointer",
                            style={
                                "borderColor": color,
                                "color": rx.cond(
                                    ZdsState.notice_form_type == t, "white", color
                                ),
                                "background": rx.cond(
                                    ZdsState.notice_form_type == t, color, "transparent"
                                ),
                            },
                        )
                        for t, label, color, _ in _NOTICE_TYPE_OPTS
                    ],
                    gap="6px", flex_wrap="wrap",
                ),
                # ── Text input ───────────────────────────────────────────────
                rx.text("Description", size="1", weight="bold", color="#6b7280",
                        text_transform="uppercase", letter_spacing="0.06em",
                        margin_top="8px"),
                rx.input(
                    placeholder="e.g. TM currently in training for Z9",
                    value=ZdsState.notice_form_text,
                    on_change=ZdsState.set_notice_text,
                    size="2",
                    width="100%",
                    auto_focus=True,
                    on_key_down=rx.cond(
                        rx.Var.create("event.key") == "Enter",
                        ZdsState.submit_notice,
                        rx.noop(),
                    ),
                ),
                # ── Buttons ──────────────────────────────────────────────────
                rx.hstack(
                    rx.button(
                        "Cancel",
                        variant="soft", color_scheme="gray",
                        size="2", cursor="pointer",
                        on_click=ZdsState.close_notice_form,
                    ),
                    rx.button(
                        rx.icon("plus", size=14),
                        "Add Notice",
                        size="2", cursor="pointer",
                        on_click=ZdsState.submit_notice,
                    ),
                    gap="10px", justify="end", width="100%", margin_top="4px",
                ),
                gap="6px", width="100%",
            ),
        ),
        open=ZdsState.notice_form_open,
    )


# ── Phase D — Night lock unlock-confirm dialog ────────────────────────────────

def _night_unlock_dialog() -> rx.Component:
    """Confirm dialog shown before clearing a night-level lock.

    Shown when ZdsState.night_lock_confirm_open is True.
    Uses rx.alert_dialog so it traps focus and is keyboard-dismissible.
    """
    return rx.alert_dialog.root(
        rx.alert_dialog.content(
            rx.alert_dialog.title("Unlock this night?"),
            rx.alert_dialog.description(
                "All editors will be able to edit slot assignments again. "
                "Are you sure you want to unlock?",
                size="2",
                color="#6b7280",
            ),
            rx.hstack(
                rx.alert_dialog.cancel(
                    rx.button(
                        "Keep locked",
                        variant="soft",
                        color_scheme="gray",
                        on_click=ZdsState.cancel_night_unlock,
                        cursor="pointer",
                    ),
                ),
                rx.alert_dialog.action(
                    rx.button(
                        rx.icon("lock-open", size=14),
                        "Unlock Night",
                        color_scheme="amber",
                        on_click=ZdsState.confirm_night_unlock,
                        cursor="pointer",
                    ),
                ),
                gap="12px", justify="end", width="100%", margin_top="16px",
            ),
        ),
        open=ZdsState.night_lock_confirm_open,
    )


# ── Section header ────────────────────────────────────────────────────────────

def _section_header(icon: str, label: str, staffed: str = "") -> rx.Component:
    """Section header — in ZDS dark mode renders as eyebrow + gold rule.
    In light mode falls back to a simple colored hstack (same as before)."""
    return section_head(label)


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
                            font_weight="bold",
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
        # Name chips — Phase J: clickable, strikethrough when called off
        rx.cond(
            names.length() == 0,
            rx.text("None scheduled", size="1", color="#d1d5db",
                    font_style="italic", padding="4px 0"),
            rx.flex(
                rx.foreach(
                    names,
                    lambda name: rx.box(
                        rx.cond(
                            ZdsState.night_called_off.contains(name),
                            # CALLED-OFF state: red border, strikethrough, "×" icon
                            rx.hstack(
                                rx.icon("octagon-x", size=11, color="#dc2626"),
                                rx.text(
                                    name,
                                    size="2", weight="medium", color="#9ca3af",
                                    text_decoration="line-through",
                                ),
                                gap="4px", align="center",
                            ),
                            # SCHEDULED (and present) state: colored chip
                            rx.text(name, size="2", weight="medium", color=color),
                        ),
                        background=rx.cond(
                            ZdsState.night_called_off.contains(name),
                            "#fef2f2",   # very light red
                            bg,
                        ),
                        border="1px solid",
                        border_color=rx.cond(
                            ZdsState.night_called_off.contains(name),
                            "#fecaca",
                            color,
                        ),
                        border_radius="full",
                        padding="3px 10px",
                        cursor="pointer",
                        on_click=ZdsState.toggle_call_off_by_name(name),
                        title="Click to toggle call-off status",
                        _hover={"opacity": "0.8"},
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
                href="/zds",
            ),
            align="center", gap="12px", padding="40px 0",
        ),
    )


# ── Full page ─────────────────────────────────────────────────────────────────

def deployment() -> rx.Component:
    night = ZdsState.current_night

    return rx.box(
        # Top nav
        rx.hstack(
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
            # Bulk operations menu — Phase K.3
            rx.menu.root(
                rx.menu.trigger(
                    rx.button(
                        rx.icon("ellipsis-vertical", size=14),
                        "Bulk",
                        variant="outline",
                        size="2",
                        cursor="pointer",
                    ),
                ),
                rx.menu.content(
                    rx.menu.item(
                        rx.hstack(
                            rx.icon("brush-cleaning", size=13, color="#9ca3af"),
                            rx.text("Clear all unlocked"),
                            gap="8px", align="center",
                        ),
                        on_click=ZdsState.bulk_clear_unlocked,
                    ),
                    rx.menu.item(
                        rx.hstack(
                            rx.icon("lock", size=13, color="#a16207"),
                            rx.text("Lock all filled"),
                            gap="8px", align="center",
                        ),
                        on_click=ZdsState.bulk_lock_filled,
                    ),
                    rx.menu.separator(),
                    rx.menu.item(
                        rx.hstack(
                            rx.icon("copy", size=13, color="#0ea5e9"),
                            rx.text("Copy from previous night"),
                            gap="8px", align="center",
                        ),
                        on_click=ZdsState.bulk_copy_from_previous_night,
                    ),
                ),
            ),
            # Run Deployment Engine — auto-fill unlocked zone/RR/aux slots from schedule
            # Phase 4e UX: spinner + disabled state when engine is running.
            rx.button(
                rx.cond(
                    ZdsState.loading,
                    rx.el.span(class_name="ops-spinner"),
                    rx.icon("cpu", size=14),
                ),
                rx.cond(ZdsState.loading, "Running…", "Run Engine"),
                variant="soft",
                size="2",
                color_scheme="amber",
                on_click=ZdsState.run_zone_engine_current_night,
                cursor=rx.cond(ZdsState.loading, "wait", "pointer"),
                disabled=ZdsState.loading,
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
            # Phase O fix — flex_wrap allows the action bar to wrap on
            # narrower viewports instead of getting clipped by .chip-header's
            # overflow rule. row_gap covers the wrapped-row spacing.
            align="center", gap="12px",
            flex_wrap="wrap",
            row_gap="8px",
            padding="16px 24px",
            border_bottom="1px solid #e5e7eb",
            background="white",
            position="sticky", top="0", z_index="10",
            width="100%",
            min_width="0",
            class_name="chip-header",
        ),

        # Night tabs (clicking a tab navigates to that day's route)
        rx.box(
            night_tab_bar(),
            padding="0 24px",
            background="white",
            border_bottom="1px solid #f3f4f6",
            class_name="night-tabs-bar",
        ),

        # Night header — use subscript access, not .get(); no f-strings with Vars.
        # Drop inline color so .zds-day-heading CSS class controls per-theme:
        # light = ink, dark = white. Inline beats CSS even with !important.
        rx.hstack(
            rx.heading(night["day_name"], size="6", class_name="zds-day-heading"),
            rx.text(night["night_date"], size="2", class_name="zds-day-heading-date",
                    align_self="flex-end", padding_bottom="2px"),
            rx.spacer(),
            # Phase D — lock badge (visible when night is locked)
            rx.cond(
                ZdsState.current_night_is_locked,
                rx.hstack(
                    rx.icon("lock", size=13, color="#b45309"),
                    # Reflex 0.9: weight prop only accepts
                    # light|regular|medium|bold — numeric strings ("700")
                    # crash compile. Use weight="bold" + font_weight for
                    # finer-grained CSS weight if needed.
                    rx.text("LOCKED", size="1", weight="bold",
                            color="#b45309", letter_spacing="0.08em",
                            class_name="night-lock-badge"),
                    gap="4px", align="center",
                ),
                rx.fragment(),
            ),
            rx.hstack(
                rx.text(night["in_rotation"], " in rotation",
                        size="2", color="#6b7280"),
                rx.separator(orientation="vertical"),
                rx.text(
                    "Breaks ", night["breaks_5"], " / ",
                    night["breaks_9"], " / ", night["breaks_4"],
                    size="2", color="#6b7280",
                ),
                # Phase D — Lock Night / Unlock Night toggle button
                rx.separator(orientation="vertical"),
                rx.button(
                    rx.cond(
                        ZdsState.current_night_is_locked,
                        rx.icon("lock-open", size=13),
                        rx.icon("lock", size=13),
                    ),
                    rx.cond(
                        ZdsState.current_night_is_locked,
                        "Unlock Night",
                        "Lock Night",
                    ),
                    variant="ghost",
                    size="1",
                    color_scheme=rx.cond(
                        ZdsState.current_night_is_locked, "amber", "gray"
                    ),
                    on_click=ZdsState.toggle_night_lock,
                    cursor="pointer",
                    title="Lock this night to prevent all edits",
                ),
                gap="8px", align="center",
            ),
            align="center", padding="16px 24px 0",
        ),

        # Phase R — At-a-glance summary chip (sticky once you scroll past it).
        # Shows fill percent + counts of warning / locked / open. Live-updates
        # as you assign / lock / clear slots.
        rx.box(  # night-scoreboard — dark CSS adds gradient bg + radial ring decorations
            rx.hstack(
                # Fill bar
                rx.vstack(
                    rx.hstack(
                        rx.text(
                            ZdsState.night_filled_count.to_string(), " / ",
                            ZdsState.night_total_count.to_string(),
                            " filled",
                            size="2", weight="bold",
                            # Drop inline color; let .scoreboard-value class
                            # control it per theme (dark = #f0f4f8, light defaults
                            # via styles.css below). Same fix pattern as the
                            # filled-TM-name issue we just shipped.
                            font_variant_numeric="tabular-nums",
                            class_name="scoreboard-value",
                        ),
                        rx.text(
                            "(", ZdsState.night_fill_pct.to_string(), "%)",
                            size="1",
                            class_name="scoreboard-pct",
                        ),
                        gap="6px", align="baseline",
                    ),
                    rx.box(
                        rx.box(
                            background=rx.cond(
                                ZdsState.night_fill_pct >= 100, "#059669",
                                rx.cond(ZdsState.night_fill_pct >= 75, "#0065BF",
                                rx.cond(ZdsState.night_fill_pct >= 50, "#eab308",
                                        "#dc2626")),
                            ),
                            height="100%",
                            border_radius="999px",
                            width=ZdsState.night_fill_pct.to_string() + "%",
                            transition="width 0.4s ease, background 0.2s ease",
                        ),
                        background="#f3f4f6",
                        height="6px",
                        border_radius="999px",
                        width="220px",
                        class_name="night-tab-fill-track",
                    ),
                    gap="3px", align="start",
                ),
                rx.spacer(),
                # Pills row
                rx.hstack(
                    rx.cond(
                        ZdsState.night_warning_count > 0,
                        rx.hstack(
                            rx.icon("triangle-alert", size=12, color="#dc2626"),
                            rx.text(
                                ZdsState.night_warning_count.to_string(),
                                " warnings",
                                size="1", color="#991b1b", weight="bold",
                            ),
                            gap="3px", align="center",
                            padding="2px 8px",
                            background="#fee2e2",
                            border="1px solid #fca5a5",
                            border_radius="999px",
                        ),
                        rx.fragment(),
                    ),
                    rx.cond(
                        ZdsState.night_locked_count > 0,
                        rx.hstack(
                            rx.icon("lock", size=12, color="#b45309"),
                            rx.text(
                                ZdsState.night_locked_count.to_string(), " locked",
                                size="1", color="#92400e", weight="bold",
                            ),
                            gap="3px", align="center",
                            padding="2px 8px",
                            background="#fef3c7",
                            border="1px solid #fbbf24",
                            border_radius="999px",
                        ),
                        rx.fragment(),
                    ),
                    rx.cond(
                        (ZdsState.night_total_count - ZdsState.night_filled_count) > 0,
                        rx.hstack(
                            rx.icon("circle-dashed", size=12, color="#6b7280"),
                            rx.text(
                                (ZdsState.night_total_count - ZdsState.night_filled_count).to_string(),
                                " open",
                                size="1", color="#374151", weight="bold",
                            ),
                            gap="3px", align="center",
                            padding="2px 8px",
                            background="#f3f4f6",
                            border="1px solid #d1d5db",
                            border_radius="999px",
                        ),
                        rx.fragment(),
                    ),
                    gap="6px", align="center", flex_wrap="wrap",
                ),
                width="100%", align="center", gap="14px",
            ),
            padding="10px 24px",
            background="#f9fafb",
            border_bottom="1px solid #e5e7eb",
            position="sticky", top="76px", z_index="9",
            class_name="night-scoreboard",
        ),

        # Phase Q.5 — Scheduled-but-not-deployed banner
        # Shows TMs in tonight's schedule pools (any shift) who aren't yet
        # placed in any zone/RR/aux/overlap slot. Excludes call-offs.
        rx.cond(
            ZdsState.unplaced_scheduled_count > 0,
            rx.box(
                rx.hstack(
                    rx.icon("user-round-search", size=14, color="#0369a1"),
                    rx.text(
                        ZdsState.unplaced_scheduled_count.to_string(),
                        " scheduled, not yet placed:",
                        size="2", weight="bold", color="#0369a1",
                    ),
                    rx.foreach(
                        ZdsState.unplaced_scheduled_tms,
                        lambda name: rx.box(
                            rx.text(name, size="1", color="#0369a1",
                                    weight="medium"),
                            padding="2px 8px",
                            background="white",
                            border="1px solid #7dd3fc",
                            border_radius="999px",
                        ),
                    ),
                    align="center", gap="6px", flex_wrap="wrap",
                    width="100%",
                ),
                margin="10px 24px",
                padding="8px 12px",
                background="#eff6ff",
                border="1px solid #bfdbfe",
                border_radius="8px",
            ),
            rx.fragment(),
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
                # Phase D — night-locked class disables pointer-events on all cards
                class_name=rx.cond(
                    ZdsState.current_night_is_locked,
                    "night-locked",
                    "",
                ),
                width="100%",
            ),
            padding="16px 24px 32px",
        ),

        # Phase R — Skeleton loading overlay. Replaces the prior full-screen
        # spinner; renders a soft pulsing scaffold that matches the deployment
        # grid shape so the layout doesn't jump when the data arrives.
        rx.cond(
            ZdsState.loading,
            _deployment_skeleton(),
            rx.fragment(),
        ),

        # TM Picker drawer (always mounted, controlled by show_picker)
        tm_picker_drawer(),

        # Audit banner — sticky bottom-right, hidden until first change
        save_banner(),

        # Engine result dialog — Phase K.1, pops up after Run Engine
        engine_result_dialog(),

        # Phase D — unlock confirm dialog (mounted globally, shown when night_lock_confirm_open)
        _night_unlock_dialog(),

        # Phase E — add-notice dialog (mounted globally, opened from context menu)
        _notice_form_dialog(),

        background="#f9fafb",
        min_height="100vh",
        on_mount=ZdsState.on_day_load,
        class_name="zds-index-page",
    )
