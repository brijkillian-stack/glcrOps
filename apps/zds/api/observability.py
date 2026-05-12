"""
ZDS Forge — Observability layer.

Provides:
  • Prometheus metrics (request count, latency histograms, cache hit/miss,
    print generation time)
  • Starlette middleware that records per-request metrics + structured logs
  • Sentry integration (no-ops gracefully when SENTRY_DSN is absent)
  • /metrics endpoint (plain text, Prometheus scrape format)

Usage in main.py
────────────────
  from .observability import instrument_app
  instrument_app(app)   # call before app.include_router(...)

Environment
───────────
  SENTRY_DSN          (optional) Sentry DSN string — enables error reporting
  SENTRY_ENVIRONMENT  (optional) defaults to APP_ENV (dev/staging/prod)
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match
from starlette.types import ASGIApp

log = logging.getLogger("zds.observability")

# ── Prometheus ────────────────────────────────────────────────────────────────

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )
    _PROM_AVAILABLE = True
except ImportError:
    _PROM_AVAILABLE = False
    log.warning(
        "prometheus_client not installed — /metrics endpoint will return 503. "
        "Install: pip install prometheus-client"
    )

if _PROM_AVAILABLE:
    _REGISTRY = CollectorRegistry(auto_describe=True)

    HTTP_REQUESTS_TOTAL = Counter(
        "zds_http_requests_total",
        "Total HTTP requests by method, endpoint template, and status code.",
        ["method", "endpoint", "status_code"],
        registry=_REGISTRY,
    )

    HTTP_REQUEST_DURATION_SECONDS = Histogram(
        "zds_http_request_duration_seconds",
        "HTTP request latency by method and endpoint template.",
        ["method", "endpoint"],
        buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
        registry=_REGISTRY,
    )

    CACHE_HITS_TOTAL = Counter(
        "zds_cache_hits_total",
        "Cache hits by cache key prefix.",
        ["prefix"],
        registry=_REGISTRY,
    )

    CACHE_MISSES_TOTAL = Counter(
        "zds_cache_misses_total",
        "Cache misses by cache key prefix.",
        ["prefix"],
        registry=_REGISTRY,
    )

    PRINT_GENERATION_SECONDS = Histogram(
        "zds_print_generation_seconds",
        "Time spent rendering HTML or PDF in the print pipeline.",
        ["format", "scope"],   # format=html|pdf, scope=week|night
        buckets=[0.1, 0.5, 1.0, 5.0, 15.0, 30.0, 60.0, 120.0, 300.0],
        registry=_REGISTRY,
    )

    PRINT_ERRORS_TOTAL = Counter(
        "zds_print_errors_total",
        "Total print render errors by format and scope.",
        ["format", "scope", "error_type"],
        registry=_REGISTRY,
    )

    ACTIVE_REQUESTS = Gauge(
        "zds_active_requests",
        "Number of requests currently being processed.",
        registry=_REGISTRY,
    )


def record_cache_hit(prefix: str) -> None:
    """Call from CacheService when a cache hit occurs."""
    if _PROM_AVAILABLE:
        CACHE_HITS_TOTAL.labels(prefix=prefix).inc()


def record_cache_miss(prefix: str) -> None:
    """Call from CacheService when a cache miss occurs."""
    if _PROM_AVAILABLE:
        CACHE_MISSES_TOTAL.labels(prefix=prefix).inc()


def record_print_duration(
    format: str, scope: str, seconds: float, error_type: str | None = None
) -> None:
    """Call from PrintService after each render attempt."""
    if _PROM_AVAILABLE:
        PRINT_GENERATION_SECONDS.labels(format=format, scope=scope).observe(seconds)
        if error_type:
            PRINT_ERRORS_TOTAL.labels(
                format=format, scope=scope, error_type=error_type
            ).inc()


# ── Sentry ────────────────────────────────────────────────────────────────────

def _init_sentry(env: str) -> bool:
    """Initialise Sentry if SENTRY_DSN is set.  Returns True if active."""
    import os
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
        sentry_sdk.init(
            dsn=dsn,
            environment=os.environ.get("SENTRY_ENVIRONMENT", env),
            traces_sample_rate=0.1,     # 10 % of transactions — tune per load
            profiles_sample_rate=0.01,  # 1 % profiling
            integrations=[
                StarletteIntegration(transaction_style="endpoint"),
                FastApiIntegration(),
            ],
            # Don't send PII (TM names, etc.) — they may appear in stack frames.
            send_default_pii=False,
        )
        log.info("Sentry initialised (env=%s)", env)
        return True
    except ImportError:
        log.warning(
            "SENTRY_DSN is set but sentry-sdk is not installed. "
            "Install: pip install sentry-sdk[fastapi]"
        )
        return False


# ── Middleware ────────────────────────────────────────────────────────────────

class MetricsMiddleware(BaseHTTPMiddleware):
    """Record per-request Prometheus metrics and emit a structured access log."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Resolve the route template for clean label cardinality
        # (e.g. "/v1/print/week/{week_id}.html" not the actual UUID).
        endpoint = self._route_template(request)
        method   = request.method

        if _PROM_AVAILABLE:
            ACTIVE_REQUESTS.inc()

        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            elapsed = time.monotonic() - start
            if _PROM_AVAILABLE:
                ACTIVE_REQUESTS.dec()
                HTTP_REQUESTS_TOTAL.labels(
                    method=method, endpoint=endpoint, status_code="500"
                ).inc()
                HTTP_REQUEST_DURATION_SECONDS.labels(
                    method=method, endpoint=endpoint
                ).observe(elapsed)
            raise

        elapsed = time.monotonic() - start
        status  = str(response.status_code)

        if _PROM_AVAILABLE:
            ACTIVE_REQUESTS.dec()
            HTTP_REQUESTS_TOTAL.labels(
                method=method, endpoint=endpoint, status_code=status
            ).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method, endpoint=endpoint
            ).observe(elapsed)

        # Structured access log — one line per request with key facts.
        log.info(
            "request completed",
            extra={
                "method":        method,
                "endpoint":      endpoint,
                "path":          request.url.path,
                "status_code":   response.status_code,
                "duration_ms":   round(elapsed * 1000, 1),
                "client_host":   (request.client.host if request.client else ""),
                "content_length": response.headers.get("content-length", ""),
            },
        )

        return response

    @staticmethod
    def _route_template(request: Request) -> str:
        """Return the matched route template or the raw path (for unmatched routes)."""
        for route in request.app.routes:
            match, _ = route.matches(request.scope)
            if match == Match.FULL:
                return getattr(route, "path", request.url.path)
        return request.url.path


