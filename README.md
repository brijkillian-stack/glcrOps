# brijkillian-stack

Unified Reflex 0.9 monorepo hosting two applications:

- **GLCR Memory** — Gun Lake Casino Operations Memory Dashboard
- **ZDS** — Zone Deployment System

## Structure

```
/Users/briankillian/dev/brijkillian-stack/
├── brijkillian_stack/          Main app module (Reflex entry point)
│   └── brijkillian_stack.py    Unified app + route registration
├── apps/
│   ├── glcr/                   GLCR Memory dashboard
│   │   ├── routes.py           Route definitions
│   │   ├── pages/              Page components
│   │   ├── state/              State management
│   │   └── components/         GLCR-specific UI
│   └── zds/                    Zone Deployment System
│       ├── routes.py           Route definitions
│       ├── pages/              Zone deployment pages
│       ├── components/         ZDS-specific UI
│       └── state.py, database.py, etc.
├── shared/                     Shared utilities + components
│   ├── db.py                   Supabase client (from GLCR)
│   ├── ai.py                   AI integration
│   ├── auth.py, base.py        Shared state (from GLCR)
│   └── components/             Shared UI (sidebar, grok panel, etc.)
├── rxconfig.py                 Root Reflex config
├── requirements.txt            Merged dependencies
├── Dockerfile / Caddyfile      Deploy infrastructure
└── entrypoint.sh               Container boot script
```

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Start the dev server (auto-reloads on file changes)
reflex run

# Browser: http://localhost:3000
```

## Deployment (Render)

```bash
# Build Docker image locally for testing
docker build -t brijkillian-stack .

# Run container
docker run -p 10000:10000 \
  -e SUPABASE_URL=... \
  -e SUPABASE_SERVICE_KEY=... \
  -e BASIC_AUTH_USER=... \
  -e BASIC_AUTH_HASH=... \
  brijkillian-stack
```

Push to GitHub; Render auto-deploys from `render.yaml`.

## Key Files Modified

- **brijkillian_stack/brijkillian_stack.py** — Unified app entry (replaces old glcr_dashboard.py + glcr_zone_app.py)
- **apps/glcr/routes.py** — GLCR route table (extracted from glcr_dashboard.py)
- **apps/zds/routes.py** — ZDS route table (extracted from glcr_zone_app.py)
- **rxconfig.py** — Root config (replaces apps/zds/rxconfig.py)
- **requirements.txt** — Merged from glcr + zds requirements

## Notes

- ZDS files in `apps/zds/glcr_zone_app/` are still nested; flattening can be done in a follow-up if import refactoring is needed.
- Auth is GLCR-only for now; ZDS routes are public.
- Grok panel is injected on protected GLCR pages; ZDS routes don't have Grok yet.
