# Changelog

Entries in reverse-chronological order. One bullet per landed feature/fix.

---

## 2026-05-08 — Phase 4g: Deployment Book visual refresh + Break Sheet redesign (Sonnet)

### 4g.1 — Title fix (`render_deployment_book.py`)
- Removed duplicate "Week ending" prefix from HTML_SHELL `<title>` tag. The
  `week_end_short` variable already contains the formatted date string; the old
  template prepended "Week ending " again → "Week ending Week ending …".

### 4g.2 — Zone color stripe boost + Admin color (`render_deployment_book.py`, `print_renderer.py`)
- `.zone-card::before` stripe height boosted 3 px → 5 px for stronger visual anchor.
- `.aux-card::before` stripe height boosted 2 px → 4 px.
- Admin aux card color changed purple → yellow in both `_AUX_COLOR` dict and
  `render_aux_card()` call site (`render_deployment_book.py`) and `_aux_color_map`
  in `_break_row_meta()` (`print_renderer.py`).

### 4g.3 — Watermark opacity/size reduction (`render_deployment_book.py`)
- `.card-watermark` base opacity: 0.10 → 0.07.
- `.zone-card .card-watermark` font-size: 130 px → 90 px (less visual noise on
  crowded zone cards; `.rr-card` stays at 95 px).

### 4g.4 — Week-dot strip dynamic highlight (`render_deployment_book.py`)
- Fixed hardcoded bug in `render_day_page()`: the F/S/S/M/T/W/T dot strip always
  highlighted T (Tuesday) because `current_idx == idx - 1` is structurally always
  True. Replaced with a dynamic `enumerate` + `i == current_idx` comparison.
- Added week-dots strip to `render_break_sheet_page()` (was showing plain text
  "Take breaks together"; now shows the matching dot row with correct day highlighted).
- `render_break_sheet_page()` gains `current_idx=None` keyword arg; call site at
  line 2444 now passes `current_idx=idx`.

### 4g.5 — Filled/Open counts in deployment masthead (`render_deployment_book.py`)
- Added `X Filled · Y Open` stat spans to the `status-row` in `render_day_page()`,
  computed from `count_summary()` totals across zones + rr + aux + overlaps.

### 4g.6 — Break Sheet group model fix (`print_renderer.py`)
- Root cause of 25/0/0 bug: Phase 4d set all `break_wave` DB column values to 1.
  `_render_break_page()` read that column → every TM ended up in Wave 1.
- Added `_wave_for_slot_ref(slot_ref: str) -> int` helper that derives the break
  wave from slot_ref using `BG_ZONE / BG_RR_M / BG_RR_W / BG_AUX` dicts (same
  source of truth as `render_deployment_book.py`). Safe fallback returns 1.
- `_render_break_page()` now sorts by `sort_order` only and derives wave via
  `_wave_for_slot_ref()` — ignores the unreliable DB column.

### 4g.7 — OVERLAPS on break sheet page (`render_deployment_book.py`)
- `render_break_sheet_page()` now renders a full OVERLAPS section (PM 11p–1a and
  AM 5a–7a mini-card grids) below the break columns — mirrors the layout the
  standalone deployment page already had.
- `break-cols` constrained to `max-height: 5.4in` so overlaps section is never
  pushed off-page.
- Task lookup uses the same `TASKS_PM_OL / TASKS_AM_OL / OVERLAP_OVERRIDES`
  globals already loaded at render time.

### 4g.8 — Selectable AM/PM overlaps on live Break Sheet (`state.py`, `deployment.py`)
- Added `ZdsState.open_overlap_picker(slot_id, window, position)` event handler
  that derives `slot_key` ("PMOL1"–"PMOL6" / "AMOL1"–"AMOL6") and delegates to
  `open_picker()` — no changes to the picker itself.
- Overlap mini-cards in `_overlap_row_comp()` now have `cursor="pointer"`,
  `on_click=ZdsState.open_overlap_picker(…)`, and a blue hover ring, matching the
  tap-to-edit pattern of zone/RR/aux cards.

---

## 2026-05-07 — Phase 4f: Hungarian/LAP solver for constrained block (Sonnet)

### F.1 — scipy dependency
- Added `scipy>=1.11.0` to `requirements.txt`.

### F.2 — `apps/zds/engine/glcr_engine/lap_solver.py` (new file)
- `SlotSpec` dataclass — descriptor for one slot in the constrained block
  (`slot_code`, `elig_col`, `priority`, `skill_priority`, `soft_prefer_set`,
  `prefer_elig`, `prefer_names`, `avoid_names`, `skip_trainees`, `pool_type`).
- `solve_constrained_block()` — accepts pool, specs, and all fill_engine state as
  parameters; builds an `n_pool × n_slots` cost matrix; runs
  `scipy.optimize.linear_sum_assignment`; returns `{slot_code: dn|None}` +
  `fallback_detail` list.
- `HARD_BLOCK_COST = 1e9` (ineligible / physically restricted / unoverridable).
- `SOFT_BLOCK_COST = 1e6` (BTB or hard-preference override — last resort).
- Graceful degradation: if scipy not installed, returns all-None so caller falls
  back to greedy for every slot individually.
- Prefer-names post-solve correction: if LAP picks a non-specialist for Z9SR on
  Fri/Sat but a specialist is available, swap applied before writing.

### F.3 — `apps/zds/engine/fill_engine.py`
- Added `PLACEMENT_METHOD: str` constant sourced from `_CONFIG_OVERRIDE.get("placement_method", "greedy")`.
- Added `_lap_fill_constrained_block(day, d, gpool, placed)` helper: builds 16
  `SlotSpec` objects (10 RRs + Admin + Z9SR + Z1/Z4/Z5/Z8), calls `_lap_solve()`,
  writes each assignment via `write_cell()` + `placed.add()` + `_record_placement()`,
  falls back to greedy `place()` for any `None` slot; logs LAP_SOFT_OVERRIDE and
  LAP_UNRESOLVED audit items.
