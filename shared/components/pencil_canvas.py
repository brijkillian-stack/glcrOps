"""
shared/components/pencil_canvas.py — Phase K.1

Reusable Apple Pencil 2 canvas component for the GLCR Ops Webapp.

This is a thin Reflex wrapper that renders the DOM structure (background image,
SVG overlay, prior-annotation layers, drawing canvas, hover-cursor div, and a
JSON config data-island). All drawing logic and toolbar construction live in
assets/pencil_canvas.js, which is loaded once at app boot via head_components.

See docs/pencil_canvas_spec.md for the full API contract and architecture notes.

──────────────────────────────────────────────────────────────────────────────
USAGE EXAMPLE (in a Reflex page):

    from shared.components.pencil_canvas import pencil_canvas

    class FloorMapState(rx.State):
        floor_map_url: str = ""
        save_status: str = ""

        def on_load(self):
            from shared.storage import get_floor_map_url
            self.floor_map_url = get_floor_map_url()

        def handle_pencil_save(self, payload: dict):
            import base64
            from shared.storage import upload_annotation
            b64 = payload["image_data"].split(",", 1)[1]
            png_bytes = base64.b64decode(b64)
            result = upload_annotation(
                image_data=png_bytes,
                kind="floor_map",
                target_type="night",
                target_id="...",
                author="...",
                pen_settings=payload.get("pen_settings", {}),
                width=payload.get("width"),
                height=payload.get("height"),
            )
            self.save_status = "saved"
            return rx.toast.success("Annotation saved")

    def floor_map_page():
        return pencil_canvas(
            canvas_id="floor-map",
            width=1800,
            height=900,
            on_save="floor_map_state.handle_pencil_save",
            background_image_url=FloorMapState.floor_map_url,
        )

──────────────────────────────────────────────────────────────────────────────
SAVE HANDLER SIGNATURE (spec §11):

    The JS dispatches via:
        window._reflexDispatch(on_save, { payload: { canvas_id, image_data,
                                                     width, height, pen_settings } })
    Python receives:
        def handle_pencil_save(self, payload: dict): ...
    where payload["image_data"] is a data:image/png;base64,... URL.

DEVIATION FROM SPEC §3:
    on_save is typed str (the Reflex dispatch key, e.g. "floor_map_state.handle_pencil_save")
    rather than rx.EventHandler. This avoids introspecting Reflex internals to extract
    the dispatch string, which would be version-unstable. K.2/K.3/K.5/K.6 builders
    should follow the dispatch-key string convention.
"""

from __future__ import annotations

import json
from typing import Any

import reflex as rx


