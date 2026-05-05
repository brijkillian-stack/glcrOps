# K.5 — Pencil hover affordances on slot cards (spec)

Independent of K.1's PencilCanvas component. K.5 is pure CSS + Pointer
Events on existing DOM (the zone_card components). Adds an iPad-with-
Pencil-2-only hover-preview pattern that desktop literally can't do —
the kind of detail that makes the iPad feel like a first-class surface,
not a phone-with-bigger-screen.

## 1. Why

Apple Pencil 2, on supported iPads (iPad Pro M2, iPad Air M2), reports
hover events when the tip is within ~12mm of the screen but not yet in
contact. This is exposed via standard Pointer Events — `pointerover`
fires with `pointerType==='pen'` and `buttons===0`.

The product opportunity: on the deployment grid, Brian can hover the
Pencil over any slot card and see a contextual preview — the assigned
TM, their last 7 placements, eligibility status, fatigue index — without
committing to a tap. That preview disappears when the Pencil moves
away. It's the iPad's equivalent of macOS hover tooltips.

Magic Trackpad cursor on iPad gets the same affordance for free, since
both surface as "hover" in the Pointer Events model. Finger touch does
NOT — finger has no hover state.

## 2. Where this lives

```
shared/components/hover_preview.py   ← new component (small)
shared/styles/hover_preview.css      ← scoped styles
apps/zds/components/zone_card.py     ← edits to attach hover handlers
```

Plus a tiny addition to the JS that already runs at app boot — register
a delegated `pointerover` / `pointerleave` listener on the document so
each zone card doesn't need its own JS attachment.

## 3. Detection — exactly what counts as "hover"

```javascript
function isPencilHover(e) {
  return e.pointerType === 'pen' && e.buttons === 0;
}
function isPointerHover(e) {
  // Magic Trackpad / mouse / Pencil-with-no-contact all qualify
  return (e.pointerType === 'mouse' || isPencilHover(e));
}
```

Critical: do not respond to `pointerType === 'touch'` for hover. Finger
hover doesn't exist; what looks like hover on touch is a stuck pointer
state from the last tap.

## 4. CSS gating — finger-only devices get no hover behavior

```css
@media (hover: hover) {
  .zone-card.hoverable { /* visual hover state */ }
  .hover-preview-popover { /* preview tooltip styles */ }
}

/* Finger-only iPads (older models without hover-capable input) and
   iPhones get nothing — no styles, no listeners attached. */
```

`(hover: hover)` is true when the primary input has hover capability:
mouse, trackpad, Pencil-on-supported-hardware. False on phones and
older iPads. This gates ALL the hover styling so finger-only users
don't see broken-feeling sticky hover states from accidental taps.

## 5. The preview popover

When `pointerover` fires on a zone card, render a popover anchored to
the card. The popover shows:

```
┌────────────────────────────────────┐
│  Joy             Z3 · Fri 5/8     │
│  ────────────────────────────────  │
│  Skill 8.0 · Active                │
│  Fatigue 14 / 28 (moderate)        │
│  ────────────────────────────────  │
│  Last 7 nights:                    │
│   Thu  Z3                          │
│   Wed  Z6                          │
│   Tue  off                         │
│   Mon  Z9                          │
│   Sun  Z3   ← repetition           │
│   Sat  off                         │
│   Fri  Z2                          │
│  ────────────────────────────────  │
│  Eligible for: Z1-7, MRR1, WRR1    │
└────────────────────────────────────┘
```

Sized ~280×220pt. Anchored top-right of the card by default; flips to
top-left when the card is near the right edge. Pencil hover OVER the
popover keeps it open; moving away hides after 200ms (so brief
intermediate motions don't dismiss it).

The popover is read-only — no interactive controls inside. If you want
to act on what you see, you tap the card (which is the existing slot
edit flow).

## 6. Data fetching — keep it cheap

Each preview needs:
- The card's current TM (already in zone_card props)
- TM's recent placements (last 7 days from `zone_assignments` joined
  with `nights`)
- TM's fatigue index (computed from load scores × recent placements)
- TM's eligibility flags (from `tm_eligibility`)

Naive implementation queries on every hover. Don't do that. Two
mitigations:

1. **Pre-fetch on page load.** When the deployment grid loads, also
   load `hover_context` for every TM placed on the night — one bulk
   query, indexed in state, hover just reads from memory.
2. **Debounce.** Even if data is in memory, debounce the popover-show
   by 150ms so quickly-passing-over hovers don't flash popovers.

The pre-fetch shape:

```python
class DeploymentState(rx.State):
    hover_context_by_tm: dict[str, dict] = {}   # tm_id → preview dict

    def load_hover_context(self):
        # One bulk query covers every TM on this night
        tm_ids = [a.tm_id for a in self.assignments if a.tm_id]
        ...  # join zone_assignments + nights + tm_eligibility
        self.hover_context_by_tm = result_dict
```

## 7. Pencil-specific affordance — slight visual difference vs. trackpad

When the hover source is Pencil, render the hover cursor as a small
orange-ish dot that follows the pencil tip (matching the K.1 pattern).
When it's trackpad/mouse, the system cursor is enough. Distinguish via
`pointerType`:

```javascript
if (e.pointerType === 'pen') {
  showPencilCursor(e.clientX, e.clientY);
} else {
  hidePencilCursor();
}
```

This makes Pencil hover *feel* different from trackpad hover — same
information, but the user sees a tip-tracking cursor that confirms
the iPad knows the Pencil is there. Tiny detail; pays back in
trust.

## 8. Pencil 2 side double-tap (optional)

Apple Pencil 2 has a side double-tap gesture (capacitive squeeze)
exposed through `pointerrawupdate` or `'pointerdown'` with specific
button mask. On supported devices, double-tap-while-hovering can
toggle a "pinned preview" — the popover stays open until the next
double-tap, so Brian can move the Pencil away and still read the
preview.

Implementation is minor (~20 lines) but device support is fragile
across Safari versions. Land as v2 of K.5 if it's flaky in testing.

## 9. Smoke tests (3, not 8 — this is a small feature)

1. Hover the Pencil over a slot on iPad Pro M2 → popover appears with
   correct TM context within 200ms.
2. Move Pencil away → popover hides within 200ms.
3. Tap with finger (no hover) → no popover, normal slot-edit flow runs.

Plus one negative test:

4. Open the deployment grid on iPhone (no hover capability) → no
   popovers ever render, no broken hover styles.

## 10. Out of scope for K.5

- Hover on the floor map view (that's K.6).
- Hover on the schedule review grid (that's K.4).
- Pinned previews via Pencil double-tap (defer to K.5.1 if useful).
- Hover state on the week-overview page (extend if it earns its keep).

## 11. Estimated implementation time

```
~1.5 hr Sonnet time, total:
  CSS gating + popover styles                     30 min
  Pointer Events listeners + pencil cursor         45 min
  Pre-fetch hover_context_by_tm in state           20 min
  Wire into zone_card.py + smoke test              25 min
```

K.5 is independent of K.1, K.2, K.3, K.4 — can ship in any session
with no upstream dependencies.
