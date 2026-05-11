"""
state/floor.py — FloorState

Manages the floor walk checklist. Each zone/restroom starts "pending".
Tapping OK marks it green. Tapping Flag opens an inline note input;
confirming immediately saves it to Supabase as a flag note.
Completing the walk saves a floor_walk summary note.
"""

import asyncio
from datetime import datetime, timezone
import reflex as rx
from shared.base import AppState
from shared.db import save_floor_walk, save_note


# ── Checklist definition ──────────────────────────────────────────────────────
# (id, section, display_name)

def _build_items() -> list[dict]:
    rows: list[dict] = []
    # Main floor zones — Z1-Z10 + Zone 9 SR
    for i in range(1, 11):
        rows.append({"id": f"z{i}", "section": "Main Floor",
                     "name": f"Zone {i}", "status": "pending", "note": ""})
    rows.append({"id": "z9sr", "section": "Main Floor",
                 "name": "Zone 9 SR", "status": "pending", "note": ""})

    # Men's restrooms — only 1+2 (combined), 6, 7, 8, 10 actually exist
    for key, label in [("mrr12", "Mens 1+2"), ("mrr6", "Mens 6"),
                       ("mrr7", "Mens 7"), ("mrr8", "Mens 8"),
                       ("mrr10", "Mens 10")]:
        rows.append({"id": key, "section": "Men's Restrooms",
                     "name": label, "status": "pending", "note": ""})

    # Women's restrooms — same canonical numbers
    for key, label in [("wrr12", "Womens 1+2"), ("wrr6", "Womens 6"),
                       ("wrr7", "Womens 7"), ("wrr8", "Womens 8"),
                       ("wrr10", "Womens 10")]:
        rows.append({"id": key, "section": "Women's Restrooms",
                     "name": label, "status": "pending", "note": ""})

    # Other walkable areas
    for key, label in [("mp1", "MP 1"), ("mp2", "MP 2"),
                       ("amol", "AM OL"), ("pmol", "PM OL"),
                       ("admin", "Admin"), ("trash1", "Trash 1"),
                       ("trash2", "Trash 2")]:
        rows.append({"id": key, "section": "Other Areas",
                     "name": label, "status": "pending", "note": ""})

    return rows


_INITIAL_ITEMS = _build_items()


class FloorState(AppState):
    # Checklist items — every item shares the same keys for rx.foreach
    walk_items: list[dict] = []

    # Walk lifecycle
    walk_started:    bool = False
    walk_completed:  bool = False
    started_at_ts:   str  = ""          # ISO timestamp when walk began
    saving:          bool = False

    # Inline flag flow — only one item flagged at a time
    flagging_id:  str = ""              # item currently being flagged
    flag_note:    str = ""              # note text for that item

    # ── Computed vars ─────────────────────────────────────────────────────────

    @rx.var
    def total_items(self) -> int:
        return len(self.walk_items)

    @rx.var
    def checked_count(self) -> int:
        return sum(1 for i in self.walk_items if i["status"] in ("ok", "flag"))

    @rx.var
    def flag_count(self) -> int:
        return sum(1 for i in self.walk_items if i["status"] == "flag")

    @rx.var
    def ok_count(self) -> int:
        return sum(1 for i in self.walk_items if i["status"] == "ok")

    @rx.var
    def skipped_count(self) -> int:
        return sum(1 for i in self.walk_items if i["status"] == "skipped")

    @rx.var
    def all_checked(self) -> bool:
        checked = sum(1 for i in self.walk_items if i["status"] in ("ok", "flag", "skipped"))
        return checked == self.total_items and self.total_items > 0

    @rx.var
    def progress_pct(self) -> int:
        if self.total_items == 0:
            return 0
        return int(self.checked_count / self.total_items * 100)

    @rx.var
    def duration_min(self) -> int:
        if not self.started_at_ts:
            return 0
        try:
            start = datetime.fromisoformat(self.started_at_ts)
            now   = datetime.now(timezone.utc)
            return max(1, int((now - start).total_seconds() / 60))
        except Exception:
            return 0

    @rx.var
    def sections(self) -> list[str]:
        seen: list[str] = []
        for item in self.walk_items:
            s = item["section"]
            if s not in seen:
                seen.append(s)
        return seen

    # ── Lifecycle events ──────────────────────────────────────────────────────

    @rx.event
    def init_walk(self):
        """Reset the checklist — called on page load."""
        self.walk_items    = [dict(item) for item in _INITIAL_ITEMS]
        self.walk_started  = False
        self.walk_completed = False
        self.started_at_ts = ""
        self.flagging_id   = ""
        self.flag_note     = ""
        self.saving        = False

    @rx.event
    def start_walk(self):
        self.walk_started  = True
        self.walk_completed = False
        self.started_at_ts = datetime.now(timezone.utc).isoformat()
        self.walk_items    = [dict(item) for item in _INITIAL_ITEMS]

    # ── Marking ───────────────────────────────────────────────────────────────

    @rx.event
    def mark_ok(self, item_id: str):
        """Mark an item green. Also cancel any in-progress flag for this item."""
        if self.flagging_id == item_id:
            self.flagging_id = ""
            self.flag_note   = ""
        self.walk_items = [
            {**item, "status": "ok", "note": ""}
            if item["id"] == item_id else item
            for item in self.walk_items
        ]

    @rx.event
    def start_flag(self, item_id: str):
        """Open the inline note input for this item."""
        self.flagging_id = item_id
        self.flag_note   = ""

    @rx.event
    def set_flag_note(self, value: str):
        self.flag_note = value

    @rx.event
    def cancel_flag(self):
        self.flagging_id = ""
        self.flag_note   = ""

    @rx.event
    async def confirm_flag(self):
        """Save the flag note to Supabase and mark the item red."""
        item_id = self.flagging_id
        note    = self.flag_note.strip()
        if not item_id:
            return

        # Find item name
        item_name = next(
            (i["name"] for i in self.walk_items if i["id"] == item_id), item_id
        )

        # Update local state immediately
        self.walk_items = [
            {**item, "status": "flag", "note": note}
            if item["id"] == item_id else item
            for item in self.walk_items
        ]
        self.flagging_id = ""
        self.flag_note   = ""
        yield

        # Save flag to Supabase in background
        import uuid
        save_note({
            "id":            f"note_{uuid.uuid4().hex[:12]}",
            "content":       f"{item_name}: {note}" if note else item_name,
            "content_type":  "flag",
            "sentiment":     "flag",
            "original_date": __import__("datetime").date.today().isoformat(),
            "author":        "brian",
            "captured_via":  "dashboard",
        })

    @rx.event
    def skip_item(self, item_id: str):
        """Mark an area as skipped/N/A for this walk — not flagged, not checked."""
        self.walk_items = [
            {**item, "status": "skipped"} if item["id"] == item_id else item
            for item in self.walk_items
        ]

    # ── Complete walk ─────────────────────────────────────────────────────────

    @rx.event
    async def complete_walk(self):
        """Save the floor walk summary note and mark walk done."""
        self.saving = True
        yield

        ok_areas = [i["name"] for i in self.walk_items if i["status"] == "ok"]
        flags    = [
            {"name": i["name"], "note": i["note"]}
            for i in self.walk_items if i["status"] == "flag"
        ]
        skipped_count = self.skipped_count
        save_floor_walk(ok_areas, flags, self.duration_min, skipped_count)

        self.walk_completed = True
        self.saving         = False
