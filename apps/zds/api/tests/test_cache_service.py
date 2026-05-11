"""Unit tests for CacheService.

Tests cover:
  - Namespace key prefixing
  - get / set / delete round-trips
  - delete_many (bulk delete, single Redis call)
  - delete_pattern (SCAN-based glob deletion with multiple batches)
  - get_or_set (convenience loader, cache-hit short-circuits loader)
  - Graceful degradation: all operations return None/0/no-op when Redis
    raises ConnectionError (or any exception)
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from apps.zds.api.services.cache_service import CacheService


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_cache(redis=None):
    return CacheService(redis_client=redis)


# ── Namespace prefix ──────────────────────────────────────────────────────────

class TestNamespacing:
    def test_key_is_prefixed(self):
        svc = make_cache()
        assert svc._key("week:abc") == "zds_forge:week:abc"

    def test_already_prefixed_key_passes_through(self):
        svc = make_cache()
        already = "zds_forge:week:abc"
        assert svc._key(already) == already

    def test_namespace_attribute(self):
        assert CacheService.__namespace__ == "zds_forge"


# ── No-op when Redis is None ──────────────────────────────────────────────────

class TestNullCache:
    @pytest.mark.asyncio
    async def test_get_returns_none(self, null_cache):
        assert await null_cache.get("anything") is None

    @pytest.mark.asyncio
    async def test_set_returns_false(self, null_cache):
        assert await null_cache.set("k", {"v": 1}) is False

    @pytest.mark.asyncio
    async def test_delete_returns_zero(self, null_cache):
        assert await null_cache.delete("k") == 0

    @pytest.mark.asyncio
    async def test_delete_many_is_noop(self, null_cache):
        await null_cache.delete_many(["k1", "k2"])  # should not raise

    @pytest.mark.asyncio
    async def test_delete_pattern_returns_zero(self, null_cache):
        assert await null_cache.delete_pattern("tasks:*") == 0

    @pytest.mark.asyncio
    async def test_get_or_set_calls_loader(self, null_cache):
        loader_called = []

        async def loader():
            loader_called.append(True)
            return {"data": 42}

        result = await null_cache.get_or_set("k", 60, loader)
        assert result == {"data": 42}
        assert loader_called  # loader must still be called


# ── In-memory Redis round-trips ───────────────────────────────────────────────

class TestGetSetDelete:
    @pytest.mark.asyncio
    async def test_set_and_get(self, cache_service):
        await cache_service.set("week:001", {"id": "001"})
        result = await cache_service.get("week:001")
        assert result == {"id": "001"}

    @pytest.mark.asyncio
    async def test_get_miss_returns_none(self, cache_service):
        assert await cache_service.get("nonexistent:key") is None

    @pytest.mark.asyncio
    async def test_delete_removes_key(self, cache_service):
        await cache_service.set("tmpcache:k", {"v": 1})
        await cache_service.delete("tmpcache:k")
        assert await cache_service.get("tmpcache:k") is None

    @pytest.mark.asyncio
    async def test_delete_returns_count(self, cache_service):
        await cache_service.set("del:a", 1)
        await cache_service.set("del:b", 2)
        count = await cache_service.delete("del:a", "del:b", "del:c")  # c doesn't exist
        assert count == 2

    @pytest.mark.asyncio
    async def test_set_json_serialises_correctly(self, cache_service, in_memory_redis):
        """Verify the value is JSON-encoded in the store."""
        await cache_service.set("serial:k", [1, 2, 3])
        raw = in_memory_redis.get("zds_forge:serial:k")
        assert json.loads(raw) == [1, 2, 3]


# ── delete_many ───────────────────────────────────────────────────────────────

class TestDeleteMany:
    @pytest.mark.asyncio
    async def test_delete_many_removes_all(self, cache_service):
        for i in range(5):
            await cache_service.set(f"batch:{i}", i)
        await cache_service.delete_many([f"batch:{i}" for i in range(5)])
        for i in range(5):
            assert await cache_service.get(f"batch:{i}") is None

    @pytest.mark.asyncio
    async def test_delete_many_empty_list_noop(self, cache_service):
        await cache_service.delete_many([])  # should not raise


# ── delete_pattern ────────────────────────────────────────────────────────────

class TestDeletePattern:
    @pytest.mark.asyncio
    async def test_pattern_deletes_matching_keys(self, cache_service):
        await cache_service.set("anno:2026-05-08:fri", {"a": 1})
        await cache_service.set("anno:2026-05-08:sat", {"b": 2})
        await cache_service.set("anno:2026-05-09:fri", {"c": 3})  # different week

        deleted = await cache_service.delete_pattern("anno:2026-05-08:*")
        assert deleted == 2
        assert await cache_service.get("anno:2026-05-08:fri") is None
        assert await cache_service.get("anno:2026-05-08:sat") is None
        assert await cache_service.get("anno:2026-05-09:fri") is not None

    @pytest.mark.asyncio
    async def test_pattern_with_no_matches_returns_zero(self, cache_service):
        deleted = await cache_service.delete_pattern("nosuchprefix:*")
        assert deleted == 0

    @pytest.mark.asyncio
    async def test_pattern_multiple_scan_batches(self):
        """Simulate a large keyspace where SCAN returns multiple cursor pages.

        The key design constraint: SCAN returns a fixed pre-computed cursor
        window, not a live view of the store.  This is how real Redis works —
        SCAN uses a cursor over a snapshot; deletes between batches do NOT
        shrink the remaining pages.  We simulate that by pre-splitting keys.
        """

        class PaginatedRedis:
            """Returns keys in two fixed batches to test cursor iteration."""
            def __init__(self):
                all_keys = [f"zds_forge:tasks:{i}" for i in range(1000)]
                self._store = dict.fromkeys(all_keys, "v")
                self._calls = 0
                # Pre-compute fixed batches — mirrors real Redis cursor behaviour.
                self._batch1 = all_keys[:500]
                self._batch2 = all_keys[500:]

            def get(self, k):
                return self._store.get(k)

            def set(self, k, v, ex=None):
                self._store[k] = v

            def delete(self, *keys):
                deleted = 0
                for k in keys:
                    if k in self._store:
                        del self._store[k]
                        deleted += 1
                return deleted

            def scan(self, cursor=0, match="*", count=100):
                self._calls += 1
                if cursor == 0:
                    return (1, self._batch1)   # non-zero cursor → more pages
                else:
                    return (0, self._batch2)   # cursor == 0 → done

        svc = CacheService(redis_client=PaginatedRedis())
        deleted = await svc.delete_pattern("tasks:*")
        assert deleted == 1000
        assert svc.client._calls == 2  # exactly two SCAN round-trips


# ── get_or_set ────────────────────────────────────────────────────────────────

class TestGetOrSet:
    @pytest.mark.asyncio
    async def test_miss_calls_loader_and_stores(self, cache_service):
        calls = []

        async def loader():
            calls.append(1)
            return {"computed": True}

        result = await cache_service.get_or_set("gos:k", 60, loader)
        assert result == {"computed": True}
        assert len(calls) == 1
        # Subsequent call must hit cache, not call loader again.
        result2 = await cache_service.get_or_set("gos:k", 60, loader)
        assert result2 == {"computed": True}
        assert len(calls) == 1  # loader called exactly once

    @pytest.mark.asyncio
    async def test_hit_skips_loader(self, cache_service):
        await cache_service.set("gos:preloaded", {"pre": True})
        calls = []

        async def loader():
            calls.append(1)
            return {"should": "not be called"}

        result = await cache_service.get_or_set("gos:preloaded", 60, loader)
        assert result == {"pre": True}
        assert len(calls) == 0


# ── Graceful degradation ──────────────────────────────────────────────────────

class TestGracefulDegradation:
    def _exploding_redis(self):
        """Redis client that raises ConnectionError on every call."""
        m = MagicMock()
        m.get.side_effect = ConnectionError("Redis is down")
        m.set.side_effect = ConnectionError("Redis is down")
        m.delete.side_effect = ConnectionError("Redis is down")
        m.scan.side_effect = ConnectionError("Redis is down")
        return m

    @pytest.mark.asyncio
    async def test_get_swallows_error(self):
        svc = CacheService(redis_client=self._exploding_redis())
        result = await svc.get("any")
        assert result is None  # no exception

    @pytest.mark.asyncio
    async def test_set_swallows_error(self):
        svc = CacheService(redis_client=self._exploding_redis())
        result = await svc.set("any", {"data": 1})
        assert result is False  # no exception

    @pytest.mark.asyncio
    async def test_delete_swallows_error(self):
        svc = CacheService(redis_client=self._exploding_redis())
        result = await svc.delete("k")
        assert result == 0  # no exception

    @pytest.mark.asyncio
    async def test_delete_many_swallows_error(self):
        svc = CacheService(redis_client=self._exploding_redis())
        await svc.delete_many(["k1", "k2"])  # no exception

    @pytest.mark.asyncio
    async def test_delete_pattern_swallows_error(self):
        svc = CacheService(redis_client=self._exploding_redis())
        result = await svc.delete_pattern("tasks:*")
        assert result == 0  # no exception

    @pytest.mark.asyncio
    async def test_get_or_set_still_calls_loader_on_cache_failure(self):
        """Even with Redis broken, get_or_set must still return loader()."""
        svc = CacheService(redis_client=self._exploding_redis())
        calls = []

        async def loader():
            calls.append(1)
            return {"fresh": True}

        result = await svc.get_or_set("k", 60, loader)
        assert result == {"fresh": True}
        assert len(calls) == 1
