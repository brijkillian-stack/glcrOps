"""Unit tests for CacheService — no Redis required.

Tests cover:
* No-op behavior when ``redis_client is None``
* Hit / miss / error counters
* ``get_or_set`` cache-through path for sync + async loaders
* JSON encode/decode round-trip
* Resilience when the underlying client raises
"""

from __future__ import annotations

import asyncio
import json
import unittest

from apps.zds.api.services.cache_service import CacheService


class FakeRedis:
    """In-memory Redis stand-in supporting get/set/delete/scan_iter."""

    def __init__(self, *, raises: bool = False):
        self.store: dict[str, str] = {}
        self.raises = raises

    def get(self, key):
        if self.raises:
            raise RuntimeError("simulated redis outage")
        return self.store.get(key)

    def set(self, key, value, ex=None):
        if self.raises:
            raise RuntimeError("simulated redis outage")
        self.store[key] = value
        return True

    def delete(self, *keys):
        if self.raises:
            raise RuntimeError("simulated redis outage")
        n = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                n += 1
        return n

    def scan_iter(self, match=None):
        if self.raises:
            raise RuntimeError("simulated redis outage")
        prefix = (match or "").rstrip("*")
        return [k for k in list(self.store.keys()) if k.startswith(prefix)]


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class CacheServiceNoOpTests(unittest.TestCase):
    """When Redis is unavailable, every method is a safe no-op."""

    def test_disabled_when_client_none(self):
        c = CacheService(None)
        self.assertFalse(c.enabled)

    def test_get_returns_none_no_error(self):
        c = CacheService(None)
        self.assertIsNone(run(c.get("anything")))
        self.assertEqual(c.stats["bypass"], 1)

    def test_set_returns_false(self):
        c = CacheService(None)
        self.assertFalse(run(c.set("k", {"a": 1})))
        self.assertEqual(c.stats["sets"], 0)

    def test_delete_returns_zero(self):
        c = CacheService(None)
        self.assertEqual(run(c.delete("a", "b")), 0)

    def test_get_or_set_falls_through_to_loader(self):
        c = CacheService(None)
        loader_called = []

        def loader():
            loader_called.append(True)
            return {"v": 42}

        result = run(c.get_or_set("key", loader))
        self.assertEqual(result, {"v": 42})
        self.assertEqual(len(loader_called), 1)


class CacheServiceRedisBackedTests(unittest.TestCase):
    """With a working backend, hits/misses/sets/deletes all wire through."""

    def test_set_then_get_roundtrip(self):
        c = CacheService(FakeRedis())
        run(c.set("zds:week:abc", {"id": "abc", "label": "W1"}))
        value = run(c.get("zds:week:abc"))
        self.assertEqual(value, {"id": "abc", "label": "W1"})
        self.assertEqual(c.stats["hits"], 1)
        self.assertEqual(c.stats["sets"], 1)

    def test_miss_increments_misses(self):
        c = CacheService(FakeRedis())
        self.assertIsNone(run(c.get("zds:week:missing")))
        self.assertEqual(c.stats["misses"], 1)
        self.assertEqual(c.stats["hits"], 0)

    def test_get_or_set_caches_loader_result(self):
        c = CacheService(FakeRedis())
        calls = []

        def loader():
            calls.append(1)
            return [1, 2, 3]

        first = run(c.get_or_set("zds:lst", loader, ttl=60))
        second = run(c.get_or_set("zds:lst", loader, ttl=60))
        self.assertEqual(first, [1, 2, 3])
        self.assertEqual(second, [1, 2, 3])
        self.assertEqual(len(calls), 1)
        self.assertEqual(c.stats["hits"], 1)
        self.assertEqual(c.stats["misses"], 1)

    def test_get_or_set_supports_async_loader(self):
        c = CacheService(FakeRedis())

        async def loader():
            return {"async": True}

        result = run(c.get_or_set("zds:async", loader))
        self.assertEqual(result, {"async": True})

    def test_value_is_json_encoded(self):
        backend = FakeRedis()
        c = CacheService(backend)
        run(c.set("zds:v", {"d": 1}))
        stored = backend.store["zds:v"]
        self.assertEqual(json.loads(stored), {"d": 1})

    def test_invalidate_prefix(self):
        backend = FakeRedis()
        c = CacheService(backend)
        run(c.set("zds:night:1:a", 1))
        run(c.set("zds:night:1:b", 2))
        run(c.set("zds:week:1", 9))
        deleted = run(c.invalidate_prefix("zds:night:1"))
        self.assertEqual(deleted, 2)
        self.assertIn("zds:week:1", backend.store)


class CacheServiceErrorPathTests(unittest.TestCase):
    """A flaky/down backend never raises through the CacheService API."""

    def test_get_handles_backend_exception(self):
        c = CacheService(FakeRedis(raises=True))
        self.assertIsNone(run(c.get("zds:x")))
        self.assertEqual(c.stats["errors"], 1)

    def test_set_handles_backend_exception(self):
        c = CacheService(FakeRedis(raises=True))
        self.assertFalse(run(c.set("zds:x", {"a": 1})))
        self.assertEqual(c.stats["errors"], 1)

    def test_get_or_set_recovers_on_get_error(self):
        c = CacheService(FakeRedis(raises=True))

        def loader():
            return "fallback"

        # get fails, set fails too, but loader result is still returned.
        self.assertEqual(run(c.get_or_set("zds:x", loader)), "fallback")
        self.assertGreaterEqual(c.stats["errors"], 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
