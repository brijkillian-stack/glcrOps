# PencilCanvas — Phase K.1 component spec

Single source of truth for the reusable Apple Pencil canvas component used
by K.2 (floor-map annotation), K.3 (sign-on-glass), K.5 (deployment book
annotation), and K.6 (handwritten TM comments). Implementer should treat
this as the contract; behaviors not specified here can be decided locally
but flagged in the implementation handoff.

## 1. Purpose

A reusable Reflex component that renders a transparent HTML canvas overlay
on top of arbitrary content (image / HTML / SVG), captures Pointer Events
with Apple Pencil 2 first-class support, and saves the resulting drawing
to Supabase Storage via the helpers in `shared/storage.py`.

The component must work with finger input AND Pencil input AND mouse
input. It must distinguish between them and offer different affordances
(`pencil_only` mode rejects finger; hover-preview only fires for Pencil 2).

## 2. File layout

```
shared/components/pencil_canvas.py        ← Reflex component (Python)
shared/components/pencil_canvas.js        ← canvas+pointer-events logic (browser JS)
shared/styles/pencil_canvas.css           ← scoped styles (toolbar, cursor)
```

The CSS belongs in `shared/styles/pencil_canvas.css` and is imported by
the main stylesheet via `@import` so it lives next to the component, not
buried in the 3,400-line global stylesheet.

## 3. API surface

```python
def pencil_canvas(
    *,
    canvas_id: str,                                    # unique per page; identifies events
    width: int = 1024,                                 # canvas pixel width
    height: int = 768,                                 # canvas pixel height
    on_save,                                           # rx.EventHandler — receives (image_data_b64, metadata_dict)
    on_clear=None,                                     # optional event handler when user clears
    background_image_url: str | None = None,           # signed URL (use get_signed_url)
    background_overlay_svg: str | None = None,         # raw SVG markup overlaid on background, under canvas
    tools: list[str] | None = None,                    # subset of ['pen','highlighter','eraser']; default all
    default_tool: str = "pen",
    pencil_only: bool = False,                         # ignore non-pen Pointer Events
    show_save_button: bool = True,                     # caller may handle save externally
    show_clear_button: bool = True,
    initial_layers: list[dict] | None = None,          # [{url, opacity, label}, ...] prior annotations
    aspect_ratio_lock: bool = True,                    # CSS-scale to fit container, preserve ratio
    dual_layer_mode: bool = False,                     # K.4 only — see note below
) -> rx.Component:
    """Reusable Pencil canvas. See docs/pencil_canvas_spec.md."""
```

### `dual_layer_mode` — forward-looking K.4 hook (OK to skip in K.1)

K.4 (the schedule annotation page) needs to render TWO synchronized
panes: the free-form canvas (this component) AND a structured-overrides
pane alongside it that maps to specific cells in a TM × Day grid. When
`dual_layer_mode=True`, the component reserves space for an external
overrides pane and emits cell-coordinate events as the user taps grid
cells with finger or Pencil — but does NOT itself render the overrides
pane (that's K.4's responsibility).

For K.1 the implementer can land `dual_layer_mode` as a no-op accepted
prop (the canvas behaves identically whether the flag is true or false).
The actual cell-event emission and pane coordination wires up in K.4.
Document the prop in the API table; smoke tests don't need to exercise
it.

Component returns a `rx.html`-based block. The Python wrapper is thin —
its job is to embed the canvas+JS+CSS, expose state knobs, and fire
`on_save` when the JS tells it to.

## 4. Architecture — Reflex × JS bridge

Reflex doesn't give us a clean way to run rich JS inside a component, so
the implementation pattern is:

1. The Python component renders `rx.html(...)` containing:
   - The canvas DOM (background `<img>`, optional `<svg>` overlay, `<canvas>`)
   - The toolbar DOM
   - A `<script>` tag that calls `window.PencilCanvas.init(canvas_id, config)`
2. The JS code in `pencil_canvas.js` is loaded once at app boot via
   `head_components` in `brijkillian_stack/brijkillian_stack.py`. It
   exposes `window.PencilCanvas` with `init(id, config)` and listens for
   pointer events on each canvas.
3. When the user clicks Save, JS calls `canvas.toBlob()` → reads as
   base64 data URL → posts to a Reflex backend event handler
   (`window._reflexDispatch` pattern, similar to how `⌘K`/`⌘N` are wired
   in `brijkillian_stack.py`). The backend handler is whatever was passed
   as `on_save`.
4. The backend handler receives `(image_data_b64, metadata_dict)` and
   typically calls `shared.storage.upload_annotation(...)` to persist.

