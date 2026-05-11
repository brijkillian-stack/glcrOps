"""Unit tests for PlacementService — uses fake db + fake cache.

Tests cover:
* Cache hits short-circuit the db call
* Cache misses populate the cache for the next read
* Graceful degradation: works when the cache layer is disabled (no Redis)
* db loader exceptions return the documented default (not a raise)
* invalidate_* hooks clear the right keys
"""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from apps.zds.api.services.cache_service import CacheService
from apps.zds.api.services.placement_service import PlacementService


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ex=None):
        self.store[key] = value
        return True

    def delete(self, *keys):
        n = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                n += 1
        return n

    def scan_iter(self, match=None):
        prefix = (match or "").rstrip("*")
        return [k for k in list(self.store.keys()) if k.startswith(prefix)]


def _fake_db(*, weeks=None, week=None, nights=None, assignments=None,
             overlaps=None, notices=None, overrides=None,
             fail_for: str | None = None):
    """Build a SimpleNamespace that quacks like apps.zds.database."""

    def _maybe_fail(name):
        if fail_for == name:
            raise RuntimeError(f"simulated {name} failure")

    return SimpleNamespace(
        fetch_weeks=lambda: (_maybe_fail("weeks") or (weeks or [])),
        fetch_week=lambda wid: (_maybe_fail("week") or (week or {})),
        fetch_nights=lambda wid: (_maybe_fail("nights") or (nights or [])),
        fetch_zone_assignments=lambda nid: (
            _maybe_fail("zone_assignments")
            or (assignments or {}).get(nid, [])
        ),
        fetch_overlap_assignments=lambda nid: (
            _maybe_fail("overlap_assignments")
            or (overlaps or {}).get(nid, [])
        ),
        fetch_notices=lambda nid: (
            _maybe_fail("notices") or (notices or {}).get(nid, [])
        ),
        fetch_schedule_overrides=lambda path: (
            _maybe_fail("overrides") or (overrides or [])
        ),
    )


def _make(svc_db, *, cache_backend=None) -> PlacementService:
    cache = CacheService(cache_backend)
    svc = PlacementService(supabase=None, cache=cache)  # type: ignore[arg-type]
    svc._db = svc_db
    return svc


class PlacementCacheThroughTests(unittest.TestCase):

    def test_get_week_cache_through(self):
        db = _fake_db(week={"id": "w1", "label": "W1"})
        svc = _make(db, cache_backend=FakeRedis())

        first = run(svc.get_week("w1"))
        self.assertEqual(first, {"id": "w1", "label": "W1"})
        self.assertEqual(svc.cache.stats["misses"], 1)
        self.assertEqual(svc.cache.stats["sets"], 1)

        # Second call hits cache; even if db now blows up, we still get the value.
        svc._db = _fake_db(fail_for="week")
        second = run(svc.get_week("w1"))
        self.assertEqual(second, {"id": "w1", "label": "W1"})
        self.assertEqual(svc.cache.stats["hits"], 1)

    def test_get_week_nights(self):
        db = _fake_db(nights=[{"id": "n1"}, {"id": "n2"}])
        svc = _make(db, cache_backend=FakeRedis())

        nights = run(svc.get_week_nights("w1"))
        self.assertEqual(len(nights), 2)
        # Cached
        again = run(svc.get_week_nights("w1"))
        self.assertEqual(again, nights)
        self.assertEqual(svc.cache.stats["hits"], 1)

    def test_get_week_assignments_warms_per_night_cache(self):
        db = _fake_db(
            nights=[{"id": "n1"}, {"id": "n2"}],
            assignments={
                "n1": [{"slot": "Z1"}],
                "n2": [{"slot": "Z2"}],
            },
        )
        svc = _make(db, cache_backend=FakeRedis())

        bundle = run(svc.get_week_assignments("w1"))
        self.assertEqual(set(bundle.keys()), {"n1", "n2"})

        # Now even with the db broken, per-night reads come from cache.
        svc._db = _fake_db(fail_for="zone_assignments")
        n1 = run(svc.get_night_assignments("n1"))
        self.assertEqual(n1, [{"slot": "Z1"}])

    def test_get_week_package_includes_overrides(self):
        db = _fake_db(
            week={"id": "w1", "schedule_path": "weeks/2025-W18.xlsx"},
            nights=[{"id": "n1"}],
            assignments={"n1": [{"slot": "Z1"}]},
            overlaps={"n1": [{"slot": "OL"}]},
            overrides=[{"tm_id": "tm-1", "cell_date": "2025-05-01"}],
        )
        svc = _make(db, cache_backend=FakeRedis())

        pkg = run(svc.get_week_package("w1"))
        self.assertEqual(pkg["week"]["id"], "w1")
        self.assertEqual(pkg["nights"], [{"id": "n1"}])
        self.assertEqual(pkg["assignments"]["n1"], [{"slot": "Z1"}])
        self.assertEqual(pkg["overlaps"]["n1"], [{"slot": "OL"}])
        self.assertEqual(len(pkg["overrides"]), 1)

    def test_invalidate_clears_keys(self):
        backend = FakeRedis()
        db = _fake_db(week={"id": "w1"}, nights=[{"id": "n1"}])
        svc = _make(db, cache_backend=backend)

        run(svc.get_week("w1"))
        run(svc.get_week_nights("w1"))
        self.assertTrue(any(k.startswith("zds:week:w1") for k in backend.store))

        run(svc.invalidate_week("w1"))
        self.assertFalse(any(k.startswith("zds:week:w1") for k in backend.store))


class PlacementGracefulDegradationTests(unittest.TestCase):
    """Acceptance criteria: system works with Redis down."""

    def test_no_cache_still_returns_data(self):
        db = _fake_db(week={"id": "w1", "label": "W1"})
        svc = _make(db, cache_backend=None)  # Redis down

        self.assertFalse(svc.cache.enabled)
        result = run(svc.get_week("w1"))
        self.assertEqual(result, {"id": "w1", "label": "W1"})

    def test_loader_failure_returns_default(self):
        db = _fake_db(fail_for="nights")
        svc = _make(db, cache_backend=None)

        self.assertEqual(run(svc.get_week_nights("w1")), [])

    def test_get_week_returns_none_on_empty(self):
        db = _fake_db(week={})
        svc = _make(db, cache_backend=None)
        self.assertIsNone(run(svc.get_week("w1")))

    def test_empty_id_short_circuits(self):
        db = _fake_db()
        svc = _make(db, cache_backend=None)
        self.assertEqual(run(svc.get_week_nights("")), [])
        self.assertEqual(run(svc.get_night_assignments("")), [])
        self.assertEqual(run(svc.get_schedule_overrides("")), [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
