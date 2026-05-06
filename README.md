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
  -e BASIC_AUTH_HASH=... \
  -e SITE_SESSION_SECRET=... \
  -e EDITOR_EMAILS=... \
  brijkillian-stack
```

**Required environment variables:**

| Variable | Purpose |
|---|---|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Service-role key (secret) |
| `BASIC_AUTH_HASH` | bcrypt hash of the site PIN — generated via `python3 -m shared.site_auth` |
| `SITE_SESSION_SECRET` | HMAC key for signing site-session tokens (32+ random bytes) |
| `EDITOR_EMAILS` | Comma-separated email allowlist for magic-link editor elevation |

> **Auth flow (Path C, 2026-05-05):** The site is protected by a PIN entered on `/unlock`.
> Successful PIN entry sets an HMAC-signed session token (valid ~1 year) in localStorage.
> Editor elevation is available via magic-link (currently disabled in dev — set
> `MAGIC_LINK_ENABLED=true` to enable). `BASIC_AUTH_USER` is no longer used.

Push to GitHub; Render auto-deploys from `render.yaml`.

## Key Files Modified

- **brijkillian_stack/brijkillian_stack.py** — Unified app entry + three-tier route auth guard
- **shared/auth.py** — AuthState: viewer / zds_editor / editor tiers, PIN gate, magic-link
- **shared/site_auth.py** — bcrypt PIN verification + HMAC session token signing
- **apps/glcr/routes.py** — GLCR route table with PUBLIC / VIEWER_OK / EDITOR_ANY tiers
- **apps/zds/routes.py** — ZDS route table (all viewer-OK; write gating is per-event-handler)
- **shared/components/** — Sidebar, Grok panel, PencilCanvas (Phase K.1), context menu
- **rxconfig.py** — Root config (replaces apps/zds/rxconfig.py)
- **requirements.txt** — Merged from glcr + zds requirements

## Notes

- Phase K (iPad + Apple Pencil): PencilCanvas component in `shared/components/pencil_canvas.py`;
  floor map + annotation storage in Supabase Storage (`casino-assets`, `annotations` buckets).
- ZDS zone deployment engine reads from Supabase DB (refactored 2026-05-05, session 579194af).
  Local `Rules/*.json` files are superseded but not yet deleted — pending engine run verification.
- Dual TM data stores: `entities.metadata` (legacy, web readers) and `tm_profiles` (new domain
  tables, engine readers). Migration plan documented in `shared/db.py:get_people()`.
