"""
state/recap.py — ShiftRecapState  (Phase L rewrite)

Manages the Shift Recap page. Re-architected around the actual email format
Brian sends to Group - Operations Department, which has six sections:

  1. Team Updates       (Days / Swings / Graves / Utilities / BCOs / BEOs)
  2. Overlaps           (Graves / Swings / Days)
  3. MPulse / AC / Uniforms
  4. Huddle attendance
  5. Shift & Floor Walk Notes (narrative)

Each section is an editable text field. Auto-population (Phase L.2) pulls
from Supabase for the sections we have data for; the rest are typed in.
"""

from datetime import date
import reflex as rx

from shared.base import AppState
from shared.db import (
    get_shift_timeline,
    get_recap_auto_populate,   # new in Phase L.2 — see shared/db.py
)


class ShiftRecapState(AppState):
    # Date the recap covers (defaults to today on load)
    shift_date: str = ""

    # Chronological list of tonight's notes (left column)
    timeline: list[dict] = []

    # ── Editable sections (Phase L.1) ─────────────────────────────────────────
    # Team Updates — six sub-sections, each a free-text string
    team_days:      str = ""
    team_swings:    str = ""
    team_graves:    str = ""
    team_utilities: str = ""
    team_bcos:      str = ""
    team_beos:      str = ""

    # Overlaps — one block per shift, each a multi-line bulleted list
    overlap_graves: str = ""
    overlap_swings: str = ""
    overlap_days:   str = ""

    # Operational systems — usually short or "None"
    mpulse:         str = ""
    access_control: str = ""
    uniforms:       str = ""

    # Huddle attendance — "Zach, Melissa, Darlene were in huddle today."
    huddle: str = ""

    # Free-form narrative — the bulk of the email
    floor_walk_notes: str = ""

    # ── Compiled output ───────────────────────────────────────────────────────
    # Built on-demand by `compile_draft`; this is what gets pasted into Outlook.
    draft: str = ""

    loading:    bool = True
    refreshing: bool = False    # Refresh-from-data spinner
    compiling:  bool = False
    copy_done:  bool = False    # flash feedback on copy

    # =========================================================================
    # Computed vars
    # =========================================================================

    @rx.var
    def timeline_count(self) -> int:
        return len(self.timeline)

    @rx.var
    def date_display(self) -> str:
        if not self.shift_date:
            return ""
        try:
            from datetime import datetime
            dt = datetime.strptime(self.shift_date, "%Y-%m-%d")
            # Matches the email convention: "Sunday | May 03, 2026"
            return dt.strftime("%A | %B %d, %Y")
        except Exception:
            return self.shift_date

    @rx.var
    def draft_ready(self) -> bool:
        return bool(self.draft.strip())

    @rx.var
    def email_subject(self) -> str:
        if not self.shift_date:
            return "Grave Shift Recap"
        try:
            from datetime import datetime
            dt = datetime.strptime(self.shift_date, "%Y-%m-%d")
            return f"Grave Shift Recap — {dt.strftime('%A | %B %d, %Y')}"
        except Exception:
            return f"Grave Shift Recap — {self.shift_date}"

    @rx.var
    def mailto_href(self) -> str:
        """Pre-composed mailto: link for opening recap in Outlook."""
        import urllib.parse
        subj = urllib.parse.quote(self.email_subject)
        body_text = self.draft[:1800] if self.draft else ""
        if self.draft and len(self.draft) > 1800:
            body_text += "\n\n[Truncated — paste full recap from dashboard]"
        body = urllib.parse.quote(body_text)
        return f"mailto:?subject={subj}&body={body}"

    # =========================================================================
    # Setters — one per section so the textareas can two-way bind
    # =========================================================================

    @rx.event
    def set_team_days(self, v: str):      self.team_days = v
    @rx.event
    def set_team_swings(self, v: str):    self.team_swings = v
    @rx.event
    def set_team_graves(self, v: str):    self.team_graves = v
    @rx.event
    def set_team_utilities(self, v: str): self.team_utilities = v
    @rx.event
    def set_team_bcos(self, v: str):      self.team_bcos = v
    @rx.event
    def set_team_beos(self, v: str):      self.team_beos = v

    @rx.event
    def set_overlap_graves(self, v: str): self.overlap_graves = v
    @rx.event
    def set_overlap_swings(self, v: str): self.overlap_swings = v
    @rx.event
    def set_overlap_days(self, v: str):   self.overlap_days   = v

    @rx.event
    def set_mpulse(self, v: str):         self.mpulse         = v
    @rx.event
    def set_access_control(self, v: str): self.access_control = v
    @rx.event
    def set_uniforms(self, v: str):       self.uniforms       = v

    @rx.event
    def set_huddle(self, v: str):           self.huddle           = v
    @rx.event
    def set_floor_walk_notes(self, v: str): self.floor_walk_notes = v

    @rx.event
    def set_draft(self, value: str):
        """Direct edit on the compiled draft textarea."""
        self.draft = value

    # =========================================================================
    # Load + refresh
    # =========================================================================

    @rx.event
    async def load_recap(self):
        """Load timeline + auto-populate sections from Supabase data."""
        if not self.shift_date:
            self.shift_date = date.today().isoformat()
        self.loading = True
        yield
        self.timeline = get_shift_timeline(self.shift_date)
        # Phase L.2 — pull section data on first load
        self._apply_auto_populate(get_recap_auto_populate(self.shift_date))
        self._compile_in_place()
        self.loading = False

    @rx.event
    async def change_date(self, value: str):
        """Switch to a different shift date and reload everything."""
        self.shift_date = value
        self.draft = ""
        self.loading = True
        yield
        self.timeline = get_shift_timeline(self.shift_date)
        self._apply_auto_populate(get_recap_auto_populate(self.shift_date))
        self._compile_in_place()
        self.loading = False

    @rx.event
    async def refresh_from_data(self):
        """Re-pull Supabase data and merge into the section fields.

        Manual edits in any section that has new auto-data are OVERWRITTEN —
        this is the user explicitly asking for a fresh pull. If you want to
        keep your manual edits, just don't click Refresh.
        """
        self.refreshing = True
        yield
        self._apply_auto_populate(get_recap_auto_populate(self.shift_date))
        self._compile_in_place()
        self.refreshing = False

    def _apply_auto_populate(self, data: dict) -> None:
        """Apply a dict of auto-populated section text. Empty strings are
        skipped — we don't blow away manual entry with empty queries."""
        # Team Updates
        if data.get("team_graves"):  self.team_graves = data["team_graves"]
        if data.get("team_beos"):    self.team_beos   = data["team_beos"]
        # Overlaps
        if data.get("overlap_graves"): self.overlap_graves = data["overlap_graves"]
        # Narrative — concatenate captured observations as a starting draft
        if data.get("floor_walk_notes"): self.floor_walk_notes = data["floor_walk_notes"]

    # =========================================================================
    # Compile draft
    # =========================================================================

    @rx.event
    async def compile_draft(self):
        """Rebuild self.draft from section fields."""
        self.compiling = True
        yield
        self._compile_in_place()
        self.compiling = False

    def _compile_in_place(self) -> None:
        """Internal compile — same as compile_draft but without the spinner."""
        self.draft = self._format_recap()

    def _format_recap(self) -> str:
        """Stringify all section fields into the email-ready format."""
        try:
            from datetime import datetime
            dt = datetime.strptime(self.shift_date, "%Y-%m-%d")
            date_str = dt.strftime("%A | %B %d, %Y")
        except Exception:
            date_str = self.shift_date or ""

        def block(label: str, value: str, default: str = "None.") -> str:
            v = (value or "").strip()
            return f"{label}: {v if v else default}"

        parts: list[str] = []
        parts.append("Grave Shift Recap")
        parts.append(f"Date: {date_str}")
        parts.append("")
        parts.append("Team Updates")
        parts.append(block("Days",      self.team_days,      "None"))
        parts.append(block("Swings",    self.team_swings,    "None"))
        parts.append(block("Graves",    self.team_graves,    "None"))
        parts.append(block("Utilities", self.team_utilities, "None"))
        parts.append(block("BCOs",      self.team_bcos,      "None"))
        parts.append(block("BEOs",      self.team_beos,      "None"))
        parts.append("")
        parts.append("Overlaps")
        parts.append("Graves:")
        parts.append((self.overlap_graves or "").rstrip() or "  None.")
        parts.append("")
        parts.append("Swings:")
        parts.append((self.overlap_swings or "").rstrip() or "  None.")
        parts.append("")
        parts.append("Days:")
        parts.append((self.overlap_days or "").rstrip() or "  None.")
        parts.append("")
        parts.append("MPulse, Access Control, and Uniform Updates")
        parts.append(block("MPulse",         self.mpulse,         "None"))
        parts.append(block("Access Control", self.access_control, "None"))
        parts.append(block("Uniforms",       self.uniforms,       "None"))
        parts.append("")
        parts.append("Huddle")
        parts.append((self.huddle or "").strip() or "None.")
        parts.append("")
        parts.append("Shift & Floor Walk Notes")
        parts.append((self.floor_walk_notes or "").strip()
                     or "No narrative recorded for this shift.")
        return "\n".join(parts)

    # =========================================================================
    # Copy
    # =========================================================================

    @rx.event
    async def copy_draft(self):
        """Flash copy feedback — actual clipboard write happens client-side."""
        self.copy_done = True
        yield rx.set_clipboard(self.draft)
        import asyncio
        await asyncio.sleep(1.5)
        self.copy_done = False
