"""
state/areas.py — AreasState

Manages the areas grid page where Brian can quickly drop notes on individual zones
and restrooms without doing a full floor walk. Each area tile shows the recent note
count and can be tapped to open an inline note-capture form.
"""

import asyncio
import reflex as rx
from shared.base import AppState
from shared.db import list_areas_with_counts, save_area_note as db_save_area_note


class AreasState(AppState):
    areas: list[dict] = []                # all 28 areas with their counts
    loading: bool = True
    selected_area_id: str = ""            # which tile is currently expanded; "" = none
    note_content: str = ""                # the textarea value
    note_sentiment: str = "neutral"       # chip selector
    saving: bool = False
    just_saved_id: str = ""               # green flash target

    @rx.event
    async def load_areas(self):
        """Load all areas with note counts on page load."""
        self.loading = True
        yield
        self.areas = list_areas_with_counts()
        self.loading = False

    @rx.event
    def select_area(self, area_id: str):
        """Open the note form for this area."""
        self.selected_area_id = area_id
        self.note_content = ""
        self.note_sentiment = "neutral"

    @rx.event
    def cancel_note(self):
        """Close the note form without saving."""
        self.selected_area_id = ""
        self.note_content = ""
        self.note_sentiment = "neutral"

    @rx.event
    def set_note_content(self, value: str):
        """Update the note textarea."""
        self.note_content = value

    @rx.event
    def set_sentiment(self, value: str):
        """Update the sentiment chip selector."""
        self.note_sentiment = value

    @rx.event
    async def save_area_note(self):
        """Save the note to Supabase and refresh counts."""
        if not self.selected_area_id or not self.note_content.strip():
            return

        self.saving = True
        yield

        area_id = self.selected_area_id
        success = db_save_area_note(area_id, self.note_content, self.note_sentiment)

        if success:
            self.just_saved_id = area_id
            # Refresh the areas list to update counts
            self.areas = list_areas_with_counts()
            self.selected_area_id = ""
            self.note_content = ""
            self.note_sentiment = "neutral"
            yield
            # Clear the flash after 600ms
            await asyncio.sleep(0.6)
            self.just_saved_id = ""

        self.saving = False

    @rx.var
    def main_floor_areas(self) -> list[dict]:
        """Main Floor areas."""
        return [a for a in self.areas if a.get("section") == "Main Floor"]

    @rx.var
    def mens_restroom_areas(self) -> list[dict]:
        """Men's Restrooms areas."""
        return [a for a in self.areas if a.get("section") == "Men's Restrooms"]

    @rx.var
    def womens_restroom_areas(self) -> list[dict]:
        """Women's Restrooms areas."""
        return [a for a in self.areas if a.get("section") == "Women's Restrooms"]

    @rx.var
    def other_areas_list(self) -> list[dict]:
        """Other Areas."""
        return [a for a in self.areas if a.get("section") == "Other Areas"]