## 5. Pointer Events spec — the load-bearing piece

```javascript
canvas.addEventListener('pointerdown', e => {
  if (config.pencilOnly && e.pointerType !== 'pen') return;
  // Pencil 2: e.pointerType === 'pen'
  // Finger:   e.pointerType === 'touch'
  // Mouse:    e.pointerType === 'mouse'
  startStroke({
    x: e.offsetX,
    y: e.offsetY,
    pressure: e.pressure || 0.5,        // 0..1; defaults for non-pressure devices
    tiltX: e.tiltX || 0,                // Pencil only
    tiltY: e.tiltY || 0,
    tool: state.currentTool,
    color: state.currentColor,
    strokeWidth: state.currentStrokeWidth,
  });
  canvas.setPointerCapture(e.pointerId);
});

canvas.addEventListener('pointermove', e => {
  if (e.buttons === 0 && e.pointerType === 'pen') {
    // Apple Pencil 2 hover (no contact yet)
    showHoverCursor(e.offsetX, e.offsetY);
    return;
  }
  if (state.activeStroke) extendStroke(e);
});

canvas.addEventListener('pointerup',     endStroke);
canvas.addEventListener('pointercancel', endStroke);
canvas.addEventListener('pointerleave',  hideHoverCursor);
```

Key constraints:
- Use `setPointerCapture` so a stroke that drags off the canvas finishes cleanly.
- Use `touch-action: none` on the canvas CSS to prevent iOS from interpreting
  drags as scrolls.
- Use `pointer-events: auto` on canvas, `pointer-events: none` on the
  background `<img>` and overlay `<svg>` so they don't intercept.
- Apple Pencil hover (Pencil 2 + iPad Pro M2 / Air M2): when
  `e.pointerType === 'pen' && e.buttons === 0`, render a small cursor at
  the projected tip location. This is the visual cue that distinguishes
  Pencil from finger.

## 6. Tool implementations

| Tool         | Stroke style                              | Pressure response          | Tilt response |
|--------------|-------------------------------------------|----------------------------|---------------|
| `pen`        | Black ink, opaque, line cap round         | width = 0.5 + pressure*3   | ignored       |
| `highlighter`| Yellow @ 50% opacity, square cap          | width = 6 + pressure*4     | ignored       |
| `eraser`     | `globalCompositeOperation = 'destination-out'`, line cap round | width = 8 + pressure*8 | ignored |
| `signature`  | Same as pen but `pencil_only` forced true and no eraser/highlighter in toolbar | as pen | ignored |

Notes:
- Highlighter overlapping itself should NOT darken — implement by
  drawing the entire stroke into an offscreen canvas at full opacity,
  then compositing onto the main canvas at 0.5 alpha at stroke end.
- Eraser does NOT clear background image — only the drawing layer.
- Tilt is captured in the saved metadata but not used for rendering in v1.

## 7. Toolbar UI

A floating toolbar anchored top-right of the canvas (default) or
bottom-center (responsive on iPhone, though K.1 is iPad-first). The
toolbar must:

- Show only the tools listed in `tools` (caller controls).
- Highlight the active tool with a brand-blue ring (token `--accent-blue`).
- Provide 3 stroke-width presets (thin / medium / thick), shown as
  visual dot sizes, not labels.
- Provide 5 colors for pen mode: black, blue, red, green, gold (use the
  brand tokens — `--fg-1`, `--accent-blue`, `--accent-flag`,
  `--accent-positive`, `--accent-gold`). Highlighter is fixed yellow.
- Show Clear button only if `show_clear_button = true`. Confirm before
  clearing if there are existing strokes.
- Show Save button only if `show_save_button = true`. Disable save
  while a stroke is in progress.
- Touch targets minimum 44×44pt per HIG.

The toolbar uses `pointer-events: auto` and sits absolutely positioned
above the canvas. Pencil hovering over a toolbar button shows the
hover-preview cursor on the button (visual only).

## 8. Save flow

1. User clicks Save (or external code calls a JS save function).
2. JS calls `mainCanvas.toBlob(blob => ...)`.
3. JS calls `FileReader.readAsDataURL(blob)` to get a base64 data URL.
4. JS dispatches the data URL + metadata via Reflex event protocol:
   ```javascript
   window._reflexDispatch(`${stateName}.handle_pencil_save`, {
     canvas_id: config.canvasId,
     image_data: dataUrl,
     width: canvas.width,
     height: canvas.height,
     pen_settings: { tool, color, strokeWidth, pressureUsed: hadPressureSamples },
   });
   ```
