# ZDS Redesign Review + Implementation Plan

Reviewed: `WebApp.zip` from Claude design canvas (uploaded 2026-05-06).

Contents: 6 HTML mocks (ZDS Dark v1/v2/v3, Print, Print Landscape,
Wireframes), `design-canvas.jsx`, `tweaks-panel.jsx`, supporting CSS +
SVG, screenshots. The "v3" file is the most complete — ~94k of React
inline rendering the entire ZDS surface (Index → Week Overview →
Deployment grid → Break Sheet) at production polish.

---

## What this is, in one paragraph

A complete dark-mode redesign of ZDS with the same data model but
significantly upgraded visual hierarchy, plus four new
functionality affordances (NoticeDot, LockBadge with metadata,
UndoToast, AuditStrip). The data shape implied by the mocks
matches what we already have in Supabase — no schema migration
required for the look, but two of the new affordances need small
schema additions. Print pages (Break Sheet) are a redesign of the
existing 14-page deployment book.

---

## Major delta vs. what we have today

### Visual / chrome
| Today | Redesign |
|---|---|
| Light-mode app, all GLCR brand | Dark mode (`#080e14` body) with casino-scatter SVG fade behind footer |
| Plain header strip | "Chip-header" with dotted-circle pattern overlay |
| Section headers as plain text | Eyebrow + thin gold rule beneath |
| Zone cards: solid backgrounds | Hover-glow rings, locked → inset gold ring, empty → faint outline |
| Plain action buttons | Lucide icons + chip-style buttons with variant system (default / primary / ghost / danger) |
| Tab pills above content | TabSwitcher component with active-tab underline-glow |

### UX
| Today | Redesign |
|---|---|
| Click slot card → modal picker | Same flow, but picker has search field + pool-type chips + recent placements per TM (TMPicker is much richer) |
| Right-click for highlights | Inline NoticeDot on each slot card; badge appears in card chrome instead of via a menu walk |
| Lock toggle on slot card | LockBadge shows `locked_by` + `locked_at` metadata, not just bool |
| No undo | UndoToast appears for 5s after destructive actions (clear, swap, lock) — single-tap to revert |
| No save metadata visible | AuditStrip footer: "Last saved 2m ago by Brian · 3 unsaved" |
| Per-night → per-day click-through | NightTabs row above grid for instant day-switching without route change |

### Print (Break Sheet redesign)
| Today's deployment book | Redesigned Break Sheet |
|---|---|
| 14 pages: per-day deployment + break sheet | Same 2-page-per-day model, but break sheet is column-based (Break 1, 2, 3) instead of full-width rows |
| Per-row: name + slot + tasks | Per-column header with break-wave indicator, then names listed under their wave |
| Coverage alerts inline | OVERLAPS strip moved to bottom — cleaner separation between what each TM does on their break vs. their actual coverage |

The redesigned print page in screenshot `Letter_8.5x11.pdf` and
`Screenshot at 1.52.11 AM.png` is **a real improvement** for the
printed handout — easier to scan during the morning huddle because
break wave is the primary axis instead of the slot label.

### Four new affordances that need real backend work

**1. NoticeDot inline on slot cards**

Already in DB: `assignment_highlights` table exists. Today it's
written/read by the right-click context menu's `mark_sweeper`
handler. The redesign moves the rendering inline (small dot in the
upper-right corner of each slot card) and adds a hover affordance
to expand into a chip. **Implementation = pure UI change**, no
schema work. Pair with the `highlight_toolbar` Sonnet spec we
already shipped to get left-click → toolbar → write
`assignment_highlights`.

**2. LockBadge with metadata**

Today: `zone_assignments.is_locked` is a bool. Redesign wants to
show "Locked by Brian · 2h ago" in the badge. **Needs schema
additions**: `zone_assignments.locked_by text` and
`zone_assignments.locked_at timestamptz`. One migration. Then
`toggle_slot_lock` writes those fields (sets to current
session-user + now() on lock; null + null on unlock).

**3. UndoToast**

