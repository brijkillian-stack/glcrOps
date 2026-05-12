# Phase 6 Completion — ZDS Forge

**Status:** Complete  
**Date:** 2026-05-12  
**Engineer:** Cyrus (backend), Brian Killian (product owner & visual QA)

---

## What Was Phase 6?

Phase 6 focused on three pillars: **print quality**, **test coverage**, and **observability**. The goal was to bring the Zone Deployment Book from a working but fragile print pipeline to a fully production-grade, regression-tested system ready for nightly shift operations.

---

## Completed Work

### 1. Printed Book — WeasyPrint Fix (Phase 1)

The root cause of the 21-page output (instead of 14) was a cascade of three WeasyPrint-specific bugs:

- **`@page { size: 11in 8.5in landscape }` silently ignored.** WeasyPrint drops the entire `@page` rule when `landscape` follows explicit dimensions. Fixed by string-replacing the `landscape` keyword and injecting a fresh `@page { size: 11in 8.5in; }` rule.
- **CSS Grid `fr` units fail in fixed-height containers.** WeasyPrint cannot resolve `fr` units inside `height: 8.5in` pages. Fixed by replacing the grid layout with Flexbox `flex-grow` ratios injected via `PrintService._inject_weasyprint_compat()`.
- **`display: none !important` ignored in paged media.** The overlaps section on break-sheet pages would not hide, causing overflow to a third spurious page per day. Fixed by physically removing the `<section class="overlaps-section">` from break-sheet articles before WeasyPrint renders.
- **Wrong class name `break-sheet` vs `break-page`.** Every CSS rule targeting `.break-sheet .break-cols` was dead code. Fixed by using the correct class name from the golden master: `break-page`.

All fixes live in `apps/zds/api/services/print_service.py → _inject_weasyprint_compat()`. The sacred renderer (`print_renderer.py`, `render_deployment_book.py`) was not modified.

**Commit:** `10d8a08 fix(print): align WeasyPrint compat with golden master`

### 2. Golden Master — 14-Page Lock (Phase 2 golden)

- Regenerated all golden artifacts from the live PrintService HTML endpoint via WeasyPrint.
- 14 pages confirmed: 7 zone deployment pages + 7 break sheet pages.
- PDF, 14 PNG pages (150 DPI), text JSON, and manifest all committed to `tests/print_regression/golden/`.
- Stale 21-page PNGs (page_15 through page_21) removed.

**Commit:** `da862a6 feat(render): Phase 2 — align CLI templates + 14-page golden`

### 3. Renderer CLI Alignment (Phase 2 render)

Updated `render_deployment_book.py`'s standalone CLI functions (`render_day_page`, `render_break_sheet_page`) to use the same class names as the golden master:

| Old | New |
|-----|-----|
| `mast-day` | `mast-day-num` |
| `month-str` | `month` |
| `status-row` | `status` |
| `break-dot g1/g2/g3` | `dot data-group="1/2/3"` |
| `mast-right` | `mast-context` |
| `shift-label` | `shift` |
| `section-lbl` | `section-label` |
| `overlap-time` | `overlap-window` |
| `foot-mark/foot-center/foot-pn` | `slug-mark/slug-path/slug-pn` |

Note: `print_renderer.py` (the live DB-connected renderer) already produced the correct class names independently. These CLI changes align the offline tool with the same conventions.

### 4. Integration & Smoke Test Suite

**`tests/integration/test_zds_forge_endpoints.py`** — 30 pytest tests covering all 5 endpoints:
- `GET /health` — status, shape, latency
- `GET /v1/print/week/{id}.html` — 200, content type, body size, 14 articles, Cache-Control, Content-Disposition, determinism, 404
- `GET /v1/print/week/{id}.pdf` — 200, PDF magic bytes, size, 404
- `GET /v1/print/night/{id}.html` — 200, 2 articles, 404
- `GET /v1/print/night/{id}.pdf` — 200 or skip (WeasyPrint)
- `GET /v1/planning/weekly/{id}` — shape, week_id match, 7 nights, links, Cache-Control max-age ≤ 15s, metrics typed, 404

