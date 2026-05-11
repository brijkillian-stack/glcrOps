"""
shared/components/context_menu.py — Global ZDS context menu

Right-click (desktop) or long-press (iPad/iPhone) on TM names, slot cards,
or TM picker chips → opens a context-sensitive popover at the cursor with
relevant quick-action items.

The menu state is global (single instance per session). Any trigger element
calls ContextMenuState.open(...) with target context; the menu computes the
item set based on (target_type, surface) and renders.

Architecture:
  • ContextMenuState — the single-source state holding open/coords/target.
  • global_context_menu() — component mounted at app root, position:fixed.
  • Triggers — callers add on_context_menu={ContextMenuState.open(...)} to
    their TM-name spans, slot cards, etc. Long-press on touch is wired in
    assets/context_menu.js (one global listener, fires preventDefault and
    dispatches the same Reflex event).

Item-set is contextual ("differs by item clicked for relevancy"):
  • surface='deployment_grid' + target='assignment'  → mark sweeper, swap,
                                                       called off, profile…
  • surface='schedule_tab'    + target='pool_tm'     → mark called off,
                                                       view profile
  • surface='tm_picker'       + target='picker_tm'   → view profile only
  • surface='week_overview'   + target='day_card_tm' → view profile, mark
                                                       called off
  • surface='deployment_grid' + target='slot'        → force assign, lock,
                                                       mark priority

See docs/context_menu_remaining_surfaces.md for the Sonnet handoff covering
the surfaces + actions not implemented in this v1.
"""

from __future__ import annotations

import reflex as rx

from shared.auth import AuthState
from shared.db import get_client


# ── Highlight types and visual tokens ────────────────────────────────────────

HIGHLIGHT_TYPES = ("sweeper", "trainer_pair", "priority", "watch", "accommodation", "custom")

HIGHLIGHT_VISUALS = {
    "sweeper":       {"icon": "🧹", "color": "#C8A77F"},   # gold
    "trainer_pair":  {"icon": "🔗", "color": "#0065BF"},   # blue
    "priority":      {"icon": "⚑",  "color": "#B91C1C"},   # red
    "watch":         {"icon": "👁",  "color": "#F59E0B"},   # amber
    "accommodation": {"icon": "✚",  "color": "#6B7280"},   # neutral
    "custom":        {"icon": "★",  "color": "#1A1A1A"},   # default
}


