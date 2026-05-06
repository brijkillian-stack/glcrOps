# ZDS Picker + Highlight UX Spec

Captured 2026-05-06 from a working session. Two adjacent UI changes for the
ZDS deployment grid that should ship together because they share the same
trigger surface (slot cards + TM name spans).

---

## 1. Tasks panel inside the TM picker

**Today.** Clicking an empty slot card on the deployment grid opens
`tm_picker` (modal). The picker shows the day's available pool and lets
Brian pick a TM. After placement, slot-specific tasks (e.g. "Sweep main
floor", "Restock Z9 supplies") live separately on the zone card itself
and have to be added in a second step.

**Goal.** When the picker opens, show the slot's *canonical* task list
in a read-only side panel so Brian knows what he's actually assigning
before he picks the body.

**Scope (v1).**
- Read-only side panel inside the existing picker modal.
- Source of tasks: `overlap_tasks` table, keyed by `slot_code`. Engine
  already loads these into `overlap_tasks` dict at runtime
  (`fill_engine.py:464`); UI layer should query the same table directly
  via a new `shared/db.py` helper (`get_canonical_tasks_for_slot`).
- Layout: picker becomes a two-column dialog. Left = TM list (today).
  Right = "What this slot does:" header + bulleted task list.
- Empty state: "No canonical tasks for this slot — add tasks after
  placement."
- No editing in v1. (Adding inline editing is the natural v2.)

**Files to touch.**
- `apps/zds/components/tm_picker.py` — split into `_left_pool_pane()` +
  `_right_tasks_pane()` helpers, add the side panel.
- `shared/db.py` — add `get_canonical_tasks_for_slot(slot_code) -> list[str]`.
- `apps/zds/state.py` — `open_picker` already takes `slot_key`; add a
  call to load tasks into a new `picker_tasks: list[str]` state field.

**Out of scope.**
- Editable task list inside picker (v2).
- Task templates per zone area (v2).
- Voice/Pencil-driven task entry (K-phase).

---

## 2. Left-click highlight on TM name spans

**Today.** Right-click (or iPad long-press) on a TM name on the
deployment grid opens the global context menu. Sweeper / priority /
watch highlights are reachable through the menu but require two taps.

**Goal.** Left-click on a TM name posts a "selected for highlight"
state, then a small inline toolbar lets Brian pick which color to apply
(sweeper / priority / watch / accommodation / custom). One click + one
toolbar tap, vs. two-tap menu walk today.

**Behaviour.**
- Left-click TM span → toolbar pops in next to the span (anchored, not
  modal). Toolbar shows the 5 highlight colors as round chips.
- Tap a chip → highlight applied (writes `assignment_highlights` row),
  toolbar dismisses.
- Tap outside / second left-click on same TM → toolbar dismisses
  without applying.
- Right-click still opens the full context menu (existing behaviour
  unchanged — escape hatch for less-common actions).

**State.**
Add a sibling state class to `ContextMenuState` (or extend it):
`HighlightToolbarState` with `open: bool`, `x: int`, `y: int`,
`tm_id: str`, `night_id: str`, `slot_key: str`. Reuses
`assignment_highlights` table; toggle behaviour same as the existing
`mark_sweeper` event handler.

**Visuals.**
Match the existing context menu chrome — same shadow, same backdrop,
same chip sizing (44pt touch targets on iPad). Use the
`HIGHLIGHT_VISUALS` color tokens already defined in
`shared/components/context_menu.py`.

**Files to touch.**
- `shared/components/highlight_toolbar.py` — new component (parallel to
  `context_menu.py`).
- `apps/zds/components/zone_card.py` — TM display name span gets
  `on_click=HighlightToolbarState.open_at(...)` in addition to the
  existing `on_context_menu`.
- `assets/highlight_toolbar.css` — chip styles + popover positioning.
- `brijkillian_stack/brijkillian_stack.py` — mount
  `global_highlight_toolbar()` next to `global_context_menu()` in both
  `_with_grok` and `_with_zds_chrome` wrappers.

**Out of scope.**
- Multi-select of TMs to bulk-apply a highlight (v2).
- Custom-color picker (the 5 canonical types should cover 95%).
- Touch-and-hold-for-toolbar on iPad (right-click long-press already
  works for the menu — toolbar is left-click only).

---

## Open questions

- Does left-click conflict with anything else on TM spans today?
  (Currently no — the slot card's `on_click` is on the *card*, not the
  inner TM span.)
- Should the left-click highlight bypass the
  `AuthState.can_edit_deployment` check? (Probably not — same gate as
  the context menu's `_require_editor`.)

---

## Implementation handoff

Built atop:
- The unified context menu work landed in `eb67f8c` (foundation) and
  unblocked in `957421f` (truncation fix).
- `assignment_highlights` table + `HIGHLIGHT_VISUALS` tokens already
  defined.
- `tm_picker` component already wired to `open_picker(slot_id, …)`.

Estimated effort: 2–3h for both pieces (1h for #1, 1.5h for #2). Sonnet
handoff candidate.
