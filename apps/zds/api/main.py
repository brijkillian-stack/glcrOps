"""ZDS Forge — FastAPI application entry point.

Run locally:

    uvicorn apps.zds.api.main:app --reload --port 8001

The app intentionally keeps the surface small for now: a `/health`
ping, a versioned print router, and warmup of shared singletons at
startup. As the unified data layer lands, additional routers (auth,
nights, weeks, annotations) will hang off this same `app` object.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .core.dependencies import get_redis_client, get_supabase_client
from .observability import instrument_app
from .routers import nights as nights_router
from .routers import planning as planning_router
from .routers import print as print_router

log = logging.getLogger("zds.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm singletons on boot, log infra status, clean shutdown."""
    settings = get_settings()
    instrument_app(app, env=settings.env)
    log.info("ZDS Forge starting (env=%s, debug=%s)", settings.env, settings.debug)

    # Touch the supabase singleton so a misconfigured env surfaces at
    # boot rather than on first request. If env vars are missing this
    # will raise — that's intentional: don't silently 500 every call.
    try:
        get_supabase_client()
        log.info("Supabase client initialized")
    except Exception as exc:  # pragma: no cover — startup guard
        log.error("Supabase initialization failed: %s", exc)
        raise

    # Redis is optional. If it's not available the cache layer no-ops.
    redis = get_redis_client()
    if redis is None:
        log.warning("Redis unavailable — CacheService will no-op")
    else:
        log.info("Redis client initialized")

    yield

    log.info("ZDS Forge shutting down")


app = FastAPI(
    title="ZDS Forge API",
    description="ZDS engine + print services for Gun Lake Casino grave shift ops.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — wide-open for now; tighten when the web UI's origin is known.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
async def health():
    """Liveness probe — does not touch Supabase or Redis on purpose."""
    return {"status": "ok", "service": "zds-forge"}


# ── Routers ──────────────────────────────────────────────────────────
app.include_router(print_router.router)
app.include_router(planning_router.router)
app.include_router(nights_router.router)
