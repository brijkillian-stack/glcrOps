"""
state/today.py — TodayState

Loads all data for the Today page from Supabase on page load.
Background polling task keeps data live without a manual refresh.
"""

import asyncio
import reflex as rx
from shared.base import AppState
from shared.db import (
    get_tonight_tasks,
    get_activity_feed,
    get_kpis,
    get_brewing_items,
    get_today_summary,
)

# How often the background task re-fetches data (seconds)
POLL_INTERVAL = 15


class TodayState(AppState):
    # ── Tonight column ────────────────────────────────────────────────────────
    tonight_tasks: list[dict] = []
    brewing_items: list[dict] = []

    # ── Activity column ───────────────────────────────────────────────────────
    activity_feed: list[dict] = []

    # ── Numbers column ────────────────────────────────────────────────────────
    kpi_captures_today:     int  = 0
    kpi_captures_delta:     str  = "—"
    kpi_captures_direction: str  = "flat"
    kpi_open_tasks:         int  = 0
    kpi_overdue_tasks:      int  = 0
    kpi_active_flags:       int  = 0
    kpi_flags_direction:    str  = "flat"
    kpi_backend_ok:         bool = False
    kpi_backend_latency:    str  = "—"

    # ── Page-level ────────────────────────────────────────────────────────────
    page_summary: str  = "Loading…"
    loading:      bool = True
    error:        str  = ""

    # ── Computed vars ─────────────────────────────────────────────────────────

    @rx.var
    def backend_status_label(self) -> str:
        if self.kpi_backend_ok:
            return f"Supabase · {self.kpi_backend_latency}"
        return "Backend unreachable"

    @rx.var
    def flags_delta_label(self) -> str:
        return f"▲ {self.kpi_active_flags} last 7 days"

    @rx.var
    def overdue_label(self) -> str:
        if self.kpi_overdue_tasks > 0:
            return f"▲ {self.kpi_overdue_tasks} overdue"
        return "None overdue"

    @rx.var
    def overdue_direction(self) -> str:
        return "down" if self.kpi_overdue_tasks > 0 else "flat"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _apply_data(self, tasks, feed, kpis, brewing, summary):
        """Apply fetched data to state vars. Called from both load and poll."""
        self.tonight_tasks          = tasks
        self.activity_feed          = feed
        self.brewing_items          = brewing
        self.page_summary           = summary
        self.kpi_captures_today     = kpis["captures_today"]
        self.kpi_captures_delta     = kpis["captures_delta"]
        self.kpi_captures_direction = kpis["captures_direction"]
        self.kpi_open_tasks         = kpis["open_tasks"]
        self.kpi_overdue_tasks      = kpis["overdue_tasks"]
        self.kpi_active_flags       = kpis["active_flags"]
        self.kpi_backend_ok         = kpis["backend_ok"]
        self.kpi_backend_latency    = (
            f"{kpis['backend_latency_ms']}ms" if kpis["backend_ok"] else "—"
        )

    # ── Events ────────────────────────────────────────────────────────────────

    @rx.event
    async def load_today(self):
        """Initial page load — fetches all Today data from Supabase."""
        self.loading = True
        self.error   = ""
        yield

        try:
            self._apply_data(
                get_tonight_tasks(),
                get_activity_feed(since_days=2, limit=4),
                get_kpis(),
                get_brewing_items(),
                get_today_summary(),
            )
        except Exception as exc:
            self.error = str(exc)
        finally:
            self.loading = False

    @rx.event
    async def reload_today(self):
        """Manual refresh button."""
        yield TodayState.load_today

    @rx.event
    async def mark_complete_tonight(self, task_id: str):
        """Quick-complete a task from the Today page. Removes it optimistically."""
        from shared.db import complete_task
        self.tonight_tasks = [t for t in self.tonight_tasks if t.get("id") != task_id]
        self.kpi_open_tasks = max(0, self.kpi_open_tasks - 1)
        complete_task(task_id)

    @rx.event(background=True)
    async def start_live_updates(self):
        """
        Background task started on page load alongside load_today.
        Subscribes to Supabase Realtime on the notes table.
        On INSERT/UPDATE, refreshes Today data. Falls back to polling every 30s if
        Realtime fails, ensuring the page stays live even if the subscription drops.
        """
        from shared.db import get_client

        await asyncio.sleep(POLL_INTERVAL)  # let load_today finish first

        fallback_poll_count = 0

        while True:
            try:
                sb = get_client()

                # Try to establish a Realtime subscription
                channel = sb.realtime.channel("notes_changes")

                # Define callback to refresh on note changes
                def on_note_change(payload):
                    """Callback fired on INSERT/UPDATE to the notes table."""
                    try:
                        tasks = get_tonight_tasks()
                        feed = get_activity_feed(since_days=2, limit=4)
                        kpis = get_kpis()
                        brewing = get_brewing_items()
                        summary = get_today_summary()

                        # Update state synchronously within Reflex's event loop
                        # Note: this runs server-side, no need for async with
                        self.tonight_tasks = tasks
                        self.activity_feed = feed
                        self.brewing_items = brewing
                        self.page_summary = summary
                        self.kpi_captures_today = kpis["captures_today"]
                        self.kpi_captures_delta = kpis["captures_delta"]
                        self.kpi_captures_direction = kpis["captures_direction"]
                        self.kpi_open_tasks = kpis["open_tasks"]
                        self.kpi_overdue_tasks = kpis["overdue_tasks"]
                        self.kpi_active_flags = kpis["active_flags"]
                        self.kpi_backend_ok = kpis["backend_ok"]
                        self.kpi_backend_latency = (
                            f"{kpis['backend_latency_ms']}ms" if kpis["backend_ok"] else "—"
                        )
                        fallback_poll_count = 0  # reset fallback counter on success
                    except Exception as exc:
                        self.error = f"Realtime update error: {str(exc)}"

                # Subscribe to all INSERT/UPDATE/DELETE on the notes table
                channel.on_postgres_changes(
                    event="*",
                    schema="public",
                    table="notes",
                    callback=on_note_change,
                ).subscribe()

                # Keep the subscription open; if it disconnects, the exception
                # handler will log it and the fallback polling loop will continue
                await asyncio.sleep(300)  # check subscription every 5 minutes

            except Exception as exc:
                # Realtime failed or subscription dropped.
                # Fall back to polling every 30 seconds (less aggressive than 15s).
                fallback_poll_count += 1
                if fallback_poll_count == 1:
                    # Log once per failure burst
                    async with self:
                        self.error = f"Realtime unavailable; polling every 30s. ({str(exc)[:50]}…)"

                try:
                    tasks = get_tonight_tasks()
                    feed = get_activity_feed(since_days=2, limit=4)
                    kpis = get_kpis()
                    brewing = get_brewing_items()
                    summary = get_today_summary()

                    async with self:
                        self._apply_data(tasks, feed, kpis, brewing, summary)
                except Exception as poll_exc:
                    async with self:
                        self.error = str(poll_exc)

                await asyncio.sleep(30)  # fallback polling interval
