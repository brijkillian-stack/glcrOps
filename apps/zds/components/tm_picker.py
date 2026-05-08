"""TM picker drawer — slides in when a zone/RR/aux card is clicked.

Layout (v2 — two-column):
  ┌──────────────────────────────────────────────────────────────────┐
  │  Header: "Assign TM" + slot label                         [X]   │
  ├──────────────────────────────────┬───────────────────────────────┤
  │  Left pane (TM list)             │  Right pane (canonical tasks) │
  │  • Search input                  │  "What this slot does:"       │
  │  • Legend chips                  │  • task 1                     │
  │  • Scrollable TM roster          │  • task 2                     │
  │                                  │  (empty state for zone slots) │
  ├──────────────────────────────────┴───────────────────────────────┤
  │  Footer: [Clear slot]                                            │
  └──────────────────────────────────────────────────────────────────┘

The right-pane task list is read-only (v1). Editing tasks inline is v2.
"""

import reflex as rx
from ..state import ZdsState
from .glcr_icons import glcr_icon

_LOCK_GOLD = "#b45309"


def _preference_star(tm: dict) -> rx.Component:
    """Gold star when the TM's preferences include the currently-open slot."""
    return rx.cond(
        ZdsState.picker_slot_key != "",
        rx.cond(
            # preferences is a list[str] — check if picker_slot_key is in it
            # Reflex list Vars support .contains()
            tm["preferences"].contains(ZdsState.picker_slot_key),
            rx.icon("star", size=12, color="#d97706",
                    fill="#d97706", flex_shrink="0",
                    title="Preferred zone"),
            rx.fragment(),
        ),
        rx.fragment(),
    )


def _pool_badge(tm: dict) -> rx.Component:
    """Coloured schedule-pool badge: GRAVE / PM OL / AM OL (hidden when off-schedule)."""
    return rx.cond(
        tm["on_schedule"],
        rx.box(
            rx.cond(
                tm["schedule_pool"] == "grave",
                rx.text("GRAVE", size="1", weight="bold",
                        color="#065f46", letter_spacing="0.05em"),
                rx.cond(
                    tm["schedule_pool"] == "pm_ol",
                    rx.text("PM OL", size="1", weight="bold",
                            color="#92400e", letter_spacing="0.05em"),
                    rx.text("AM OL", size="1", weight="bold",
                            color="#1e3a8a", letter_spacing="0.05em"),
                ),
            ),
            padding="1px 5px",
            border_radius="3px",
            background=rx.cond(
                tm["schedule_pool"] == "grave", "#d1fae5",
                rx.cond(tm["schedule_pool"] == "pm_ol", "#fef3c7", "#dbeafe"),
            ),
            flex_shrink="0",
        ),
        rx.fragment(),
    )


def _tm_row(tm: dict) -> rx.Component:
    """Single TM row inside the picker."""
    return rx.hstack(
        # Preference star (gold, left-most)
        _preference_star(tm),
        # Name + pool
        rx.vstack(
            rx.hstack(
                rx.text(
                    tm["display_name"],
                    font_weight="600", size="3",
                    text_decoration=rx.cond(tm["is_called_off"], "line-through", "none"),
                    color=rx.cond(tm["is_called_off"], "#9ca3af", "inherit"),
                ),
                # Schedule pool badge (GRAVE / PM OL / AM OL)
                _pool_badge(tm),
                # CALLED OFF badge — Phase J
                rx.cond(
                    tm["is_called_off"],
                    rx.badge(
                        "CALLED OFF",
                        color_scheme="red",
                        variant="solid",
                        font_size="9px",
                        padding="1px 5px",
                    ),
                    rx.fragment(),
                ),
                # "Already assigned" badge
                rx.cond(
                    tm["is_assigned"],
                    rx.badge(
                        tm["assigned_to"],
                        color_scheme="amber",
                        variant="soft",
                        font_size="9px",
                        padding="1px 5px",
                    ),
                    rx.fragment(),
                ),
                align="center", gap="6px", flex_wrap="wrap",
            ),
            rx.text(tm["grave_pool"], size="1", color="#6b7280"),
            # Phase K.2 — recent placement history (last 3 nights)
            rx.cond(
                tm["history_summary"] != "",
                rx.hstack(
                    rx.icon("history", size=10, color="#9ca3af"),
                    rx.text(
                        tm["history_summary"],
                        size="1", color="#9ca3af",
                        font_variant_numeric="tabular-nums",
                    ),
                    gap="3px", align="center",
                ),
                rx.fragment(),
            ),
            align="start", gap="0", flex="1",
        ),
        rx.spacer(),
        # Skill score badge
        rx.box(
            rx.text(tm["skill_str"], size="1", weight="bold", color="white"),
            background=tm["skill_color"],
            padding="1px 6px", border_radius="full",
            flex_shrink="0",
        ),
        # Action button:
        #   - Already assigned to another slot → Swap (Phase I) — moves both ways
        #   - Not yet placed                   → Assign — single write
        # The Swap button is violet to distinguish from blue Assign, and shows
        # the source slot label so Brian knows what's flipping out.
        rx.cond(
            tm["is_assigned"],
            rx.button(
                rx.icon("arrow-left-right", size=12),
                "Swap with ", tm["assigned_to"],
                size="1",
                color_scheme="violet",
                variant="soft",
                on_click=ZdsState.swap_tms(tm["id"]),
                title="Move this TM here, move whoever is here into their old slot",
            ),
            rx.button(
                "Assign",
                size="1",
                color_scheme="blue",
                variant="soft",
                on_click=ZdsState.assign_tm(tm["id"]),
            ),
        ),
        align="center", width="100%",
        padding="8px 12px",
        border_radius="6px",
        background=rx.cond(tm["is_assigned"], "#fffbeb", "transparent"),
        _hover={"background": rx.cond(tm["is_assigned"], "#fef3c7", "#f0f9ff")},
        cursor="pointer",
    )


