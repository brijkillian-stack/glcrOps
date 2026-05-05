# Role gating spec — write-action permission sweep

The auth foundation (3-tier: viewer / zds_editor / editor) shipped on 2026-05-05.
This spec is the focused Sonnet task that gates every write surface across
the codebase against the appropriate role.

Foundation already in place at handoff:
  shared/auth.py         AuthState with permission Vars (can_edit_deployment,
                          can_run_engine, can_upload_schedule, can_edit_rules,
                          can_write_memory, can_save_zds_annotation,
                          can_save_memory_annotation, plus is_editor /
                          is_zds_editor)
  shared/components/sidebar.py   role chip + sign-in / sign-out actions
  Routes                  /unlock public; /login + /auth/callback public;
                          / and others gated by AuthState.require_unlock

What's missing: per-write-action gating. Right now a viewer (PIN-only) can
still trigger write event handlers because the gating is at the page level
(require_unlock = "you have the PIN") and not at the action level.

## 1. The pattern

Two complementary gating shapes. Use both as appropriate:

### Pattern A — inline on every write event handler (preferred for actions)

```python
class CaptureState(rx.State):
    @rx.event
    async def save_capture(self, payload: dict):
        if not (await AuthState.get_state(self)).can_write_memory:
            return rx.toast.error("Sign in as editor to capture")
        # ... existing capture logic
```

For Reflex 0.6+, the cleaner idiom is to use a guard via reflex's
`return rx.cond(...)` patterns OR to use the AuthState directly when the
state class can reach it. In practice the simplest approach inside any
event handler is:

```python
from shared.auth import AuthState

@rx.event
def my_write(self):
    auth = await self.get_state(AuthState)   # for cross-state access
    if not auth.can_write_memory:
        return rx.toast.error("Sign in as editor to do this")
    # ... the actual write
```

(Reflex provides `self.get_state(OtherState)` for cross-state reads in
event handlers — this is the idiomatic way to check AuthState from a
non-AuthState event.)

### Pattern B — render-time disable for buttons / FABs (preferred for UI)

Buttons / FABs / write affordances render with reduced opacity + a
disabled-feeling style when the current role can't use them. A click
shows the same toast as Pattern A.

```python
rx.el.button(
    "Capture",
    on_click=CaptureState.open_capture_box,
    class_name=rx.cond(AuthState.can_write_memory,
                       "fab", "fab fab-disabled"),
    disabled=~AuthState.can_write_memory,
    title=rx.cond(AuthState.can_write_memory,
                  "Capture (⌘N)",
                  "Sign in as editor to capture"),
)
```

The CSS class `fab-disabled` reduces opacity to 0.5 and changes cursor
to `not-allowed`. When clicked despite being disabled (touch devices
ignore disabled sometimes), Pattern A's inline check catches it.

## 2. Write surfaces — exhaustive inventory

For each surface below, apply Pattern A on the event handler AND
Pattern B on the rendering button/control.

### Memory surfaces — gate with `can_write_memory` (editor only)

```
Capture box (⌘N FAB)                  shared/components/capture.py
                                       open_capture_box, save_capture
Capture quick-action buttons          shared/components/capture.py
TM profile edit                       apps/glcr/pages/people.py
                                       (any setter that writes back to
                                       tm_profiles or score_history)
TM score adjust                       apps/glcr/pages/people.py
                                       set_skill_score, etc.
TM comment add                        apps/glcr/pages/people.py + people state
TM accommodation/preference edit      apps/glcr/state/people.py
Write-up draft generate               apps/glcr/pages/writeups.py
Write-up save / export                apps/glcr/pages/writeups.py
Threads — create / edit / delete      apps/glcr/state/threads.py
Tasks — create / complete / delete    apps/glcr/state/tasks.py
Areas observation save                apps/glcr/state/areas.py
Floor walk capture                    apps/glcr/state/floor.py
Recap edit / send                     apps/glcr/state/recap.py
Search log writes                     (probably none; reads only)
```

### ZDS surfaces — gate with `can_edit_deployment` or sub-permission

