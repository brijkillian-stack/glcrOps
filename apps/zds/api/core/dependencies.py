"""FastAPI dependency providers for shared infrastructure clients.

These live in `core/` rather than per-router so every service shares a
single Supabase client (one connection pool) and a single Redis pool.

Redis is optional: if `REDIS_URL` is unset OR the import fails OR a
connection cannot be opened, `get_redis_client` returns `None` and
downstream code (e.g. `CacheService`) is expected to no-op.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from supabase import Client, create_client

from .config import get_settings


# ── Supabase ────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _supabase_singleton() -> Client:
    s = get_settings()
    if not s.supabase_url or not s.supabase_service_key:
        raise RuntimeError(
            "Supabase credentials missing — set SUPABASE_URL and "
            "SUPABASE_SERVICE_KEY in the environment."
        )
    return create_client(s.supabase_url, s.supabase_service_key)


def get_supabase_client() -> Client:
    """FastAPI dependency — returns the shared Supabase client."""
    return _supabase_singleton()


# ── Redis (optional) ────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _redis_singleton() -> Optional[object]:
    s = get_settings()
    if not s.redis_url:
        return None
    try:
        import redis  # type: ignore[import-untyped]
    except ImportError:
        return None
    try:
        client = redis.Redis.from_url(s.redis_url, decode_responses=True)
        # Best-effort ping so we fail fast if the URL is wrong.
        client.ping()
        return client
    except Exception:
        return None


def get_redis_client() -> Optional[object]:
    """FastAPI dependency — returns a Redis client, or None if unavailable.

    Returning None instead of raising lets the API stay up when Redis
    is down or not configured (e.g. local dev). Callers must handle
    None — see `CacheService` for the no-op pattern.
    """
    return _redis_singleton()