# ── Left pane — TM list ───────────────────────────────────────────────────────

def _left_pool_pane() -> rx.Component:
    """Search input + legend + scrollable TM roster."""
    return rx.vstack(
        # Search
        rx.box(
            rx.input(
                placeholder="Search by name…",
                value=ZdsState.tm_search,
                on_change=ZdsState.set_tm_search,
                width="100%",
                auto_focus=True,
            ),
            padding="12px 16px 6px",
            width="100%",
        ),
        # Legend
        rx.hstack(
            rx.icon("star", size=10, color="#d97706", fill="#d97706"),
            rx.text("Preferred", size="1", color="#9ca3af"),
            rx.separator(orientation="vertical", height="10px"),
            rx.box(width="8px", height="8px", background="#fffbeb",
                   border="1px solid #fbbf24", border_radius="2px"),
            rx.text("Placed", size="1", color="#9ca3af"),
            rx.separator(orientation="vertical", height="10px"),
            rx.box(width="22px", height="12px", background="#d1fae5",
                   border_radius="2px"),
            rx.text("Scheduled", size="1", color="#9ca3af"),
            padding="0 16px 8px",
            gap="4px", align="center",
            flex_wrap="wrap",
        ),
        # TM list
        rx.scroll_area(
            rx.vstack(
                rx.foreach(ZdsState.filtered_tms, _tm_row),
                gap="0", width="100%",
            ),
            flex="1",
            overflow_y="auto",
            width="100%",
        ),
        flex="1",
        min_width="0",
        overflow="hidden",
        gap="0",
        align="start",
        width="100%",
    )


# ── Right pane — canonical tasks ──────────────────────────────────────────────

def _right_tasks_pane() -> rx.Component:
    """Read-only canonical task list for the slot being assigned.

    Source: overlap_tasks table (same data the engine uses). Zone / RR / aux
    slots won't have rows and will show the empty-state message.
    """
    return rx.vstack(
        rx.text(
            "What this slot does:",
            weight="bold", size="2", color="#374151",
        ),
        rx.cond(
            ZdsState.picker_tasks.length() > 0,
            rx.vstack(
                rx.foreach(
                    ZdsState.picker_tasks,
                    lambda task: rx.hstack(
                        rx.text("·", size="2", color="#9ca3af", flex_shrink="0",
                                margin_top="1px"),
                        rx.text(task, size="2", color="#374151", line_height="1.45",
                                flex="1"),
                        align="start", gap="8px", width="100%",
                    ),
                ),
                gap="8px", width="100%",
            ),
            rx.text(
                "No canonical tasks for this slot — add tasks after placement.",
                size="1", color="#9ca3af", font_style="italic", line_height="1.5",
            ),
        ),
        padding="16px",
        width="220px",
        flex_shrink="0",
        border_left="1px solid #e5e7eb",
        background="#f9fafb",
        overflow_y="auto",
        align="start",
        gap="10px",
        height="100%",
    )


# ── Card options section ──────────────────────────────────────────────────────

