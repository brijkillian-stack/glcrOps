# GLCR Memory + ZDS Unified Webapp — Comprehensive Review

**Last updated:** 2026-05-05  
**Codebase:** `brijkillian-stack/` on `main` (c8dc7db, Phase A-G complete)  
**Live URL:** https://glcrops.onrender.com (Render web service, $7/mo, Ohio)

---

## Executive Summary

You have a working, unified Reflex 0.9 monorepo that combines two operationally critical apps (GLCR Memory dashboard + Zone Deployment System) into a single Supabase-backed product. **The structure matches your intent almost perfectly.** The codebase is past "personal hack" and into "shippable internal product" territory. 

The Phase A-G unification was successful: both apps now share one auth layer, one database, one deploy pipeline, one container, and one mobile home-screen icon. Code that was duplicated is now centralized in `shared/`. The route registration pattern is clean. The deployment pipeline (Caddy + basic-auth gate + Reflex backend as a subprocess) works.

**Key brittleness** is real but not architectural: bus factor (you're the only reviewer), Reflex 0.9 framework edges (sharp corners in routing, Var system, SSR), slow deploy loop (5-8 min Render rebuild), and some tech debt (in-tree mutable state, 13 stale `.bak` files, auth seam complexity). None of these require tearing up the foundation.

---

## Structure Verification

✅ **Actual codebase matches your description exactly.** Here's what's actually present:

```
brijkillian-stack/                          ← Git root
├── brijkillian_stack/                      ← Reflex app entry (rx.App lives here)
│   └── brijkillian_stack.py (130 lines)    ← Unified app + route registration
├── apps/
│   ├── glcr/                               ← GLCR Memory (15 pages, 13 state modules)
│   │   ├── routes.py (57 lines)            ← Route table: 2 public + 13 protected
│   │   ├── pages/ (13 .py files)           ← login, today, search, people, etc.
│   │   ├── state/ (13 .py + 13 .py.bak)    ← State for each page
│   │   ├── components/ (6 files)           ← 1 real (tm_drawer.py), 5 stubs
│   │   └── {ai.py, db.py, glcr_dashboard.py} ← 1-line stubs (safe to delete)
│   └── zds/                                ← Zone Deployment System (3 pages, 1 state)
│       ├── routes.py (17 lines)            ← Route table: 3 routes, all public
│       ├── pages/ (3 .py files)            ← index, week_overview, deployment
│       ├── state.py (1127 lines)           ← ZdsState (fill, render, DB sync)
│       ├── engine/ (1358 + 2407 lines)     ← fill_engine.py + render_deployment_book.py
│       ├── engine/Rules/ (8 JSON + 1 xlsx) ← Config (Eligibility Roster, TM Profiles, etc.)
│       └── [database.py, engine_bridge.py, components/] ← Supporting code
├── shared/ (6 core modules + 6 components)
│   ├── db.py (1774 lines)                  ← Supabase client + GLCR helpers
│   ├── ai.py (431 lines)                   ← Grok client + tool dispatch
│   ├── auth.py (198 lines)                 ← Magic-link + JWT flow
│   ├── base.py (161 lines)                 ← AppState (nav, dark mode, palette/capture toggles)
│   ├── grok_state.py (209 lines)           ← GrokState (panel, query, results)
│   ├── storage.py (148 lines)              ← Supabase Storage helpers
│   └── components/ (6 files)               ← sidebar, app_switcher, grok_panel, capture, palette, ui
├── assets/ (styles.css, manifest.json, sw.js, icons/)
├── rxconfig.py (22 lines)                  ← Root Reflex config
├── requirements.txt (5 deps)               ← reflex 0.6+, supabase 2.4+, openpyxl, etc.
├── Dockerfile (88 lines)                   ← Single-stage, python:3.13-slim + Caddy
├── Caddyfile (42 lines)                    ← Reverse proxy, basic-auth gate, statics
├── entrypoint.sh (30 lines)                ← Reflex backend + Caddy boot
└── render.yaml (18 lines)                  ← Render web service config
```

### What's Actually Wired

**Route registration (brijkillian_stack.py, lines 94–119):**
- GLCR public routes (`/login`, `/auth/callback`) register without auth or Grok.
- GLCR protected routes wrap with `_with_grok()` (which injects grok_fab + grok_panel) + auth guard.
- ZDS routes register as public, no Grok wrap yet.
- Keyboard shortcuts injected at app level: ⌘K (palette), ⌘N (capture), ⌘J (Grok toggle), Esc (close-all).
- PWA metadata in `head_components` (manifest, theme-color, apple-touch-icon, service worker).

**Authentication (shared/auth.py):**
- Magic-link flow: email → Supabase Auth OTP → token exchange → JWT.
- Auth gate: Caddy basic-auth (username + bcrypt hash) sits in front; Reflex magic-link is the inner layer.
- Dual auth exists for a reason: ops staff won't always have email handy for magic links, but they have credentials for Caddy.
- Seam issue flagged: iPad auth bug is probably here (Caddy → browser magic-link flow state isn't clear).

**Database (shared/db.py, 1774 lines):**
- Supabase client singleton wrapping the service_role key (never exposed to browser).
- Schema: notes, tasks, events, entities, link tables, threads, files, search_log, _schema.
- Embeddings on notes and entities (vector(1536)).
- One helper per major feature: get_tonight_tasks(), get_notes_for_today(), get_search_results(), etc.

**AI (shared/ai.py, 431 lines):**
- xAI Grok client (grok-4 model, https://api.x.ai/v1).
- API key stored in Supabase Vault; fetched at startup via RPC, cached.
- System prompt positions Grok as a thinking partner who knows TM names, zone slang, GLCR policy.
- Foundation laid for Phase 5 (capture autocomplete, nightly Grok pass, insight cards).

**Deployment:**
- Docker: python:3.13-slim + Caddy from cloudsmith.
- Build-time: `reflex export --frontend-only` bakes API_URL into the JS bundle.
- Runtime: entrypoint starts Reflex backend (port 8000) + Caddy (port $PORT=10000).
- Healthcheck: hits `/health` every 15s (no auth, no proxy).
- Render: web service, Ohio region, $7/mo standard plan, auto-deploys from render.yaml.

---

## What's Working (and Why)

### ✅ Unified Architecture
- Single `rx.App()`, one route table, shared state + components.
- Both apps see the same Supabase database. Phone, iPad, work computer all have the same state.
- Container restart doesn't lose work (state is in Supabase, config is in git).
- One mobile home-screen icon per device (PWA manifest + service worker handle the install).

### ✅ The Engine
The Zone Deployment fill_engine.py (1358 lines) is the crown jewel. It:
- Encodes every rule you've worked out: skip-priority Z9 → Z3, Z9 SR specialist Fri/Sat, Daryl no_sweeper, women-no-sweeper default, 8-week area rotation, soft Admin preference.
- Runs in ~5–20 seconds; produces both the spreadsheet for ADP and a 7-page Deployment Book.
- Outputs an audit JSON explaining exactly why each TM ended up where.
- Would walk out the door with you in any other system; here it's executable.
- Currently runs as a subprocess (`engine_bridge.py` wraps it); fine for once/week Friday execution, latency would matter if you wanted live-update as you toggle eligibility.

### ✅ The Capture-to-Memory Loop
- One-line capture box (⌘N shortcut) → saves to notes table → auto-tags entities (TM names, zones, dates) → resurfaces in /search, /people, /logs.
- Nightly recap skill can pull a night's notes and compile a morning email.
- Progresssive discipline write-up generator drafts from captured evidence + policy text.
- Annual appraisal generator pulls a year's notes + events, applies the GLC rubric, produces a draft.
- This flow has teeth because every feature solves a real grave-shift problem you actually had.

### ✅ Grok Integration (Early Stage, Solid Foundation)
- Panel on every protected GLCR page; interrogates the memory via tools.
- Knows your TM names, zone slang, shift hours, GLCR Progressive Discipline policy.
- System prompt positions it as a thinking partner, not a chatbot.
- Phase 5 roadmap (capture autocomplete, nightly Grok pass, insight cards) builds cleanly on this.

### ✅ Basic-Auth Gate + Caddy
- Nobody on your ops team gets blocked by Supabase magic-link UX.
- Caddy sits in front, no auth required for `/health`.
- Backend paths (`/_event/*`, `/_upload/*`) proxy cleanly to Reflex.
- Statics served from pre-exported frontend.

### ✅ Code Organization After Phase A-G
- Shared code genuinely lives in `shared/` (db, ai, auth, components).
- App-specific code stays in `apps/{glcr,zds}/`.
- Route registration is explicit and auditable (route tuples with on_load handlers).
- Adds a new app (e.g., Floor Walk tab, Public Sweep Board)? Drop a new `apps/<name>/` directory, register routes.

---

## Brittleness & Technical Debt

### 🔴 Bus Factor = 1
- You wrote this, you maintain it.
- Tonight's debugging (broken relative imports, missing on_load handlers, unprefixed URLs, OneDrive paths) shipped because nobody else reviewed the PR.
- A second pair of eyes on code + smoke tests would catch a chunk of that.
- **Impact:** Medium. You catch issues on shift, but that's reactive. Proactive review would reduce reactive debugging.

### 🔴 Reflex 0.9 Framework Edges
- The framework churns. Var system, routing config, SSR build pipeline all have sharp corners.
- Tonight involved working around surprise behavior (e.g., relative imports breaking, on_load handler registration).
- You'll keep paying this tax as the framework evolves.
- **Impact:** Medium-high. Not a blocker, but a persistent source of friction.

### 🔴 Deploy Loop Too Slow for Debugging
- Each Render rebuild: 5–8 minutes.
- No preview environment. Every fix → push to prod main → watch glcrops.onrender.com.
- A staging branch deployed to a separate Render service (or even a local prod-mode test) would cut this in half.
- **Impact:** Medium. Tolerable for once/week deploys; painful for active debugging nights.

### 🟡 Auth Seams (Caddy + Supabase)
- Basic-auth (Caddy) + magic-link auth (Supabase) exist for good reasons, but the seams are where confusion lives.
- iPad auth bug you've been deferring is probably here.
- **Impact:** Low. It works, but the layers aren't clean.

### 🟡 In-Tree Mutable State
- `TM Profiles.json` and `Eligibility Roster.xlsx` live in git repo, marked runtime-mutable.
- If engine writes back on Render, they're lost on restart.
- If you edit locally, they dirty git.
- Long-term: these should be Supabase tables (no urgency; they don't change daily).
- **Impact:** Low. Technical debt, but not urgent.

### 🟡 Engine Latency
- fill_engine.py takes 5–20 seconds as a subprocess.
- Fine for once/week Friday execution.
- If you want it to live-update as you toggle TM eligibility, this latency dominates.
- Eventually: run in-process or cache results.
- **Impact:** Low. Future problem, not today's.

### 🟡 Stale Migration Artifacts
- `apps/glcr/state/*.py.bak` — 13 files left from Phase A-G (areas, deployment, floor, health, logs, patterns, people, recap, search, tasks, threads, today, writeups).
- `apps/glcr/components/` — 5 stubs (capture, grok_panel, palette, sidebar, ui) that say "Moved to shared/".
- `apps/glcr/{ai.py, db.py, glcr_dashboard.py}` — 1-line stubs.
- `apps/zds/glcr_zone_app.py` — 2-line stub.
- **Impact:** Very low (git history preserved, imports don't break). Cleanup is cosmetic.

### 🟡 Migrations Directory Empty
- `supabase/migrations/` and `docs/` are both present but empty.
- Reflex doesn't use migrations for its own tables (Supabase does the schema).
- This could become useful if you ever need to pin schema versions or document migrations.
- **Impact:** Very low.

---

## Specific Findings

### GLCR Routes (apps/glcr/routes.py)
- **Public:** /login, /auth/callback (✓ correct)
- **Protected:** 13 routes, each with an on_load handler (✓ sound pattern)
- **Pattern:** Each route tuple is (page_fn, route_path, title, on_load_list). Clean and auditable.
- **Example:** `(people_page, "/people", "People · GLCR Memory", [PeopleState.load_people])`

### ZDS Routes (apps/zds/routes.py)
- **All public:** /zds/, /zds/week/[week_id], /zds/week/[week_id]/day/[night_id].
- **On-load pattern:** URL params drive state hydration (ZdsState.on_week_overview_load reads router.page.params, fetches week).
- **Note:** ZDS routes don't have auth wrap or Grok wrap yet. When you extend ZDS (e.g., add a role-based deployment view), you'll want to add both.

### GLCR State Organization
- **One .py per page:** people.py (586 lines), tasks.py (293), today.py (208), etc.
- **Page-specific state:** TodayState has load_today + start_live_updates; PeopleState has load_people + skill scoring.
- **No cross-page state:** Each page's state is isolated (good for complexity, less good for sharing data across pages).
- **Shared state:** AuthState, AppState (nav, dark mode, palette/capture toggles), GrokState all live in `shared/`.

### GLCR Pages (apps/glcr/pages/)
- **today.py:** Command center (quick-log chips, tonight-task rows, privacy toggle).
- **search.py, logs.py:** Memory queries with Grok interrogation.
- **people.py (907 lines):** Biggest page; TM profiles, skill scores, observations history.
- **recap.py, writeups.py, deployment.py:** Output generation (morning email, discipline write-up, zone roster).
- **patterns.py, health.py, areas.py, floor.py, threads.py:** Specialized views (call-out clusters, TM fatigue, shift patterns, floor walks, conversation threads).

### ZDS Engine (apps/zds/engine/)
- **fill_engine.py (1358 lines):** The fill algorithm. Rules-based placement with multi-objective scoring.
  - Configurable from JSON (Training Config, Slot Difficulty, Scorecard Weights, Overlap Tasks, Utility Porters).
  - Outputs placement audit JSON (why each TM landed where).
  - Escapes relative to its own directory, which is why it works in both local and Render contexts.
- **render_deployment_book.py (2407 lines):** Generates a 7-page Deployment Book (HTML + PDF).
- **schedule_parser.py (262 lines):** ADP xlsx → week shape (Friday–Thursday, night names, day columns).
- **seed_week.py (354 lines):** Populates a new week record in Supabase from schedule + archive.
- **engine_bridge.py (184 lines):** Subprocess shim. ZdsState calls it; results come back as JSON.

### Shared Components
- **sidebar.py:** GLCR navigation (NAV_ITEMS + NAV_EXTRA, page titles, app switcher at top).
- **app_switcher.py:** GLCR ↔ ZDS toggle (pills, used in both apps).
- **grok_panel.py (184 lines):** Panel + FAB (Grok chat interface).
- **capture.py (121 lines):** Global capture box (⌘N).
- **palette.py (47 lines):** Command palette (⌘K).
- **ui.py (196 lines):** Shared primitives (kpi_card, brewing_card, feed_row, empty_state, skeleton_card).

---

## Deployment & Infrastructure

### Docker & Render
- **Image:** python:3.13-slim + Caddy (installed from cloudsmith).
- **Build time:** reflex export --frontend-only + API_URL baked in.
- **Runtime:** 
  - Reflex backend: `reflex run --env prod --backend-only` on port 8000.
  - Caddy: reverse proxy on port $PORT (10000 on Render).
  - Healthcheck: /health every 15s.
- **Render:** web service, standard $7/mo, Ohio region, auto-deploy from main.

### Caddyfile
- Basic-auth gate on all routes except /health.
- Backend paths (`/_event/*`, `/ping`, `/_upload/*`, etc.) proxy to localhost:8000.
- Static frontend served from /app/.web/build/client.

### entrypoint.sh
- Starts Reflex backend + Caddy in parallel.
- Uses `wait -n` (bash extension) to exit when either dies.
- Render handles restart.

---

## Phase 5 Readiness

The unified backend unlocks the Phase 5 work that's been queued:
- **Capture-box ghost-text autocomplete:** Query Grok for suggestions as you type.
- **Nightly Grok pass (via Edge Function + pg_cron):** Summarize shift, flag patterns.
- **Page-level insight cards:** "Cookie's got 3 late-ins in 8 days. Check in?"
- **Cowork ↔ Dashboard parity:** Shift-recap skill, TM-profile skill, write-up skill can all read/write the same backend.

All of this is built-in-able now because the database is unified, the Grok layer is alive, and the route registration is clean.

---

## Recommendations (Prioritized)

### Priority 1: Reduce Bus Factor (2–3 hours)
- **Add smoke tests:** Does capture save? Does engine run? Does print render? Run on each push to main.
- **Set up a staging branch:** Deploy to a separate Render service. Test migrations, auth flows, engine runs there before merging to main.
- **Code review cadence:** Even 15 min of second-opinion review on PRs catches most of the relative-import and on_load bugs.
- **Why now:** You're carrying all risk solo. This buys you insurance.

### Priority 2: Cleanup Stale Migration Artifacts (30 min)
- **Delete .bak files:** `apps/glcr/state/*.py.bak` (13 files).
- **Delete stubs:** `apps/glcr/components/{capture,grok_panel,palette,sidebar,ui}.py`, `apps/glcr/{ai,db,glcr_dashboard}.py`, `apps/zds/glcr_zone_app.py`.
- **Verify imports don't break:** `grep -r "from.*\.py\.bak" .` and `grep -r "glcr/ai\|glcr/db\|glcr/glcr_dashboard" .` should return nothing.
- **Why now:** Git history is preserved; cleanup is purely cosmetic. Do it once and move on.

### Priority 3: Document the Engine (1–2 hours)
- **Readme in apps/zds/engine/:** Explain the fill algorithm, config files, how to run it locally.
- **Inline scorecard.py:** Multi-objective scoring is the heart; add a walkthrough comment.
- **Reference card:** Zone geometry, skip-priority rules, training pre-pass logic.
- **Why now:** If you ever bring in another supervisor, the engine is the knowledge transfer bottleneck.

### Priority 4: Migrate In-Tree Mutable State to Supabase (4–6 hours, not urgent)
- **TM Profiles.json → tm_profiles table:** Schema: id, name, skill_scores (zone1–zone10), notes, archived, updated_at.
- **Eligibility Roster.xlsx → eligibility_roster table:** Schema: id, name, zones_trained, archival_date, etc.
- **Archive.xlsx → separate archive_placements table:** Track historical placements for rotation logic.
- **Why later:** These don't change daily. Current approach (in-tree, mutable) is technically debt but not urgent.

### Priority 5: iPad Auth Bug (1–2 hours debugging when you hit it again)
- **Expected issue:** Caddy basic-auth → browser → Supabase magic-link → token exchange → redirect loop or blank page.
- **Workaround for now:** Use Safari on iPad; check if incognito mode helps.
- **Fix when you debug:** Add logging at each seam (Caddy, magic-link form, callback, JWT store). Pin down which layer is failing.

### Priority 6: Phase 5 Roadmap (Separate conversations)
- Capture autocomplete (Grok suggestions as you type).
- Nightly Grok pass (summarize shift, flag patterns).
- Insight cards (contextual TM observations).
- Cowork ↔ Dashboard parity (shared backend for skills, notes).

---

## Architecture Critique

### What's Solid
- **Route registration pattern:** Explicit tuples with on_load handlers. Easy to audit, easy to add routes.
- **Shared layer:** db, ai, auth, components all centralized. Minimal duplication.
- **Database schema:** Supabase design (notes, entities, link tables, embeddings) is sound. Flexible for future queries.
- **Deployment:** One container, one Render service, one GitHub push. Complexity is low.

### What's Awkward
- **Caddy + Supabase auth:** Dual layers exist for UX reasons (ops staff credentials vs magic links), but the seam is where bugs hide. Not wrong, just not clean.
- **Reflex 0.9 framework fit:** Reflex is young; sharp edges in routing, Var system, SSR. You're paying the tax of early adoption. Not a blocker, but a friction point.
- **Page-level state isolation:** Each page has its own state module (people.py, tasks.py, today.py). Good for complexity control, but harder to share data across pages (e.g., selected TM in people.py used on tasks.py requires lifting state to AppState). Not a blocker, just a pattern to keep in mind.

### What Works Better Than You'd Expect
- **Subprocess engine:** fill_engine.py runs as a subprocess (engine_bridge.py wraps it). For a once/week Friday execution, this is perfectly fine. If you wanted live-update, you'd cache or move in-process. Not a blocker.
- **Service Worker + PWA:** Mobile install works (manifest, apple-touch-icon, SW registration). Users can add to home screen. Offline support is baseline.
- **Git as source of truth:** Code, config (Rules/*.json, Templates/*.xlsx) all in repo. Render rebuilds from main. State lives in Supabase. Clear separation.

---

## Summary Table

| Area | Status | Risk | Action |
|------|--------|------|--------|
| **Architecture** | ✅ Sound | Low | None. Foundations are solid. |
| **Route registration** | ✅ Clean | Low | None. Pattern is clear. |
| **Shared state & components** | ✅ Organized | Low | None. Code is centralized. |
| **Database (Supabase)** | ✅ Working | Low | None. Schema is flexible. |
| **GLCR pages** | ✅ Functional | Low | Add smoke tests (Priority 1). |
| **ZDS engine** | ✅ Working | Low | Document it (Priority 3). |
| **Grok integration** | ✅ Foundational | Low | Roadmap Phase 5 (later). |
| **Deploy pipeline** | ✅ Working | Medium | Add staging branch (Priority 1). |
| **Bus factor** | 🔴 Critical | High | Add review + tests (Priority 1). |
| **Reflex 0.9 edges** | 🟡 Friction | Medium | Monitor, work around. Accept tax. |
| **Stale artifacts** | 🟡 Clutter | Very low | Clean up (Priority 2). |
| **In-tree mutable state** | 🟡 Debt | Low | Migrate to Supabase later (Priority 4). |
| **Auth seams** | 🟡 Awkward | Low | Debug iPad bug when it resurfaces (Priority 5). |

---

## Next Steps

1. **Immediate (today):** Review this document. Do the .bak file cleanup if you have 30 min.
2. **This week:** Add 2–3 smoke tests. Spin up a staging branch + separate Render service.
3. **Next two weeks:** Document the engine. Get one other person to review a pull request (any small fix, just to build the habit).
4. **May/June:** Phase 5 planning conversation (autocomplete, nightly Grok, insight cards).

You've built something real here. The unification is complete, the infrastructure is sound, and the operations work you've encoded in the engine is genuinely unique. Keep building.
