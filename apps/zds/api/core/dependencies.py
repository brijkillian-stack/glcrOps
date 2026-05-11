"""FastAPI dependency providers for shared infrastructure clients.

These live in `core/` rather than per-router so every service shares a
single Supabase client (one connection pool) and a single Redis pool.

Redis is optional: if `REDIS_URL` is unset OR the import fails OR a
connection cannot be opened, `get_redis_client` returns `None` and
downstream code (e.g. `CacheService`) is expected to no-op.

Design rule
───────────
Route handlers must consume services via `Depends(get_*)` — never
construct service instances inline in route functions.  This gives tests
a clean override point and ensures the whole app shares singletons.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from supabase import Client, create_client

from .config import get_settings


# ── Supabase ────────────────────────────────────────────────────────────────

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


# ── Redis (optional) ────────────────────────────────────────────────────────

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


# ── Higher-level service singletons ─────────────────────────────────────────

@lru_cache(maxsize=1)
def _cache_service_singleton():
    from ..services.cache_service import CacheService
    return CacheService(redis_client=get_redis_client())


def get_cache_service():
    """FastAPI dependency — shared CacheService instance."""
    return _cache_service_singleton()


@lru_cache(maxsize=1)
def _placement_service_singleton():
    from ..services.placement_service import PlacementService
    return PlacementService(
        supabase=get_supabase_client(),
        cache=get_cache_service(),
    )


def get_placement_service():
    """FastAPI dependency — shared PlacementService instance.

    Uses module-level lru_cache so the same instance (with its warm
    Redis connection) is returned on every request.  Tests override this
    via app.dependency_overrides[get_placement_service] = lambda: FakeService().
    """
    return _placement_service_singleton()


@lru_cache(maxsize=1)
def _print_service_singleton():
    from ..services.print_service import PrintService
    return PrintService(
        placement=get_placement_service(),
        cache=get_cache_service(),
    )


def get_print_service():
    """FastAPI dependency — shared PrintService instance."""
    return _print_service_singleton()


@lru_cache(maxsize=1)
def _planning_service_singleton():
    from ..services.planning_service import PlanningService
    return PlanningService(placement=get_placement_service())


def get_planning_service():
    """FastAPI dependency — shared PlanningService instance (GLC-12).

    PlanningService wraps PlacementService; it does not touch Supabase or
    Redis directly.  Tests override via
    ``app.dependency_overrides[get_planning_service] = lambda: FakePlanningService()``.
    """
    return _planning_service_singleton()
