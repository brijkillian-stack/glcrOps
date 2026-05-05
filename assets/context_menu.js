/**
 * context_menu.js — global handler for right-click + long-press context menu
 *
 * Trigger pattern: any element with `class="ctx-menu-trigger"` and
 * `data-ctx-*` attributes describing the target opens the menu when:
 *   - desktop: right-click (contextmenu event)
 *   - touch:   sustained press for ~500ms
 *
 * Context attributes the JS reads from the trigger element:
 *   data-ctx-target-type   — 'tm' | 'slot' | 'assignment' | 'pool_tm' | 'picker_tm'
 *   data-ctx-target-id     — tm_id, slot_key, or composite
 *   data-ctx-target-label  — human-readable header for the menu
 *   data-ctx-surface       — 'deployment_grid' | 'schedule_tab' | etc.
 *   data-ctx-night-id      — for slot/assignment context
 *   data-ctx-slot-key      — for slot/assignment context
 *
 * Both right-click and long-press funnel into one Reflex dispatch:
 *   window._reflexDispatch('context_menu_state.open_at',
 *     { args: [x, y, target_type, target_id, target_label,
 *              surface, night_id, slot_key] })
 */

(function () {
  "use strict";

  const LONG_PRESS_MS = 500;
  const MOVE_TOLERANCE_PX = 8;

  // ── Helpers ───────────────────────────────────────────────────────────────

  function readContext(trigger) {
    const ds = trigger.dataset || {};
    return {
      target_type:  ds.ctxTargetType  || "",
      target_id:    ds.ctxTargetId    || "",
      target_label: ds.ctxTargetLabel || "",
      surface:      ds.ctxSurface     || "",
      night_id:     ds.ctxNightId     || "",
      slot_key:     ds.ctxSlotKey     || "",
    };
  }

  function dispatchOpen(x, y, ctx) {
    if (!window._reflexDispatch) return;
    window._reflexDispatch("context_menu_state.open_at", {
      args: [
        Math.round(x),
        Math.round(y),
        ctx.target_type,
        ctx.target_id,
        ctx.target_label,
        ctx.surface,
        ctx.night_id,
        ctx.slot_key,
      ],
    });
  }

  // ── Desktop: contextmenu event (right-click) ──────────────────────────────

  document.addEventListener("contextmenu", function (e) {
    const trigger = e.target && e.target.closest && e.target.closest(".ctx-menu-trigger");
    if (!trigger) return;
    e.preventDefault();
    dispatchOpen(e.clientX, e.clientY, readContext(trigger));
  });

  // ── Touch: long-press (~500ms hold) ───────────────────────────────────────

  let pressState = null;

  function startPress(e) {
    if (e.pointerType !== "touch" && e.pointerType !== "pen") return;
    const trigger = e.target && e.target.closest && e.target.closest(".ctx-menu-trigger");
    if (!trigger) return;
    cancelPress();
    pressState = {
      x: e.clientX,
      y: e.clientY,
      startX: e.clientX,
      startY: e.clientY,
      pointerId: e.pointerId,
      trigger: trigger,
      timer: setTimeout(function () {
        if (pressState) {
          dispatchOpen(pressState.x, pressState.y, readContext(pressState.trigger));
          // Mark that a long-press fired so the subsequent click handler
          // doesn't also open the picker. The Reflex on_click is a separate
          // event (click), so usually fine — but iOS sometimes synthesizes
          // a click after long-press. Set a brief flag.
          window.__ctxMenuJustOpened = Date.now();
          pressState = null;
        }
      }, LONG_PRESS_MS),
    };
  }

  function movePress(e) {
    if (!pressState || e.pointerId !== pressState.pointerId) return;
    pressState.x = e.clientX;
    pressState.y = e.clientY;
    if (Math.abs(e.clientX - pressState.startX) > MOVE_TOLERANCE_PX ||
        Math.abs(e.clientY - pressState.startY) > MOVE_TOLERANCE_PX) {
      cancelPress();
    }
  }

  function cancelPress() {
    if (pressState && pressState.timer) clearTimeout(pressState.timer);
    pressState = null;
  }

  document.addEventListener("pointerdown",   startPress,  { passive: true });
  document.addEventListener("pointermove",   movePress,   { passive: true });
  document.addEventListener("pointerup",     cancelPress, { passive: true });
  document.addEventListener("pointercancel", cancelPress, { passive: true });
  document.addEventListener("scroll",        cancelPress, { passive: true, capture: true });

  // ── Suppress the click that follows a long-press on iOS ──────────────────
  // When the menu just opened from a long-press, the synthesized click
  // shouldn't also open the swap picker. We swallow click events that fire
  // within 500ms of a context-menu open.

  document.addEventListener("click", function (e) {
    const justOpened = window.__ctxMenuJustOpened || 0;
    if (Date.now() - justOpened < 500) {
      const trigger = e.target && e.target.closest && e.target.closest(".ctx-menu-trigger");
      if (trigger) {
        e.stopPropagation();
        e.preventDefault();
      }
    }
  }, true);
})();
