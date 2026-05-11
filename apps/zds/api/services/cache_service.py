"""Async-friendly Redis cache facade with graceful no-op fallback.

Wraps a `redis.Redis` client (sync) behind an `async`-shaped API so
upstream callers can write `await cache.get(...)` without caring
whether Redis is actually configured. When `redis_client is None`
every method is a no-op — so the whole stack stays functional in
local/dev environments without Redis.

Values are JSON-encoded on the way in and decoded on the way out.

Cache hits, misses, and backend errors are logged through
``logging.getLogger("zds.cache")`` so the operator can see Redis
health at a glance, and a small in-process counter is exposed for
test assertions and future metric scraping.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Awaitable, Callable, Optional

log = logging.getLogger("zds.cache")


class CacheService:
    """Cache facade that is correct-by-default even with no Redis.

    The class never raises on cache miss / cache failure — caching is
    treated as an optimization, never a correctness boundary. If Redis
    is unreachable mid-request the call falls through to the loader and
    the error is logged once per call.
    """

    DEFAULT_TTL = 300  # seconds
    KEY_PREFIX = "zds"

    def __init__(
        self,
        redis_client: Optional[Any],
        *,
        default_ttl: int = DEFAULT_TTL,
        namespace: Optional[str] = None,
    ):
        self.client = redis_client
        self.default_ttl = default_ttl
        self.namespace = namespace or self.KEY_PREFIX
        # Lightweight counters — handy for tests and future /metrics export.
        self.stats: dict[str, int] = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0,
            "bypass": 0,  # incremented when Redis is disabled / unavailable
        }

    # ── Properties ────────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return self.client is not None

    # ── Key helpers ───────────────────────────────────────────────

    def key(self, *parts: str) -> str:
        """Build a namespaced cache key from positional parts."""
        return ":".join((self.namespace, *(str(p) for p in parts if p != "")))

    # ── Core ──────────────────────────────────────────────────────

    async def get(self, key: str) -> Optional[Any]:
        if not self.enabled:
            self.stats["bypass"] += 1
            return None
        try:
            raw = self.client.get(key)
        except Exception as exc:
            self.stats["errors"] += 1
            log.warning("cache.get(%s) failed: %s", key, exc)
            return None
        if raw is None:
            self.stats["misses"] += 1
            log.debug("cache MISS %s", key)
            return None
        self.stats["hits"] += 1
        log.debug("cache HIT  %s", key)
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return raw

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        if not self.enabled:
            self.stats["bypass"] += 1
            return False
        try:
            payload = json.dumps(value, default=str)
            self.client.set(key, payload, ex=ttl or self.default_ttl)
            self.stats["sets"] += 1
            return True
        except Exception as exc:
            self.stats["errors"] += 1
            log.warning("cache.set(%s) failed: %s", key, exc)
            return False

    async def delete(self, *keys: str) -> int:
        if not self.enabled or not keys:
            return 0
        try:
            n = int(self.client.delete(*keys))
            self.stats["deletes"] += n
            return n
        except Exception as exc:
            self.stats["errors"] += 1
            log.warning("cache.delete(%s) failed: %s", keys, exc)
            return 0

    async def invalidate_prefix(self, prefix: str) -> int:
        """Best-effort prefix delete using SCAN. Returns count deleted."""
        if not self.enabled:
            return 0
        try:
            deleted = 0
            for k in self.client.scan_iter(match=f"{prefix}*"):
                self.client.delete(k)
                deleted += 1
            self.stats["deletes"] += deleted
            return deleted
        except Exception as exc:
            self.stats["errors"] += 1
            log.warning("cache.invalidate_prefix(%s) failed: %s", prefix, exc)
            return 0

    # ── Cache-through helper ──────────────────────────────────────

    async def get_or_set(
        self,
        key: str,
        loader: Callable[[], Any] | Callable[[], Awaitable[Any]],
        ttl: Optional[int] = None,
    ) -> Any:
        """Canonical cache-through: return cached value or invoke loader.

        The loader may be sync or async. A loader exception is logged
        and re-raised so callers can decide whether to recover; we do
        NOT cache loader failures.
        """
        cached = await self.get(key)
        if cached is not None:
            return cached

        start = time.perf_counter()
        result = loader()
        if hasattr(result, "__await__"):
            result = await result  # type: ignore[misc]
        elapsed_ms = (time.perf_counter() - start) * 1000

        if result is not None:
            await self.set(key, result, ttl=ttl)
        log.debug(
            "cache LOAD %s ttl=%s elapsed_ms=%.1f",
            key, ttl or self.default_ttl, elapsed_ms,
        )
        return result

    # ── Diagnostics ───────────────────────────────────────────────

    def snapshot_stats(self) -> dict[str, int]:
        """Return a copy of the in-process counters."""
        return dict(self.stats)
