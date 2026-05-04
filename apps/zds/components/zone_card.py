"""
Zone card, RR card, and Aux card components.
Each card's top area is clickable (opens TM picker); the task section below
has its own click handlers so it doesn't propagate to the picker.

IMPORTANT: Inside rx.foreach the item is a Reflex Var, NOT a plain Python dict.
- Never use Python `or`, `and`, `if/else`, or dict.get(Var_key) on Var objects.
- Always use rx.cond(condition, true_val, false_val).
- All derived display fields (label, color, display_name, name_color, etc.) are
  pre-computed in database.fetch_zone_assignments() so components just read them.
"""

from __future__ import annotations
import reflex as rx

from ..styles import CARD_BASE, C_ALERT
from ..state import ZdsState


# ── Shared sub-components ─────────────────────────────────────────────────────

_LOCK_GOLD = "#b45309"


def _lock_icon(slot_id, is_locked) -> rx.Component:
    """Clickable gold lock in the top-right corner of a card."""
    return rx.box(
        rx.icon(
            rx.cond(is_locked, "lock", "lock-open"),
            size=11,
            color=rx.cond(is_locked, _LOCK_GOLD, "#d1d5db"),
        ),
        position="absolute", top="6px", right="6px",
        cursor="pointer",
        on_click=ZdsState.toggle_slot_lock(slot_id),
        _hover={"opacity": "0.7"},
        z_index="2",
    )


def _duplicate_banner() -> rx.Component:
    return rx.hstack(
        rx.icon("triangle-alert", size=9, color="#92400e"),
        rx.text("Double-booked", size="1", color="#92400e",
                font_weight="700", letter_spacing="0.04em"),
        background="#fef3c7",
        border="1px solid #fbbf24",
        border_radius="3px",
        padding="1px 6px",
        align="center", gap="3px",
        margin_top="2px",
        display="inline-flex",
    )


def _inline_clear(slot_id) -> rx.Component:
    """Small × button that clears the slot without opening the picker."""
    return rx.box(
        rx.icon("x", size=10, color="#ef4444"),
        position="absolute", top="6px", right="24px",
        cursor="pointer",
        on_click=ZdsState.clear_slot(slot_id),
        _hover={"opacity": "0.7"},
        z_index="2",
        title="Clear slot",
    )


def _color_bar(color: str, height: str = "3px") -> rx.Component:
    return rx.box(
        position="absolute", top="0", left="0", right="0",
        height=height, background=color, border_radius="8px 8px 0 0",
    )


def _alert_banner(target: str) -> rx.Component:
    return rx.hstack(
        rx.icon("triangle-alert", size=10, color="white"),
        rx.text(target, size="1", weight="bold", color="white",
                letter_spacing="0.07em", text_transform="uppercase"),
        position="absolute", bottom="0", left="0", right="0",
        height="16px", background=C_ALERT,
        align="center", justify="center", gap="4px",
        border_radius="0 0 8px 8px",
    )


def _sweeper_pill(route: str) -> rx.Component:
    return rx.hstack(
        rx.badge("SWEEPER", color_scheme="orange", variant="solid",
                 font_size="7px", padding="0 4px"),
        rx.text(route, size="1", color="#92400e", font_weight="600"),
        align="center", gap="4px", margin_top="2px",
    )


def _group_badge(group_num) -> rx.Component:
    color = rx.cond(
        group_num == 1, "blue",
        rx.cond(group_num == 2, "green",
                rx.cond(group_num == 3, "purple", "gray"))
    )
    return rx.badge(
        group_num,
        color_scheme=color,
        variant="solid", radius="full", font_size="9px",
        width="18px", height="18px",
        display="flex", align_items="center", justify_content="center",
    )


# ── Task section (shared by all card types) ───────────────────────────────────

def _trainee_chip(name) -> rx.Component:
    """Small amber chip showing the trainee's name."""
    return rx.hstack(
        rx.icon("graduation-cap", size=9, color="#92400e"),
        rx.text("Trainee:", size="1", color="#92400e", weight="bold"),
        rx.text(name, size="1", color="#92400e"),
        background="#fef3c7",
        border="1px solid #fbbf24",
        border_radius="3px",
        padding="1px 6px",
        align="center", gap="3px",
        margin_top="2px",
        display="inline-flex",
    )


