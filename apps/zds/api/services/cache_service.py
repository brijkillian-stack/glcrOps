"""Async-shaped cache facade over a sync Redis client.

Wraps `redis.Redis` (sync) behind `async` method signatures so upstream
callers can write `await cache.get(...)` without caring whether Redis is
actually configured.

When `redis_client is None` every method is a graceful no-op — so the
whole API stays functional in dev environments without Redis.

Namespace prefix
────────────────
All keys are automatically prefixed with ``{__namespace__}:``.  This lets
multiple FastAPI services share a single Redis keyspace without key
collisions.  Pass already-namespaced keys if you need to share across
services; normally callers pass bare keys like ``"week:abc-123"``.

Graceful degradation
────────────────────
No method raises on cache miss or Redis failure.  Caching is an
optimisation — not a correctness boundary.  All cache errors are swallowed
silently (or logged at DEBUG level).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable, Optional

log = logging.getLogger(__name__)


class CacheService:
    """Redis-backed cache with graceful no-op degradation.

    Attributes
    ----------
    __namespace__:
        Prefix applied to every key.  Change per-service to isolate
        keyspaces on a shared Redis instance.
    DEFAULT_TTL:
        Fallback TTL (seconds) used when callers don't specify one.
    """

    __namespace__: str = "zds_forge"
    DEFAULT_TTL: int = 300  # seconds

    def __init__(self, redis_client: Optional[Any]):
        self.client = redis_client

    # ── Internals ─────────────────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def _key(self, key: str) -> str:
        """Apply namespace prefix.  Already-prefixed keys pass through."""
        ns = self.__namespace__ + ":"
        return key if key.startswith(ns) else ns + key

    def _keys(self, keys: list[str]) -> list[str]:
        return [self._key(k) for k in keys]

    # ── Core get / set / delete ────────────────────────────────────────────

    async def get(self, key: str) -> Optional[Any]:
        """Return the cached value for *key*, or None on miss / error."""
        if not self.enabled:
            return None
        try:
            raw = self.client.get(self._key(key))
        except Exception as exc:
            log.debug("cache.get(%r) error: %s", key, exc)
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return raw

    async def set(
        self, key: str, value: Any, ttl: int = DEFAULT_TTL
    ) -> bool:
        """Store *value* under *key* with expiry *ttl* seconds.

        Returns True on success, False if Redis unavailable or on error.
        """
        if not self.enabled:
            return False
        try:
            payload = json.dumps(value, default=str)
            self.client.set(self._key(key), payload, ex=ttl)
            return True
        except Exception as exc:
            log.debug("cache.set(%r) error: %s", key, exc)
            return False

    async def delete(self, *keys: str) -> int:
        """Delete one or more keys.  Returns count actually deleted."""
        if not self.enabled or not keys:
            return 0
        try:
            return int(self.client.delete(*self._keys(list(keys))))
        except Exception as exc:
            log.debug("cache.delete error: %s", exc)
            return 0

    # ── Bulk / pattern operations (Phase 2) ───────────────────────────────

    async def delete_many(self, keys: list[str]) -> None:
        """Bulk-delete *keys* in a single Redis call.  No-op on empty list."""
        if not self.enabled or not keys:
            return
        try:
            self.client.delete(*self._keys(keys))
        except Exception as exc:
            log.debug("cache.delete_many error: %s", exc)

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a glob *pattern*.

        Uses Redis SCAN (cursor-based) to avoid blocking large keyspaces.
        The namespace prefix is prepended to *pattern* automatically.

        Returns the count of keys deleted, or 0 if Redis unavailable.

        Example
        -------
        ``await cache.delete_pattern("anno:2026-05-08:*")``
        deletes every annotation cache key for that week/day.
        """
        if not self.enabled:
            return 0
        full_pattern = self._key(pattern)
        deleted = 0
        try:
            cursor = 0
            while True:
                cursor, keys = self.client.scan(
                    cursor=cursor, match=full_pattern, count=100
                )
                if keys:
                    self.client.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break
        except Exception as exc:
            log.debug("cache.delete_pattern(%r) error: %s", pattern, exc)
        return deleted

    # ── Convenience ───────────────────────────────────────────────────────

    async def get_or_set(
        self,
        key: str,
        ttl: int,
        loader: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Try cache first; on miss call *loader()*, store result, return it.

        Not atomically safe at the Redis level — two concurrent misses will
        both call *loader()*. Acceptable for read-heavy, idempotent data.

        Parameters
        ----------
        key:
            Cache key (namespace is prepended automatically).
        ttl:
            Expiry in seconds for the stored value.
        loader:
            An async callable that returns the value to cache on miss.
        """
        cached = await self.get(key)
        if cached is not None:
            return cached
        value = await loader()
        if value is not None:
            await self.set(key, value, ttl=ttl)
        return value

    # ── Legacy alias (kept for backward-compat with pre-Phase-2 callers) ──

    async def invalidate_prefix(self, prefix: str) -> int:
        """Alias for delete_pattern.  Kept for existing callers."""
        return await self.delete_pattern(f"{prefix}*")
