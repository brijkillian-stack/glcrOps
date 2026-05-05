# Memory + Shift split — implementation spec

This spec turns the current `apps/glcr/` directory into two sibling apps:
**`apps/memory/`** (the brain — search, people, logs, threads, patterns,
write-ups, health) and **`apps/shift/`** (in-the-moment — today, tasks,
recap, floor walk, areas, deployment). ZDS stays in `apps/zds/` unchanged.

Design is locked. Sonnet builds from this spec.

## 1. Why

The existing `apps/glcr/` houses 13 routes that pull double duty: half are
"sit at the desk and ask the corpus a question" (search, people, logs,
patterns, write-ups, threads, health) and half are "I'm on shift right
now, capture this, fix this, plan tonight" (today, tasks, recap, floor,
areas, deployment). Forcing both into one sidebar means every page wears
two hats and the entry point is always a compromise.

Splitting them along the brain-vs-in-the-moment axis lets each app
optimize for its actual mode of use, fits the iPhone bottom-tab cap of 5
naturally (each sub-app has 6-7 routes, not 13), and lets the Memory app
mature independently as a queryable corpus while Shift stays
operationally lean.

## 2. Final route map

```
/                                 home_page                 (Three-card launchpad — already shipped)
/login, /auth/callback            login, auth_callback      (public, unchanged)

────── apps/memory/ — the brain ──────────────────────────────────────────
/search                           search_page
/logs                             logs_page
/people                           people_page
/threads                          threads_page
/patterns                         patterns_page
/writeups                         writeups_page
/health                           health_page

────── apps/shift/ — in the moment ───────────────────────────────────────
/today                            today_page                (already moved off /)
/tasks                            tasks_page
/recap                            recap_page
/floor                            floor_page
/areas                            areas_page
/deployment                       deployment_page

────── apps/zds/ — unchanged ─────────────────────────────────────────────
/zds/                             ZDS index
/zds/week/[week_id]               week overview
/zds/week/[week_id]/day/[night]   per-night deployment
```

**No URL prefix** (e.g. `/memory/search`, `/shift/today`) — the routes
stay flat. Reasoning: existing notes, captures, and external docs link
to `/search`, `/people`, `/today`, etc. Adding a prefix breaks every
prior link and the team's muscle memory. The split is logical
(directory structure, sidebar nav, app switcher), not URL-level.

If a future need for prefixes arises (multi-tenant, branded subdomains),
introduce them as a route alias layer at that point.

## 3. File move plan

```
apps/glcr/                   →  apps/memory/  +  apps/shift/

apps/glcr/routes.py          →  apps/memory/routes.py  +  apps/shift/routes.py
                                (split the ROUTES list along the categorization above)

apps/glcr/pages/
  search.py, logs.py,
  people.py, threads.py,
  patterns.py, writeups.py,
  health.py                  →  apps/memory/pages/

  today.py, tasks.py,
  recap.py, floor.py,
  areas.py, deployment.py    →  apps/shift/pages/

  login.py, auth_callback.py →  apps/memory/pages/  (auth is shared but
                                  the magic-link surface logically belongs
                                  with the brain since that's where TM data
                                  lives)

apps/glcr/state/
  search.py, logs.py,
  people.py, threads.py,
  patterns.py, writeups.py,
  health.py                  →  apps/memory/state/

  today.py, tasks.py,
  recap.py, floor.py,
  areas.py, deployment.py    →  apps/shift/state/

apps/glcr/components/
  tm_drawer.py               →  apps/memory/components/
                                (used only by people.py)

apps/glcr/__init__.py        →  apps/memory/__init__.py  +  apps/shift/__init__.py

# Stubs to delete after migration verified
apps/glcr/glcr_dashboard.py
apps/glcr/db.py, ai.py
apps/glcr/components/{capture,grok_panel,palette,sidebar,ui}.py
apps/glcr/state/{auth,base,grok}.py
apps/glcr/state/*.bak files
```