Today: every destructive action commits immediately, no undo.
Redesign wants a 5s window where the user can revert. Two
implementation options:
  - **Client-only optimistic state** (Reflex var holds the
    last-action-undo state; tap "Undo" → revert via the inverse
    operation). No backend change. ~30 min per action wired.
  - **Server-side undo log** (new `assignment_audit_log` table
    capturing every change with diff payload + an `undone_at`
    field; "Undo" reverses the row). Heavier; useful for cross-
    session undo and audit trail. ~1.5h schema + 2h wiring.

The mocks don't dictate which model. **Recommended: client-only
for v1** (simpler, covers the supervisor's "oops" case) and
upgrade to server-side later if/when audit trail becomes a real
need.

**4. AuditStrip footer**

Today: nothing tracks "when was this week last saved." Redesign
wants a footer with last-saved timestamp + last editor + unsaved
count. **Needs schema additions**: `weeks.last_saved_at
timestamptz`, `weeks.last_saved_by text`. Touch on every
zone_assignments / overlap_assignments / engine run write — bump
those two fields.

---

## What's already there — won't need re-implementation

- **Zone card structure** (`apps/zds/components/zone_card.py`) is
  already cleanly split into header + body + tasks. The redesign
  is mostly a styling pass on the same component.
- **NightTabs** (`apps/zds/components/night_tabs.py`) — same idea,
  just needs the dark-mode CSS tokens.
- **TM picker** (`apps/zds/components/tm_picker.py`) was just
  upgraded by Sonnet (commit `1f3195d`) to have the tasks side
  panel. The redesign adds search + pool-type chips on top of
  what Sonnet shipped — incremental, not a rewrite.
- **Context menu** (`shared/components/context_menu.py`) — already
  shipped with right-click on TM names. The redesign keeps this
  for less-common actions (escape hatch).
- **Highlight toolbar** (left-click) — Sonnet handoff spec already
  written; implementation pending.
- **Brand tokens** (`assets/colors_and_type.css`) — same file the
  redesign uses. No changes needed; just need a `dark` mode
  variant which the design canvas mostly does inline.

---

## What's risky / worth flagging

1. **Dark mode is a big surface area.** Every existing Reflex
   component renders against light tokens (`var(--fg-1)` =
   ink-900 on white). Ship dark mode as a `prefers-color-scheme:
   dark` media query OR a top-level `data-theme="dark"` toggle —
   not by find-replacing color values. The latter would break
   the GLCR design system's usability for the Memory side, which
   doesn't want dark mode.

2. **Casino-scatter background is a 2k-line inlined SVG.** Cute,
   but it's heavy. Move it to `assets/casino_scatter.svg` and
   reference via `background-image: url(…)` — keeps the Reflex
   component clean and lets the browser cache it.

3. **TMPicker search field implies client-side filter.** Today's
   picker loads pool data server-side per-request. Adding a
   search field that filters in-place means either (a) load the
   full pool client-side once and filter via Reflex `Var` ops, or
   (b) round-trip every keystroke. (a) is fine for ~50 TMs;
   premature to worry about (b).

4. **The redesign's `WeekOverviewPage` shows per-day stats**
   (filled count, callouts, breaks) inline on each day card.
   Computing these on every page load means 7 nights × 3 queries
   = 21 round-trips. Pre-aggregate into a `week_summary` view
   (Postgres view, not table — auto-refresh) so the page is one
   query. ~30 min.

5. **The four new affordances have inter-dependencies.**
   AuditStrip's "unsaved count" only makes sense if writes are
   queued client-side rather than committed live. Today every
   slot write commits immediately. To have a meaningful "unsaved"
   number, ZDS would need a draft mode. Decide: ship the
   AuditStrip showing only last-saved (no unsaved) in v1, OR
   redesign the write path to be draft-then-commit. The mocks
   don't force a choice.

---

## Phased implementation plan

### Phase 1 — Visual reskin (no backend, no functional change)
- Apply dark-mode tokens via top-level theme toggle (single CSS
  file referencing `colors_and_type.css` in dark variant).
- Restyle `zone_card`, `rr_card`, `aux_card`, `night_tabs`,
  `zds_header` to match the redesign visuals.
- Move casino-scatter SVG to `assets/casino_scatter.svg`, mount
  on the ZDS pages (not Memory pages).
- Add eyebrow + gold-rule pattern to section headers in the
  deployment grid.

**Effort:** 4–6h. **Sonnet candidate:** yes (clean reskin work,
spec is the screenshots + brand tokens). **Risk:** low.

### Phase 2 — Inline NoticeDot + LockBadge metadata
- Schema migration: `zone_assignments.locked_by text`,
  `zone_assignments.locked_at timestamptz`.
- Update `toggle_slot_lock` to write the metadata.
- Render NoticeDot on slot cards reading from
  `assignment_highlights`.
- Render LockBadge with "Locked by X · Y ago" formatting.

**Effort:** 2–3h. **Sonnet candidate:** yes (small scope, clear
spec). **Risk:** low — schema additions are nullable.

### Phase 3 — TMPicker upgrade (search + pool chips + recent)
- Add search field to existing `tm_picker` component.
- Add pool-type chips (Grave / PM OL / AM OL / All).
- Add "Recent placements" mini-list per TM (already have the
  `fetch_recent_placements_bulk` helper — just needs the
  truncation fix from the dogfood findings).

**Effort:** 3–4h. **Sonnet candidate:** yes. **Risk:** medium —
depends on `fetch_recent_placements_bulk` truncation fix landing
first.

### Phase 4 — UndoToast (client-only v1)
- New `shared/components/undo_toast.py` component.
- New `UndoState` with `last_action`, `last_inverse`, timer.
- Wire into clear_slot, swap, lock/unlock — each fires
  `UndoState.queue(inverse_fn)`.
- 5s auto-dismiss.

**Effort:** 2–3h. **Sonnet candidate:** yes. **Risk:** low if we
don't try server-side undo log in v1.

### Phase 5 — AuditStrip + week_summary view
- Schema: `weeks.last_saved_at`, `weeks.last_saved_by`.
- Postgres view: `week_summary` aggregating per-night fill counts,
  callouts, break wave totals.
- Triggers (or app-level updates) to bump
  `weeks.last_saved_at` on every write.
- Footer component reading from view + week metadata.

**Effort:** 4–6h. **Sonnet candidate:** maybe — touches schema,
view, app, component. Could split: schema/view (1h, Brian +
Supabase MCP) → component (3h, Sonnet).

### Phase 6 — Break Sheet print redesign
- New page model in `render_deployment_book.py`: replace the
  current break sheet's row layout with the redesigned column-by-
  wave layout.
- Keep the Daily Deployment page mostly unchanged (the v2.3
  redesign is still the right frame for that page).

**Effort:** 3–4h. **Sonnet candidate:** yes (purely a renderer
update — `render_break_sheet_page()` only). **Risk:** low.

### Phase 7 (optional) — Server-side undo log
- New `assignment_audit_log` table with
  `(id, target_table, target_id, action, before_payload,
  after_payload, performed_by, performed_at, undone_at)`.
- Refactor every destructive ZDS handler to write a log row.
- Replace UndoToast's client-only v1 with reads from the log.

**Effort:** 6–8h. **Sonnet candidate:** yes but heavier prompt.
**Recommended only if** the v1 UndoToast doesn't cover Brian's
real-world workflow.

---

## Total estimated effort

- **Minimum viable redesign** (Phases 1–4, 6): ~16–20h
- **With AuditStrip + week summary** (add Phase 5): ~22–28h
- **With server-side undo** (add Phase 7): ~28–36h

Most phases are independently shippable, so we can land Phase 1
(reskin) immediately, then layer the functional changes one by
one as time allows.

---

## What I'd hand to Sonnet first

Phases 1, 2, 3, 4, 6 in that order — each as its own focused
prompt. Phase 5 needs Brian + Supabase MCP for the schema and
view definitions; component work after that can hand off.

Each prompt should:
- Reference this doc
- Include the relevant screenshot(s)
- Point at existing components in the repo (don't re-create)
- Specify the dark-mode CSS strategy for that phase
- Note the auth gating (editor required for writes; viewers see
  the redesigned UI but can't actually mutate)
