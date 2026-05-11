# Archived Apps

Three Reflex apps are parked here while the ZDS migration to Next.js
runs. Each will be rebuilt on the new stack (FastAPI + Next.js) in its
own phase, but until then they're kept here read-only.

---

## What's parked

- **admin/** — Sudo admin hub (TM management, engine config, tasks
  CRUD, write-up review). Last shipped commit: see `git log apps/_archive/admin`.
- **glcr/** — GLCR Memory dashboard (Today page, Patterns, Threads,
  Writeups, People, Health, Recap). Last shipped commit: see `git log apps/_archive/glcr`.
- **shift/** — Shift HUD (live grave-shift dashboard, capture modals,
  Tonight panel). Last shipped commit: see `git log apps/_archive/shift`.

## Why they're parked

Reflex 0.9's type system, hydration model, and developer ergonomics
have caused recurring production issues (see the bug pattern from
2026-05-08 → 2026-05-12). The ZDS app is being rebuilt first as a
proof-of-architecture for FastAPI + Next.js. Other apps follow once
the new stack is validated.

## What they need to come back

Each app needs:

1. A FastAPI router added to `apps/zds/api/routers/` (or peer Forge
   service) — e.g. `apps/zds/api/routers/shift.py`
2. A Next.js route tree in `zds-web/app/(shift)/...`
3. Data models in `apps/zds/api/models/`
4. Migration of any `state.py` logic into Forge service methods
5. Phase documentation in `docs/ZDS_Forge_Full_Project_Redesign.md`

## Shared dependencies to audit when unarchiving

When unarchiving an app, check:

- `shared/db.py` — many functions only served archived apps; verify
  they're still wired (some may have been deleted during ZDS
  consolidation). Functions tagged `# ARCHIVED-APP-ONLY` are safe to
  port and remove here.
- `shared/auth.py` — auth strategy may have changed (Phase 8 introduces
  proper token-based auth replacing the site-PIN gate)
- `shared/base.py` — `AppState` class structure may need updates;
  `save_capture()` currently no-ops the Today refresh because
  `TodayState` (GLCR) is archived

## Note on auth pages

The auth pages (`/unlock`, `/login`, `/auth/callback`) still serve
the live ZDS app. They live at:

    apps/_archive/glcr/pages/unlock.py
    apps/_archive/glcr/pages/login.py
    apps/_archive/glcr/pages/auth_callback.py

…and are imported directly from `brijkillian_stack/brijkillian_stack.py`.
These pages only depend on `shared.auth` — no GLCR state.

## Reviving an app quickly (escape hatch)

If something archived urgently needs to come back BEFORE proper
migration, the safety tag `pre-archive-2026-05-12` captures the exact
state before any of these moves:

```bash
# Restore just one app from the tag
git checkout pre-archive-2026-05-12 -- apps/admin

# Then re-add the route registration in brijkillian_stack.py:
# from apps.admin.routes import ROUTES as ADMIN_ROUTES
# for entry in ADMIN_ROUTES: app.add_page(...)
```

The tag also captures the original `brijkillian_stack.py` with all four
route groups registered, if a full rollback is needed.
