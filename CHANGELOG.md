# Changelog

Entries in reverse-chronological order. One bullet per landed feature/fix.

---

## 2026-05-06 — Session zds_picker_highlight_ux (Sonnet)

### Part 1 — Tasks side panel inside TM picker
- **`get_canonical_tasks_for_slot(slot_code)`** (`shared/db.py`) — new DB helper; queries `overlap_tasks` by `slot_id` (case-insensitive); returns `list[str]`; empty list for zone/RR/aux slots with no canonical tasks.
- **`picker_tasks: list[str] = []`** (`apps/zds/state.py`) — new state field; populated in `open_picker` via `get_canonical_tasks_for_slot(slot_key)`; reset in `close_picker`.
- **`tm_picker_drawer` refactored** (`apps/zds/components/tm_picker.py`) — 2-column layout: `_left_pool_pane()` (search + legend + TM roster) + `_right_tasks_pane()` (canonical tasks, read-only). Drawer widened from 360px → 580px. Empty state: "No canonical tasks for this slot — add tasks after placement."

### Part 2 — Left-click highlight toolbar
- **`HighlightToolbarState`** (`shared/components/highlight_toolbar.py`) — new state class; `open_at(x, y, tm_id, night_id, slot_key)` opens toolbar; `apply_highlight(highlight_type)` toggles `assignment_highlights` row (same toggle logic as `ContextMenuState.mark_sweeper`); `close()` dismisses. 5 chips: sweeper / priority / watch / accommodation / custom.
- **`global_highlight_toolbar()`** (`shared/components/highlight_toolbar.py`) — fixed-position overlay component; anchored to element bounding rect; no modal backdrop shadow.
- **`assets/highlight_toolbar.css`** — chip styles (44pt touch targets, 2px colored border, hover fills with chip color); popover panel (white, rounded, shadow matching context menu chrome).
- **`assets/highlight_toolbar.js`** — document click listener (capture phase); intercepts `.ht-trigger` clicks; reads `data-ht-*` attrs; calls `e.stopPropagation()` to suppress parent `on_click` (picker); dispatches `highlight_toolbar_state.open_at` with `getBoundingClientRect()` anchor coords.
- **`.ht-trigger` wired** (`apps/zds/components/zone_card.py`) — TM name span in `zone_card` gains `class_name="ctx-menu-trigger ht-trigger"` + `data-ht-tm-id / night-id / slot-key` attrs (additive to existing `data-ctx-*` attrs; right-click behaviour unchanged).
- **`global_highlight_toolbar()` mounted** (`brijkillian_stack/brijkillian_stack.py`) — added to both `_with_grok` and `_with_zds_chrome` wrappers; CSS + JS registered in `head_components`.

---

## 2026-05-06 — Session engine_implementer (Sonnet)

### Phase A — Schedule Pool Date-Mismatch Fix
- **`get_active_schedule_path(week_id)`** (`apps/zds/schedule_parser.py`) — 3-tier fallback: DB-linked `weeks.schedule_path` → date-intersect scan of local xlsx files → mtime-newest with stderr warning. Replaces blind mtime-newest pick that caused empty pools when last week's file was still newest on disk.
- **`_reload_schedule()` updated** (`apps/zds/state.py`) — now calls `get_active_schedule_path(self.current_week_id)` and passes the path explicitly to `parse_daily_pools()`, fixing the root cause of the pool date-mismatch bug.

### Phase B — `engine_overrides` Table + DB Helpers
- **`engine_overrides` migration applied** — new Supabase table for engine deployment overrides (distinct from `schedule_overrides`, the Phase N.3 schedule-editor table). Schema: `(week_id, tm_id, override_date, override_type, payload, note, source, expires_at, applied_count, last_applied_at)` with `UNIQUE(week_id, tm_id, override_date, override_type)`.
- **Five DB helpers added** (`shared/db.py`): `get_engine_overrides()`, `set_engine_override()`, `clear_engine_override()`, `list_engine_overrides_for_week()`, `mark_engine_overrides_applied()`.

