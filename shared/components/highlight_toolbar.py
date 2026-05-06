"""
shared/components/highlight_toolbar.py — Left-click highlight toolbar

Left-clicking a TM display-name span on the deployment grid opens a small
inline toolbar with 5 highlight chips (sweeper / priority / watch /
accommodation / custom). Tapping a chip writes (or toggles) an
assignment_highlights row and dismisses the toolbar.

Right-click still opens the full context menu (unchanged behaviour).

Architecture mirrors context_menu.py:
  • HighlightToolbarState — single-instance global state with open/coords/target.
  • global_highlight_toolbar() — component mounted at app root, position:fixed.
  • .ht-trigger elements — carry data-ht-* attributes; click events are caught by
    assets/highlight_toolbar.js, which reads element bounds via getBoundingClientRect
    and dispatches HighlightToolbarState.open_at. The JS handler calls
    e.stopPropagation() (capture phase) so the parent zone card's on_click
    (which opens the picker) does NOT fire.

State field naming: prefixed with ctx_ to avoid shadowing dynamic route args
(Reflex 0.9 raises DynamicRouteArgShadowsStateVarError for same-named vars).
"""

from __future__ import annotations

import reflex as rx

from shared.auth import AuthState
from shared.db import get_client
from shared.components.context_menu import HIGHLIGHT_VISUALS


# ── Highlight types shown in the toolbar (5 canonical) ───────────────────────
# trainer_pair is excluded — that's a two-TM concept better handled via the
# context menu's full UI. The toolbar is a one-tap quick-apply surface.

_TOOLBAR_CHIPS: list[str] = ["sweeper", "priority", "watch", "accommodation", "custom"]


class HighlightToolbarState(rx.State):
    """Global state for the left-click highlight toolbar."""

    # ── Visibility + anchor position ─────────────────────────────────────────
    open:  bool = False
    x:     int  = 0
    y:     int  = 0

    # ── Target context — ctx_ prefix avoids dynamic route arg shadowing ──────
    ctx_tm_id:    str = ""
    ctx_night_id: str = ""
    ctx_slot_key: str = ""

    # ── Transient feedback ────────────────────────────────────────────────────
    error:          str  = ""
    last_action_ok: bool = True

    # ── Open / close ─────────────────────────────────────────────────────────

    @rx.event
    def open_at(
        self,
        x:        int,
        y:        int,
        tm_id:    str,
        night_id: str,
        slot_key: str,
    ):
        """Open the toolbar anchored just below the TM name span.

        Called from highlight_toolbar.js after reading getBoundingClientRect()
        on the clicked .ht-trigger element. x/y are the pixel coords of the
        bottom-left of the element (plus a small gap), in viewport space.
        """
        self.x            = int(x or 0)
        self.y            = int(y or 0)
        self.ctx_tm_id    = tm_id    or ""
        self.ctx_night_id = night_id or ""
        self.ctx_slot_key = slot_key or ""
        self.error        = ""
        self.open         = True

    @rx.event
    def close(self):
        self.open = False

    # ── Permission helper (non-event — called from event handlers) ────────────

    async def _require_editor(self) -> bool:
        auth = await self.get_state(AuthState)
        if not auth.can_edit_deployment:
            self.error = "Sign in as editor to make changes"
            self.last_action_ok = False
            return False
        return True

    # ── Apply / toggle highlight ──────────────────────────────────────────────

    @rx.event
    async def apply_highlight(self, highlight_type: str):
        """Write or toggle an assignment_highlights row for the current target.

        Toggle behaviour: if a row already exists with the same
        (night_id, slot_key, highlight_type) triple, it is deleted; otherwise
        a new row is inserted. Mirrors ContextMenuState.mark_sweeper.
        """
        if not (await self._require_editor()):
            return
        if not self.ctx_night_id or not self.ctx_slot_key:
            self.error = "Missing night/slot context"
            self.last_action_ok = False
            self.open = False
            return

        visuals = HIGHLIGHT_VISUALS.get(highlight_type, {})

        try:
            sb = get_client()

            # Check for an existing row — toggle if present
            existing = (
                sb.table("assignment_highlights")
                .select("id")
                .eq("night_id",       self.ctx_night_id)
                .eq("slot_key",       self.ctx_slot_key)
                .eq("highlight_type", highlight_type)
                .limit(1)
                .execute()
                .data
            )

            if existing:
                # Toggle off — remove the existing row
                sb.table("assignment_highlights").delete().eq(
                    "id", existing[0]["id"]
                ).execute()
            else:
                # Insert new highlight
                row = {
                    "night_id":       self.ctx_night_id,
                    "slot_key":       self.ctx_slot_key,
                    "tm_id":          self.ctx_tm_id or None,
                    "highlight_type": highlight_type,
                    "color":          visuals.get("color", ""),
                    "icon":           visuals.get("icon", ""),
                    "created_by":     "site_session",
                }
                sb.table("assignment_highlights").insert(row).execute()

            self.last_action_ok = True
            self.error = ""

        except Exception as exc:
            self.error = f"Save failed: {exc}"
            self.last_action_ok = False

        finally:
            self.open = False


# ── Sub-components ────────────────────────────────────────────────────────────


def _highlight_chip(highlight_type: str) -> rx.Component:
    """Single round chip button in the toolbar.

    `highlight_type` is a static Python string (toolbar is built at render time,
    not via rx.foreach over a Var) so we can index HIGHLIGHT_VISUALS directly.
    """
    vis = HIGHLIGHT_VISUALS[highlight_type]
    label = highlight_type.replace("_", " ").title()
    return rx.el.button(
        rx.el.span(vis["icon"],  class_name="ht-chip-icon"),
        rx.el.span(label,        class_name="ht-chip-label"),
        on_click=HighlightToolbarState.apply_highlight(highlight_type),
        class_name="ht-chip",
        style={"--ht-chip-color": vis["color"]},
        title=f"Mark as {label.lower()}",
    )


def global_highlight_toolbar() -> rx.Component:
    """Mount once at app root — renders the toolbar when HighlightToolbarState.open."""
    s = HighlightToolbarState
    return rx.cond(
        s.open,
        rx.el.div(
            # ── Backdrop — transparent, catches outside clicks to close ──────
            rx.el.div(
                on_click=s.close,
                class_name="ht-backdrop",
            ),
            # ── Toolbar panel ─────────────────────────────────────────────────
            rx.el.div(
                # Chips (static list — safe to expand at Python render time)
                *[_highlight_chip(t) for t in _TOOLBAR_CHIPS],
                class_name="ht-panel",
                style={
                    # Flip left when near the right viewport edge
                    "left": rx.cond(
                        s.x.to(int) > 800,
                        f"{s.x - 280}px",
                        f"{s.x}px",
                    ),
                    "top": f"{s.y}px",
                },
            ),
            class_name="ht-root",
        ),
        rx.fragment(),
    )