5. The Python event handler receives this, decodes the base64 PNG, and
   calls `shared.storage.upload_annotation(image_data=png_bytes, ...)`.
6. The handler updates Reflex state (e.g. `last_saved_id`, `save_status`)
   so the UI can show a confirmation toast.

The handler is provided by the page that uses the component — the
component itself is agnostic to which target_type/target_id the
annotation attaches to.

## 9. Layer rendering (replay mode)

When `initial_layers` is provided, the component renders prior
annotations as transparent images stacked between the background and
the active drawing canvas. Each layer:

```python
{
  "url": "<signed url>",          # via get_signed_url
  "opacity": 0.5,                  # 0..1
  "label": "Tonight's marks",     # for the layer-toggle UI
  "id": "<annotation row id>",   # for keying
}
```

A small layer-list UI in the toolbar lets the user toggle each layer
on/off. Toggling does not affect the active drawing layer.

## 10. Accessibility + responsiveness

- Respect `@media (prefers-reduced-motion: reduce)` — toolbar transitions
  use `animation` only outside reduce-motion.
- Respect `@media (hover: hover)` — the Pencil-hover cursor only renders
  when the host device has hover capability (Pencil 2, Magic Trackpad,
  mouse). On finger-only devices, no hover cursor.
- Canvas CSS `width: 100%; max-width: <prop width>px; aspect-ratio: <w>/<h>`
  scales to container while preserving the internal pixel resolution.
- iPad split-view at narrow widths: toolbar relocates to bottom edge.

## 11. Reflex backend event handler shape (reference)

Pages embedding this component should provide a state class with:

```python
class FloorMapState(rx.State):
    last_saved_annotation_id: str = ""
    save_status: str = ""

    def handle_pencil_save(self, payload: dict):
        import base64, io
        b64 = payload["image_data"].split(",", 1)[1]
        png_bytes = base64.b64decode(b64)
        from shared.storage import upload_annotation
        result = upload_annotation(
            image_data=png_bytes,
            kind="floor_map",
            target_type="night",
            target_id=self.current_night_id,   # state-specific
            author=AuthState.user_email,
            pen_settings=payload.get("pen_settings", {}),
            width=payload.get("width"),
            height=payload.get("height"),
        )
        self.last_saved_annotation_id = result["id"]
        self.save_status = "saved"
        return rx.toast.success("Annotation saved")
```

## 12. Smoke tests (bare minimum the implementer must verify)

1. Floor map renders behind canvas via signed URL — image fully visible.
2. Pen drawing on iPad with finger AND with Pencil — both work unless
   `pencil_only=true`, in which case only Pencil registers.
3. Pressure varies stroke width visibly when drawing with Pencil.
4. Apple Pencil 2 hover — cursor follows pencil tip without contact.
5. Toolbar tool switching — pen → highlighter → eraser, all behave per
   spec table.
6. Save → annotation uploaded to bucket, row inserted in
   `public.annotations`, `signed_url` returned in the row.
7. `initial_layers` — prior PNG renders below active canvas with toggle.
8. Reduce Motion preference disables toolbar transitions.

## 13. Out of scope for K.1

These belong to later K phases (note: ZDS-first reordering, see project log):

- The actual ZDS deployment-grid integration (K.2 composes this
  component over `apps/zds/pages/deployment.py`).
- The week-overview integration (K.3, similar pattern over
  `apps/zds/pages/week_overview.py`).
- The schedule-annotation page + structured overrides + engine
  consumption (K.4 — uses `dual_layer_mode` flag from this spec).
- Floor-map annotation (K.6, deferred).
- Sign-on-glass for write-ups + PDF embed (K.7, deferred).
- Forward-check / Memory integration (annotations are linked, not yet
  triggering downstream events).
- Multi-user real-time collaboration (single author per drawing for now).
- Vector / SVG export (raster PNG is enough for v1).
- Pencil-driven swap gesture (drag-from-slot-to-slot — separate phase K.9).

## 14. Open questions for Brian

1. Default save behavior on the floor map: should saving create a new
   annotation row each time, or update a single "tonight's marks" row?
   — Recommendation: new row each time (immutable history), but with a
   `<canvas-id>-current` view that shows the latest in K.2.
2. Highlighter color: yellow or the GLCR brand gold? — Recommendation:
   yellow for visibility on the dark casino floor map; gold for
   on-document use (write-ups, deployment book).
3. Should canvas state persist across page navigations within a session
   (so accidentally swiping away doesn't lose the drawing)? —
   Recommendation: not in K.1; revisit if it becomes a real loss.
