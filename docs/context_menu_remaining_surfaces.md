# Context menu — remaining surfaces, actions, and print rendering

The foundation is shipped (2026-05-05):

```
public.assignment_highlights table              live
shared/components/context_menu.py               ContextMenuState + global_context_menu
assets/context_menu.css + context_menu.js       desktop right-click + iPad long-press
brijkillian_stack/brijkillian_stack.py          mounted in _with_grok and _with_zds_chrome
apps/zds/components/zone_card.py                deployment-grid TM names wired
ContextMenuState.mark_sweeper()                 idempotent toggle, writes to highlights table
ContextMenuState.view_profile()                 opens TM drawer
```

What's NOT yet wired (this spec).

## 1. Remaining trigger surfaces

For each, follow the pattern in `apps/zds/components/zone_card.py` —
add `class_name="ctx-menu-trigger"` and `custom_attrs={"data-ctx-..."}`
to the trigger element.

### 1.1 Schedule tab — TM chips in GRAVE / PM OL / AM OL pools

```
file:    apps/zds/pages/deployment.py
location: the chip rendering inside the rx.foreach over names in
          _overlap_row_comp / the GRAVE_SHIFT block (search for
          "ZdsState.night_grave_pool" / "ZdsState.pm_overlaps" /
          "ZdsState.am_overlaps").

surface attribute: "schedule_tab"
target_type:       "pool_tm"
target_id:         the tm_id (look up via ZdsState.tm_name_to_id)
target_label:      the name string
night_id:          ZdsState.current_night_id
slot_key:          "" (pool TMs aren't in a slot yet)

Item set computed in context_menu.py for (schedule_tab, pool_tm):
  - View profile  (already implemented)
  - Mark called off  (NEW handler — see §2.1)
  - Add note about [name]  (NEW handler — opens capture box)
```

### 1.2 Week overview — TM names on day cards

```
file:    apps/zds/pages/week_overview.py
location: each day card may show a roster summary; if individual TM
          names are visible add the trigger.

surface attribute: "week_overview"
target_type:       "day_card_tm"
target_id:         tm_id
target_label:      display name
night_id:          the day's night_id (each card knows it)
slot_key:          ""

Item set:
  - View profile  (already implemented)
  - Jump to deployment editor for this day (NEW handler — emits
    rx.redirect to /zds/week/[week_id]/day/[night_id])
```

### 1.3 TM picker / swap modal

```
file:    apps/zds/components/tm_picker.py
location: each candidate TM card

surface attribute: "tm_picker"
target_type:       "picker_tm"
target_id:         tm_id
target_label:      display name
night_id:          ZdsState.current_night_id
slot_key:          ZdsState.picker_slot_key

Item set:
  - View profile  (already implemented)
  - (no destructive actions — picker is browse-only context)
```

### 1.4 Empty slot / slot label cells

```
file:    apps/zds/components/zone_card.py
location: the slot-label area when no TM assigned (slot["display_name"]
          is "Unfilled" or empty).

surface attribute: "deployment_grid"
target_type:       "slot"
target_id:         slot["slot_key"]   (NOT a tm_id since no TM)
target_label:      slot["label"]       (e.g. "Zone 3", "WRR 8")
night_id:          ZdsState.current_night_id
slot_key:          slot["slot_key"]

Item set:
  - Mark slot priority  (writes priority highlight to assignment_highlights
    with tm_id=NULL)
  - Force assign…       (opens the regular swap picker)
  - Lock empty          (sets is_locked=true on the assignment)
  - Print just this slot (calls a new print_single_slot handler)
```

## 2. Remaining action handlers

Add these methods to `ContextMenuState` in
`shared/components/context_menu.py`. Each follows the pattern of
`mark_sweeper`: gate via `_require_editor`, check context, write to
the appropriate table, set status, close.

### 2.1 mark_called_off()

```
Inserts/toggles a 'callout' note in public.notes for the target TM
on the current night_date. ALSO updates ZdsState.night_called_off
set so the in-memory deployment grid greys the name.

Reuses existing capture flow: from shared.db import save_capture
or similar — there's already a callout content_type.
```

### 2.2 add_note_about()

```
Closes the menu, opens the global capture box pre-populated with
the target TM's name + content_type='observation'. The user types
their note and saves via the existing capture handler.

Implementation:
  return [
      AppState.open_capture_for(self.target_label),
      ContextMenuState.close,
  ]
```

### 2.3 add_highlight(highlight_type)

```
Generic version of mark_sweeper for the other types — priority,
trainer_pair, watch, accommodation, custom. Same idempotent toggle
pattern, just with different highlight_type and visual tokens
from HIGHLIGHT_VISUALS dict.

For 'custom', open a small inline note input first to capture the
free-form text before saving.
```