**`scripts/smoke_test.py`** — standalone go/no-go script, exits 0 (pass) or 1 (fail). Hits all endpoints with colour-coded output. Safe to run in CI after `uvicorn` starts.

### 5. Observability

**`apps/zds/api/observability.py`** — full observability layer:

- **Prometheus metrics** (via `prometheus-client`, no-ops gracefully if absent):
  - `zds_http_requests_total` — labelled by method, endpoint template, status code
  - `zds_http_request_duration_seconds` — histogram, labelled by method + endpoint
  - `zds_cache_hits_total` / `zds_cache_misses_total` — labelled by cache key prefix
  - `zds_print_generation_seconds` — histogram, labelled by format + scope
  - `zds_print_errors_total` — labelled by format, scope, error_type
  - `zds_active_requests` — gauge

- **`/metrics` endpoint** — Prometheus scrape format, excluded from OpenAPI docs, `Cache-Control: no-store`.

- **`MetricsMiddleware`** — Starlette BaseHTTPMiddleware that records all of the above + emits a structured access log per request (method, endpoint template, status, duration_ms, client_host).

- **Sentry integration** — initialises if `SENTRY_DSN` is set; uses `StarletteIntegration` + `FastApiIntegration`; 10% trace sampling, 1% profiling, PII off. No-ops silently if `sentry-sdk` is not installed.

- **Wired into `main.py`** via `instrument_app(app, env=settings.env)` called at lifespan startup.

### 6. CI/CD Updates

**`.github/workflows/integration_tests.yml`** (new):
- `smoke` job: starts Forge, runs `scripts/smoke_test.py`, requires `SMOKE_WEEK_ID` + `SMOKE_NIGHT_ID` secrets.
- `integration` job: runs `pytest tests/integration/ -m integration`, depends on smoke passing.

**`.github/workflows/visual_regression.yml`** (updated):
- Added `golden-guard` job: post-Tier-1 check that PNG count in the directory matches the manifest. Catches accidental golden drift before it reaches main.

---

## Verification Commands

```bash
# Tier 1 golden integrity (no server needed)
PYTHONPATH=. pytest tests/print_regression/test_book_render.py -v -k tier1

# Integration tests (requires running server + env vars)
uvicorn apps.zds.api.main:app --port 8001 &
export PRINT_SERVICE_URL=http://localhost:8001
export PRINT_SERVICE_WEEK_ID=7f31103a-4bcd-4f65-99e8-dd6bbae580a9
pytest tests/integration/ -v

# Smoke test
python scripts/smoke_test.py

# Prometheus metrics
curl http://localhost:8001/metrics | head -40
```

---

## Phase 7 Outline — Migration & Cutover

Phase 7 is the transition from the internal grave-shift tool to a production-deployed, multi-user operations platform. Recommended scope:

**7.1 Auth & Multi-Tenancy**
- Add Supabase JWT auth to all non-`/health` endpoints
- Role model: `viewer`, `shift_lead`, `admin`
- Row-level security on the DB side to enforce per-tenant data isolation

**7.2 Render Deployment Book — Full Parity Audit**
- Run a full SSIM visual regression against a browser-print golden (Tier 3)
- Identify any remaining layout gaps (font rendering, card spacing, aux strip)
- Target: SSIM ≥ 0.97 on all 14 pages

**7.3 Live Annotations Write-Through**
- Promotion of the annotation layer from read-only to read-write via the API
- Invalidate print cache on annotation change (`invalidate_week_prints`)
- Webhook or Supabase Realtime push to connected browsers

**7.4 Staging → Production Cutover**
- Render staging pipeline validation (health, smoke, visual regression in staging env)
- DNS / environment promotion runbook
- Rollback procedure documented

**7.5 Monitoring & Alerting**
- Prometheus scrape configured in Render (or Grafana Cloud)
- Alert rules: p99 latency > 5s, error rate > 1%, print errors > 0 for 5 min
- Sentry project created, DSN set in Render env

**7.6 Operational Runbook**
- Golden update procedure (who approves, which commands, commit message format)
- Incident response for print failures during shift
- Weekly DB backup verification

---

*Phase 6 signed off by Brian Killian — 2026-05-12*