def pencil_canvas(
    *,
    canvas_id: str,
    width: int = 1024,
    height: int = 768,
    on_save: str,
    on_clear: str | None = None,
    background_image_url: Any = None,
    background_overlay_svg: str | None = None,
    tools: list[str] | None = None,
    default_tool: str = "pen",
    pencil_only: bool = False,
    show_save_button: bool = True,
    show_clear_button: bool = True,
    initial_layers: list[dict] | None = None,
    aspect_ratio_lock: bool = True,
    dual_layer_mode: bool = False,
) -> rx.Component:
    """Reusable Apple Pencil 2 canvas component.

    Args:
        canvas_id: Unique string per page; must be URL-safe (used in DOM ids).
        width: Canvas pixel width (internal resolution, not CSS size).
        height: Canvas pixel height.
        on_save: Reflex dispatch key for the save handler, e.g.
            "floor_map_state.handle_pencil_save". Handler receives
            ``(self, payload: dict)`` where payload contains canvas_id,
            image_data (data URL), width, height, pen_settings.
        on_clear: Optional Reflex dispatch key called when user clears canvas.
        background_image_url: Signed URL for background image (str or Var).
            Use shared.storage.get_signed_url() or get_floor_map_url().
        background_overlay_svg: Raw SVG markup overlaid above background,
            below drawing canvas. pointer-events: none — for zone outlines etc.
        tools: Subset of ['pen','highlighter','eraser']. Defaults to all three.
        default_tool: Which tool is active on mount. Default 'pen'.
        pencil_only: If True, only pointerType==='pen' events register strokes.
            Palm rejection for sign-on-glass use (K.3). Hover cursor still works.
        show_save_button: Include the 💾 button in the toolbar.
        show_clear_button: Include the 🗑 button in the toolbar.
        initial_layers: List of prior annotation dicts to render as image layers:
            [{"url": signed_url, "opacity": 0.5, "label": "Tonight's marks"}, ...]
            Each layer gets a toggle in the toolbar.
        aspect_ratio_lock: Apply CSS aspect-ratio so the wrapper auto-sizes height.
        dual_layer_mode: K.4 forward-hook (no-op in K.1). When K.4 implements
            the schedule_review page, it will pass True so the canvas reserves
            space for an external structured-overrides pane and emits cell-
            coordinate events. K.1's behavior is identical regardless of this
            flag — it's accepted here so the API surface is settled before K.4.

    Returns:
        rx.Component — the full canvas block with DOM + JS config data-island.

    See docs/pencil_canvas_spec.md for full architecture notes.
    """
    _tools  = tools or ["pen", "highlighter", "eraser"]
    _layers = initial_layers or []

    # ── JS config (serialised into the data-island <script type="application/json">) ──
    # Keys match what pencil_canvas.js expects in its init() call.
    config: dict[str, Any] = {
        "canvasId":       canvas_id,
        "onSaveHandler":  on_save,
        "onClearHandler": on_clear,
        "tools":          _tools,
        "defaultTool":    default_tool,
        "pencilOnly":     pencil_only,
        "showSaveButton": show_save_button,
        "showClearButton": show_clear_button,
        "initialLayers":  _layers,
        "dualLayerMode":  dual_layer_mode,   # K.4 forward hook; ignored by K.1 JS
    }
    # Guard against </script> in JSON values (safe for our config; belt-and-suspenders)
    config_json = json.dumps(config).replace("</", "<\\/")

    # ── Wrapper styles ──────────────────────────────────────────────────────
    wrapper_style: dict[str, Any] = {
        "position":          "relative",
        "display":           "block",
        "width":             "100%",
        "maxWidth":          f"{width}px",
        "lineHeight":        "0",
        "userSelect":        "none",
        "WebkitUserSelect":  "none",
    }
    if aspect_ratio_lock:
        wrapper_style["aspectRatio"] = f"{width} / {height}"

    # ── Build child elements ────────────────────────────────────────────────
    children: list[rx.Component] = []

    # 1. Background image (pointer-events: none so it doesn't intercept strokes)
    if background_image_url is not None:
        children.append(
            rx.el.img(
                src=background_image_url,
                class_name="pencil-canvas-bg",
                alt="Canvas background",
                draggable=False,
            )
        )

    # 2. SVG overlay (zone outlines, floor-plan labels, etc.)
    if background_overlay_svg:
        # rx.html renders raw HTML via dangerouslySetInnerHTML; <svg> is safe here.
        children.append(
            rx.html(
                f'<div class="pencil-canvas-svg-overlay" aria-hidden="true">'
                f'{background_overlay_svg}</div>'
            )
        )

    # 3. Prior annotation layers (rendered as semi-transparent images)
    for i, layer in enumerate(_layers):
        layer_url     = layer.get("url", "")
        layer_opacity = str(layer.get("opacity", 0.5))
        layer_label   = layer.get("label", f"Layer {i + 1}")
        children.append(
            rx.el.img(
                src=layer_url,
                class_name="pencil-canvas-layer-img",
                alt=layer_label,
                draggable=False,
                style={"opacity": layer_opacity},
            )
        )

    # 4. Drawing canvas — transparent overlay; all strokes go here.
    #    width/height set the pixel resolution; CSS width/height (via class) set display size.
    #    pencil_canvas.js scales pointer coordinates accordingly.
    children.append(
        rx.el.canvas(
            class_name="pencil-canvas-draw",
            width=str(width),
            height=str(height),
            aria_label="Drawing canvas",
            role="img",
        )
    )

    # 5. Hover cursor div — the Pencil 2 tip preview circle.
    #    Shown/hidden by JS on pointermove; gated to hover-capable devices via CSS media query.
    children.append(
        rx.el.div(
            class_name="pencil-hover-cursor",
            aria_hidden="true",
        )
    )

    # 6. JSON config data-island — read by pencil_canvas.js's MutationObserver.
    #    <script type="application/json"> is a pure data block; browsers don't execute it.
    #    This is the Reflex×React-compatible alternative to inline <script>...</script>
    #    (which React does not execute when injected via JSX rendering).
    children.append(
        rx.html(
            f'<script type="application/json" id="pc-config-{canvas_id}">'
            f'{config_json}'
            f'</script>'
        )
    )

    return rx.el.div(
        *children,
        id=f"pc-wrapper-{canvas_id}",
        class_name="pencil-canvas-wrapper",
        style=wrapper_style,
    )
