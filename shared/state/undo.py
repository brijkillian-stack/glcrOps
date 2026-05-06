"""
shared/state/undo.py — Client-side undo buffer

Holds the last destructive action so it can be reverted via a toast prompt.
Single-slot: only the most recent action is undo-able. A new action silently
replaces any previously queued undo.

Inverse operations by kind
  restore_assignment  → re-assign tm_id back to slot_id
                        payload: {slot_id, tm_id, night_id}
  restore_lock        → restore lock state to prev_lock
                        payload: {slot_id, prev_lock, night_id}
  restore_highlight   → add or remove an assignment_highlights row
                        payload: {action: "added"|"removed",
                                  highlight_id?: str,   # when action=added
                                  row?: dict}            # when action=removed
"""

from __future__ import annotations

import reflex as rx


class UndoState(rx.State):
    """Single-slot undo buffer. Tracks the last undoable destructive action."""

    last_label: str = ""
    last_inverse_kind: str = ""
    last_inverse_payload: dict = {}
    toast_open: bool = False

    # ── Internal helper ───────────────────────────────────────────────────────
    # Call via `undo = await self.get_state(UndoState); undo.queue(...)` from
    # within another event handler. Mutations commit in the same event batch.

    def queue(self, label: str, kind: str, payload: dict):
        """Queue an undoable action. Overwrites any previously queued undo."""
        self.last_label = label
        self.last_inverse_kind = kind
        self.last_inverse_payload = payload
        self.toast_open = True

    # ── Public event handlers (called from UI) ────────────────────────────────

    @rx.event
    def dismiss(self):
        """Dismiss the toast without undoing."""
        self.toast_open = False
        self.last_inverse_kind = ""

    @rx.event
    async def undo(self):
        """Replay the inverse of the last queued action."""
        kind = self.last_inverse_kind
        payload = dict(self.last_inverse_payload)

        if not kind:
            self.toast_open = False
            return

        try:
            if kind == "restore_assignment":
                # Lazy import avoids circular dep at module load time
                from apps.zds import database
                from apps.zds.state import ZdsState
                zds = await self.get_state(ZdsState)
                database.update_zone_assignment(payload["slot_id"], payload["tm_id"])
                zds._do_engine_night(payload["night_id"])
                zds._load_night(payload["night_id"])

            elif kind == "restore_lock":
                from apps.zds import database
                from apps.zds.state import ZdsState
                zds = await self.get_state(ZdsState)
                database.update_slot_lock(payload["slot_id"], payload["prev_lock"])
                zds._load_night(payload["night_id"])

            elif kind == "restore_highlight":
                from shared.db import get_client
                sb = get_client()
                action = payload.get("action")
                if action == "added":
                    # We added a row — undo by deleting it
                    highlight_id = payload.get("highlight_id")
                    if highlight_id:
                        sb.table("assignment_highlights").delete().eq("id", highlight_id).execute()
                elif action == "removed":
                    # We removed a row — undo by re-inserting it (strip id so DB assigns new one)
                    row = {k: v for k, v in payload["row"].items() if k != "id"}
                    sb.table("assignment_highlights").insert(row).execute()

        except Exception:
            pass  # Undo is best-effort; failures are silently swallowed

        self.last_inverse_kind = ""
        self.toast_open = False