- Main fill loop now branches: `if PLACEMENT_METHOD == "lap"` → LAP constrained
  block + greedy skip-priority zones; `else` → original sequential greedy
  (byte-identical, just wrapped in `else:`).

### F.4 — Supabase migration `add_placement_method_to_engine_config`
- `engine_config.placement_method TEXT NOT NULL DEFAULT 'greedy'`
- `engine_config_history.placement_method TEXT` (nullable; back-filled to 'greedy')
- `engine_config_drafts.placement_method TEXT NOT NULL DEFAULT 'greedy'`

### F.5 — `apps/admin/engine_state.py` + `apps/admin/pages/engine.py`
- `placement_method: str = "greedy"` added to `EngineConfiguratorState`.
- `_placement_method_str()` helper; `set_placement_method(v: str)` event.
- `_apply_config_row()` unpacks `placement_method` from DB row.
- `save_config()`, `run_simulation()`, and `run_multi_week_simulation()` all pass
  `placement_method` through `config_override`.
- `_placement_method_toggle()` radio component added to Thresholds tab.

### F.6 — `shared/db.py` + `apps/zds/engine/simulate_weeks.py`
- `get_active_engine_config()` now selects `placement_method`.
- `save_engine_config_active()` accepts `placement_method` kwarg; writes to
  active row and includes in history snapshot.
- `simulate_weeks._load_active_config()` includes `placement_method` in returned dict.

---

## 2026-05-07 — Phase 4e.1 + 4e.2: Enriched sim report + inline disclosure (Sonnet)

### Phase 4e.1 — Inline report disclosure in engine pane

- Added `msim_report_md: str = ""` to `EngineConfiguratorState`.
- After a successful multi-week sim run, `run_multi_week_simulation()` reads the
  `sim_report.md` file and stores it in `msim_report_md`.
- Added collapsible `rx.el.details` / `rx.el.summary("View full report")` block
  after stat cards in `_sim_pane()` — renders the markdown inline via `rx.markdown`.
- Added `.ops-sim-report-body` CSS to `assets/ops_tokens.css`: dark/light themed,
  scrollable at 480 px max-height, table + heading styles.

### Phase 4e.2A — `_extract_metrics()` enrichment (`simulate_weeks.py`)

- Added `MUST_FILL_ZONES = {"Zone1", "Zone4", "Zone5", "Zone8"}` and
  `SUPPORT_SLOTS = {"Support1", "Support2", "Support3", "MP1", "MP2"}` constants.
- Added `_load_slot_loads()`: fetches `slot_load_scores` table from DB once at
  startup; returns `{slot_id: float}`.
- `_extract_metrics()` now accepts `slot_loads` kwarg and computes three new fields:
  - `per_tm_load`: `{dn: weighted_load_sum}` — sum of `slot_load_scores` per TM.
  - `per_must_fill`: `{zone: {filled_nights, total_nights}}` for Z1/Z4/Z5/Z8.
  - `trainee_support_placements`: `{dn: count}` for TMs with `tm_skill ≤ 3` in
    support slots.

### Phase 4e.2B — `_aggregate()` enrichment

- Added `per_tm_load_mean`: `{dn: mean_weighted_load}` across all runs.
- Added `must_fill_rate`: `{zone: mean_fill_rate}` for Z1/Z4/Z5/Z8.
- Added `must_fill_avg`: scalar average of the 4 must-fill rates (feeds UI stat card).
- Added `trainee_support_mean`: `{dn: mean_support_placements}` across runs.
- Added `trainee_support_total`: scalar sum (feeds UI stat card).

### Phase 4e.2C — `_write_markdown()` enrichment (7 sections)

1. Aggregated Results (existing)
2. Comparison Delta with ✓/✗/≈ indicators (if baseline run)
3. Must-Fill Zone Coverage table (Z1/Z4/Z5/Z8 + avg row)
4. TM Load Distribution — top 10 most-loaded and bottom 10 least-loaded
5. Trainee Support Exposure (skill ≤ 3 TMs only)
6. Per-Run Details Proposed (existing)
7. Per-Run Details Baseline (existing, if applicable)

### Phase 4e.2D — Two new UI stat cards in `_sim_pane()`

- **Z1/4/5/8 covered** — `must_fill_avg` formatted as float, warns red if < 0.9.
- **Trainee runs/wk** — `trainee_support_total` (sum of trainee support placements
  across all trainees, mean across runs).

### Regression

- All 6/6 Phase 4e regression smoke tests still pass after changes.

---

## 2026-05-07 — Phase 4e: Scoring component wiring + multi-week simulator (Sonnet)

### Phase 4e Part A — Wire all four Phase 4c scoring components

**A.1 — `sweeper_history` (fill_engine.py + scorecard.py)**
- Built from `archive_history` + `SWEEPER_TAGGED_SLOTS` after archive loads.
  14-day lookback window; `{display_name: [iso_date, ...]}` structure counts
  each sweeper slot's most-recent date within the window.
- Passed to `_sc.init(sweeper_history=...)` so `sweeper_rotation_penalty`
  fires on real data instead of always returning 0.

**A.2 — `prior_placements` (fill_engine.py)**
- Added `_slot_key_to_engine_code()` helper: maps DB `zone_assignments.slot_key`
  + `rr_side` → fill_engine slot codes (e.g. `"rr_1_2"/"mens"` → `"MRR1"`).
- Added `_load_prior_placements()`: queries `zone_assignments JOIN nights JOIN
  tm_profiles` for the current week_id, returns `{day_name: {slot_code: dn}}`.