def _task_section(slot_id, tasks) -> rx.Component:
    """
    Shows the task list for a slot with per-task remove buttons and an
    inline add-task form.  `slot_id` and `tasks` may both be Reflex Vars.
    """
    return rx.vstack(
        # ── Existing tasks ──
        rx.foreach(
            tasks,
            lambda task: rx.hstack(
                rx.text("·", size="1", color="#9ca3af", flex_shrink="0"),
                rx.text(task, size="1", color="#6b7280", flex="1", line_height="1.3"),
                rx.text(
                    "×",
                    size="1", color="#c4c4c4",
                    cursor="pointer",
                    _hover={"color": "#ef4444"},
                    on_click=ZdsState.remove_task(slot_id, task),
                    flex_shrink="0",
                    padding="0 2px",
                ),
                width="100%", align="center", gap="3px", padding="1px 0",
            ),
        ),
        # ── Add-task row / input ──
        rx.cond(
            ZdsState.task_edit_slot_id == slot_id,
            # Input mode
            rx.hstack(
                rx.input(
                    value=ZdsState.task_edit_text,
                    on_change=ZdsState.set_task_edit_text,
                    placeholder="New task…",
                    size="1",
                    flex="1",
                    auto_focus=True,
                ),
                rx.icon_button(
                    rx.icon("check", size=10),
                    size="1", variant="soft", color_scheme="blue",
                    on_click=ZdsState.submit_task(slot_id),
                ),
                rx.icon_button(
                    rx.icon("x", size=10),
                    size="1", variant="ghost",
                    on_click=ZdsState.close_task_input,
                ),
                gap="4px", align="center", width="100%",
            ),
            # Button mode
            rx.text(
                "+ task",
                size="1", color="#d1d5db",
                cursor="pointer",
                _hover={"color": "#3b82f6"},
                on_click=ZdsState.open_task_input(slot_id),
            ),
        ),
        gap="1", width="100%",
        border_top="1px solid #f3f4f6",
        padding_top="4px",
        margin_top="4px",
    )


# ── Zone Card (zone_1 … zone_10) ─────────────────────────────────────────────

def zone_card(slot: dict) -> rx.Component:
    """
    Fields used (all pre-computed in database.py):
      label, color, display_name, name_color, name_style, name_size,
      is_filled, has_alert, alert_target, is_sweeper, sweeper_route,
      group_num, has_group, id, slot_key, display_tasks
    """
    return rx.box(
        # Absolute decorations
        _color_bar(slot["color"]),
        rx.cond(slot["has_alert"], _alert_banner(slot["alert_target"]), rx.fragment()),
        # Lock icon (top-right) and inline clear × (left of lock, only when filled)
        _lock_icon(slot["id"], slot["is_locked"]),
        rx.cond(slot["is_filled"], _inline_clear(slot["id"]), rx.fragment()),
        # ── Clickable "assign TM" area ──
        rx.box(
            rx.hstack(
                rx.text(slot["label"], size="1", weight="bold", color=slot["color"],
                        letter_spacing="0.08em", text_transform="uppercase"),
                rx.cond(
                    slot["has_group"],
                    _group_badge(slot["group_num"]),
                    rx.fragment(),
                ),
                justify="between", align="center", width="100%",
                margin_top="6px",
                padding_right="40px",   # make room for lock + clear icons
            ),
            rx.text(
                slot["display_name"],
                font_size=slot["name_size"],
                font_weight="700",
                line_height="1",
                color=slot["name_color"],
                font_style=slot["name_style"],
                white_space="nowrap",
                overflow="hidden",
                text_overflow="ellipsis",
                max_width="100%",
            ),
            rx.cond(
                slot["is_sweeper"],
                _sweeper_pill(slot["sweeper_route"]),
                rx.fragment(),
            ),
            rx.cond(slot["has_trainee"], _trainee_chip(slot["trainee_name"]), rx.fragment()),
            # Duplicate warning
            rx.cond(slot["has_duplicate"], _duplicate_banner(), rx.fragment()),
            on_click=ZdsState.open_picker(slot["id"], slot["slot_key"], "", slot["label"]),
            cursor="pointer",
            _hover={"opacity": "0.85"},
            width="100%",
        ),
        # ── Task section (doesn't propagate to picker) ──
        _task_section(slot["id"], slot["display_tasks"]),
        **{
            **CARD_BASE,
            "cursor": "default",
            "border": rx.cond(
                slot["is_locked"],
                f"1px solid {_LOCK_GOLD}",
                "1px solid #e5e7eb",
            ),
        },
        padding_bottom=rx.cond(slot["has_alert"], "22px", "10px"),
        min_height="90px",
    )


# ── RR Card (rr_1_2, rr_6, rr_7, rr_8, rr_10) ───────────────────────────────