class ContextMenuState(rx.State):
    """Global state for the right-click / long-press context menu."""

    # ── Visibility + position ────────────────────────────────────────────────
    open: bool = False
    x: int = 0
    y: int = 0

    # ── Target context ───────────────────────────────────────────────────────
    target_type:   str = ""   # 'tm' | 'slot' | 'assignment' | 'pool_tm' | 'picker_tm'
    target_id:     str = ""   # tm_id, slot_key, or composite
    target_label:  str = ""   # human-readable header for the menu
    surface:       str = ""   # 'deployment_grid' | 'schedule_tab' | 'week_overview' | 'tm_picker'
    # NOTE: prefixed with ctx_ to avoid shadowing the dynamic route args
    # `[night_id]` and `[slot_key]` exposed by /zds/week/[week_id]/day/[night_id]
    # and similar routes. Reflex 0.9 raises DynamicRouteArgShadowsStateVarError
    # if a state var has the same name as any registered dynamic route segment.
    ctx_night_id:  str = ""
    ctx_slot_key:  str = ""

    # ── Status + transient feedback ──────────────────────────────────────────
    error:    str = ""
    last_action_ok: bool = True

    # ── Open / close ─────────────────────────────────────────────────────────

    @rx.event
    def open_at(
        self,
        x: int,
        y: int,
        target_type: str,
        target_id: str,
        target_label: str = "",
        surface: str = "",
        night_id: str = "",
        slot_key: str = "",
    ):
        """Open the menu at the given client coords with full target context.

        Triggers call this from on_context_menu (desktop right-click) or via
        the long-press JS handler dispatching the same event. The incoming
        `night_id` / `slot_key` args are stored on the `ctx_night_id` /
        `ctx_slot_key` state fields to avoid shadowing dynamic route args.
        """
        self.x = int(x or 0)
        self.y = int(y or 0)
        self.target_type  = target_type or ""
        self.target_id    = target_id or ""
        self.target_label = target_label or target_id or ""
        self.surface      = surface or ""
        self.ctx_night_id = night_id or ""
        self.ctx_slot_key = slot_key or ""
        self.error        = ""
        self.open         = True

    @rx.event
    def close(self):
        self.open = False

    # ── Permission helpers (read AuthState to gate write actions) ────────────
    # In DEV MODE, can_edit_deployment is True for any unlocked user. When the
    # magic-link layer comes back, the AuthState.can_edit_deployment Var will
    # naturally tighten this without changes here.
    #
    # NOTE: this is a private async helper, NOT an @rx.event handler.
    # Reflex 0.9 rejects underscore-prefixed event handlers as "private",
    # but a regular async method called from within an event handler is fine
    # — `self.get_state(...)` is available on any State instance.

    async def _require_editor(self) -> bool:
        auth = await self.get_state(AuthState)
        if not auth.can_edit_deployment:
            self.error = "Sign in as editor to make changes"
            self.last_action_ok = False
            return False
        return True

    # ── Action handlers (foundation set; more in Sonnet handoff) ─────────────

    @rx.event
    async def mark_sweeper(self):
        """Add a 'sweeper' highlight on the current target's slot/TM/night."""
        if not (await self._require_editor()):
            return
        if not self.ctx_night_id or not self.ctx_slot_key:
            self.error = "Missing night/slot context"
            self.last_action_ok = False
            return
        try:
            sb = get_client()
            # Idempotent: check for existing sweeper highlight on this row first.
            # select("*") so we have the full row for undo re-insert.
            existing = (
                sb.table("assignment_highlights")
                .select("*")
                .eq("night_id", self.ctx_night_id)
                .eq("slot_key", self.ctx_slot_key)
                .eq("highlight_type", "sweeper")
                .limit(1)
                .execute()
                .data
            )
            if existing:
                # Already marked — clear it (toggle behavior)
                sb.table("assignment_highlights").delete().eq("id", existing[0]["id"]).execute()
                self.error = ""
                self.last_action_ok = True
                # Queue undo: restore the deleted row
                from shared.state.undo import UndoState
                undo = await self.get_state(UndoState)
                undo.queue(
                    f"Cleared sweeper for {self.target_label}",
                    "restore_highlight",
                    {"action": "removed", "row": existing[0]},
                )
            else:
                row = {
                    "night_id":       self.ctx_night_id,
                    "slot_key":       self.ctx_slot_key,
                    "tm_id":          self.target_id if self.target_type in ("tm", "assignment") else None,
                    "highlight_type": "sweeper",
                    "note":           "Sweeper duty tonight",
                    "color":          HIGHLIGHT_VISUALS["sweeper"]["color"],
                    "icon":           HIGHLIGHT_VISUALS["sweeper"]["icon"],
                    "created_by":     "site_session",
                }
                result = sb.table("assignment_highlights").insert(row).execute()
                new_id = result.data[0]["id"] if result.data else None
                self.error = ""
                self.last_action_ok = True
                # Queue undo: delete the row we just added
                from shared.state.undo import UndoState
                undo = await self.get_state(UndoState)
                undo.queue(
                    f"Marked {self.target_label} as sweeper",
                    "restore_highlight",
                    {"action": "added", "highlight_id": new_id},
                )
        except Exception as exc:
            self.error = f"Save failed: {exc}"
            self.last_action_ok = False
        finally:
            self.open = False

    @rx.event
    async def view_profile(self):
        """Open the TM drawer for the menu's target. No-op if target isn't a TM.

        Phase A (2026-05-12): PeopleState lives in apps.glcr which is archived
        during the ZDS → Next.js migration.  Import is guarded so ZDS boots and
        operates normally; the profile drawer is simply unavailable until the
        GLCR People page is rebuilt on the new stack.
        """
        if self.target_type not in ("tm", "assignment", "pool_tm", "picker_tm"):
            self.open = False
            return
        try:
            from apps.glcr.state.people import PeopleState
        except ImportError:
            # GLCR is archived — people drawer not available in ZDS-only mode.
            self.open = False
            return
        self.open = False
        return PeopleState.open_drawer(self.target_id)

    @rx.event
    async def open_notice_for_ctx_slot(self):
        """Phase E — open the ZDS add-notice dialog for ctx_slot_key."""
        slot_key = self.ctx_slot_key
        self.open = False
        if not slot_key:
            return
        from apps.zds.state import ZdsState
        zds = await self.get_state(ZdsState)
        zds.open_notice_form(slot_key)