- Passed to `_sc.init(prior_placements=...)` so `prior_run_continuity`
  penalizes displacing stable assignments.

**A.3 — `week_load_so_far` accumulator (scorecard.py + fill_engine.py)**
- New `"week_load_so_far": {}` key in `_state` (reset on every `init()`).
- New `record_placement_load(dn, slot_code)` function: O(1) increment of
  `_state["week_load_so_far"][dn] += slot_load`.
- `weekly_load_balance` component updated: reads `week_load_so_far[dn]`
  directly instead of iterating all `day_placements` (O(n) → O(1)).
- `_record_placement()` in fill_engine calls `_sc.record_placement_load(dn, slot)`
  after every successful placement.

**A.4 — `skill_stretch_reward` confirmed already wired correctly** (pure
  function, no state change needed).

**A.5 — Baseline weight migration applied via Supabase MCP**
- New active `engine_config` row with Phase 4e tuned baselines:
  `sweeper_rotation_penalty=0.3, skill_stretch_reward=0.3,
  prior_run_continuity=0.4, weekly_load_balance=0.5`.
- Previous all-zero row deactivated (preserved for rollback).

**A.6 — Regression smoke test: `apps/zds/engine/tests/test_regression_weights.py`**
- 6 tests verify byte-identical scorecard output when all 4 new component
  weights are 0.0. Confirms new wiring is a strict no-op at zero weight.
  All 6 pass.

### Phase 4e Part B — Multi-week stochastic simulator

**`apps/zds/engine/simulate_weeks.py`** (new CLI tool + library)
- Discovers N most-recent schedule xlsx files, runs fill_engine M times per
  schedule with Poisson(λ)-distributed simulated call-offs.
- Call-offs injected via the `"simulated_unavailable"` key in the
  `--config-override` JSON. fill_engine strips those TMs from all daily pools
  before placement.
- Aggregates per-run metrics: fill_rate, unresolved/critical count, load
  variance σ, simulated call-off count. Computes mean + p95 across all runs.
- Comparison mode (`--baseline`): runs both proposed and DB-active config with
  the same RNG seed sequence; output table shows Δ for each metric.
- Writes `Outputs/sim_<ts>/sim_results.json` and `sim_report.md`.
- Fixed seed (default 42); Knuth Poisson draw for small λ, normal approx for λ≥30.

**`fill_engine.py`** — `simulated_unavailable` support (Phase 4e B.2)
- Reads `_CONFIG_OVERRIDE.get("simulated_unavailable", [])` after schedule
  parsing and strips those TMs from all `daily_pools` before the fill loop.
  Invisible to production runs (no `--config-override` → list is empty).

**`apps/admin/engine_state.py`** — multi-week sim state + event (Phase 4e B.6)
- New state vars: `sim_mode`, `msim_weeks`, `msim_runs`, `msim_callout_rate`,
  `msim_seed`, `msim_compare_baseline`, `msim_running`, `msim_agg_proposed`,
  `msim_agg_baseline`, `msim_run_rows`, `msim_json_path`, `msim_md_path`.
- New event `run_multi_week_simulation()`: invokes simulate_weeks.main() in
  executor; populates aggregate result vars on completion.
- New setter events for all multi-week config params.

**`apps/admin/pages/engine.py`** — sim pane upgraded (Phase 4e B.6)
- `_sim_pane()` now has a Single-shot / Multi-week pill toggle.
- Multi-week mode shows compact config controls (weeks, runs, λ, seed, baseline
  checkbox) and after the run displays proposed vs baseline aggregate stat cards.

## 2026-05-07 — Session gshiftpage_phase4c_engine_configurator (Sonnet)

### GShiftPage Phase 4c — Engine Configurator + Dry-Run Simulation

**New scoring components (scorecard.py):**
- **`sweeper_rotation_penalty`** — rises with consecutive sweeper
  assignments, decays with rest days. Default weight 0.0 (safe deploy).
- **`skill_stretch_reward`** — small reward when difficulty − skill_score = 1
  (intentional growth slot). Default weight 0.0.
- **`prior_run_continuity`** — tiny penalty when an assignment changes
  between runs without a forced reason. Default weight 0.0.
- **`weekly_load_balance`** — penalizes concentrating high-load slots on
  the same TM across the week. Default weight 0.0.
  All four components are wired in `score_placement()` and appear in the
  audit `components` dict. Default weights are 0.0 → production behavior
  is byte-identical until first Save & Apply.

**Dry-run mode:**
- **`apps/zds/engine/fill_engine.py`** — new `--config-override <json-path>`
  CLI arg: when present, loads weights/thresholds/headcount/slot_priority
  from that JSON instead of querying scorecard_config. Audit JSON gains a
  top-level `config_used` field (dry_run bool + effective values).
- **`apps/zds/engine_bridge.py`** — `run_fill_engine()` gains an optional
  `config_override: dict | None` param. Serializes override to a temp JSON,
  passes via `--config-override`, cleans up the temp file after the
  subprocess exits. Returns dict gains `config_used` key.

**DB schema (applied via Supabase MCP migration):**
- `engine_config` — single active row (partial unique index on is_active),
  holds weights/thresholds/headcount/slot_priority as jsonb. Backfilled
  with current DEFAULT_WEIGHTS + production constants.
- `engine_config_history` — append-only snapshot table; FK to engine_config.
  Written on every Save & Apply.
- `engine_config_drafts` — named draft table for Save as Draft.

**DB helpers (shared/db.py):**
- `get_active_engine_config()` — returns the single is_active=True row.
- `save_engine_config_active(weights, thresholds, headcount, slot_priority)`
  — updates active row + snapshots old values to history.
- `save_engine_config_draft(name, ...)` — creates a named draft row.
- `list_engine_config_history(limit)` — returns history rows newest-first.

