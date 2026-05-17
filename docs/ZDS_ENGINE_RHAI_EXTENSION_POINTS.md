# ZDS Engine (Rust + Rhai) — Living Roadmap & Extension Points

**Engine Architect Owner:** Grok (long-term)  
**Last Updated:** 2026-05-16 (post first-round proposals from all 6 dedicated roles)  
**Status:** Sprint 1 Planning — Ready for parallel execution  
**Related:** Linear Project "ZDS Forge - Full Backend Rebuild", glcrOps repo (apps/zds/engine/, supabase/migrations/, docs/)

---

## 1. Executive Summary

All six specialist roles have delivered high-quality first-round proposals:

- **Rust Core Developer**: Domain model (`Tm`, `Slot`, `Placement`, `RuleContext`, `ScoreComponent`), first native scoring components, Rhai bridge skeleton in `zds-engine`.
- **Rhai Integration Specialist**: Sandboxed runtime, hook registration, safe execution patterns.
- **Engine Playground Developer**: Historical + synthetic scenario data flows, 3-pane experimentation UI, RuleSet tweaking, rich explainability, safe activation workflow.
- **Migration & Validation Lead**: `WeekSnapshot` JSON contract, golden-master harness (inspired by `print_regression` / `simulate_weeks.py`), parallel Python ↔ Rust execution, high-fidelity diffing (placements + every score component + full audit), ≥10-night historical gate, live soak + canary + instant rollback via RuleSet + feature flag.
- **Configuration & Rules Backend Developer**: Versioned data model (`rulesets` + `ruleset_versions` containing `weights` + `rhai_hooks`), Supabase schema, rich REST API (`/v1/rulesets/...`), granular `PATCH`-per-weight and `PATCH`-per-hook, `validate` + `simulate` paths, safe activation/rollback with audit.
- **Engine Architect** (this synthesis): Cross-role coordination, contracts, critical path, and this living plan.

**Goal for next 4–6 weeks (Sprint 1):** Deliver a production-safe, UI-configurable Rust + Rhai engine that:
- Achieves byte-for-byte (or better) parity on historical nights via golden harness.
- Exposes granular, versioned RuleSet editing (exactly the "highly granular tweaking" requested).
- Powers a rich Playground for safe what-if experimentation.
- Enables zero-downtime cutover with instant rollback.

**Tone:** Deliberate, safety-first, contracts-first. No production activation until the historical gate is passed and the rollback path is exercised.

---

## 2. Critical Path for Safe Cutover (Highest Priority — Blocks Everything Else)

The highest-risk item is the production cutover from the existing Python `fill_engine.py` (in `apps/zds/engine/`). Everything funnels through these items:

1. **Locked `WeekSnapshot` JSON contract** (input for one night: TMs + pools + attributes + eligibility + preferences, slots + metadata + difficulty/load, current context, RuleSet snapshot or id).
2. **Rust core scoring parity** (identical or superior placements + identical score components + rich audit).
3. **Rules Backend schema + `/validate` + `/simulate` endpoints** (the surface the Playground and harness consume).
4. **Golden-master harness + high-fidelity diff reporter** (placements + every score component + audit trail) running cleanly on ≥10 historical nights.
5. **Rhai bridge + first production-safe hooks** (with sandbox).
6. **Activation/rollback mechanism** (active `ruleset_version_id` + engine feature flag in `engine_config` / `scorecard_config`).

**No prod traffic until 1–6 are green.** Shadow mode and canary are mandatory intermediates.

---

## 3. 4–6 Week Implementation Roadmap (Sprint 1)

### Phase 1: Contracts + Rust Skeleton + Rules Backend MVP (Days 1–7)

**Primary Owners:** Engine Architect (facilitator), Rust Core, Configuration & Rules Backend, Migration & Validation Lead.

- **Day 1–2 (Contract Lock)**
  - 60–90 min sync (all 6 roles + Architect): finalize and commit:
    - `WeekSnapshot` JSON schema (v1) + examples from real nights (Migration Lead produces).
    - `RuleSet` / `RuleContext` / `Placement` / `ScoreBreakdown` / `AuditEntry` Rust structs + JSON shapes.
    - Simulate request/response payload (Playground + Backend).
    - Rhai hook signatures (Rhai Specialist leads).
  - Update this doc and add to repo `docs/`.
  - Create Linear issues under ZDS Forge for each contract + "Engine Sprint 1 Contracts".