# ── Component ────────────────────────────────────────────────────────────────


def _menu_item(
    *,
    label: str,
    icon: str,
    on_click,
    disabled: bool = False,
    danger: bool = False,
) -> rx.Component:
    color = "var(--accent-flag)" if danger else "var(--fg-1)"
    return rx.el.button(
        rx.el.span(icon, class_name="ctx-menu-item-icon"),
        rx.el.span(label, class_name="ctx-menu-item-label"),
        on_click=on_click,
        disabled=disabled,
        class_name="ctx-menu-item",
        style={"color": color},
    )


def _menu_divider() -> rx.Component:
    return rx.el.div(class_name="ctx-menu-divider")


def _items_for_target() -> rx.Component:
    """Render the item set based on (target_type, surface).

    Wrapped in rx.cond so each surface/target combo only renders its
    relevant items. Order: most-likely action first.
    """
    s = ContextMenuState

    return rx.fragment(
        # ── Header (target label) ────────────────────────────────────────
        rx.el.div(s.target_label, class_name="ctx-menu-header"),

        # ── Per-target action sets ───────────────────────────────────────

        # surface=deployment_grid + target=assignment (TM in slot)
        rx.cond(
            (s.surface == "deployment_grid") & (s.target_type == "assignment"),
            rx.fragment(
                _menu_item(label="Mark sweeper tonight", icon="🧹",
                           on_click=s.mark_sweeper),
                _menu_item(label="View profile", icon="◍",
                           on_click=s.view_profile),
                _menu_divider(),
                # Phase E — Add Notice (opens ZdsState notice form dialog)
                _menu_item(label="Add notice", icon="📌",
                           on_click=s.open_notice_for_ctx_slot),
            ),
        ),

        # surface=deployment_grid + target=slot (empty cell)
        rx.cond(
            (s.surface == "deployment_grid") & (s.target_type == "slot"),
            rx.fragment(
                # Phase E — notices available on empty slots too
                _menu_item(label="Add notice", icon="📌",
                           on_click=s.open_notice_for_ctx_slot),
            ),
        ),

        # surface=schedule_tab + target=pool_tm
        rx.cond(
            (s.surface == "schedule_tab") & (s.target_type == "pool_tm"),
            rx.fragment(
                _menu_item(label="View profile", icon="◍",
                           on_click=s.view_profile),
            ),
        ),

        # surface=tm_picker + target=picker_tm
        rx.cond(
            (s.surface == "tm_picker") & (s.target_type == "picker_tm"),
            rx.fragment(
                _menu_item(label="View profile", icon="◍",
                           on_click=s.view_profile),
            ),
        ),

        # surface=week_overview + target=day_card_tm
        rx.cond(
            (s.surface == "week_overview") & (s.target_type == "day_card_tm"),
            rx.fragment(
                _menu_item(label="View profile", icon="◍",
                           on_click=s.view_profile),
            ),
        ),
    )


def global_context_menu() -> rx.Component:
    """Mount this once at app root. Renders the menu when ContextMenuState.open."""
    return rx.cond(
        ContextMenuState.open,
        rx.el.div(
            # Backdrop — click to close
            rx.el.div(
                on_click=ContextMenuState.close,
                class_name="ctx-menu-backdrop",
            ),
            # Menu panel — position:fixed at click coords
            rx.el.div(
                _items_for_target(),
                class_name="ctx-menu-panel",
                style={
                    "left": rx.cond(
                        ContextMenuState.x.to(int) > 800,
                        f"{ContextMenuState.x - 240}px",   # flip left near right edge
                        f"{ContextMenuState.x}px",
                    ),
                    "top": f"{ContextMenuState.y}px",
                },
            ),
            class_name="ctx-menu-root",
        ),
        rx.fragment(),
    )