**Configurator state (apps/admin/engine_state.py — new):**
- `EngineConfiguratorState` — 12 weight floats, 4 threshold vars, 7
  headcount ints, slot_difficulty_rows list, history_rows list,
  sim_placements/sim_unresolved/sim_error/sim_ran/sim_config_used vars.
- Events: `load_config` (on_load), `set_tab`, `load_history`, `set_weight`,
  `set_difficulty_threshold`, `set_load_threshold`, `set_fatigue_window`,
  `set_rotation_weeks`, `set_headcount`, `discard_changes`, `save_config`,
  `run_simulation`.
- `dirty` flag tracks unsaved local edits; `save_success` / `save_error`
  for inline feedback.

**Configurator page (apps/admin/pages/engine.py — replaced stub):**
- 5-tab configurator: Weights | Thresholds | Headcount | Slot Difficulty |
  History. Tab strip uses `.engine-tab-btn` + `.active` CSS class.
- Weights tab: 12 sliders + number inputs (0.0–1.0 initially; CSS-constrained)
  for all weight keys. `rx.foreach` over `WEIGHT_KEYS`.
- Thresholds tab: 4 number inputs (difficulty threshold, load threshold,
  fatigue window days, rotation weeks).
- Headcount tab: 7 DOW inputs in a responsive grid.
- Slot Difficulty tab: read-only table of slot/priority pairs from active config.
- History tab: chronological list of engine_config_history rows; lazy-loaded
  on first tab visit.
- Simulator pane (always visible below Weights tab): [Run Simulation] button
  fires dry-run via `run_fill_engine(config_override=...)`. Results show
  placed count + unresolved count. Error surface if engine fails.
- Action bar: dirty-dot indicator, Discard, Save Config buttons.

**Diff component (shared/components/engine_config_diff.py — new):**
- `compute_diff(before, after) → dict` — Python-side diff across weights /
  thresholds / headcount sections. Returns changed rows with +/- deltas.
- `engine_config_diff(diff, ...)` — Reflex component that renders the diff
  dict as three labeled tables; changed rows get amber background highlight
  and colored delta chip. Summary header counts total changed fields.

**CSS (assets/engine_config.css — new):**
- Tab strip, weight row (slider + number input), threshold/headcount grids,
  slot difficulty table, history list, simulation pane, action bar — all
  scoped to `.engine-*` classes. Dual-theme via CSS custom properties.

**Wiring:**
- `apps/admin/routes.py` — `/admin/engine` on_load now fires
  `EngineConfiguratorState.load_config`.
- `brijkillian_stack/brijkillian_stack.py` — registers `/engine_config.css`
  in head_components.

---

## 2026-05-07 — Session gshiftpage_phase4b_admin_hub (Sonnet)

### GShiftPage Phase 4b — Sudo Admin Hub + Long-Tail Memory Aliases

- **`apps/admin/state.py`** (new) — `AdminHubState`: loads `logs_recent`
  count (events in last 7 days) on page mount for the Logs card chip.
- **`shared/components/admin_card.py`** (new) — `admin_card(glyph, title,
  tagline, href, count=None)`: reusable hub card rendered as `<a>`. Hover
  produces border-color: var(--blue) + blue-dim bg + translateY(-1px).
  Optional count chip (monospace, muted, top-right) via `count` arg.