def _card_options_section() -> rx.Component:
    """Annotation controls for the card that is currently open in the picker.

    Always visible when the picker is open (picker_card_code is set).
    Shows: card note, priority toggle, ad-hoc task list + add input, print card.
    """
    return rx.cond(
        ZdsState.picker_card_code != "",
        rx.vstack(
            # Section header
            rx.hstack(
                rx.html(glcr_icon("ui", "menu-hamburger", size=12)),
                rx.text("Card options", size="1", weight="bold",
                        text_transform="uppercase", letter_spacing="0.08em",
                        color="#6b7280"),
                class_name="drawer-section-header",
                gap="6px", align="center",
            ),
            # ── Card note ────────────────────────────────────────────────
            rx.vstack(
                rx.text("Card note", size="1", color="#374151", weight="medium"),
                rx.text_area(
                    value=rx.cond(
                        ZdsState.picker_note_text != "",
                        ZdsState.picker_note_text,
                        ZdsState.picker_card_saved_note_text,
                    ),
                    on_change=ZdsState.set_picker_note_text,
                    placeholder="Note about this card tonight…",
                    rows="2",
                    width="100%",
                    size="1",
                ),
                rx.hstack(
                    rx.button(
                        "Save note",
                        size="1", color_scheme="blue", variant="soft",
                        on_click=ZdsState.save_card_note,
                    ),
                    rx.cond(
                        ZdsState.picker_card_has_note,
                        rx.button(
                            "Clear",
                            size="1", variant="ghost", color_scheme="red",
                            on_click=ZdsState.clear_card_note,
                        ),
                        rx.fragment(),
                    ),
                    gap="6px",
                ),
                gap="4px", width="100%",
            ),
            # ── Priority toggle ───────────────────────────────────────────
            rx.button(
                rx.icon(
                    rx.cond(ZdsState.picker_card_has_priority, "flag", "flag-off"),
                    size=13,
                ),
                rx.text(
                    rx.cond(ZdsState.picker_card_has_priority,
                            "Priority watch: ON", "Priority watch: OFF"),
                    size="1",
                ),
                size="1",
                variant=rx.cond(ZdsState.picker_card_has_priority, "soft", "ghost"),
                color_scheme=rx.cond(ZdsState.picker_card_has_priority, "amber", "gray"),
                on_click=ZdsState.toggle_card_priority,
                width="100%",
            ),
            # ── Ad-hoc tasks ──────────────────────────────────────────────
            rx.vstack(
                rx.text("Ad-hoc tasks", size="1", color="#374151", weight="medium"),
                rx.foreach(
                    ZdsState.picker_card_adhoc_tasks,
                    lambda t: rx.hstack(
                        rx.text("→ " + t["name"], size="1", flex="1"),
                        rx.text(
                            "×",
                            size="1", color="#c4c4c4",
                            cursor="pointer",
                            _hover={"color": "#ef4444"},
                            on_click=ZdsState.delete_card_adhoc_task(t["ref"]),
                        ),
                        width="100%", align="center", gap="4px",
                    ),
                ),
                rx.hstack(
                    rx.input(
                        value=rx.cond(
                            ZdsState.picker_card_adhoc_tasks.length() == 0,
                            ZdsState.picker_note_text,
                            ZdsState.picker_note_text,
                        ),
                        on_change=ZdsState.set_picker_note_text,
                        placeholder="Add a task…",
                        size="1",
                        flex="1",
                    ),
                    rx.icon_button(
                        rx.icon("plus", size=12),
                        size="1", variant="soft", color_scheme="blue",
                        on_click=ZdsState.add_card_adhoc_task,
                    ),
                    gap="4px", width="100%",
                ),
                gap="4px", width="100%",
            ),
            # ── Print card ────────────────────────────────────────────────
            rx.button(
                rx.icon("printer", size=13),
                rx.text("Print just this card", size="1"),
                size="1", variant="ghost", color_scheme="gray",
                width="100%",
                on_click=ZdsState.print_single_card,
            ),
            class_name="drawer-section",
            gap="8px", width="100%",
        ),
        rx.fragment(),
    )


# ── TM options section ────────────────────────────────────────────────────────