- **Rust Core Developer (parallel)**
  - Create `engine/rust/zds-engine/` workspace/crate (Cargo.toml, `src/lib.rs` charter with domain model).
  - Implement core types: `Tm`, `Slot`, `Placement`, `RuleContext`, `ScoreComponent` (skill, load, difficulty, preference, custom, total).
  - First native scorers (port key logic from `fill_engine.py` / Rules/*.json).
  - Rhai bridge skeleton (compile Rhai scripts, call registered fns, safe context injection).
  - CLI or JSON stdin/stdout harness entrypoint for the golden master (or cdylib for FFI).

- **Configuration & Rules Backend Developer (parallel)**
  - New migration: `rulesets` (id, name, description, created_by, active_version_id) and `ruleset_versions` (id, ruleset_id, version, weights jsonb, rhai_hooks jsonb[], notes, created_at, activated_at).
  - Extend or replace parts of `engine_config` / `scorecard_config` (keep backward compat during transition).
  - Core REST: `GET/POST /v1/rulesets`, `GET/POST /v1/rulesets/{id}/versions`, `GET /v1/rulesets/active`.
  - Seed v1 from current engine_config + Rules/ JSONs (one-time import script).

- **Migration & Validation Lead (parallel)**
  - Harness skeleton (Python or Rust test binary) modeled directly on existing `simulate_weeks.py` + `print_regression` pattern.
  - Produce 3–5 real `WeekSnapshot` JSON fixtures from historical data (via current DB + schedule_parser).
  - Basic parallel runner stub + diff reporter (exact placement match + per-component numeric tolerance + audit diff).

**Deliverable:** All contracts committed in repo + first Rust crate compiles and can score a hand-crafted snapshot.

### Phase 2: Native Parity + Rhai Bridge + Simulate Surface (Days 8–14)

**Primary Owners:** Rust Core + Rhai Specialist + Rules Backend + Migration Lead.

- **Rust Core + Rhai**
  - Complete scoring pipeline that reproduces current behavior (or improves it).
  - Full Rhai integration: register all agreed hooks, support loading `rhai_hooks` from a `RuleSet` version.
  - Produce rich `Audit` / explainability output (every decision includes contributing scores + which hooks fired).
  - Binary/CLI that accepts `WeekSnapshot` JSON → `Placements + Scores + Audit` JSON (used by harness + backend simulate).

- **Rules Backend**
  - Implement `POST /v1/rulesets/{id}/versions/{vid}/validate` (static checks + Rhai syntax).
  - Implement `POST /v1/simulate` (accepts WeekSnapshot + optional RuleSet override → calls Rust, returns placements + scores + audit).
  - Decision on Rust invocation: **recommended for Sprint 1** = subprocess + JSON over stdin/stdout (simple, isolated, matches current engine_bridge pattern). Later: PyO3 or dedicated Rust microservice.

- **Migration Lead**
  - Run harness daily on accumulating historical nights.
  - Rust Core triages every diff (placement mismatch, score drift, audit gap).
  - Target by end of phase: clean run on ≥5 nights with 0 placement diffs and <0.5% score component drift.

- **Playground Developer (starts here)**
  - Data layer: load historical WeekSnapshots (or generate on demand via DB queries).
  - Synthetic scenario generator (vary load, training pairs, new TMs, rule tweaks).
  - Basic 3-pane UI scaffold (left: scenario + RuleSet selector; center: tweakable weights table + hook editor; right: results table + first explain cards).

**Deliverable:** First end-to-end simulate path (UI or CLI → Backend → Rust → results) and ≥5 nights passing harness.

### Phase 3: Granular Editing + Rich Playground + Explainability (Days 15–21)

**Primary Owners:** Rules Backend + Playground Developer + Rust Core + Rhai.

- **Rules Backend (granular control — user request)**
  - `PATCH /v1/ruleset_versions/{vid}/weights` (partial update of specific weight keys, with validation + auto new minor version or draft).
  - `PATCH /v1/ruleset_versions/{vid}/rhai_hooks/{hook_key}` (update script text, with syntax validate).
  - Full activation flow: `POST /activate` creates audit record, snapshots previous active version for instant rollback.
  - History + diff view between versions.

- **Playground Developer**
  - Complete 3-pane experience.
  - "Run Simulation" calls the simulate endpoint.
  - Side-by-side before/after (current RuleSet vs tweaked).
  - Rich explainability: per-placement breakdown (bars or tree of score components + fired Rhai), "why this TM over that one".
  - "Save as new version" + "Activate this version" (with confirmation + rollback link).
  - Historical + synthetic tabs.

- **Rust + Rhai**
  - Expand explainability output (structured JSON the Playground can render beautifully).
  - Additional safe extension points (see section 5).

- **Migration Lead**
  - Expand harness to full regression suite + nightly CI job.
  - Produce "Parity Gate Report" template (sign-off artifact).

**Deliverable:** Usable internal Playground where an editor can tweak a weight or a Rhai hook, re-simulate a real night, see the exact impact, and safely promote a new version.

### Phase 4: Validation Gate, Shadow, Canary, Cutover Prep (Days 22–28)

**Primary Owners:** Migration Lead + Architect + Rules Backend + Rust Core.

- **Historical Gate**
  - Clean runs on ≥10 distinct historical nights (different load patterns, training, events).
  - Sign-off by Architect + Migration Lead + at least one domain expert.

- **Shadow Mode**
  - In ZDS app (or new backend path): for selected nights or all, run both engines, log diffs to `agent_logs` or new `engine_runs` table. No user-visible change.

- **Canary + Rollback**
  - Feature flag / RuleSet selector: pick a night → "Use Engine v2 (RuleSet X)".
  - One-night prod canary.
  - Instant rollback: flip flag or re-activate previous `ruleset_version` (Backend guarantees previous placements can be restored via audit).

- **Integration**
  - Update `apps/zds/engine_bridge.py` (or new `rust_engine_bridge.py`) to support dual path.
  - Update `state.py` deployment flow to respect active RuleSet.

**Deliverable:** Documented "Safe Cutover Runbook" + exercised rollback in staging.

### Phase 5: Polish, Performance, Documentation, Phase 2 Planning (Days 29–42)

- Performance tuning (Rust is expected to be dramatically faster).
- More Rhai hooks (custom break logic, dynamic sweeper routing, preference learning hooks, etc.).
- Playground: "Scenario library", export/import, diff two RuleSets.
- Full test coverage in harness + property-based tests in Rust.
- Update all docs (this file, ZDS PDF Pipeline, handoff PDF notes, READMEs).
- Architect + team retrospective: what worked for parallel squads, next 6 weeks (advanced optimization, multi-week lookahead, learned weights, printed book parity tests, etc.).

---

## 4. Ownership Matrix & Parallelization Opportunities

| Workstream                    | Primary Owner(s)                  | Depends On                          | Can Start In Parallel With          |
|-------------------------------|-----------------------------------|-------------------------------------|-------------------------------------|
| Contracts (WeekSnapshot, RuleSet, Simulate payload, Hook sigs) | Architect (lead) + all            | —                                   | Day 1                               |
| Rust crate + domain + native scorers | Rust Core Developer               | Contracts (partial)                 | Rules Backend schema, Migration harness skeleton |
| Supabase rulesets + versions + basic REST | Rules Backend Developer           | —                                   | Rust skeleton                       |
| Golden harness + fixtures + diff reporter | Migration & Validation Lead       | WeekSnapshot contract               | Rust early builds                   |
| Rhai sandbox + registration + first hooks | Rhai Integration Specialist       | Hook signatures + Rust bridge       | Rust core                           |
| /validate + /simulate endpoints + Rust invocation | Rules Backend + Rust Core         | Simulate payload + Rust binary      | Parity work                         |
| 3-pane Playground UI + data flows | Engine Playground Developer       | Simulate endpoint                   | Backend + Rust parity               |
| Granular PATCH + activation/rollback + audit | Rules Backend                     | Ruleset schema + simulate           | Playground scaffold                 |
| Historical gate runs + soak/canary plan | Migration Lead + Architect        | Parity on 5+ nights                 | Everything above                    |
| Production bridge integration + feature flag | Rust Core + Backend + ZDS team    | Gate passed + rollback exercised    | Late Phase 4                        |

**Key:** Most streams have 2–3 week overlap windows. Contracts are the only true serial bottleneck.

---

## 5. Rhai Extension Points (Core of "ZDS_ENGINE_RHAI_EXTENSION_POINTS")

This section will be the authoritative, living catalog. Initial set derived from domain + all proposals:

### Core Scoring Hooks (called per TM × Slot during placement)
- `fn score_slot(ctx: RuleContext) -> f64`
- `fn score_preference(ctx: RuleContext) -> f64`
- `fn score_fatigue(ctx: RuleContext) -> f64`
- `fn score_training(ctx: RuleContext) -> f64`

### Decision / Mutation Hooks
- `fn pre_placement_filter(ctx: RuleContext) -> bool` (veto a candidate)
- `fn post_placement(ctx: &mut PlacementContext)` (adjust groups, waves, locks)
- `fn resolve_tie(ctx: RuleContext, candidates: Vec<Tm>) -> TmId`

### Night / Global Hooks
- `fn pre_night(ctx: NightContext)` → adjustments to pools, priorities, or global params
- `fn assign_break_waves(placements: Vec<Placement>, ctx) -> Vec<BreakAssignment>`
- `fn custom_audit_entry(placement: Placement, ctx) -> Option<String>`

### Safety & Sandbox Rules (Rhai Specialist owns enforcement)
- No I/O, no network, limited std, time/memory caps, deterministic.
- All hooks receive immutable or carefully cloned context.
- Errors in hook → treat as 0 contribution + log to audit (never crash placement).

Full signatures, `RuleContext` fields, and example Rhai snippets will be added by Rhai Specialist and Rust Core in Phase 1–2 and kept in this section + `engine/rust/zds-engine/examples/`.

---

## 6. Immediate Next Steps (Execute Starting Now)

1. **Engine Architect** (today): Post this document to repo + Linear project. Schedule 90-min contract lock meeting (invite all 6 + key domain stakeholders). Create the Rust crate skeleton PR template.
2. **Rust Core Developer**: Begin `engine/rust/zds-engine` crate + initial `lib.rs` with domain types + first two scorers. Propose WeekSnapshot shape in Rust.
3. **Configuration & Rules Backend Developer**: Draft Supabase migration for `rulesets`/`ruleset_versions` + basic FastAPI router skeleton.
4. **Migration & Validation Lead**: Extract 3 real historical nights into `WeekSnapshot` JSON fixtures + open the harness repo location (probably under `apps/zds/engine/rust_harness/` or `tools/`).
5. **All**: Comment on this doc in repo or Linear with questions / proposed contract tweaks before the sync meeting.

---

## 7. References & Artifacts

- Current engine: `apps/zds/engine/fill_engine.py`, `glcr_engine/`, `Rules/`, `simulate_weeks.py`, `render_deployment_book.py`
- Bridge: `apps/zds/engine_bridge.py`
- Existing engine config: supabase migration `20260505_000003_create_engine_config.sql` + related
- Historical context: `GLCR Placement Engine - Engineering Handoff.pdf` (root), `docs/engine_dogfood_findings_2026_05_06.md`, `PROJECT_REVIEW.md`, `PHASE_6_COMPLETION.md`
- Future Rust home: `engine/rust/zds-engine/` (to be created)
- This doc lives at `docs/ZDS_ENGINE_RHAI_EXTENSION_POINTS.md`

**Next update cadence:** Architect will refresh this doc after each major contract lock and at the end of each phase. Sub-teams update their sections.

---

*This is the single source of truth for the engine rewrite. All implementation work must trace back to a line in this roadmap or an approved deviation recorded here.*

**— Engine Architect**

---

## Appendix: Quick-Start Charter for `engine/rust/zds-engine/src/lib.rs` (to be created)

```rust
//! ZDS Placement Engine — Rust + Rhai Core
//!
//! Domain model and scoring for the GLCR Zone Deployment System.
//! Designed for:
//! - Byte-level parity with legacy Python fill_engine during transition
//! - Versioned, UI-editable RuleSets (weights + Rhai hooks)
//! - Rich explainability for the Playground
//! - Safe, sandboxed extensibility via Rhai
//!
//! See docs/ZDS_ENGINE_RHAI_EXTENSION_POINTS.md for the full living roadmap,
//! WeekSnapshot contract, and Rhai hook catalog.
//!
//! Safety invariants:
//! - All public APIs are deterministic given the same RuleSet + WeekSnapshot.
//! - Rhai execution is strictly sandboxed (no I/O, bounded time/memory).
//! - Every Placement decision carries a full ScoreBreakdown + Audit trail.

pub mod domain;      // Tm, Slot, Placement, RuleContext, ScoreComponent, ...
pub mod scoring;     // native scorers + pipeline
pub mod rhai_bridge; // sandbox, hook registration, execution
pub mod ruleset;     // RuleSet, RuleSetVersion loading & validation
pub mod snapshot;    // WeekSnapshot (de)serialization + validation

// Public entry points for harness / backend simulate
pub fn score_week(snapshot: &WeekSnapshot, ruleset: &RuleSet) -> EngineResult<EngineOutput> { ... }
pub fn validate_ruleset(ruleset: &RuleSet) -> Result<(), Vec<ValidationError>> { ... }
```

Update this charter in `lib.rs` as the crate evolves.

---

*End of synthesized roadmap. Team: start executing the Phase 1 items in parallel immediately after the contract sync.*