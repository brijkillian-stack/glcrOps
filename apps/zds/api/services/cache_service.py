"""Minimal async-friendly cache facade.

Wraps a `redis.Redis` client (sync) behind an `async`-shaped API so
upstream callers can write `await cache.get(...)` without caring
whether Redis is actually configured. When `redis_client is None`
every method is a no-op — so the whole stack stays functional in
local/dev environments without Redis.

Values are JSON-encoded on the way in and decoded on the way out.
"""

from __future__ import annotations

import json
from typing import Any, Optional


class CacheService:
    """No-op-if-no-redis cache.

    The class never raises on cache miss / cache failure — caching is
    treated as an optimization, never a correctness boundary.
    """

    DEFAULT_TTL = 300  # seconds

    def __init__(self, redis_client: Optional[Any]):
        self.client = redis_client

    @property
    def enabled(self) -> bool:
        return self.client is not None

    async def get(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None
        try:
            raw = self.client.get(key)
        except Exception:
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return raw

    async def set(self, key: str, value: Any, ttl: int = DEFAULT_TTL) -> bool:
        if not self.enabled:
            return False
        try:
            payload = json.dumps(value, default=str)
            self.client.set(key, payload, ex=ttl)
            return True
        except Exception:
            return False

    async def delete(self, *keys: str) -> int:
        if not self.enabled or not keys:
            return 0
        try:
            return int(self.client.delete(*keys))
        except Exception:
            return 0

    async def invalidate_prefix(self, prefix: str) -> int:
        """Best-effort prefix delete using SCAN. Returns count deleted."""
        if not self.enabled:
            return 0
        try:
            deleted = 0
            for key in self.client.scan_iter(match=f"{prefix}*"):
                self.client.delete(key)
                deleted += 1
            return deleted
        except Exception:
            return 0
