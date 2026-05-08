"""
Zone card, RR card, and Aux card components.
Each card's top area is clickable (opens TM picker); the task section below
has its own click handlers so it doesn't propagate to the picker.

IMPORTANT: Inside rx.foreach the item is a Reflex Var, NOT a plain Python dict.
- Never use Python `or`, `and`, `if/else`, or dict.get(Var_key) on Var objects.
- Always use rx.cond(condition, true_val, false_val).
- All derived display fields (label, color, display_name, name_color, etc.) are
  pre-computed in database.fetch_zone_assignments() so components just read them.

Phase 2026-05-05 — Right-click / long-press TM names now opens a context
menu with relevant actions (mark sweeper, view profile, etc.). The trigger
is the .ctx-menu-trigger class + on_context_menu firing
ContextMenuState.open_at on the display_name span.
"""

from __future__ import annotations
import reflex as rx

from ..styles import CARD_BASE, C_ALERT
from ..state import ZdsState
from shared.components.context_menu import ContextMenuState
from .task_popover import task_popover


# ── Shared sub-components ─────────────────────────────────────────────────────

# Phase E — notice type → dot color
_NOTICE_COLORS: dict[str, str] = {
    "alert":    "#fbbf24",
    "info":     "#30b2ff",
    "training": "#34d399",
    "meeting":  "#a78bfa",
}
_NOTICE_ICONS: dict[str, str] = {
    "alert":    "⚠",
    "info":     "ℹ",
    "training": "🎓",
    "meeting":  "📅",
}

_LOCK_GOLD = "#b45309"


def _notice_dot(notices) -> rx.Component:
    """Phase E — colored dot in the top-left corner of a card when notices exist.

    `notices` is a Reflex Var (list[dict]) — may be empty.
    When non-empty, shows the dot colored by the first (newest) notice's type,
    plus a CSS tooltip listing all notices on hover.

    The dot is purely decorative CSS; on-hover tooltip is a sibling div
    revealed by the .notice-dot:hover ~ .notice-tooltip selector in zds_dark.css.
    """
    # Map the top notice type to a color via rx.match
    dot_color = rx.match(
        notices[0]["type"],
        ("alert",    "#fbbf24"),
        ("info",     "#30b2ff"),
        ("training", "#34d399"),
        ("meeting",  "#a78bfa"),
        "#fbbf24",   # default
    )
    return rx.cond(
        notices.length() > 0,
        rx.box(
            # The dot itself
            rx.box(
                class_name="notice-dot",
                background=dot_color,
                box_shadow=rx.match(
                    notices[0]["type"],
                    ("alert",    "0 0 6px rgba(251,191,36,0.55)"),
                    ("info",     "0 0 6px rgba(48,178,255,0.55)"),
                    ("training", "0 0 6px rgba(52,211,153,0.55)"),
                    ("meeting",  "0 0 6px rgba(167,139,250,0.55)"),
                    "0 0 6px rgba(251,191,36,0.55)",
                ),
            ),
            # Tooltip (revealed by CSS :hover on parent)
            rx.box(
                rx.foreach(
                    notices,
                    lambda n: rx.box(
                        rx.text(
                            n["type"].upper() + " · " + n["text"],
                            size="1", color="#e8edf2",
                        ),
                        padding="2px 0",
                    ),
                ),
                class_name="notice-tooltip",
            ),
            class_name="notice-dot-wrapper",
            position="absolute",
            top="6px", left="6px",
            z_index="5",
        ),
        rx.fragment(),
    )


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


