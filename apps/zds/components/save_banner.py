"""
Audit banner — sticky bottom-right pill that tracks user-driven mutations
for the current night. Click to expand into a scrollable list with per-row
undo and a "Mark all reviewed" button.

Reads `ZdsState.change_count`, `ZdsState.visible_changes`,
`ZdsState.banner_expanded`. Writes via `toggle_banner`, `revert_change`,
`clear_change_log`.
"""

from __future__ import annotations
import reflex as rx

from ..state import ZdsState


# ── Single change row ────────────────────────────────────────────────────────

def _kind_icon(entry) -> rx.Component:
    """Render the right lucide icon based on the entry's kind.

    rx.icon's tag must be a literal string at compile time, so we can't pass
    `entry["icon"]` directly — instead, switch on `kind` and render a tag-literal
    rx.icon in each branch. Color stays driven by `entry["accent"]` (Vars are
    fine for style props).
    """
    return rx.match(
        entry["kind"],
        ("assign",      rx.icon("user-plus",  size=14, color=entry["accent"])),
        ("clear",       rx.icon("user-minus", size=14, color=entry["accent"])),
        ("lock_toggle", rx.cond(
            entry["prev_lock"],   # prev_lock=True → just unlocked → show unlock
            rx.icon("lock_open", size=14, color=entry["accent"]),
            rx.icon("lock",   size=14, color=entry["accent"]),
        )),
        ("task_add",    rx.icon("list-plus",  size=14, color=entry["accent"])),
        ("task_remove", rx.icon("list-minus", size=14, color=entry["accent"])),
        rx.icon("circle", size=14, color=entry["accent"]),  # fallback
    )


def _change_row(entry) -> rx.Component:
    """One row in the expanded change list."""
    return rx.hstack(
        # Kind-specific icon
        _kind_icon(entry),
        # Detail + timestamp
        rx.vstack(
            rx.text(
                entry["detail"],
                size="2",
                color=rx.cond(entry["undone"], "#9ca3af", "#111827"),
                text_decoration=rx.cond(entry["undone"], "line-through", "none"),
                line_height="1.3",
            ),
            rx.text(
                # ISO timestamp is "YYYY-MM-DDTHH:MM:SS" — chars 11..15 are "HH:MM"
                entry["timestamp"][11:16],
                size="1",
                color="#9ca3af",
            ),
            gap="0",
            align="start",
            flex="1",
            min_width="0",
        ),
        # Undo / Redo button — Phase K.4: undone entries get a Redo action
        rx.cond(
            entry["undone"],
            rx.button(
                rx.icon("redo-2", size=12),
                "Redo",
                size="1",
                variant="soft",
                color_scheme="blue",
                on_click=ZdsState.redo_change(entry["id"]),
                cursor="pointer",
                title="Re-apply this change",
            ),
            rx.button(
                rx.icon("undo-2", size=12),
                "Undo",
                size="1",
                variant="soft",
                color_scheme="gray",
                on_click=ZdsState.revert_change(entry["id"]),
                cursor="pointer",
            ),
        ),
        align="center",
        gap="10px",
        padding="8px 4px",
        border_bottom="1px solid #f3f4f6",
        width="100%",
    )


# ── Collapsed pill ───────────────────────────────────────────────────────────

def _collapsed_pill() -> rx.Component:
    return rx.hstack(
        rx.box(
            background="#3b82f6",
            width="6px",
            height="6px",
            border_radius="50%",
        ),
        rx.text(
            ZdsState.change_count,
            " ",
            rx.cond(ZdsState.change_count == 1, "change", "changes"),
            size="2",
            weight="medium",
            color="#111827",
        ),
        rx.icon("chevron-up", size=14, color="#6b7280"),
        align="center",
        gap="8px",
        padding="10px 14px",
        background="white",
        border="1px solid #e5e7eb",
        border_radius="999px",
        box_shadow="0 4px 12px rgba(0,0,0,0.08)",
        cursor="pointer",
        on_click=ZdsState.toggle_banner,
        _hover={
            "border_color": "#3b82f6",
            "box_shadow": "0 4px 16px rgba(59,130,246,0.18)",
        },
        transition="all 0.15s",
    )


# ── Expanded panel ───────────────────────────────────────────────────────────

def _expanded_panel() -> rx.Component:
    return rx.vstack(
        # Header
        rx.hstack(
            rx.hstack(
                rx.box(
                    background="#3b82f6",
                    width="6px",
                    height="6px",
                    border_radius="50%",
                ),
                rx.text(
                    ZdsState.change_count,
                    " ",
                    rx.cond(ZdsState.change_count == 1, "change", "changes"),
                    " this session",
                    size="2",
                    weight="bold",
                    color="#111827",
                ),
                align="center",
                gap="8px",
            ),
            rx.spacer(),
            rx.button(
                rx.icon("check-check", size=12),
                "Mark all reviewed",
                size="1",
                variant="soft",
                color_scheme="green",
                on_click=ZdsState.clear_change_log,
                cursor="pointer",
            ),
            rx.icon_button(
                rx.icon("chevron-down", size=14),
                size="1",
                variant="ghost",
                on_click=ZdsState.toggle_banner,
                cursor="pointer",
            ),
            align="center",
            gap="8px",
            width="100%",
            padding_bottom="6px",
            border_bottom="1px solid #e5e7eb",
        ),
        # Scrollable list
        rx.box(
            rx.foreach(ZdsState.visible_changes, _change_row),
            max_height="320px",
            overflow_y="auto",
            width="100%",
        ),
        # Footer note
        rx.text(
            "Changes save to Supabase instantly. Undo reverses the action and re-runs the engine.",
            size="1",
            color="#9ca3af",
            padding_top="6px",
            line_height="1.4",
        ),
        gap="8px",
        padding="14px 16px",
        background="white",
        border="1px solid #e5e7eb",
        border_radius="10px",
        box_shadow="0 8px 24px rgba(0,0,0,0.12)",
        width="380px",
        max_width="calc(100vw - 32px)",
    )


# ── Public component ─────────────────────────────────────────────────────────

def save_banner() -> rx.Component:
    """Sticky bottom-right banner. Hidden until there's at least one change."""
    return rx.cond(
        ZdsState.has_changes,
        rx.box(
            rx.cond(
                ZdsState.banner_expanded,
                _expanded_panel(),
                _collapsed_pill(),
            ),
            position="fixed",
            bottom="20px",
            right="20px",
            z_index="30",
        ),
        rx.fragment(),
    )
