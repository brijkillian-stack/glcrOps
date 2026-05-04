"""
state/base.py — AppState

Shared state: command palette, capture modal, active nav route.
All page states inherit from this.
"""

import reflex as rx
from datetime import date


class AppState(rx.State):
    # ── Navigation ───────────────────────────────────────────────────────────
    active_route: str = "/"

    # ── Privacy mode ─────────────────────────────────────────────────────────
    # When True, personal content (TM names, note text) is blurred on Today page.
    privacy_mode: bool = False

    # ── Dark mode ────────────────────────────────────────────────────────────
    dark_mode: bool = False

    # ── Command palette ──────────────────────────────────────────────────────
    palette_open: bool = False
    palette_query: str = ""

    # ── Capture modal ────────────────────────────────────────────────────────
    capture_open: bool = False
    capture_content: str = ""
    capture_type: str = "observation"
    capture_sentiment: str = "neutral"
    capture_entities: str = ""
    capture_date: str = ""
    capture_saving: bool = False
    capture_saved: bool = False

    # ── Computed ─────────────────────────────────────────────────────────────

    @rx.var
    def today_label(self) -> str:
        """e.g. 'Sunday, May 3 · Graves'"""
        d = date.today()
        day_name = d.strftime("%A")
        month_name = d.strftime("%B")
        day_num = d.day
        return f"{day_name}, {month_name} {day_num} · Graves"

    @rx.var
    def capture_date_default(self) -> str:
        return date.today().isoformat()

    @rx.event
    def toggle_privacy(self):
        self.privacy_mode = not self.privacy_mode

    @rx.event
    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode

    @rx.var
    def app_class_name(self) -> str:
        return "app dark" if self.dark_mode else "app"

    # ── Palette events ───────────────────────────────────────────────────────

    @rx.event
    def open_palette(self):
        self.palette_open = True
        self.palette_query = ""

    @rx.event
    def close_palette(self):
        self.palette_open = False

    @rx.event
    def set_palette_query(self, value: str):
        self.palette_query = value

    # ── Capture modal events ─────────────────────────────────────────────────

    @rx.event
    def open_capture(self):
        self.capture_open = True
        self.capture_saved = False
        self.capture_content = ""
        self.capture_date = date.today().isoformat()

    @rx.event
    def open_capture_for(self, name: str):
        """Open capture pre-filled with a TM's name so it's ready to type after."""
        self.capture_open = True
        self.capture_saved = False
        self.capture_content = f"{name} — "
        self.capture_date = date.today().isoformat()

    @rx.event
    def open_capture_typed(self, content_type: str, prefix: str):
        """Open capture with a specific content_type and optional text prefix."""
        self.capture_open = True
        self.capture_saved = False
        self.capture_type = content_type
        self.capture_content = prefix
        self.capture_date = date.today().isoformat()

    @rx.event
    def close_capture(self):
        self.capture_open = False
        self.capture_content = ""
        self.capture_type = "observation"
        self.capture_sentiment = "neutral"
        self.capture_entities = ""
        self.capture_saved = False

    @rx.event
    async def save_capture(self):
        """Write the capture form to Supabase, then refresh Today data."""
        import uuid
        from ..db import save_note
        from .today import TodayState

        if not self.capture_content.strip():
            return  # nothing to save

        note_id = f"note_{uuid.uuid4().hex[:12]}"
        ok = save_note({
            "id":           note_id,
            "content":      self.capture_content.strip(),
            "content_type": self.capture_type,
            "sentiment":    self.capture_sentiment,
            "original_date": self.capture_date or None,
            "author":       "brian",
            "captured_via": "dashboard",
        })
        if ok:
            self.capture_saved = True
            self.capture_open  = False
            self.capture_content  = ""
            self.capture_type     = "observation"
            self.capture_sentiment = "neutral"
            self.capture_entities = ""
            yield TodayState.load_today   # immediate refresh

    @rx.event
    def set_capture_content(self, value: str):
        self.capture_content = value

    @rx.event
    def set_capture_type(self, value: str):
        self.capture_type = value

    @rx.event
    def set_capture_sentiment(self, value: str):
        self.capture_sentiment = value

    @rx.event
    def set_capture_entities(self, value: str):
        self.capture_entities = value

    @rx.event
    def set_capture_date(self, value: str):
        self.capture_date = value