`shared/` stays exactly as-is — the auth/db/ai/grok layer is identical
for both apps.

## 4. Sidebar split

The sidebar today is one fixed nav list. After the split, it's
context-aware:

```python
# shared/components/sidebar.py — replace static NAV_ITEMS / NAV_EXTRA with
# context-driven lists keyed off AppState.active_route.

MEMORY_NAV = [
    ("⌕", "Search",      "/search"),
    ("◉", "Logs",        "/logs"),
    ("◍", "People",      "/people"),
    ("❯❯","Threads",     "/threads"),
    ("✦", "Patterns",    "/patterns"),
    ("⊟", "Write-Ups",   "/writeups"),
    ("♥", "Health",      "/health"),
]

SHIFT_NAV = [
    ("⊙", "Today",       "/today"),
    ("☐", "Tasks",       "/tasks"),
    ("≡", "Shift Recap", "/recap"),
    ("◫", "Floor Walk",  "/floor"),
    ("⊞", "Areas",       "/areas"),
    ("▦", "Deployment",  "/deployment"),
]

ZDS_NAV = [
    ("▦", "Weeks",       "/zds/"),
    # ZDS sub-nav comes from the active week if any
]
```

Sidebar resolves which list to render based on the active route:
- routes in MEMORY_NAV → MEMORY_NAV is shown
- routes in SHIFT_NAV → SHIFT_NAV
- /zds/* → ZDS_NAV
- / (home) → no list (or a "pick an app" hint)

The shared chrome (brand mark, app switcher at top, dark-mode toggle,
palette ⌘K hint) stays identical across all three.

## 5. App switcher evolution — 2-pill → 3-way segmented control

```python
# shared/components/app_switcher.py — current is two pills (GLCR / ZDS).
# Evolve to three-segment iOS-style segmented control:
#
#   ┌──────────┬──────────┬──────────┐
#   │ Memory   │ Shift    │ ZDS      │
#   └──────────┴──────────┴──────────┘
#
# Active segment determined by AppState.active_route.
# Each segment is a link; tap navigates to the app's landing route
# (Memory → /search, Shift → /today, ZDS → /zds/).
```

Segmented control is the iOS HIG-correct pattern for ≤5 mutually
exclusive peer destinations. Pills with N=2 were defensible; pills with
N=3 start losing — segmented control is the right move.

## 6. Default route decision

`/` is the homepage (already shipped). When the user is unauthenticated,
require_auth redirects to `/login`. After login, redirect to `/` (the
launchpad), not to a specific app. That's the explicit "pick what
you're here for" behavior.

If you want to change later — e.g., land directly in Shift on launch —
update `exchange_session_from_url` and `handle_callback` to redirect
to `/today` instead of `/`. Single line change, no architectural
implication.

## 7. Shared state and cross-app references

State classes that are referenced across both apps:

```
shared/auth.py       AuthState              both apps
shared/base.py       AppState               both apps + ZDS
shared/grok_state.py GrokState              both apps
```

State classes used only within their app (most of the existing
GLCR state):

```
apps/memory/state/{search, logs, people, threads, patterns,
                   writeups, health}.py
apps/shift/state/{today, tasks, recap, floor, areas, deployment}.py
```

**TM data is read by both apps but written only from Memory.**
TM_drawer (the per-TM detail UI) lives in Memory but Shift's pages
(today, deployment) read tm_profiles + tm_eligibility for their own
displays. The discipline that keeps the split clean: Shift never
edits canonical TM data — it only reads. Edits route through Memory
pages.

**Capture is fired from anywhere, lands in Memory's tables.** The
global capture box (⌘N FAB) keeps writing to public.notes regardless
of which app the user is in. Authorship is the user; target/category
is what they pick at capture time.

**Grok panel is global to both apps.** GrokState stays shared.

## 8. Migration order — minimize broken-state windows

```
Step 1   Create empty apps/memory/, apps/shift/ skeletons (just __init__.py).

Step 2   Copy (don't move yet) all files into their new homes:
            cp apps/glcr/pages/*.py apps/memory/pages/   (memory pages)
            cp apps/glcr/state/*.py apps/memory/state/
            cp apps/glcr/pages/*.py apps/shift/pages/    (shift pages)
            cp apps/glcr/state/*.py apps/shift/state/
         Then delete the wrong-app copies from each new home so each
         app holds only its routes.

Step 3   Rewrite imports in the copied files:
            from .state.X         → unchanged (stays inside same app)
            from apps.glcr.state.X → from apps.memory.state.X
                                  or from apps.shift.state.X
            from apps.glcr.components.tm_drawer
                                  → from apps.memory.components.tm_drawer
         Keep imports of shared.* unchanged.

Step 4   Create apps/memory/routes.py and apps/shift/routes.py with
         the appropriate slice of the existing GLCR_ROUTES list.

Step 5   Update brijkillian_stack/brijkillian_stack.py:
            from apps.memory.routes import ROUTES as MEMORY_ROUTES, PUBLIC_ROUTES as MEMORY_PUBLIC
            from apps.shift.routes  import ROUTES as SHIFT_ROUTES,  PUBLIC_ROUTES as SHIFT_PUBLIC
            # remove apps.glcr.routes import
         Register both lists with _with_grok wrapping protected routes.

Step 6   Update shared/components/sidebar.py to context-driven nav lists
         (MEMORY_NAV / SHIFT_NAV / ZDS_NAV based on active_route).

Step 7   Update shared/components/app_switcher.py to a 3-segment
         segmented control.

Step 8   Smoke test:
            ✓ / shows the homepage
            ✓ Memory cards lead to /search
            ✓ Shift cards lead to /today
            ✓ ZDS cards lead to /zds/
            ✓ Sidebar shows the right nav per app
            ✓ App switcher shows 3 segments, active one highlighted
            ✓ ⌘K palette still opens
            ✓ Capture (⌘N) still writes to memory
            ✓ Grok panel still opens (⌘J)
            ✓ TM drawer on /people still works (was apps/glcr/components,
              now apps/memory/components)
            ✓ Engine refactor session is unaffected (apps/zds is untouched)

Step 9   Delete apps/glcr/ entirely. Verify nothing imports from there.

Step 10  Update README.md to reflect the new structure.
```

## 9. Open questions to resolve at start

```
Q1   Login surface — does login_page live in apps/memory/pages/, or in
     a top-level apps/auth/ since it's used by all three apps?
     Recommendation: apps/memory/ for now (simpler, fewer modules).
     Move to apps/auth/ if a third login surface (admin?) ever shows up.

Q2   The deployment_page in apps/glcr/pages/deployment.py is the
     read-only Shift view of ZDS output. Confirm it goes to
     apps/shift/pages/, not apps/zds/. (It's distinct from
     apps/zds/pages/deployment.py which is the editable per-night.)
     Recommendation: yes, apps/shift/pages/ — it's a Shift-side reader.

Q3   When Sonnet finds a state class referenced by both halves
     (none expected based on current code, but possible), promote it
     to shared/.
```

## 10. Estimated time

```
Step 1-2 (skeleton + copy)              30 min
Step 3 (import rewrite, ~30 files)      45-60 min
Step 4 (routes.py × 2)                  20 min
Step 5 (entry point update)             15 min
Step 6 (sidebar context-driven)         30-45 min
Step 7 (app_switcher 3-segment)         20-30 min
Step 8 (smoke tests + fixes)            30-45 min
Step 9-10 (delete glcr/, README)        15 min

Total: 3.5-4.5 hr Sonnet time, single focused session.
```

Recommend Sonnet hold off on starting until Brian has verified the
homepage + login changes shipped tonight don't introduce regressions.
The split is dependency-heavy on the current shared/auth.py state of
play — once Path A is settled and stable, the split inherits clean.