### Phase C — Call-Off Entry Points Write `engine_overrides`
- **`mark_called_off()`** (`apps/zds/state.py`) — after writing `call_offs`, also upserts an `engine_overrides` row with `override_type='unavailable'` for the current night + week. Non-fatal if the override write fails.
- **`unmark_called_off()`** (`apps/zds/state.py`) — after deleting from `call_offs`, also deletes the matching `engine_overrides` unavailable row.

### Phase D — Engine Consumes `engine_overrides`
- **`get_engine_overrides` + `mark_engine_overrides_applied` imported** (`apps/zds/engine/fill_engine.py`).
- **`WEEK_ID` lookup** — engine resolves `weeks.id` from `WEEK_ENDING` at startup; builds `_tmid_to_dn` map for tm_id→display_name translation. Gracefully no-ops if week isn't found (local stand-alone runs).
- **Hard filter in main fill loop** — for each night, loads engine_overrides and removes `unavailable` TMs from all three pools (grave, pm_ol, am_ol) before any slot fill. Emits `OVERRIDE_UNAVAILABLE` audit_item per filtered TM.
- **Soft overrides noted** — `prefer_easier`, `avoid_high_load`, etc. are logged to audit_items as `OVERRIDE_<TYPE>` with a "scoring integration: Phase K.4" note. Scoring integration deferred to K.4.
- **`applied_override_ids`** tracked across the full run; `applied_count` + `last_applied_at` incremented via `mark_engine_overrides_applied()` after AUDIT_JSON is written.
- **Audit JSON extended** — `applied_override_ids` list + `applied_overrides_count` in summary.

### Phase E — Persist `overlap_assignments`
- **`sync_engine_to_week()`** (`apps/zds/database.py`) — new step 6: after zone_assignments sync, iterates PMOL/AMOL placements and upserts into `overlap_assignments` on `UNIQUE(night_id, overlap_window, position)`. `overlap_updated` added to return dict.

### Phase F — Deferred
- `Rules/*.json` deletion deferred: `render_deployment_book.py` still actively reads `Overlap Tasks.json`, `Utility Porters.json`, `Training Config.json`, and TM Profiles.json. Files remain in place until that script is migrated to DB reads.

---

## 2026-05-05 — Session 4cc44251 (Opus + Sonnet)

### Auth & Access Control (Path C+)
- **Site PIN gate** (`shared/site_auth.py`, `apps/glcr/pages/unlock.py`, `assets/unlock.css`) — bcrypt PIN + HMAC-signed year-long session token replaces Caddy basic-auth and Supabase magic-link for access control
- **Three-tier role system** (`shared/auth.py`, `assets/role.css`) — viewer / zds_editor / editor roles; role chip in sidebar; PIN is TIER 2, editor role required for TIER 3 Memory pages
- **Route-level auth guard** (`brijkillian_stack/brijkillian_stack.py`) — `_on_load_for()` helper dispatches PUBLIC / VIEWER_OK / EDITOR_ANY on_load chains
- **Magic-link editor elevation** (`apps/glcr/pages/login.py`, `shared/auth.py`) — dev-mode disabled; `EDITOR_EMAILS` allowlist gates elevation
- **auth.py race condition fix** — `require_unlock` + `require_editor_any` correctly defer to `restore_editor_from_storage` async flow
- **Caddy basic-auth removed** (`Caddyfile`) — site-PIN gate is now the only auth layer

### Homepage & Navigation
- **Three-card launchpad homepage** (`shared/components/homepage.py`, `assets/homepage.css`) — Memory / ZDS / Floor Map cards at `/`
- **App switcher pills** (`shared/components/app_switcher.py`, `assets/styles.css`) — GLCR Memory ↔ ZDS navigation in sidebar and ZDS top-nav

### Context Menu
- **Global context menu foundation** (`shared/components/context_menu.py`, `assets/context_menu.css`, `assets/context_menu.js`) — right-click + long-press; wired on zone cards in ZDS

### Roles Feature
- **Roles on People page** (`apps/glcr/pages/people.py`, `shared/db.py`) — Porter / Utility Porter / ZDS Editor / Editor role chips with toggle UI
- **Roles in ZDS roster** (`apps/zds/database.py`) — utility_porter role excludes TMs from zone-deployment rotation
- **Roles backfill** — `roles=['porter']` written to all 127 active TM entities in `entities.metadata`
- **per-night highlights table** (`public.assignment_highlights`) — ephemeral nightly highlight storage for ZDS

