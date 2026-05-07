"""
apps/admin/state.py — AdminHubState

Loads lightweight counts for the Sudo Admin hub cards.
Called via on_load when /admin renders.
"""

from __future__ import annotations

import datetime

import reflex as rx


class AdminHubState(rx.State):
    """Hub-level state: cheap counts for the hub card chips."""

    logs_recent: int = 0    # events captured in the last 7 days (Logs card)
    loading: bool = False

    @rx.event
    async def load_hub(self):
        """Fetch counts. One cheap SELECT count(*) query."""
        self.loading = True
        try:
            from shared.db import get_client

            sb = get_client()
            since = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()

            # Recent events (Logs card) — last 7 days
            r = (
                sb.table("events")
                .select("id", count="exact")
                .gte("event_date", since)
                .execute()
            )
            self.logs_recent = r.count or 0

        except Exception:
            pass
        finally:
            self.loading = False