# ── /metrics endpoint ─────────────────────────────────────────────────────────

async def metrics_endpoint(request: Request) -> Response:
    """Prometheus scrape endpoint — plain text exposition format."""
    if not _PROM_AVAILABLE:
        return PlainTextResponse(
            "# prometheus_client not installed\n",
            status_code=503,
        )
    data = generate_latest(_REGISTRY)
    return Response(
        content=data,
        media_type=CONTENT_TYPE_LATEST,
        headers={"Cache-Control": "no-store"},
    )


# ── Public entry point ────────────────────────────────────────────────────────

def instrument_app(app: FastAPI, env: str = "dev") -> None:
    """Attach observability middleware and /metrics route to the FastAPI app.

    Call this once in main.py *before* include_router().

    Args:
        app: The FastAPI application instance.
        env: The deployment environment (dev / staging / prod).
             Used as the Sentry environment tag.
    """
    # Sentry (best effort — no-ops if SDK or DSN absent)
    sentry_active = _init_sentry(env)
    if sentry_active:
        log.info("Sentry error tracking active")
    else:
        log.debug("Sentry not configured (SENTRY_DSN not set)")

    # Prometheus middleware
    app.add_middleware(MetricsMiddleware)

    # /metrics scrape endpoint (Prometheus pull model)
    app.add_route("/metrics", metrics_endpoint, include_in_schema=False)

    log.info(
        "Observability instrumented (prometheus=%s, sentry=%s)",
        _PROM_AVAILABLE,
        sentry_active,
    )
