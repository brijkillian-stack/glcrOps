# ZDS Forge API

FastAPI service that exposes the Zone Deployment Book renderer and the ZDS
data layer over HTTP.

---

## Boot

```bash
# From the repo root (brijkillian-stack/)
uvicorn apps.zds.api.main:app --reload --port 8001
```

Health check:

```bash
curl http://localhost:8001/health
# {"status": "ok"}
```

Interactive docs: http://localhost:8001/docs

---

## Print endpoints

The print router converts Zone Deployment Book data into browser-ready HTML
and PDF.  URL suffixes — not Accept headers — control the format so browsers
open the right viewer without content negotiation.

### Full-week deployment book

```bash
# HTML — open in browser, use Ctrl+P to print
curl http://localhost:8001/v1/print/week/{week_id}.html -o book.html

# PDF — opens in browser PDF viewer
curl http://localhost:8001/v1/print/week/{week_id}.pdf -o book.pdf
```

### Single-night pages

```bash
curl http://localhost:8001/v1/print/night/{night_id}.html -o night.html
curl http://localhost:8001/v1/print/night/{night_id}.pdf  -o night.pdf
```

### Response headers (all print endpoints)

| Header | Value |
|---|---|
| `Cache-Control` | `private, max-age=300` |
| `Content-Disposition` | `inline; filename="zone_deployment_book_<date>_<hash>.<ext>"` |

The filename embeds a content hash that changes whenever the underlying
assignment data changes, giving browsers a reliable cache-bust hint.

### Error envelopes

```json
// 404 — week or night not found
{"detail": {"error": "not_found", "detail": "Week not found: 'bad-id'"}}

// 500 — renderer or weasyprint failure
{"detail": {"error": "render_failed", "detail": "..."}}
```

---

## The sacred-renderer rule

> **§7 — ABSOLUTE**: `apps/zds/print_renderer.py` and
> `apps/zds/engine/render_deployment_book.py` must never be modified.

`PrintService` wraps the renderer as a read-only black box.  It adds a
cache layer around the renderer's output; it does not touch the renderer
itself.  The Phase 0 visual regression suite (`tests/print_regression/`)
enforces this by locking golden PDF and per-page PNG checksums.

If you need to change rendered output, update the renderer in its own
branch, regenerate the golden files with `python tests/print_regression/update_golden.py`,
and verify all three regression tiers pass before merging.

---

## Cache strategy

PrintService uses content-hash keyed caching:

```
print:week:{week_id}:{sha1_8char}.html   TTL 1 h
print:week:{week_id}:{sha1_8char}.pdf    TTL 2 h
print:night:{night_id}:{sha1_8char}.html TTL 1 h
print:night:{night_id}:{sha1_8char}.pdf  TTL 2 h
```

The hash is `sha1(json({week_ending, status, sorted_night_ids, sorted_tm_ids}))[:8]`.
It changes whenever PlacementService caches are busted by a write, so stale
HTML/PDF entries are never served after a supervisor edit — the old hash key
simply expires while the fresh hash key holds the new render.

### Manual cache invalidation

Use the `invalidate_*` helpers in `PrintService` when an admin flush is
needed (e.g. after a direct DB edit that bypasses the API):

```python
await print_service.invalidate_week_prints(week_id)   # clears all print:week:{id}:* keys
await print_service.invalidate_night_prints(night_id) # clears all print:night:{id}:* keys
```

Redis is optional.  If `REDIS_URL` is unset or Redis is unreachable,
`CacheService` silently no-ops and every render hits the sacred renderer
directly.

---

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | Service-role key (bypasses RLS) |
| `REDIS_URL` | No | Redis connection string — caching disabled if unset |

---

## PDF dependency

PDF endpoints require [weasyprint](https://weasyprint.org/):

```bash
pip install weasyprint

# macOS also needs:
brew install pango cairo
```

If weasyprint is not installed, PDF endpoints return `500 render_failed`
immediately.  There is no fallback engine — this is intentional.

---

## Running tests

```bash
# Unit + service tests (no DB needed)
pytest apps/zds/api/tests/ -v --asyncio-mode=auto

# API-tier structural tests (no DB needed)
pytest tests/print_regression/test_api_print.py -v --asyncio-mode=auto -k tier1

# Full print regression suite (requires SUPABASE_URL + SUPABASE_SERVICE_KEY)
pytest tests/print_regression/ -v --asyncio-mode=auto

# All of the above
pytest apps/zds/api/tests/ tests/print_regression/ -v --asyncio-mode=auto
```

All Tier 1 tests run without a database.  Tier 2 (adapter transparency) and
Tier 3 (SSIM visual) auto-skip when Supabase env vars are absent.

---

## Project layout

```
apps/zds/api/
├── main.py                     FastAPI app + lifespan
├── core/
│   ├── config.py               Pydantic Settings (env vars)
│   └── dependencies.py         DI singletons (get_print_service, etc.)
├── models/
│   ├── week.py                 WeekRow, NightRow
│   ├── task.py                 TaskRow
│   ├── annotation.py           AnnotationRow
│   ├── override.py             OverrideRow
│   ├── tm.py                   TMRow
│   └── assignment.py           AssignmentRow, MultiAreaAssignmentRow
├── routers/
│   └── print.py                /v1/print/* endpoints
├── services/
│   ├── cache_service.py        Redis cache-through layer
│   ├── placement_service.py    DB read/write + cache invalidation
│   ├── print_service.py        Sacred-renderer adapter
│   └── exceptions.py           WeekNotFoundError, NightNotFoundError, RenderError
└── tests/
    ├── conftest.py             Fakes and fixtures
    ├── test_cache_service.py   27 unit tests
    └── test_placement_service.py  20 unit tests

tests/print_regression/
├── conftest.py                 Tier 2/3 fixtures
├── test_book_render.py         Tier 1/2/3 visual regression
├── test_api_print.py           Tier 1/2 API-tier regression
├── update_golden.py            Regenerate golden files
└── golden/                     PDF master, PNGs, text JSON, manifest
```
