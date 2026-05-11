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

    # ── Quick Area Check (Phase M) ───────────────────────────────────────────
    # Floor-walk spot-rating overlay. Brian taps the FAB → picks an area →
    # the assigned TM is auto-resolved from tonight's deployment → he scores
    # 1-10 and saves. The row writes to area_checks with both area_key and
    # tm_id so trends are queryable from either side.
    area_check_open: bool = False
    area_check_step: str = "pick"           # "pick" → "rate"
    area_check_area_key: str = ""
    area_check_area_side: str = ""
    area_check_area_label: str = ""
    area_check_tm_id: str = ""
    area_check_tm_name: str = ""
    area_check_score: int = 0
    area_check_note: str = ""
    area_check_saving: bool = False
    area_check_saved: bool = False
    area_check_error: str = ""

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
        """Write the capture form to Supabase, then refresh Today data.

        Phase A (2026-05-12): TodayState lives in apps.glcr which is archived.
        Import is guarded; save still persists to DB but the Today panel refresh
        is skipped until GLCR is rebuilt on the new stack.
        """
        import uuid
        from shared.db import save_note
        try:
            from apps.glcr.state.today import TodayState
            _today_state_available = True
        except ImportError:
            _today_state_available = False

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
            if _today_state_available:
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

    # =========================================================================
    # Quick Area Check (Phase M)
    # =========================================================================

    @rx.event
    def open_area_check(self):
        """Reset state and open the Quick Area Check overlay on the picker step."""
        self.area_check_open       = True
        self.area_check_step       = "pick"
        self.area_check_area_key   = ""
        self.area_check_area_side  = ""
        self.area_check_area_label = ""
        self.area_check_tm_id      = ""
        self.area_check_tm_name    = ""
        self.area_check_score      = 0
        self.area_check_note       = ""
        self.area_check_saved      = False
        self.area_check_error      = ""

    @rx.event
    def close_area_check(self):
        self.area_check_open = False

    @rx.event
    def pick_area_check_area(self, area_key: str, rr_side: str, label: str):
        """User selected an area in the picker — resolve tonight's assigned TM
        and advance to the rating step."""
        from datetime import date as _date
        from shared.db import fetch_assigned_tm_for_area

        self.area_check_area_key   = area_key
        self.area_check_area_side  = rr_side or ""
        self.area_check_area_label = label
        self.area_check_score      = 0
        self.area_check_note       = ""
        self.area_check_error      = ""

        tonight = _date.today().isoformat()
        info = fetch_assigned_tm_for_area(area_key, rr_side or "", tonight)
        self.area_check_tm_id   = info.get("tm_id", "") if info else ""
        self.area_check_tm_name = info.get("display_name", "") if info else ""
        self.area_check_step    = "rate"

    @rx.event
    def set_area_check_score(self, score: int):
        self.area_check_score = int(score)

    @rx.event
    def set_area_check_note(self, value: str):
        self.area_check_note = value

    @rx.event
    def back_to_area_picker(self):
        """User wants to pick a different area — return to the picker step."""
        self.area_check_step = "pick"

    @rx.event
    async def save_area_check(self):
        """Write the area check to Supabase. Closes the overlay on success."""
        from datetime import date as _date
        from shared.db import insert_area_check

        if not self.area_check_area_key or not (1 <= self.area_check_score <= 10):
            self.area_check_error = "Pick an area and a 1-10 score."
            return
        self.area_check_saving = True
        self.area_check_error  = ""
        yield
        ok = insert_area_check(
            area_key=self.area_check_area_key,
            rr_side=self.area_check_area_side,
            score=self.area_check_score,
            tm_id=self.area_check_tm_id or "",
            note=self.area_check_note or "",
            night_date=_date.today().isoformat(),
        )
        self.area_check_saving = False
        if ok:
            self.area_check_saved = True
            self.area_check_open  = False
        else:
            self.area_check_error = "Failed to save area check. Try again."