- **`shared/components/admin_section_head.py`** (new) — Two exports:
  `admin_section_head(title)`: 10px/700/gold-bar section header matching
  the SectionHead atom from shift-hud-hifi.jsx.
  `admin_breadcrumb(section, page_title)`: 11px eyebrow sub-bar
  "← Sudo Admin · {section} · {page_title}" shown at top of all
  /admin/* sub-pages.
- **`assets/admin_hub.css`** (new) — `.admin-hub-card`, `.admin-hub-grid`
  (3-col responsive → 2-col → 1-col), `.admin-breadcrumb`, `.admin-hub-*`
  layout classes. All colors use ops_tokens.css vars — dual-theme automatic.
- **`apps/admin/pages/index.py`** (replaced stub) — Full 3-section hub:
  Activity (Logs/Threads/Floor Walk/Write-Ups), Workflows (Shift Recap/
  Areas/Engine Config), System (Health/Today legacy/Deployment legacy).
  11 cards total. PT Serif italic "Sudo Admin" heading + gold eyebrow.
- **`apps/admin/pages/today.py`** (new) — `admin_today_page()`: breadcrumb
  (System > Today legacy) + `today_page()` from apps/glcr/pages/today.py.
- **`apps/admin/pages/deployment.py`** (new) — `admin_deployment_page()`:
  breadcrumb (System > Deployment legacy) + `deployment_page()`.
- **`apps/admin/pages/engine.py`** (new) — `admin_engine_page()`: Phase 4c
  stub with breadcrumb (Workflows > Engine Config) + coming-soon chips for
  Weight Sliders, Threshold Editors, Slot-Difficulty Editor, Simulation Pane.
- **`apps/admin/routes.py`** (updated) — 4 routes: /admin (AdminHubState
  .load_hub), /admin/today (TodayState.load_today), /admin/deployment
  (DeploymentState.load_roster), /admin/engine (no on_load).
- **`brijkillian_stack/brijkillian_stack.py`** (updated) — Registers
  `/admin_hub.css` in `head_components`.

---

## 2026-05-07 — Session gshiftpage_phase4a_captures (Sonnet)

### GShiftPage Phase 4a — Thumb Cluster Capture Handlers + Command Palette + ⌘K

- **`shared/db.py`** (extended) — `insert_note()`: writes to `public.notes`,
  links entities via `note_entities`, anchors to parent shift_log event via
  `event_notes`. `ensure_shift_log_event(shift_date)`: idempotent — one
  `event_type=shift_log` event per date, created on first call, reused
  thereafter. `lookup_entity_id_by_name(display_name)`: fallback entity
  resolution by display_name.
- **`apps/shift/types.py`** — Added `tm_id: str` field to `HudRosterChip`.
- **`apps/shift/state.py`** — New vars `shift_date_iso`, `shift_log_event_id`,
  `roster_name_to_id`. `on_load` anchors shift_log event after header build.
  `_build_header` sets `shift_date_iso`. `_build_from_zds` sets
  `roster_name_to_id` and populates `tm_id` on each roster chip.
  New `refresh()` event: lightweight `_build_tasks + _build_activity`.
- **`shared/state/capture_toast.py`** (new) — `CaptureToastState`: message,
  visible, `show(msg)`, `dismiss()`.
- **`shared/state/call_out_modal.py`** (new) — `CallOutModalState`: TM picker
  chips, points float input, note dropdown (PTO/LOA/Intermittent/FMLA).
  `confirm()`: writes `call_offs` row + `notes` row (content_type=flag,
  section=Call-Outs), shows toast, refreshes HUD.
- **`shared/state/kudos_modal.py`** (new) — `KudosModalState`: TM picker +
  textarea. `submit()`: writes kudos note (content_type=kudos, section=Floor Walk).
- **`shared/state/beo_modal.py`** (new) — `BeoModalState`: multi-select TM chips
  + time input (default = current hour). `submit()`: one observation note per
  selected TM (section=BEOs, beo_time in metadata).
- **`shared/state/command_palette.py`** (new) — `CommandPaletteState`: open,
  raw_text, submitting. `toggle/close/set_raw_text`. Quick-action openers
  close palette then call the corresponding modal. `submit_raw()`: writes
  content_type=reference note via `insert_note`.
- **`shared/components/capture_toast.py`** (new) — `capture_toast()`: fixed
  bottom-center 3s auto-dismiss toast. MutationObserver JS watches
  `.capture-toast-panel` and fires `capture_toast_state.dismiss` after 3s.
- **`shared/components/capture_modals.py`** (new) — `call_out_modal()`,
  `kudos_modal()`, `beo_modal()`, `command_palette_modal()`. All use
  `rx.dialog.root(open=..., on_open_change=...)` — Radix handles focus-trap
  and Escape. `capture_modals()` mounts all four as `rx.fragment`.
- **`shared/components/thumb_cluster.py`** (updated) — All four buttons wired:
  ⚑ → `CallOutModalState.open_modal`, ★ → `KudosModalState.open_modal`,
  ⊟ → `BeoModalState.open_modal`, + FAB → `CommandPaletteState.toggle`.
- **`apps/shift/pages/index.py`** (updated) — `capture_toast()` and
  `capture_modals()` mounted at page root inside `shift_page()`.
- **`brijkillian_stack/brijkillian_stack.py`** (updated) — `_KBD_SCRIPT`
  extended: ⌘K/Ctrl+K now also dispatches `command_palette_state.toggle`
  (no-op on non-Shift pages); Escape also closes `command_palette_state`.

---

## 2026-05-07 — Session gshiftpage_phase3_shifthud (Sonnet)

### GShiftPage Phase 3 — Shift HUD at /shift

- **`apps/shift/`** (new sub-app) — Sibling to `apps/glcr/` and `apps/zds/`.
  Contains `types.py`, `state.py`, `routes.py`, `pages/__init__.py`, `pages/index.py`.
- **`apps/shift/types.py`** — TypedDicts for HUD state vars: `HudZoneSlot`,
  `HudRRSlot`, `HudAuxSlot`, `HudBreakWave`, `HudRosterChip`, `HudCarryOverItem`,
  `HudTask`, `HudActivityEntry`. All fields str/int/bool so Reflex infers them
  inside `rx.foreach` without manual `.to()` casts.
- **`apps/shift/state.py`** — `ShiftState` with `on_load` that:
  reads tonight's zone/rr/aux/break data from `ZdsState` (via `get_state()`),
  builds deployment summary bar counts (filled / locked / warn / open / ok),
  builds roster chips with kind classification (grave / pm_ol / am_ol / off),
  reads tasks from `shared/db.get_tonight_tasks()`, marks overdue tasks as
  ⚑ carry-over items, reads activity feed from `shared/db.get_activity_feed()`.
  Header derives shift date label, greeting (Good morning/afternoon/evening),
  and elapsed-time live label.
- **`apps/shift/pages/index.py`** — Full HUD page composition matching
  `design/gshiftpage/shift-hud-hifi.jsx` layout exactly:
  sticky gradient header (eyebrow · serif greeting · pills · timeline),
  body `1.55fr | 1fr` grid. Left: deployment headline + 5×2 zone grid + RR+Aux
  2-col + break wave strip. Right: roster chips + ⚑ carried-over amber panel +
  tonight tasks + activity feed. `position:fixed` thumb cluster bottom-right.
- **`apps/shift/routes.py`** — `ROUTES = [(shift_page, "/shift", "Shift HUD · GLCR", [ShiftState.on_load])]`.
- **`shared/components/shift_zone_card.py`** (new) — Read-only `shift_zone_card(slot)`
  rendered via `rx.foreach`. Status palette: ok → line2/panel2, lock → gold/gold-dim,
  warn → amber/amber-dim, open → red/red-dim. Footer shows wave number + wave time.
- **`shared/components/shift_timeline.py`** (new) — `shift_timeline()` with 7 phase
  segments (Open/Wave1/Mid/Wave2/Late/Wave3/Close by percentage of 8-hr window),
  wave tint fills, NOW marker gold line + chip, progress fill driven by
  `--hud-now-pct` CSS custom property. Inline JS ticks every 60s, no page reload.
  Bottom row: 9 time ticks 11P → 7A.
- **`shared/components/thumb_cluster.py`** (new) — `thumb_cluster()` fixed
  bottom-right: ⚑ Call-out (red) · ★ Kudos (gold) · ⊟ BEO (blue) + 64×64 blue
  gradient FAB. Phase 3 ships read-only; capture wiring follows in Phase 4.
- **`assets/shift_hud.css`** (new) — HUD layout: `.shift-hud` flex column,
  `.hud-header` gradient, `.hud-body` 1.55fr|1fr grid, `.hud-left/.hud-right`
  overflow-y:auto, `.hud-thumb-cluster` fixed, `.hud-now-chip` pointer-events:none,
  scrollbar cosmetics, responsive fallback to single column at <900px.
- **`brijkillian_stack/brijkillian_stack.py`** — Imports `SHIFT_ROUTES`;
  registers shift routes as TIER-2 (viewer-OK, `require_unlock` guard) via
  `_with_zds_chrome` wrapper; adds `/shift_hud.css` to `head_components`.
  Docstring updated to list `/shift`.
- **`shared/components/nav_rail.py`** — ⊙ Shift nav chip now links to `/shift`
  (was `/today`) with `active == "/shift"` match.

---

## 2026-05-07 — Session gshiftpage_phase2_navrail (Sonnet)

### GShiftPage Phase 2 — Unified 60px nav rail + avatar dropdown + Sudo Admin stub

- **`shared/components/nav_rail.py`** (new) — Single `nav_rail()` component
  used by every page (Memory + ZDS). 60px sticky left column: G-mark logo → /,
  divider, 6 nav chips (⊙ Shift, ▦ ZDS, ⌕ Search, ◍ People, ☐ Tasks, ✦ Patterns),
  spacer, avatar chip "BK". Active state: blue color + blue-dim bg + 2px left
  indicator. ZDS active check uses `.contains("/zds")` for sub-route matching.
- **`shared/state/avatar_menu.py`** (new) — `AvatarMenuState` with `open: bool`,
  `toggle()`, `close()` handlers.
- **`assets/nav_rail.css`** (new) — Rail CSS with `.app-shell` grid
  (`grid-template-columns: 60px 1fr`), `.nav-rail-*` classes, avatar dropdown,
  `.app-shell .app { display: block }` override to unbreak GLCR page layout
  after sidebar removal.
- **`assets/avatar_menu.js`** (new) — Outside-click-to-close handler: dispatches
  `avatar_menu_state.close` when click lands outside `.nav-rail-avatar-menu`.
- **`apps/admin/`** (new) — Sudo Admin stub. `/admin` renders a placeholder page
  "Coming soon. Phase 4 will populate this hub…" Registered as TIER-2 route.
- **`brijkillian_stack/brijkillian_stack.py`** — Both `_with_grok` and
  `_with_zds_chrome` now render `nav_rail()` in the left column of a 60px|1fr
  CSS grid. Admin routes imported and registered. `nav_rail.css` + `avatar_menu.js`
  added to `head_components`.
- **`apps/zds/components/zds_header.py`** — Removed `app_switcher()` and
  `theme_toggle` (both now in rail). Only `title_block` + optional `right` action
  remain in the sticky header.
- **`apps/zds/pages/{deployment,week_overview,schedule_editor}.py`** — Removed
  inline `app_switcher()` import + call from each page's top-nav hstack.
- **`apps/glcr/pages/*.py`** (13 files) — Removed `from shared.components.sidebar
  import sidebar` and `sidebar()` call. Pages now render as right-column content
  inside the shell grid supplied by `_with_grok`.
- **`shared/components/sidebar.py`** — Deleted (replaced by nav rail).
- **`shared/components/app_switcher.py`** — Deleted (replaced by nav rail).

---

## 2026-05-06 — Session zds_phase1b_light_mode (Sonnet)

### Phase 1b — Sun/moon light-mode toggle with LocalStorage persistence
- **`apps/zds/state.py`** — `theme: str` field changed from session-scoped to `rx.LocalStorage("zds-dark")` for persistence across page reloads and devices.
- **`apps/zds/components/zds_header.py`** — Theme toggle button added to header with sun/moon icon (lucide-react, 16px), positioned before the optional right-side action. Icon shows "sun" when dark mode active (click to go light), "moon" when light mode active (click to go dark). Button styled to match header chrome with hover effects. On-click handler calls `ZdsState.toggle_theme`.
- **`assets/zds_dark.css`** — Casino scatter background now `display:none` on light mode (was `opacity:0.06`); light-mode surface kept clean without the dark-mode flourish.
- **`brijkillian_stack/brijkillian_stack.py`** — No changes; already using `ZdsState.theme` for `data_theme` binding in `_with_zds_chrome`.
- **Note:** Memory/GLCR pages (`_with_grok`) remain light-mode unconditionally, unaffected by ZDS theme toggle.

---

## 2026-05-06 — Session zds_handoff_phases_B_thru_F (Sonnet)

### Phase B — Zone card typography + visual corrections
- **`apps/zds/styles.py`** — `ZONE_COLORS` corrected: Zone 6 fixed to blue (`#2563eb`), Zone 7 to pink (`#ec4899`) (were swapped); Zone 2 corrected from purple to amber; all zone colors updated to match handoff spec.
- **`apps/zds/components/zone_card.py`** — Label gets `class_name="card-slot-label"` (CSS: 9px/700/0.14em). TM name `class_name` emits `card-tm-name-calledoff` when `warning_status=="called_off"`. Color bar: filled=3px zone-color, unfilled=2px `#2e4357` dim. Card `min_height` bumped from 90px → 108px.
- **`assets/zds_dark.css`** — Complete CSS token migration to `--zds-*` namespace with `[data-theme="light"]` override block. Zone 6↔7 colors corrected in CSS. Light mode tokens: GLCR blue `#0065bf` as `--zds-blue`, lighter surfaces. Casino scatter bg opacity 0.06 in light mode. Night tab fill bar: `28×3px border-radius:999`. Scoreboard day-name: `font-size:36px; font-weight:800`. Break wave badge classes (blue/green/violet). Called-off badge. Audit strip CSS. Notice dot CSS. Night lock CSS.

### Phase C — Audit strip (commit `aff4f80`)
- **`shared/components/audit_strip.py`** — New `audit_strip()` component: fixed bottom-right strip reads `ZdsState.last_saved_at` and `ZdsState.has_changes`. Green dot + "Saved {time}" when saved; amber dot + "Unsaved changes" when dirty; hidden when clean. CSS class `audit-strip` (already in `zds_dark.css`).
- **`apps/zds/state.py`** — `last_saved_at: str = ""` field; stamped in `_log_change` after each successful write using `strftime("%I:%M %p")`.
- **`brijkillian_stack/brijkillian_stack.py`** — `audit_strip()` imported and mounted in `_with_zds_chrome`.

### Phase D — Night-level lock/unlock (commit `291bf99`)
- **DB migration** (`zds_phase_d_night_lock`) — `nights.is_locked bool NOT NULL DEFAULT false`, `nights.locked_by text`, `nights.locked_at timestamptz`. Index `nights_locked_idx (week_id, is_locked)`.
- **`apps/zds/types.py`** — `Night` TypedDict: `+is_locked`, `+locked_by`, `+locked_at`. `EMPTY_NIGHT` defaults added.
- **`apps/zds/database.py`** — `update_night_lock(night_id, is_locked, locked_by)`: stamps `locked_at=now()` on lock, clears on unlock.
- **`apps/zds/state.py`** — `night_lock_confirm_open: bool` state var. `current_night_is_locked` `@rx.var` (reads from `self.nights`). `toggle_night_lock()`: role gate (`zds_editor`+); lock immediate, unlock opens confirm dialog. `confirm_night_unlock()` / `cancel_night_unlock()`. Night-level guard prepended to `clear_slot`, `assign_tm`, `swap_tms`.
- **`apps/zds/pages/deployment.py`** — `_night_unlock_dialog()`: `rx.alert_dialog` confirm before unlock. Night header: gold LOCKED badge + Lock/Unlock toggle button. Deployment body wrapped in `.night-locked` class when locked (CSS: `pointer-events:none; opacity:0.75` on all cards). Dialog mounted at page root.

### Phase E — Notices system (commit `e5ea018`)
- **DB migration** (`zds_phase_e_notices`) — `notices` table: `id, night_id, slot_key, type CHECK(alert|info|training|meeting), text, created_by, created_at`. Indexes on `night_id` and `(night_id, slot_key)`.
- **`apps/zds/types.py`** — `ZoneSlot.notices: list` field (injected in `_load_night`).
- **`apps/zds/database.py`** — `fetch_notices(night_id)`, `create_notice(...)`, `delete_notice(notice_id)` helpers.
- **`apps/zds/state.py`** — `notice_form_open/slot_key/type/text` state vars. `open/close/set_type/set_text/submit_notice/delete_notice` handlers. `_load_night`: fetches notices, groups by `slot_key`, injects into each slot dict.
- **`apps/zds/components/zone_card.py`** — `_notice_dot(notices)`: 8px colored dot top-left with CSS tooltip on hover, hidden when list empty. Dot color driven by `rx.match` on `notices[0]["type"]`.
- **`shared/components/context_menu.py`** — `open_notice_for_ctx_slot()` handler (cross-state → `ZdsState.open_notice_form`). "Add notice 📌" item in both assignment and empty-slot menus.
- **`apps/zds/pages/deployment.py`** — `_notice_form_dialog()`: type picker (4 color-coded buttons) + text input + submit; mounted at page root.
- **`assets/zds_dark.css`** — `.notice-dot-wrapper` + `.notice-tooltip` hover-reveal styles added.

### Phase F — Print layout landscape fixes + lock/notice integration
- **`apps/zds/engine/render_deployment_book.py`** — `.body` grid rows `1.55fr/1fr` → `1.4fr/0.85fr`; padding `10px/8px` → `8px/6px`; gap `9px` → `7px`. `.zones-grid` gap `7px` → `6px`. `.foot-lock-stamp` CSS: gold 8.5px/700 for print-safe lock indicator. `.print-notice-*` CSS: inline badges with print-contrast darker palette.
- **`apps/zds/print_renderer.py`** — `_fetch_night_data` fetches notices and groups by `slot_key`. `day` dict gains `is_locked`, `locked_by`, `notices_by_slot`. `_notice_badges_html()` helper renders `.print-notice` spans. `_render_deployment_page` emits lock stamp in footer when locked. (Notice badges available via helper for future zone card integration.)

---

## 2026-05-06 — Session zds_phase4_undo_toast (Sonnet)

### Phase 4 — Client-side undo toast (no schema changes)

- **`shared/state/__init__.py`** — New package marker for `shared.state` sub-package.
- **`shared/state/undo.py`** — New `UndoState(rx.State)` with fields `last_label`, `last_inverse_kind`, `last_inverse_payload`, `toast_open`. Internal `queue(label, kind, payload)` method called via `await self.get_state(UndoState)` from other event handlers. Public `@rx.event dismiss()` (clear toast, wipe kind) and `@rx.event async undo()` (replay inverse by kind: `restore_assignment` → `update_zone_assignment + _load_night`; `restore_lock` → `update_slot_lock + _load_night`; `restore_highlight` → delete added row or re-insert removed row). Undo is best-effort; exceptions silently swallowed.
- **`shared/components/undo_toast.py`** — New `global_undo_toast()` component. Fixed bottom-right position; conditionally renders `rx.cond(UndoState.toast_open, ...)`. Contains: rotate-ccw icon, label text, solid blue "Undo" button (`UndoState.undo`), and `×` dismiss button (`UndoState.dismiss`). CSS class `undo-toast-panel` is the MutationObserver sentinel.
- **`assets/undo_toast.css`** — `.undo-toast-root` fixed bottom-right wrapper (z-index 400, pointer-events none). `.undo-toast-panel` dark-navy card (`background: #1a2a3e`, blue border, box-shadow), pointer-events restored, slide-in keyframe animation. `.undo-toast-close` minimal × button style.
- **`assets/undo_toast.js`** — IIFE MutationObserver on `document.body`. When `.undo-toast-panel` appears, arms a 5-second `setTimeout`; when it disappears, cancels the timer. On timeout, dispatches `undo_state.dismiss` via `window._reflexDispatch`. No Reflex-side polling needed.
- **`apps/zds/state.py`** — `clear_slot` converted to `@rx.event async def`; after successful `_log_change` (only when `prev_tm_id` is non-null), calls `undo.queue(label, "restore_assignment", {slot_id, tm_id, night_id})`. `toggle_slot_lock` converted to `@rx.event async def`; after `_log_change`, calls `undo.queue(label, "restore_lock", {slot_id, prev_lock, night_id})`. Both use lazy `from shared.state.undo import UndoState` inside the handler body to avoid circular imports.
- **`shared/components/context_menu.py`** — `mark_sweeper`: changed `select("id")` → `select("*")` so the full row is available for undo re-insert. Remove branch queues `restore_highlight / action=removed / row=existing[0]`. Insert branch captures `result.data[0]["id"]` and queues `restore_highlight / action=added / highlight_id=new_id`. Lazy `UndoState` import inside both branches.
- **`brijkillian_stack/brijkillian_stack.py`** — `global_undo_toast` imported and mounted in both `_with_grok` (GLCR Memory pages) and `_with_zds_chrome` (ZDS pages). `undo_toast.css` + `undo_toast.js` registered in `app.head_components`.

**Strategy:** Pure client-side, zero schema changes. `UndoState` is a top-level `rx.State`; cross-state writes from `ZdsState`/`ContextMenuState` use `await self.get_state(UndoState)` which commits mutations in the same event batch. JS timer keeps dismiss logic out of Reflex's event loop entirely.

---

## 2026-05-06 — Session zds_phase1_reskin (Sonnet)

### Phase 1 — Dark-mode visual reskin of all ZDS pages (no backend changes)

- **`assets/casino_scatter.svg`** — Casino-scatter SVG extracted from the v3 mock's base64 data-URI and saved as a standalone cacheable asset.
- **`assets/zds_dark.css`** — New CSS file (~260 lines) with all dark-mode overrides scoped to `[data-theme="zds-dark"]`. Covers: bg/surface tokens (bg0–bg4), border accents, text colors (t1–t4), zone card classes (`zone-card-filled/empty/locked` glow rings), section gold rule, chip-header overlay, night scoreboard gradient + radial rings, night tabs bar, week overview night cards, skeleton pulse, drawer + input + button + badge overrides.
- **`brijkillian_stack/brijkillian_stack.py`** — `_with_zds_chrome` wrapper changed from `rx.fragment` to `rx.box(data_theme="zds-dark")`. Casino-scatter fixed overlay (`class_name="zds-casino-bg"`) rendered behind all page content. `zds_dark.css` registered in `app.stylesheets`.
- **`shared/components/eyebrow.py`** — New helper: `eyebrow(label)` renders an uppercase 10px eyebrow span with `.section-eyebrow` CSS class. Light- and dark-mode compatible.
- **`shared/components/section_head.py`** — New helper: `section_head(label, count=None)` renders eyebrow + thin gold-rule rule (`linear-gradient(90deg, rgba(224,203,182,0.4)…)`). Optional count badge shown right of label.
- **`apps/zds/components/zone_card.py`** — `zone_card`, `rr_card`, `aux_card` outer boxes gain conditional `class_name` using `rx.cond` to emit `zone-card zone-card-{filled|empty}` ± `zone-card-locked`. `_task_section` wrapper gets `class_name="card-task-section"` so dark CSS can override the separator border + task text colors.
- **`apps/zds/components/night_tabs.py`** — Each tab button gets `class_name="night-tab"` + `class_name="night-tab-active"` (conditional). Tab bar `rx.hstack` gains `class_name="night-tabs-bar"`.
- **`apps/zds/components/zds_header.py`** — Header `rx.hstack` gains `class_name="chip-header"` — in dark mode renders dotted-circle overlay via `::after` pseudo-element + gradient background.
- **`apps/zds/pages/deployment.py`** — `_section_header()` refactored to delegate to `section_head()` (eyebrow + gold rule). Top nav gets `class_name="chip-header"`. Night tabs wrapper gets `class_name="night-tabs-bar"`. Scoreboard strip gets `class_name="night-scoreboard"`. Fill bar track gets `class_name="night-tab-fill-track"`. Outer page box gets `class_name="zds-index-page"`.
- **`apps/zds/pages/week_overview.py`** — Night cards get `class_name="week-night-card"`. Sticky header gets `class_name="chip-header"`. Fill bar track gets `class_name="night-tab-fill-track"`. Outer box gets `class_name="zds-index-page"`.
- **`apps/zds/pages/index.py`** — Outer box and week cards get dark-mode CSS classes. Page body gets `class_name="zds-index-page"`.

**Strategy:** `data-theme="zds-dark"` on the `_with_zds_chrome` wrapper scopes all overrides to ZDS; Memory/GLCR pages (using `_with_grok`) are unaffected. All Python component color arguments are preserved unchanged — dark CSS wins via specificity.

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