### 2.4 swap_to_slot()

```
Opens the TM swap picker (existing ZdsState.open_picker) with the
target TM pre-selected as the source. The user then taps the
destination slot. No new state needed — wire to existing flow.

return ZdsState.open_picker_for_tm(self.target_id, self.night_id)
  (this method may not exist yet — would need to add it to ZdsState
   or use existing open_picker with a 'source_tm_id' override.)
```

### 2.5 force_assign() / lock_empty() / force_clear()

```
All wire to existing ZdsState methods on the assignment. No new
backend logic — just menu items that fire the right state events.
```

## 3. Print renderer — visual treatment per highlight_type

`apps/zds/engine/render_deployment_book.py` is the heavy file
(2407 lines). The integration:

### 3.1 Add a fetch helper

```python
# shared/db.py or apps/zds/database.py
def get_highlights_for_night(night_id: str) -> dict[str, list[dict]]:
    """Return {slot_key: [highlight_dict, ...]} for the given night.
    Skips expired rows."""
    sb = get_client()
    rows = (
        sb.table("assignment_highlights")
        .select("*")
        .eq("night_id", night_id)
        .or_("expires_at.is.null,expires_at.gt.now()")
        .execute()
        .data or []
    )
    by_slot = {}
    for r in rows:
        by_slot.setdefault(r["slot_key"], []).append(r)
    return by_slot
```

### 3.2 Pass highlights into render

```python
# In whatever wraps render_deployment_book — typically engine_bridge.py
# or print_renderer.py.

def render_book(night_id, ...):
    highlights = get_highlights_for_night(night_id)
    return render_deployment_book.render(..., highlights=highlights)
```

### 3.3 Apply visual treatment per type

```python
# Inside render_zone_card / render_aux_card, look up highlights by slot_key
# and apply CSS classes / inline styles. Suggested treatment:

VISUAL_TREATMENT = {
    'sweeper':       {'border': '#C8A77F', 'icon': '🧹', 'label': 'SWEEPER'},
    'trainer_pair':  {'border': '#0065BF', 'icon': '🔗', 'label': 'TRAINER PAIR'},
    'priority':      {'border': '#B91C1C', 'icon': '⚑',  'label': 'PRIORITY'},
    'watch':         {'border': '#F59E0B', 'icon': '👁',  'label': 'WATCH'},
    'accommodation': {'border': '#6B7280', 'icon': '✚',  'label': 'ACCOMM'},
    'custom':        {'border': '#1A1A1A', 'icon': '★',  'label': 'NOTE'},
}

# When a slot has a highlight:
#  - Card gets a 3px border in the highlight color (replacing the
#    existing zone-color border, or stacking via a wrapper div).
#  - Icon + label render as a small chip below the TM name.
#  - If multiple highlights, stack them vertically.
```

### 3.4 Backwards compat with the existing sweeper

The current code already has `is_sweeper` + `sweeper_route` on tm_slot
dicts (driven by the pre-existing logic). Keep that as a fallback —
if `assignment_highlights` has a sweeper row OR the legacy is_sweeper
is true, render the sweeper treatment. They can co-exist; new
highlights take precedence visually.

## 4. Smoke tests after Sonnet ships these

```
1. Right-click a TM in the deployment grid → menu opens with
   "Mark sweeper", "View profile". Click "Mark sweeper" — toast
   confirms saved. Re-open menu → same TM now shows the toggle as
   active. Click again → cleared.

2. Right-click a TM chip in the Schedule tab → menu opens with only
   "View profile" + "Mark called off" + "Add note". (No swap, no
   highlight — pool TMs aren't placed yet.)

3. Long-press on iPad anywhere a trigger exists → same menu fires
   after ~500ms hold. The picker / swap doesn't also open after the
   long-press (verified via the click-suppression in context_menu.js).

4. Run the engine and re-print → the deployment book HTML shows the
   gold sweeper border + 🧹 icon on whatever slots had sweeper
   highlights set.

5. Viewer (in non-DEV-MODE) clicks "Mark sweeper" → toast: "Sign in
   as editor to make changes". The menu closes. No DB write.
```

## 5. Estimated time

```
§1.1 Schedule tab triggers + mark_called_off + add_note_about    1.5 hr
§1.2 Week overview triggers                                      0.5 hr
§1.3 TM picker triggers                                          0.5 hr
§1.4 Empty slot triggers + slot-level handlers                   1 hr
§2  Remaining action handlers (callout, swap, force assign,
    add_highlight generic)                                       1.5 hr
§3  Print renderer integration                                   2 hr
§4  Smoke testing + polish                                       1 hr
                                                              ─────────
                                                       Total:   ~8 hr Sonnet
```
