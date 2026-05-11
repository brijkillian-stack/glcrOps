"""pytest fixtures for ZDS Forge API tests.

All fixtures are async-compatible via pytest-asyncio with asyncio_mode="auto"
(configured in pyproject.toml or pytest.ini — see note below).

Supabase is mocked via a FakeSupabase class that chains method calls and
returns pre-baked fixture data.  The point is NOT to test Supabase itself,
but to verify that PlacementService correctly:
  - translates DB rows into Pydantic models
  - caches results and returns cached copies without re-hitting the DB
  - invalidates the right keys after writes
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

from apps.zds.api.services.cache_service import CacheService
from apps.zds.api.services.placement_service import PlacementService

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ── Fixture data ──────────────────────────────────────────────────────────────

def load_fixture(name: str) -> Any:
    """Load a JSON fixture file from the fixtures/ directory."""
    return json.loads((FIXTURES_DIR / name).read_text())


@pytest.fixture(scope="session")
def week_fixture():
    return load_fixture("week_2026_05_14.json")


@pytest.fixture(scope="session")
def tasks_fixture():
    return load_fixture("tasks_canonical.json")


# ── Fake Supabase client ──────────────────────────────────────────────────────

class FakeQueryBuilder:
    """Fluent fake that records calls and returns canned data on .execute().

    Tracks whether `.maybe_single()` was called so that execute() returns
    a single dict (first item) rather than a list — matching the supabase-py
    behaviour where `.maybe_single().execute().data` is a dict or None.
    """

    def __init__(self, data=None, call_tracker=None):
        self._data = data if data is not None else []
        self._call_tracker = call_tracker or []
        self._single = False

    def select(self, *a, **kw):   return self
    def eq(self, *a, **kw):       return self
    def neq(self, *a, **kw):      return self
    def order(self, *a, **kw):    return self
    def limit(self, *a, **kw):    return self
    def upsert(self, *a, **kw):   return self
    def insert(self, *a, **kw):   return self
    def update(self, *a, **kw):   return self
    def delete(self, *a, **kw):   return self
    def is_(self, *a, **kw):      return self
    def or_(self, *a, **kw):      return self
    def not_(self):                return self
    def in_(self, *a, **kw):      return self

    def maybe_single(self, *a, **kw):
        self._single = True
        return self

    def execute(self):
        self._call_tracker.append("execute")
        result = MagicMock()
        if self._single:
            # Return first item of list, or the raw value if already a dict.
            if isinstance(self._data, list):
                result.data = self._data[0] if self._data else None
            else:
                result.data = self._data  # already a single dict or None
        elif isinstance(self._data, list):
            result.data = self._data
        else:
            result.data = self._data
        return result


class FakeSupabase:
    """Minimal supabase.Client stand-in that routes table() calls to fixture data."""

    def __init__(self, table_data: dict[str, Any]):
        """
        Parameters
        ----------
        table_data:
            Map of table_name → data to return from .execute().
            Data can be a list (multi-row) or a single dict (single-row).
        """
        self._table_data = table_data
        self.call_counts: dict[str, int] = {}

    def table(self, name: str) -> FakeQueryBuilder:
        self.call_counts[name] = self.call_counts.get(name, 0) + 1
        data = self._table_data.get(name, [])
        tracker: list = []
        return FakeQueryBuilder(data=data, call_tracker=tracker)


# ── In-memory CacheService ────────────────────────────────────────────────────

class InMemoryRedis:
    """Minimal Redis substitute backed by a Python dict.

    Supports get/set/delete/scan for testing CacheService without a real
    Redis process.
    """

    def __init__(self):
        self._store: dict[str, str] = {}

    def get(self, key: str) -> Optional[str]:
        return self._store.get(key)

    def set(self, key: str, value: str, ex: int = None):
        self._store[key] = value

    def delete(self, *keys: str) -> int:
        deleted = 0
        for k in keys:
            if k in self._store:
                del self._store[k]
                deleted += 1
        return deleted

    def scan(self, cursor: int = 0, match: str = "*", count: int = 100):
        """Fake SCAN: returns all matching keys in one shot (cursor=0 always)."""
        import fnmatch
        matching = [k for k in self._store if fnmatch.fnmatch(k, match)]
        return (0, matching)  # cursor=0 → done in one batch

    def ping(self):
        return True


@pytest.fixture
def in_memory_redis():
    return InMemoryRedis()


@pytest.fixture
def cache_service(in_memory_redis):
    return CacheService(redis_client=in_memory_redis)


@pytest.fixture
def null_cache():
    """CacheService with no Redis — all operations are no-ops."""
    return CacheService(redis_client=None)


# ── PlacementService with fake DB ─────────────────────────────────────────────

@pytest.fixture
def placement_service(cache_service, week_fixture, tasks_fixture):
    """PlacementService wired to in-memory cache and fake Supabase.

    table_data mirrors what the real Supabase client would return.
    """
    fx = week_fixture
    fake_supabase = FakeSupabase({
        "weeks":   fx["week"],        # single-row for .maybe_single()
        "nights":  fx["nights"],
        "zone_assignments": fx["assignments"],
        "entities": fx["tms"],
        "engine_overrides": [],
        "multi_area_assignments": [],
    })

    svc = PlacementService(supabase=fake_supabase, cache=cache_service)

    # Patch the lazy _db / _shared_db with thin fakes so we don't need
    # the full Reflex app on sys.path during unit tests.
    class FakeZdsDb:
        def __init__(self, fx):
            self._fx = fx
            self.call_count = 0

        def fetch_week(self, week_id):
            self.call_count += 1
            # Return a dict with week_ending so invalidate_night can build anno keys.
            return self._fx["week"]

        def fetch_nights(self, week_id):
            self.call_count += 1
            return self._fx["nights"]

        def fetch_zone_assignments(self, night_id):
            self.call_count += 1
            return self._fx["assignments"]

        def fetch_overlap_assignments(self, night_id):
            self.call_count += 1
            return []

    class FakeSharedDb:
        def __init__(self, tasks):
            self._tasks = tasks
            self.call_count = 0

        def list_tasks(self, category=None, active_only=True, include_overlap=True):
            self.call_count += 1
            return self._tasks

        def upsert_task(self, data):
            self.call_count += 1
            return {**self._tasks[0], **data}

        def list_annotations_grouped(self, week_ending, day):
            self.call_count += 1
            return {"task": {"task-sweep-001": {"highlight": {"color": "yellow"}}}}

        def upsert_annotation(self, week_ending, day, target_kind, target_ref,
                              annotation_kind, value, created_by=None):
            self.call_count += 1
            return {
                "id": "anno-001",
                "week_ending": str(week_ending),
                "day": day,
                "target_kind": target_kind,
                "target_ref": target_ref,
                "annotation_kind": annotation_kind,
                "value": value,
                "created_by": created_by,
                "created_at": "2026-05-08T22:00:00Z",
                "updated_at": "2026-05-08T22:00:00Z",
            }

        def delete_annotation(self, week_ending, day, target_kind, target_ref, annotation_kind):
            self.call_count += 1
            return True

    svc._db = FakeZdsDb(fx)
    svc._shared_db = FakeSharedDb(tasks_fixture)

    return svc