```
Per-night swap / slot edit / lock     apps/zds/components/zone_card.py
                                       apps/zds/components/tm_picker.py
                                       apps/zds/state.py (ZdsState swap_*,
                                       lock_*, save_*)
                                       → can_edit_deployment

Save banner ("apply changes")          apps/zds/components/save_banner.py
                                       → can_edit_deployment

Schedule upload (ADP xlsx)             apps/zds/state.py upload handler
                                       → can_upload_schedule (editor only)

Run fill engine                        apps/zds/state.py run_engine
                                       apps/zds/engine_bridge.py
                                       → can_run_engine (editor only)

Edit ZDS rule files (TM Profiles,      not yet UI-exposed; will be when
Eligibility, Slot Difficulty, etc.)    edit pages exist
                                       → can_edit_rules (editor only)
```

### Annotation surfaces (Phase K) — gate per surface

```
PencilCanvas save dispatch            shared/components/pencil_canvas.py + JS
                                       Save handler in the host page checks:
                                         floor_map  → can_save_memory_annotation
                                         deployment_book → can_save_zds_annotation
                                         signature   → can_save_memory_annotation
                                         tm_comment  → can_write_memory
                                         scratch     → permissive (or none)

  Implementation note: the pencil_canvas component itself stays
  permission-agnostic — the host page's handle_pencil_save event handler
  is where the gate lives.
```

## 3. Suggested file edit order

```
1. shared/components/capture.py + state/capture            (highest-frequency write)
2. apps/zds/state.py                                       (deployment/swap writes)
3. apps/zds/components/{zone_card, tm_picker, save_banner} (UI disable)
4. apps/glcr/pages/people.py + state/people.py             (TM edits)
5. apps/glcr/pages/writeups.py + state/writeups.py
6. apps/glcr/state/threads.py + state/tasks.py
7. apps/glcr/state/areas.py + state/floor.py + state/recap.py
8. apps/zds/state.py upload + run_engine handlers          (editor-only ZDS)
```

Estimated 2-3 hours for the full sweep. Each surface is a small inline-
gate + a UI-disable; the work is mostly mechanical pattern application
once the first two surfaces (capture + ZDS state) are done as templates.

## 4. Smoke tests after the sweep

For each role, walk through:

```
Viewer (PIN only)
  ✓ can browse all dashboards, navigate routes
  ✓ can open ZDS week / day pages, view deployment grid
  ✓ can read TM profiles, captures feed
  ✗ capture FAB shows dimmed; click → toast "sign in as editor"
  ✗ ZDS swap UI dimmed; click → toast "sign in as editor"
  ✗ schedule upload button dimmed
  ✗ engine run button dimmed
  ✓ "Sign in as editor" link in sidebar → /login

ZDS Editor
  ✓ everything Viewer can do
  ✓ can swap, edit slots, lock/unlock per-night
  ✓ can save Pencil annotations on ZDS deployment + week pages
  ✗ capture FAB dimmed
  ✗ schedule upload dimmed
  ✗ engine run dimmed
  ✗ TM profile edit dimmed

Editor
  ✓ everything works as before
```

## 5. CSS hygiene

Add a single new CSS class `.fab-disabled` (and similar for buttons /
write affordances) to assets/styles.css:

```css
.fab-disabled,
.btn-disabled,
.action-disabled {
  opacity: 0.45;
  cursor: not-allowed !important;
  pointer-events: auto;        /* still get clicks → trigger toast */
}
```

Pattern B uses `class_name=rx.cond(AuthState.can_X, "...", "...-disabled")`.

## 6. Out of scope for this sweep

- New permission roles beyond viewer / zds_editor / editor
- Per-row Supabase RLS (the gates are application-level — service role still
  bypasses on the backend; the gate is in the Reflex event handlers)
- Audit logging of denied writes (could be a follow-up — every denial
  could log to agent_logs.actions for visibility)
- "Request access" workflow when a viewer sees something they want to do
- Per-page route-level lockout (we keep route-level open for everyone with
  PIN; gating is per-action, which is the right trade-off for read-heavy UX)