def rr_card(slot: dict) -> rx.Component:
    """
    RR slots are pre-paired in state._load_night into one dict per bank:
      slot_key, label, color, mens_name, mens_slot_id, womens_name, womens_slot_id,
      has_alert, alert_target, is_sweeper, sweeper_route, display_tasks
    """
    def _side(name, slot_id, side_label: str, rr_side: str,
              group_num, is_filled, is_locked, has_duplicate) -> rx.Component:
        return rx.box(
            # Lock icon for this side
            rx.box(
                rx.icon(
                    rx.cond(is_locked, "lock", "lock-open"),
                    size=10,
                    color=rx.cond(is_locked, _LOCK_GOLD, "#e5e7eb"),
                ),
                position="absolute", top="2px", right="2px",
                cursor="pointer",
                on_click=ZdsState.toggle_slot_lock(slot_id),
                _hover={"opacity": "0.7"},
                z_index="2",
            ),
            # Inline clear × (only when filled)
            rx.cond(
                is_filled,
                rx.box(
                    rx.icon("x", size=9, color="#ef4444"),
                    position="absolute", top="2px", right="16px",
                    cursor="pointer",
                    on_click=ZdsState.clear_slot(slot_id),
                    _hover={"opacity": "0.7"},
                    z_index="2",
                ),
                rx.fragment(),
            ),
            rx.vstack(
                rx.hstack(
                    rx.text(side_label, size="1", color="#9ca3af",
                            letter_spacing="0.07em", text_transform="uppercase",
                            weight="medium"),
                    rx.cond(
                        (group_num > 0) & is_filled,
                        _group_badge(group_num),
                        rx.fragment(),
                    ),
                    align="center", gap="4px",
                ),
                rx.text(
                    name,
                    font_size="18px", font_weight="700", line_height="1",
                    color=rx.cond(name != "Unfilled", "#111827", "#d1d5db"),
                    font_style=rx.cond(name != "Unfilled", "normal", "italic"),
                    white_space="nowrap", overflow="hidden", text_overflow="ellipsis",
                ),
                rx.cond(has_duplicate, _duplicate_banner(), rx.fragment()),
                align="start", gap="1",
                cursor="pointer",
                on_click=ZdsState.open_picker(slot_id, slot["slot_key"], rr_side,
                                              f"{slot['label']} {side_label}"),
                _hover={"opacity": "0.7"},
                padding_right="30px",
            ),
            position="relative",
            flex="1",
            border=rx.cond(is_locked, f"1px solid {_LOCK_GOLD}", "none"),
            border_radius="4px",
            padding="2px",
        )

    return rx.box(
        _color_bar(slot["color"], "2px"),
        rx.cond(slot["has_alert"], _alert_banner(slot["alert_target"]), rx.fragment()),
        rx.text(slot["label"], size="1", weight="bold", color=slot["color"],
                letter_spacing="0.08em", text_transform="uppercase",
                margin_top="6px"),
        rx.hstack(
            _side(slot["mens_name"],   slot["mens_slot_id"],   "Men's",   "mens",
                  slot["mens_group"],   slot["mens_is_filled"],
                  slot["mens_is_locked"], slot["mens_has_duplicate"]),
            rx.divider(orientation="vertical", height="36px", color="#e5e7eb"),
            _side(slot["womens_name"], slot["womens_slot_id"], "Women's", "womens",
                  slot["womens_group"], slot["womens_is_filled"],
                  slot["womens_is_locked"], slot["womens_has_duplicate"]),
            gap="8px", width="100%", align="start", margin_top="4px",
        ),
        rx.cond(
            slot["is_sweeper"],
            _sweeper_pill(slot["sweeper_route"]),
            rx.fragment(),
        ),
        # ── Task section — uses mens_slot_id as the authoritative slot ──
        _task_section(slot["mens_slot_id"], slot["display_tasks"]),
        **{**CARD_BASE, "cursor": "default"},
        padding_bottom=rx.cond(slot["has_alert"], "22px", "10px"),
        min_height="80px",
    )


# ── Aux Card ─────────────────────────────────────────────────────────────────

def aux_card(slot: dict) -> rx.Component:
    """
    Fields: label, color, display_name, name_color, name_style,
            has_alert, alert_target, id, slot_key, display_tasks
    """
    return rx.box(
        _color_bar(slot["color"], "2px"),
        rx.cond(slot["has_alert"], _alert_banner(slot["alert_target"]), rx.fragment()),
        _lock_icon(slot["id"], slot["is_locked"]),
        rx.cond(slot["is_filled"], _inline_clear(slot["id"]), rx.fragment()),
        # ── Clickable area ──
        rx.box(
            rx.text(slot["label"], size="1", weight="bold", color=slot["color"],
                    letter_spacing="0.08em", text_transform="uppercase",
                    margin_top="6px", padding_right="40px"),
            rx.text(
                slot["display_name"],
                font_size="15px", font_weight="700", line_height="1.1",
                color=slot["name_color"],
                font_style=slot["name_style"],
                margin_top="3px",
            ),
            rx.cond(slot["has_duplicate"], _duplicate_banner(), rx.fragment()),
            on_click=ZdsState.open_picker(slot["id"], slot["slot_key"], "", slot["label"]),
            cursor="pointer",
            _hover={"opacity": "0.85"},
            width="100%",
        ),
        # ── Task section ──
        _task_section(slot["id"], slot["display_tasks"]),
        **{
            **CARD_BASE,
            "cursor": "default",
            "border": rx.cond(
                slot["is_locked"],
                f"1px solid {_LOCK_GOLD}",
                "1px solid #e5e7eb",
            ),
        },
        padding_bottom=rx.cond(slot["has_alert"], "22px", "10px"),
        min_height="60px",
    )