### Phase K — iPad + Apple Pencil 2
- **Storage infrastructure** (`shared/storage.py`) — `get_signed_url`, `get_floor_map_url`, `upload_annotation`, `list_annotations` helpers; `casino-assets` + `annotations` private buckets
- **Annotations metadata table** (`public.annotations`) — kind, target_type, target_id, image_path, pen_settings, text_value, expires_at
- **Floor map uploaded** — `casino-assets/floor-maps/glcr_floor_map_dec_2025_no_logos.png` + 2 PDFs + Wayfinder/Satellite references; `zone_geometry.geometry.map_image_storage` updated
- **Scribble compatibility audit** — 38 text inputs across 17 files; all pass (standard rx.text_field/input/textarea); no blockers
- **K.1 PencilCanvas component** (`shared/components/pencil_canvas.py`, `assets/pencil_canvas.js`, `assets/pencil_canvas.css`) — pen/highlighter/eraser tools, Pencil 2 hover cursor, offscreen highlighter trick, pressure-sensitive widths, MutationObserver auto-init, save via `_reflexDispatch`
- **K.4 schedule annotation spec** (`docs/k4_schedule_review_spec.md`) — hybrid canvas overlay + structured schedule_overrides; ZDS-first reprioritization
- **K.5 Pencil hover spec** (`docs/k5_pencil_hover_spec.md`) — hover affordances design doc

### ZDS Engine Refactor (session 579194af)
- **fill_engine.py Supabase migration** — all 12 file reads (Rules/*.json, Eligibility Roster.xlsx, Profiles.json) replaced with Supabase DB calls via `shared/db.py` engine helpers
- **Engine DB helpers** (`shared/db.py`) — `get_engine_roster_from_db`, `get_engine_profiles_from_db`, `get_slot_difficulty`, `get_slot_load_scores`, `get_scorecard_config`, `get_overlap_tasks_for_engine`, `get_training_schedule_from_db`, `create_new_tm_stub_in_db`
- Smoke-tested: roster=50 TMs, all with complete 28-key eligibility dicts; all helpers pass shape checks

### Cleanup (this pass — session 4cc44251)
- Removed 3 debug `print()` statements from `shared/db.py` + `apps/glcr/state/people.py`
- `SUPABASE_ANON_KEY` removed from `render.yaml` (never read by code)
- `_on_load_for()` route guard helper extracted in `brijkillian_stack.py`
- Dual-storage doc comment added to `shared/db.py:get_people()` and `apps/zds/database.py:fetch_all_tms()`
- `logging` module introduced to `shared/db.py`; init `print()` replaced with `log.info()`
- Dockerfile API_URL/DEPLOY_URL hardcode annotated as intentional
- README updated: env var table, auth flow docs, current architecture notes
- `.bak` files (13) + stub `.py` files (11) in `apps/glcr/` confirmed inert; pending manual `git rm` (sandbox EPERM)

---

## 2026-05 — Session fac7cc87 (Prior session — Phase G / J groundwork)

- TM domain tables created (`tm_profiles`, `tm_eligibility`, `tm_preferences`, `tm_accommodations`, `tm_pair_affinities`, `scorecard_config`, `slot_difficulty`, `overlap_tasks`, `training_schedule`)
- ZDS webapp routes + database layer (`apps/zds/database.py`, `apps/zds/routes.py`)
- Shared component extraction: sidebar, palette, capture, grok panel → `shared/components/`
- Shared state extraction: auth, base, grok → `shared/`
- Grok panel + FAB (`shared/components/grok_panel.py`, `shared/grok_state.py`)
- Area check modal (`shared/components/area_check.py`)
- Agent logging infrastructure (`agent_logs` schema, `shared/agent_logs.py`)
- Memory/Shift split spec (`docs/memory_shift_split_spec.md`)
- Context menu remaining surfaces spec (`docs/context_menu_remaining_surfaces.md`)
