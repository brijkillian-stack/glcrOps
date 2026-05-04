"""
state/search.py — SearchState

Manages the Search page: query text, kind filter, results list, and
recent-search history.

Search fires automatically when the query is >= 2 characters (debounced
250 ms). A filter change re-runs the current query without debounce.
Recent searches are kept in memory for the session (last 8 unique queries
that returned at least one result).
"""

import asyncio
import reflex as rx
from shared.base import AppState
from shared.db import search_all

_MAX_RECENT = 8


class SearchState(AppState):
    # ── State vars ────────────────────────────────────────────────────────────
    query:           str        = ""
    kind_filter:     str        = "all"   # all | notes | tasks | people
    results:         list[dict] = []
    loading:         bool       = False
    has_searched:    bool       = False   # True once the user has typed >= 2 chars
    recent_searches: list[str]  = []      # Most-recent first, max _MAX_RECENT

    # ── Computed vars ─────────────────────────────────────────────────────────

    @rx.var
    def result_count(self) -> int:
        return len(self.results)

    @rx.var
    def notes_count(self) -> int:
        return sum(1 for r in self.results if r["kind"] == "note")

    @rx.var
    def tasks_count(self) -> int:
        return sum(1 for r in self.results if r["kind"] == "task")

    @rx.var
    def people_count(self) -> int:
        return sum(1 for r in self.results if r["kind"] == "person")

    @rx.var
    def status_line(self) -> str:
        if self.loading:
            return "Searching…"
        if not self.has_searched or not self.query.strip():
            return "Type to search notes, tasks, and team members."
        if not self.results:
            return f"No results for \"{self.query}\"."
        n = self.result_count
        return f"{n} result{'s' if n != 1 else ''} for \"{self.query}\""

    @rx.var
    def show_empty(self) -> bool:
        return self.has_searched and not self.loading and not self.results

    @rx.var
    def show_results(self) -> bool:
        return bool(self.results) and not self.loading

    @rx.var
    def show_recent(self) -> bool:
        """True when we should render the recent-searches row in the hero."""
        return not self.has_searched and not self.loading and len(self.recent_searches) > 0

    # ── Events ────────────────────────────────────────────────────────────────

    @rx.event
    async def set_query(self, value: str):
        self.query = value
        if len(value.strip()) < 2:
            self.results      = []
            self.has_searched = False
            self.loading      = False
            return
        # Small debounce: yield so the input re-renders, then search
        self.loading = True
        yield
        await asyncio.sleep(0.25)
        # If the query changed while we were sleeping, abort
        if self.query != value:
            return
        self._do_search()

    @rx.event
    def set_kind_filter(self, value: str):
        self.kind_filter = value
        if self.query.strip() and len(self.query.strip()) >= 2:
            self.loading = True
            self._do_search()

    @rx.event
    def clear_search(self):
        self.query        = ""
        self.results      = []
        self.has_searched = False
        self.loading      = False

    @rx.event
    async def apply_recent(self, term: str):
        """Load a recent search term and immediately run the query."""
        self.query   = term
        self.loading = True
        yield
        self._do_search()

    @rx.event
    def remove_recent(self, term: str):
        """Remove a single entry from the recent-searches list."""
        self.recent_searches = [r for r in self.recent_searches if r != term]

    @rx.event
    def clear_recent(self):
        self.recent_searches = []

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _do_search(self):
        """Runs the DB query, updates results, and records recent search."""
        try:
            hits              = search_all(self.query, self.kind_filter)
            self.results      = hits
            self.has_searched = True
            # Record in recent searches only when results were found
            if hits:
                term = self.query.strip()
                # Deduplicate (remove existing occurrence, prepend fresh)
                deduped = [r for r in self.recent_searches if r.lower() != term.lower()]
                self.recent_searches = ([term] + deduped)[:_MAX_RECENT]
        except Exception as exc:
            print(f"[SearchState] search error: {exc}")
            self.results = []
        finally:
            self.loading = False
