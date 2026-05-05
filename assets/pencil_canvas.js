/**
 * pencil_canvas.js — Phase K.1
 * Apple Pencil 2 first-class canvas for the GLCR Ops Webapp.
 *
 * Loaded once at app boot via head_components; exposes window.PencilCanvas.
 * Auto-initializes via MutationObserver when a <script type="application/json">
 * config data-island with id="pc-config-{canvasId}" appears in the DOM.
 *
 * Tools: pen, highlighter (no-darken offscreen trick), eraser (drawing layer only).
 * Pointer Events: pen / touch / mouse; pencil_only mode; Pencil 2 hover cursor.
 * Save: base64 PNG + metadata → window._reflexDispatch → Python handler.
 *
 * Spec: docs/pencil_canvas_spec.md
 */

(function () {
  "use strict";

  // ── Per-canvas instance registry ──────────────────────────────────────────
  const _instances = {};

  // ── Tool definitions (spec §6) ────────────────────────────────────────────
  // highlighter width multiplier is applied to the offscreen canvas stroke;
  // eraser uses destination-out on the drawing layer only (not the bg img).
  const TOOLS = {
    pen: {
      emoji: "✒️",
      label: "Pen",
      lineCap: "round",
      lineJoin: "round",
      composite: "source-over",
      alpha: 1.0,
      /** @param {number} pressure 0..1  @param {number} sw stroke-width preset multiplier */
      getWidth(pressure, sw) { return sw * (0.5 + pressure * 3); },
    },
    highlighter: {
      emoji: "🖊",
      label: "Highlighter",
      lineCap: "square",
      lineJoin: "round",
      composite: "source-over",
      alpha: 1.0,          // drawn full-opacity on offscreen; composited at 0.5 at stroke end
      getWidth(pressure, sw) { return sw * (6 + pressure * 4); },
    },
    eraser: {
      emoji: "⬜",
      label: "Eraser",
      lineCap: "round",
      lineJoin: "round",
      composite: "destination-out",
      alpha: 1.0,
      getWidth(pressure) { return 8 + pressure * 8; },
    },
  };

  // Pen colors — spec §7: black, blue, red, green, gold (brand tokens)
  const PEN_COLORS = [
    { name: "black", value: "#1A1A1A" },   // --fg-1
    { name: "blue",  value: "#0065BF" },   // --accent-blue
    { name: "red",   value: "#B91C1C" },   // --accent-flag
    { name: "green", value: "#16A34A" },   // --accent-positive
    { name: "gold",  value: "#C8A77F" },   // --accent-gold
  ];

  // Stroke-width presets: { label, dotSize (px), multiplier }
  const STROKE_WIDTHS = [
    { label: "thin",   dotSize: 6,  mult: 1 },
    { label: "medium", dotSize: 10, mult: 2 },
    { label: "thick",  dotSize: 16, mult: 3 },
  ];

  // ── Tiny DOM helper ──────────────────────────────────────────────────────
  function el(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (k === "style" && typeof v === "object") {
          Object.assign(e.style, v);
        } else {
          e.setAttribute(k, v);
        }
      }
    }
    for (const k of kids) {
      if (k == null) continue;
      if (typeof k === "string") e.appendChild(document.createTextNode(k));
      else e.appendChild(k);
    }
    return e;
  }

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  // ── Coordinate scaling ────────────────────────────────────────────────────
  // Canvas CSS display size ≠ pixel size. offsetX/offsetY are CSS pixels;
  // we must scale to canvas pixel coordinates for drawing.
  function _scale(inst, e) {
    const cx = inst.canvas.clientWidth  || inst.canvas.width;
    const cy = inst.canvas.clientHeight || inst.canvas.height;
    return {
      x: e.offsetX * (inst.canvas.width  / cx),
      y: e.offsetY * (inst.canvas.height / cy),
    };
  }

  // ── Drawing ───────────────────────────────────────────────────────────────

  function _startStroke(inst, e) {
    const s = inst.state;
    s.activeStroke = true;
    s.strokePoints = [];
    const p = clamp(e.pressure === 0.5 ? 0.5 : (e.pressure || 0.5), 0, 1);
    if (e.pressure !== 0.5 && e.pressure !== undefined) s.hadPressureSamples = true;
    const { x, y } = _scale(inst, e);
    const td = TOOLS[s.currentTool];

    if (s.currentTool === "highlighter") {
      // Draw at full opacity onto the offscreen canvas; composite later.
      inst.offCtx.clearRect(0, 0, inst.offCanvas.width, inst.offCanvas.height);
      inst.offCtx.globalCompositeOperation = "source-over";
      inst.offCtx.globalAlpha = 1.0;
      inst.offCtx.lineCap = td.lineCap;
      inst.offCtx.lineJoin = td.lineJoin;
      inst.offCtx.strokeStyle = "#FFFF00";   // yellow default (spec §14 Q2)
      inst.offCtx.lineWidth = td.getWidth(p, s.currentWidthMult);
      inst.offCtx.beginPath();
      inst.offCtx.moveTo(x, y);
    } else {
      const ctx = inst.ctx;
      ctx.globalCompositeOperation = td.composite;
      ctx.globalAlpha = td.alpha;
      ctx.lineCap = td.lineCap;
      ctx.lineJoin = td.lineJoin;
      ctx.strokeStyle = s.currentTool === "eraser" ? "rgba(0,0,0,1)" : s.currentColor;
      ctx.lineWidth = td.getWidth(p, s.currentWidthMult);
      ctx.beginPath();
      ctx.moveTo(x, y);
    }

    s.lastX = x;
    s.lastY = y;
    s.strokePoints.push({ x, y, pressure: p, tiltX: e.tiltX || 0, tiltY: e.tiltY || 0 });
  }

  function _extendStroke(inst, e) {
    const s = inst.state;
    if (!s.activeStroke) return;
    const p = clamp(e.pressure === 0.5 ? 0.5 : (e.pressure || 0.5), 0, 1);
    if (e.pressure !== 0.5 && e.pressure !== undefined) s.hadPressureSamples = true;
    const { x, y } = _scale(inst, e);
    const td = TOOLS[s.currentTool];

    if (s.currentTool === "highlighter") {
      inst.offCtx.lineWidth = td.getWidth(p, s.currentWidthMult);
      inst.offCtx.lineTo(x, y);
      inst.offCtx.stroke();
      inst.offCtx.beginPath();
      inst.offCtx.moveTo(x, y);
    } else {
      const ctx = inst.ctx;
      ctx.lineWidth = td.getWidth(p, s.currentWidthMult);
      ctx.lineTo(x, y);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(x, y);
    }

    s.lastX = x;
    s.lastY = y;
    s.strokePoints.push({ x, y, pressure: p, tiltX: e.tiltX || 0, tiltY: e.tiltY || 0 });
  }

  function _endStroke(inst) {
    const s = inst.state;
    if (!s.activeStroke) return;
    s.activeStroke = false;

    if (s.currentTool === "highlighter") {
      // Composite offscreen at 50% alpha — prevents strokes darkening on overlap (spec §6)
      inst.ctx.save();
      inst.ctx.globalAlpha = 0.5;
      inst.ctx.globalCompositeOperation = "source-over";
      inst.ctx.drawImage(inst.offCanvas, 0, 0);
      inst.ctx.restore();
    } else {
      // Reset ctx state for next stroke
      inst.ctx.globalAlpha = 1.0;
      inst.ctx.globalCompositeOperation = "source-over";
    }

    s.strokeCount++;
    s.strokePoints = [];
    _updateSaveBtn(inst);
  }

  // ── Hover cursor (Pencil 2) ───────────────────────────────────────────────

  function _showHover(inst, e) {
    const cursor = inst.hoverCursor;
    if (!cursor) return;
    // offsetX/offsetY are relative to canvas CSS size — correct for CSS overlay positioning
    cursor.style.left = e.offsetX + "px";
    cursor.style.top  = e.offsetY + "px";
    cursor.classList.add("visible");
  }

  function _hideHover(inst) {
    if (inst.hoverCursor) inst.hoverCursor.classList.remove("visible");
  }

  // ── Toolbar state sync ───────────────────────────────────────────────────

  function _updateToolBtns(inst) {
    const s = inst.state;
    inst.wrapper.querySelectorAll(".pencil-tool-btn[data-tool]").forEach(btn => {
      const active = btn.dataset.tool === s.currentTool;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-pressed", String(active));
    });
    // Color palette: only visible for pen
    const colorRow = inst.wrapper.querySelector(".pencil-colors-row");
    if (colorRow) colorRow.style.display = s.currentTool === "pen" ? "" : "none";
  }

  function _updateColorSwatches(inst) {
    inst.wrapper.querySelectorAll(".pencil-color-swatch").forEach(sw => {
      sw.classList.toggle("active", sw.dataset.color === inst.state.currentColor);
    });
  }

  function _updateWidthDots(inst) {
    inst.wrapper.querySelectorAll(".pencil-width-dot").forEach(d => {
      d.classList.toggle("active", Number(d.dataset.widthMult) === inst.state.currentWidthMult);
    });
  }

  function _updateSaveBtn(inst) {
    const btn = inst.wrapper.querySelector(".pencil-save-btn");
    if (!btn) return;
    btn.disabled = inst.state.activeStroke || inst.state.strokeCount === 0;
  }

  function _updateLayerVisibility(inst) {
    inst.layerEls.forEach((imgEl, i) => {
      imgEl.style.display = inst.state.layerVisible[i] !== false ? "" : "none";
    });
  }

  // ── Save (spec §8) ────────────────────────────────────────────────────────

  function _doSave(inst) {
    if (inst.state.activeStroke) return;
    const cfg = inst.config;
    const s   = inst.state;
    inst.canvas.toBlob(blob => {
      if (!blob) return;
      const fr = new FileReader();
      fr.onloadend = () => {
        const payload = {
          payload: {
            canvas_id:  cfg.canvasId,
            image_data: fr.result,          // data:image/png;base64,…
            width:       inst.canvas.width,
            height:      inst.canvas.height,
            pen_settings: {
              tool:          s.currentTool,
              color:         s.currentColor,
              strokeWidth:   s.currentWidthMult,
              pressureUsed:  s.hadPressureSamples,
            },
          },
        };
        if (window._reflexDispatch) {
          window._reflexDispatch(cfg.onSaveHandler, payload);
        } else {
          console.warn("[PencilCanvas] _reflexDispatch not available — cannot save");
        }
      };
      fr.readAsDataURL(blob);
    }, "image/png");
  }

  // ── Build toolbar ─────────────────────────────────────────────────────────

  function _buildToolbar(inst) {
    const cfg = inst.config;
    const s   = inst.state;

    const bar = el("div", {
      class: "pencil-toolbar",
      role: "toolbar",
      "aria-label": "Drawing tools",
    });

    // ─ Tool buttons ─
    if (cfg.tools.length > 0) {
      const grp = el("div", { class: "pencil-toolbar-group" });
      for (const toolName of cfg.tools) {
        const td = TOOLS[toolName];
        if (!td) continue;
        const btn = el("button", {
          class: "pencil-tool-btn" + (toolName === s.currentTool ? " active" : ""),
          "data-tool": toolName,
          type: "button",
          title: td.label,
          "aria-label": td.label,
          "aria-pressed": String(toolName === s.currentTool),
        }, td.emoji);
        btn.addEventListener("click", () => {
          s.currentTool = toolName;
          _updateToolBtns(inst);
        });
        grp.appendChild(btn);
      }
      bar.appendChild(grp);
    }

    // ─ Color palette (pen only) ─
    if (cfg.tools.includes("pen")) {
      bar.appendChild(el("div", { class: "pencil-toolbar-divider" }));
      const row = el("div", {
        class: "pencil-colors-row",
        style: { display: s.currentTool === "pen" ? "" : "none" },
      });
      for (const c of PEN_COLORS) {
        const sw = el("div", {
          class: "pencil-color-swatch" + (c.value === s.currentColor ? " active" : ""),
          "data-color": c.value,
          title: c.name,
          role: "radio",
          "aria-label": c.name,
          tabindex: "0",
          style: { background: c.value },
        });
        const pick = () => { s.currentColor = c.value; _updateColorSwatches(inst); };
        sw.addEventListener("click", pick);
        sw.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
        row.appendChild(sw);
      }
      bar.appendChild(row);
    }

    // ─ Stroke-width dots ─
    bar.appendChild(el("div", { class: "pencil-toolbar-divider" }));
    const wRow = el("div", { class: "pencil-widths-row" });
    for (const w of STROKE_WIDTHS) {
      const dot = el("div", {
        class: "pencil-width-dot" + (w.mult === s.currentWidthMult ? " active" : ""),
        "data-width-mult": String(w.mult),
        title: w.label + " stroke",
        role: "radio",
        "aria-label": w.label + " stroke width",
        tabindex: "0",
        style: { width: w.dotSize + "px", height: w.dotSize + "px" },
      });
      const pick = () => { s.currentWidthMult = w.mult; _updateWidthDots(inst); };
      dot.addEventListener("click", pick);
      dot.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
      wRow.appendChild(dot);
    }
    bar.appendChild(wRow);

    // ─ Layer toggles ─
    if (cfg.initialLayers && cfg.initialLayers.length > 0) {
      bar.appendChild(el("div", { class: "pencil-toolbar-divider" }));
      const list = el("div", { class: "pencil-layer-list" });
      cfg.initialLayers.forEach((layer, i) => {
        const lbl = el("label", {
          class: "pencil-layer-toggle",
          title: layer.label || ("Layer " + (i + 1)),
        });
        const cb = el("input", { type: "checkbox" });
        cb.checked = true;
        cb.addEventListener("change", () => {
          s.layerVisible[i] = cb.checked;
          _updateLayerVisibility(inst);
        });
        lbl.appendChild(cb);
        lbl.appendChild(document.createTextNode(
          (layer.label || ("Layer " + (i + 1))).slice(0, 18)
        ));
        list.appendChild(lbl);
      });
      bar.appendChild(list);
    }

    // ─ Action buttons (Clear / Save) ─
    bar.appendChild(el("div", { class: "pencil-toolbar-divider" }));
    const actGrp = el("div", { class: "pencil-toolbar-group" });

    if (cfg.showClearButton) {
      const clearBtn = el("button", {
        class: "pencil-action-btn pencil-clear-btn",
        type: "button",
        title: "Clear drawing",
        "aria-label": "Clear drawing",
      }, "🗑");
      clearBtn.addEventListener("click", () => {
        if (s.strokeCount === 0) return;
        if (window.confirm("Clear the drawing? This cannot be undone.")) {
          _doClear(inst);
        }
      });
      actGrp.appendChild(clearBtn);
    }

    if (cfg.showSaveButton) {
      const saveBtn = el("button", {
        class: "pencil-action-btn pencil-save-btn",
        type: "button",
        title: "Save annotation",
        "aria-label": "Save annotation",
      }, "💾");
      saveBtn.disabled = true;   // enabled after first stroke
      saveBtn.addEventListener("click", () => {
        if (!saveBtn.disabled) _doSave(inst);
      });
      actGrp.appendChild(saveBtn);
    }

    bar.appendChild(actGrp);
    return bar;
  }

  // ── Clear ─────────────────────────────────────────────────────────────────

  function _doClear(inst) {
    inst.ctx.clearRect(0, 0, inst.canvas.width, inst.canvas.height);
    inst.state.strokeCount = 0;
    inst.state.hadPressureSamples = false;
    _updateSaveBtn(inst);
    const cfg = inst.config;
    if (cfg.onClearHandler && window._reflexDispatch) {
      window._reflexDispatch(cfg.onClearHandler, { canvas_id: cfg.canvasId });
    }
  }

  // ── Public clear / save (for external callers) ────────────────────────────

  function save(canvasId)  { const i = _instances[canvasId]; if (i) _doSave(i); }
  function clear(canvasId) { const i = _instances[canvasId]; if (i) _doClear(i); }

  // ── Core init ─────────────────────────────────────────────────────────────

  function init(canvasId, config) {
    // Re-init check: if old instance exists but its wrapper is gone, clear it.
    if (_instances[canvasId]) {
      const oldW = document.getElementById("pc-wrapper-" + canvasId);
      if (oldW && oldW.dataset.pencilInited === "1") return;  // still live
      delete _instances[canvasId];
    }

    const wrapper = document.getElementById("pc-wrapper-" + canvasId);
    if (!wrapper) return;

    const canvas = wrapper.querySelector(".pencil-canvas-draw");
    if (!canvas) return;

    // Mark as initialized so MutationObserver doesn't re-fire.
    wrapper.dataset.pencilInited = "1";

    const ctx      = canvas.getContext("2d");
    const offCanvas = document.createElement("canvas");
    offCanvas.width  = canvas.width;
    offCanvas.height = canvas.height;
    const offCtx = offCanvas.getContext("2d");

    const hoverCursor = wrapper.querySelector(".pencil-hover-cursor");
    const layerEls    = Array.from(wrapper.querySelectorAll(".pencil-canvas-layer-img"));

    const state = {
      currentTool:      config.defaultTool || "pen",
      currentColor:     PEN_COLORS[0].value,   // black
      currentWidthMult: STROKE_WIDTHS[1].mult,  // medium
      activeStroke:     false,
      strokeCount:      0,
      hadPressureSamples: false,
      strokePoints:     [],
      lastX: 0, lastY: 0,
      layerVisible:     (config.initialLayers || []).map(() => true),
    };

    const inst = { config, state, canvas, ctx, offCanvas, offCtx, hoverCursor, layerEls, wrapper };
    _instances[canvasId] = inst;

    // Append toolbar (built entirely in JS — Python wrapper is thin)
    const toolbar = _buildToolbar(inst);
    wrapper.appendChild(toolbar);

    // ── Pointer Events (spec §5) ──────────────────────────────────────────

    canvas.addEventListener("pointerdown", e => {
      if (config.pencilOnly && e.pointerType !== "pen") return;
      canvas.setPointerCapture(e.pointerId);   // keep stroke alive off-canvas
      _hideHover(inst);
      _startStroke(inst, e);
      _updateSaveBtn(inst);
    });

    canvas.addEventListener("pointermove", e => {
      // Apple Pencil 2 hover: pointerType==='pen' && buttons===0 (no contact)
      if (e.pointerType === "pen" && e.buttons === 0) {
        _showHover(inst, e);
        return;
      }
      _hideHover(inst);
      if (state.activeStroke) _extendStroke(inst, e);
    });

    canvas.addEventListener("pointerup",     () => _endStroke(inst));
    canvas.addEventListener("pointercancel", () => _endStroke(inst));
    canvas.addEventListener("pointerleave",  () => _hideHover(inst));

    // Initial UI sync
    _updateToolBtns(inst);
    _updateColorSwatches(inst);
    _updateWidthDots(inst);
  }

  // ── Auto-init via data-island config ──────────────────────────────────────
  // The Reflex component renders a <script type="application/json" id="pc-config-{id}">
  // element containing the config JSON. This function scans for uninitialized
  // config islands and calls init() for each.

  function _autoInit() {
    document.querySelectorAll('script[type="application/json"][id^="pc-config-"]').forEach(configEl => {
      const canvasId = configEl.id.replace("pc-config-", "");
      const wrapper  = document.getElementById("pc-wrapper-" + canvasId);
      if (!wrapper) return;
      if (wrapper.dataset.pencilInited === "1") return;   // already running
      try {
        const config = JSON.parse(configEl.textContent);
        init(canvasId, config);
      } catch (err) {
        console.error("[PencilCanvas] config parse error for", canvasId, err);
      }
    });
  }

  // Run immediately in case HTML is already painted (non-SPA entry or SSR)
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", _autoInit);
  } else {
    _autoInit();
  }

  // Watch for Reflex/React rendering new canvas components dynamically
  const _observer = new MutationObserver(_autoInit);
  _observer.observe(document.documentElement, { childList: true, subtree: true });

  // ── Public API ────────────────────────────────────────────────────────────
  window.PencilCanvas = {
    /**
     * Programmatically initialize a canvas (called by auto-init; also usable directly).
     * @param {string} canvasId - must match the canvas_id passed to pencil_canvas() in Python
     * @param {object} config - config object matching the pencil_canvas_spec.md §3 API
     */
    init,
    /**
     * Programmatically trigger a save for a canvas by ID.
     * Useful when show_save_button=False and the host page manages save externally.
     */
    save,
    /**
     * Programmatically clear a canvas by ID.
     */
    clear,
  };

})();