def _tm_options_section() -> rx.Component:
    """Pre-shift annotation controls for the TM currently assigned to the open slot.

    Only visible when the picker is open on a filled slot (picker_tm_id is set).
    Shows: pre-shift note, log observation to profile, view profile.
    """
    return rx.cond(
        ZdsState.picker_tm_id != "",
        rx.vstack(
            # Section header
            rx.hstack(
                rx.html(glcr_icon("people", "person-user", size=12)),
                rx.text(
                    "Pre-shift: " + ZdsState.picker_tm_name,
                    size="1", weight="bold",
                    text_transform="uppercase", letter_spacing="0.08em",
                    color="#6b7280",
                ),
                class_name="drawer-section-header",
                gap="6px", align="center",
            ),
            # ── Pre-shift note ────────────────────────────────────────────
            rx.vstack(
                rx.text_area(
                    value=rx.cond(
                        ZdsState.picker_note_text != "",
                        ZdsState.picker_note_text,
                        ZdsState.picker_tm_note_text,
                    ),
                    on_change=ZdsState.set_picker_note_text,
                    placeholder=rx.cond(
                        ZdsState.picker_tm_has_note,
                        "Update pre-shift note…",
                        "Add pre-shift note…",
                    ),
                    rows="2",
                    width="100%",
                    size="1",
                ),
                rx.hstack(
                    rx.button(
                        "Save note",
                        size="1", color_scheme="blue", variant="soft",
                        on_click=ZdsState.save_tm_preshift_note,
                    ),
                    rx.button(
                        "Log to profile",
                        size="1", variant="soft", color_scheme="violet",
                        on_click=ZdsState.log_tm_to_profile,
                    ),
                    rx.cond(
                        ZdsState.picker_tm_has_note,
                        rx.button(
                            "Clear",
                            size="1", variant="ghost", color_scheme="red",
                            on_click=ZdsState.clear_tm_note,
                        ),
                        rx.fragment(),
                    ),
                    gap="6px", flex_wrap="wrap",
                ),
                gap="4px", width="100%",
            ),
            # ── View profile ──────────────────────────────────────────────
            rx.button(
                rx.icon("user", size=13),
                rx.text("View " + ZdsState.picker_tm_name + "'s profile", size="1"),
                size="1", variant="ghost", color_scheme="gray",
                width="100%",
                on_click=ZdsState.navigate_to_tm_profile,
            ),
            class_name="drawer-section",
            gap="8px", width="100%",
        ),
        rx.fragment(),
    )


# ── Main drawer ───────────────────────────────────────────────────────────────

def tm_picker_drawer() -> rx.Component:
    return rx.drawer.root(
        rx.drawer.overlay(z_index="40"),
        rx.drawer.portal(
            rx.drawer.content(
                # ── Header ──────────────────────────────────────────────────
                rx.hstack(
                    rx.vstack(
                        rx.text("Assign TM", weight="bold", size="4"),
                        rx.text(ZdsState.picker_label, size="2", color="#6b7280"),
                        align="start", gap="0",
                    ),
                    rx.spacer(),
                    rx.icon_button(
                        rx.icon("x"),
                        variant="ghost",
                        on_click=ZdsState.close_picker,
                    ),
                    width="100%", align="center",
                    padding="16px 16px 12px",
                    border_bottom="1px solid #e5e7eb",
                    flex_shrink="0",
                ),
                # ── Body: left TM list + right panel ────────────────────
                rx.hstack(
                    _left_pool_pane(),
                    # Right panel: canonical tasks + annotation sections
                    rx.vstack(
                        _right_tasks_pane(),
                        rx.scroll_area(
                            rx.vstack(
                                _card_options_section(),
                                _tm_options_section(),
                                gap="0", width="100%",
                                padding="0 16px 16px",
                            ),
                            width="220px",
                            flex_shrink="0",
                            overflow_y="auto",
                        ),
                        flex_shrink="0",
                        width="220px",
                        gap="0",
                        align="start",
                        overflow="hidden",
                        border_left="1px solid #e5e7eb",
                    ),
                    flex="1",
                    overflow="hidden",
                    align="stretch",
                    gap="0",
                    width="100%",
                ),
                # ── Footer — clear slot ──────────────────────────────────
                rx.box(
                    rx.button(
                        rx.icon("user-x", size=14),
                        "Clear slot",
                        variant="ghost",
                        color_scheme="red",
                        size="2",
                        width="100%",
                        on_click=[
                            ZdsState.clear_slot(ZdsState.picker_slot_id),
                            ZdsState.close_picker(),
                        ],
                    ),
                    padding="12px 16px",
                    border_top="1px solid #e5e7eb",
                    flex_shrink="0",
                ),
                # Drawer styles
                top="0", right="0",
                height="100%",
                width="580px",       # wider than v1 (360px) to fit task panel
                background="white",
                display="flex",
                flex_direction="column",
                box_shadow="-4px 0 24px rgba(0,0,0,0.12)",
                z_index="50",
            ),
        ),
        direction="right",
        open=ZdsState.show_picker,
        on_open_change=ZdsState.close_picker,
    )