def _warning_badge(status) -> rx.Component:
    """Phase J — Call-off / not-scheduled warning displayed below the TM name.

    `status` is a Reflex Var; one of "ok", "called_off", "not_scheduled", or "".
    """
    return rx.cond(
        status == "called_off",
        rx.hstack(
            rx.icon("octagon-x", size=10, color="white"),
            rx.text("CALLED OFF", size="1", color="white",
                    font_weight="800", letter_spacing="0.06em"),
            background="#dc2626",
            border_radius="3px",
            padding="1px 6px",
            align="center", gap="3px",
            margin_top="2px",
            display="inline-flex",
        ),
        rx.cond(
            status == "not_scheduled",
            rx.hstack(
                rx.icon("triangle-alert", size=10, color="#7c2d12"),
                rx.text("NOT SCHEDULED", size="1", color="#7c2d12",
                        font_weight="800", letter_spacing="0.06em"),
                background="#fed7aa",
                border="1px solid #fb923c",
                border_radius="3px",
                padding="1px 6px",
                align="center", gap="3px",
                margin_top="2px",
                display="inline-flex",
            ),
            rx.fragment(),
        ),
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


def _task_section(slot_id, tasks, card_label) -> rx.Component:
    """
    Shows the task list for a slot with per-task annotation popovers,
    remove buttons, and an inline add-task form.

    Phase 4k.6: clicking a task line opens an inline popover (task_popover.py)
    instead of the old right-click JS context menu.
    card_label is passed so open_task_popover knows which card the task is in.
    """
    return rx.vstack(
        # ── Existing tasks ──
        rx.foreach(
            tasks,
            lambda task: rx.box(
                rx.hstack(
                    rx.text("·", size="1", color="#9ca3af", flex_shrink="0"),
                    rx.text(
                        task["name"],
                        size="1", flex="1", line_height="1.3",
                        class_name="task-line-clickable",
                        on_click=ZdsState.open_task_popover(task["id"], card_label),
                        cursor="pointer",
                    ),
                    rx.text(
                        "×",
                        size="1", color="#c4c4c4",
                        cursor="pointer",
                        _hover={"color": "#ef4444"},
                        on_click=ZdsState.remove_task(slot_id, task["name"]),
                        flex_shrink="0",
                        padding="0 2px",
                    ),
                    width="100%", align="center", gap="3px", padding="1px 0",
                ),
                # Inline popover — only visible when this task is the open one
                task_popover(task["id"]),
                class_name="task-line-li",
                position="relative",
                width="100%",
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
        class_name="card-task-section",
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
        # Filled: 3px bar with zone color. Unfilled: 2px dim bar (no glow).
        rx.cond(
            slot["is_filled"],
            _color_bar(slot["color"], height="3px"),
            _color_bar("#2e4357", height="2px"),
        ),
        rx.cond(slot["has_alert"], _alert_banner(slot["alert_target"]), rx.fragment()),
        # Phase E — notice dot (top-left, color by notice type)
        _notice_dot(slot["notices"]),
        # Lock icon (top-right) and inline clear × (left of lock, only when filled)
        _lock_icon(slot["id"], slot["is_locked"]),
        rx.cond(slot["is_filled"], _inline_clear(slot["id"]), rx.fragment()),
        # ── Clickable "assign TM" area ──
        rx.box(
            rx.hstack(
                # card-slot-label class: CSS overrides to 9px/700/0.14em tracking
                rx.text(slot["label"], size="1", weight="bold", color=slot["color"],
                        letter_spacing="0.08em", text_transform="uppercase",
                        class_name="card-slot-label"),
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
                # Phase 2026-05-05 — right-click / long-press → context menu
                # (ContextMenuState.open_at via context_menu.js).
                # Phase 2026-05-06 — left-click → highlight toolbar
                # (HighlightToolbarState.open_at via highlight_toolbar.js).
                # Both JS handlers read data-* attrs from this span.
                # The highlight toolbar JS runs in capture phase and calls
                # stopPropagation() so the parent on_click (picker) is suppressed.
                # Phase 1 dark-mode (2026-05-06): card-tm-name / card-empty-label
                # classes let CSS pick the right color per theme — inline
                # color is now empty for filled rows so the class wins.
                # card-tm-name-calledoff → red text via CSS; card-tm-name → normal filled
                class_name=(
                    "ctx-menu-trigger ht-trigger "
                    # Phase 4k.4 — badge classes (✎ note / 📌 profile-log)
                    + rx.cond(
                        slot["is_filled"]
                        & ZdsState.tm_badge_classes.contains(slot["tm_id"]),
                        ZdsState.tm_badge_classes[slot["tm_id"]] + " ",
                        "",
                    )
                    + rx.cond(
                        slot["is_filled"],
                        rx.cond(
                            slot["warning_status"] == "called_off",
                            "card-tm-name card-tm-name-calledoff",
                            "card-tm-name",
                        ),
                        "card-empty-label",
                    )
                ),
                custom_attrs={
                    # Context menu attrs (ContextMenuState — operational actions)
                    "data-ctx-target-type":  "assignment",
                    "data-ctx-target-id":    slot["tm_id"],
                    "data-ctx-target-label": slot["display_name"],
                    "data-ctx-surface":      "deployment_grid",
                    "data-ctx-night-id":     ZdsState.current_night_id,
                    "data-ctx-slot-key":     slot["slot_key"],
                    # Highlight toolbar attrs
                    "data-ht-tm-id":         slot["tm_id"],
                    "data-ht-night-id":      ZdsState.current_night_id,
                    "data-ht-slot-key":      slot["slot_key"],
                },
            ),
            rx.cond(
                slot["is_sweeper"],
                _sweeper_pill(slot["sweeper_route"]),
                rx.fragment(),
            ),
            rx.cond(slot["has_trainee"], _trainee_chip(slot["trainee_name"]), rx.fragment()),
            # Duplicate warning
            rx.cond(slot["has_duplicate"], _duplicate_banner(), rx.fragment()),
            # Phase J — call-off / not-scheduled warning
            _warning_badge(slot["warning_status"]),
            on_click=ZdsState.open_picker(slot["id"], slot["slot_key"], "", slot["label"]),
            cursor="pointer",
            _hover={"opacity": "0.85"},
            width="100%",
        ),
        # ── Task section (doesn't propagate to picker) ──
        _task_section(slot["id"], slot["display_tasks"], slot["label"]),
        **{
            **CARD_BASE,
            "cursor": "default",
            "border": rx.cond(
                slot["is_locked"],
                f"1px solid {_LOCK_GOLD}",
                "1px solid #e5e7eb",
            ),
            "class_name": rx.cond(
                slot["is_locked"],
                rx.cond(
                    slot["is_filled"],
                    "zone-card zone-card-filled zone-card-locked "
                    + rx.cond(
                        ZdsState.card_badge_classes.contains(slot["label"]),
                        ZdsState.card_badge_classes[slot["label"]],
                        "",
                    ),
                    "zone-card zone-card-empty zone-card-locked "
                    + rx.cond(
                        ZdsState.card_badge_classes.contains(slot["label"]),
                        ZdsState.card_badge_classes[slot["label"]],
                        "",
                    ),
                ),
                rx.cond(
                    slot["is_filled"],
                    "zone-card zone-card-filled "
                    + rx.cond(
                        ZdsState.card_badge_classes.contains(slot["label"]),
                        ZdsState.card_badge_classes[slot["label"]],
                        "",
                    ),
                    "zone-card zone-card-empty "
                    + rx.cond(
                        ZdsState.card_badge_classes.contains(slot["label"]),
                        ZdsState.card_badge_classes[slot["label"]],
                        "",
                    ),
                ),
            ),
        },
        padding_bottom=rx.cond(slot["has_alert"], "22px", "10px"),
        min_height="108px",
    )


# ── RR Card (rr_1_2, rr_6, rr_7, rr_8, rr_10) ───────────────────────────────

def rr_card(slot: dict) -> rx.Component:
    """
    RR slots are pre-paired in state._load_night into one dict per bank:
      slot_key, label, color, mens_name, mens_slot_id, womens_name, womens_slot_id,
      has_alert, alert_target, is_sweeper, sweeper_route, display_tasks
    """
    def _side(name, slot_id, side_label: str, rr_side: str,
              group_num, is_filled, is_locked, has_duplicate,
              warning_status) -> rx.Component:
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
                    # Phase 1 dark mode: drop inline color for filled so the
                    # .card-tm-name CSS rule wins on the dark theme. Unfilled
                    # keeps the inline gray (works on both light + dark).
                    color=rx.cond(name != "Unfilled", "", "#d1d5db"),
                    font_style=rx.cond(name != "Unfilled", "normal", "italic"),
                    white_space="nowrap", overflow="hidden", text_overflow="ellipsis",
                    class_name=rx.cond(name != "Unfilled", "card-tm-name", "card-empty-label"),
                ),
                rx.cond(has_duplicate, _duplicate_banner(), rx.fragment()),
                # Phase J — call-off / not-scheduled badge
                _warning_badge(warning_status),
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
                  slot["mens_is_locked"], slot["mens_has_duplicate"],
                  slot["mens_warning_status"]),
            rx.divider(orientation="vertical", height="36px", color="#e5e7eb"),
            _side(slot["womens_name"], slot["womens_slot_id"], "Women's", "womens",
                  slot["womens_group"], slot["womens_is_filled"],
                  slot["womens_is_locked"], slot["womens_has_duplicate"],
                  slot["womens_warning_status"]),
            gap="8px", width="100%", align="start", margin_top="4px",
        ),
        rx.cond(
            slot["is_sweeper"],
            _sweeper_pill(slot["sweeper_route"]),
            rx.fragment(),
        ),
        # ── Task section — uses mens_slot_id as the authoritative slot ──
        _task_section(slot["mens_slot_id"], slot["display_tasks"], slot["label"]),
        **{
            **CARD_BASE,
            "cursor": "default",
            "class_name": rx.cond(
                slot["mens_is_filled"] | slot["womens_is_filled"],
                "zone-card rr-card rr-card-filled "
                + rx.cond(
                    ZdsState.card_badge_classes.contains(slot["label"]),
                    ZdsState.card_badge_classes[slot["label"]],
                    "",
                ),
                "zone-card rr-card rr-card-empty "
                + rx.cond(
                    ZdsState.card_badge_classes.contains(slot["label"]),
                    ZdsState.card_badge_classes[slot["label"]],
                    "",
                ),
            ),
        },
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
                # Phase 1 dark mode: name_color is "" for filled rows so the
                # .card-tm-name CSS rule controls color per theme. Unfilled
                # carries inline gray which works on both light and dark.
                color=slot["name_color"],
                font_style=slot["name_style"],
                margin_top="3px",
                class_name=rx.cond(slot["is_filled"], "card-tm-name", "card-empty-label"),
            ),
            rx.cond(slot["has_duplicate"], _duplicate_banner(), rx.fragment()),
            # Phase J — call-off / not-scheduled badge
            _warning_badge(slot["warning_status"]),
            on_click=ZdsState.open_picker(slot["id"], slot["slot_key"], "", slot["label"]),
            cursor="pointer",
            _hover={"opacity": "0.85"},
            width="100%",
        ),
        # ── Task section ──
        _task_section(slot["id"], slot["display_tasks"], slot["label"]),
        **{
            **CARD_BASE,
            "cursor": "default",
            "border": rx.cond(
                slot["is_locked"],
                f"1px solid {_LOCK_GOLD}",
                "1px solid #e5e7eb",
            ),
            "class_name": rx.cond(
                slot["is_locked"],
                rx.cond(
                    slot["is_filled"],
                    "zone-card aux-card zone-card-filled zone-card-locked "
                    + rx.cond(
                        ZdsState.card_badge_classes.contains(slot["label"]),
                        ZdsState.card_badge_classes[slot["label"]],
                        "",
                    ),
                    "zone-card aux-card zone-card-empty zone-card-locked "
                    + rx.cond(
                        ZdsState.card_badge_classes.contains(slot["label"]),
                        ZdsState.card_badge_classes[slot["label"]],
                        "",
                    ),
                ),
                rx.cond(
                    slot["is_filled"],
                    "zone-card aux-card zone-card-filled "
                    + rx.cond(
                        ZdsState.card_badge_classes.contains(slot["label"]),
                        ZdsState.card_badge_classes[slot["label"]],
                        "",
                    ),
                    "zone-card aux-card zone-card-empty "
                    + rx.cond(
                        ZdsState.card_badge_classes.contains(slot["label"]),
                        ZdsState.card_badge_classes[slot["label"]],
                        "",
                    ),
                ),
            ),
        },
        padding_bottom=rx.cond(slot["has_alert"], "22px", "10px"),
        min_height="60px",
    )
