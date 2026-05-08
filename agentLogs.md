##Agent Logs

---

### Phase 4d — Shift HUD UX Polish
**Agent:** Sonnet  
**Commit:** 8fc4c28  
**Status:** complete  
**Date:** 2026-05-07

**Summary of changes:**

- `apps/shift/utils.py` *(new)* — `fmt_time()` helper: 12-hr no-leading-zero lowercase am/pm (e.g. `1:10am`, `11:59pm`)
- `apps/shift/types.py` — Added `BreakSlot`, `BreakGroup`, `ZoneCardData` TypedDicts; deprecated `HudBreakWave`
- `apps/shift/state.py` — Replaced `break_waves` with `break_groups: list[BreakGroup]` (3×3 model); added `zone_cards: list[ZoneCardData]`; wired `fmt_time` into `_format_due` + `_now_approx_label`; `_build_from_zds` now builds both zone_cards (with real zone_label, zone_area, group_num, current_task) and break_groups (3 groups × 3 waves, status derived from ET clock)
- `apps/shift/pages/index.py` — Replaced flat wave strip with 3×3 break grid (`_break_group_row` + `_break_wave_cell` using `<details>/<summary>` for click-to-expand TM names); updated zone grid to use `ShiftState.zone_cards`; all status labels driven by state field (`upcoming`→`—`, `active`→`● Active` pulsing, `complete`→`✓ Complete`)
- `shared/components/shift_zone_card.py` — Rewritten for `ZoneCardData`: shows zone_label (Z1/Z3), zone_area name, TM name, group badge (G1/G2/G3 with CSS token color), current_task
- `apps/zds/types.py` — Added `group_num: int` to `BreakRow`
- `apps/zds/database.py` — `fetch_break_assignments` now selects `group_num`
- `apps/zds/state.py` — `_do_engine_night` updated: `group_num = BG_ZONE/RR/AUX.get(...)`, `break_wave = 1`
- `assets/ops_tokens.css` — Added `--group-1/2/3` + `--group-1/2/3-dim` for dark and light themes; added `@keyframes pulse`; added `<details>` summary reset
- **DB migration:** `add_group_num_to_break_assignments` — added `group_num smallint NOT NULL DEFAULT 1` to `break_assignments`; migrated existing data (`group_num = old break_wave`, `break_wave = 1`)