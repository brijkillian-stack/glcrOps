/**
 * highlight_toolbar.js — dispatch HighlightToolbarState.open_at on left-click
 *
 * Trigger pattern: any element with class "ht-trigger" and data-ht-* attributes
 * opens the highlight chip toolbar when left-clicked.
 *
 * Data attributes the JS reads from the trigger element:
 *   data-ht-tm-id    — the TM's entity id (e.g. "tm_sheri_o")
 *   data-ht-night-id — the current night's UUID
 *   data-ht-slot-key — the slot key (e.g. "zone_3", "PMOL2")
 *
 * The handler runs in capture phase and calls e.stopPropagation() so the
 * parent zone card's React on_click (which opens the TM picker) does NOT fire.
 * This mirrors the long-press suppression pattern in context_menu.js.
 *
 * Position: the toolbar is anchored just below the trigger element's bounding
 * box via getBoundingClientRect(). The Reflex state stores x/y in viewport
 * coords; the CSS uses position:fixed so scrolling doesn't shift the panel.
 */

(function () {
  "use strict";

  /**
   * Dispatch HighlightToolbarState.open_at via Reflex's global dispatcher.
   * Args order must match the Python event handler signature:
   *   open_at(self, x, y, tm_id, night_id, slot_key)
   */
  function dispatchOpen(x, y, tmId, nightId, slotKey) {
    if (!window._reflexDispatch) return;
    window._reflexDispatch("highlight_toolbar_state.open_at", {
      args: [
        Math.round(x),
        Math.round(y),
        tmId,
        nightId,
        slotKey,
      ],
    });
  }

  /**
   * Read data-ht-* attributes from a trigger element.
   * Dataset keys are camelCased by the browser: data-ht-tm-id → htTmId.
   */
  function readHtContext(trigger) {
    var ds = trigger.dataset || {};
    return {
      tmId:    ds.htTmId    || "",
      nightId: ds.htNightId || "",
      slotKey: ds.htSlotKey || "",
    };
  }

  /**
   * Global click handler — runs in capture phase so we fire before React's
   * synthetic onClick bubble handlers. We only intercept clicks that land on
   * (or inside) a .ht-trigger element.
   */
  document.addEventListener(
    "click",
    function (e) {
      var trigger =
        e.target &&
        e.target.closest &&
        e.target.closest(".ht-trigger");

      if (!trigger) return;

      // Stop the event from reaching the parent zone card's React on_click
      // (which would open the TM picker). Both stopPropagation and
      // preventDefault are called to be safe across browsers / React versions.
      e.stopPropagation();
      e.preventDefault();

      var ctx  = readHtContext(trigger);
      var rect = trigger.getBoundingClientRect();

      // Anchor just below the element with a small gap
      var anchorX = rect.left;
      var anchorY = rect.bottom + 6;

      dispatchOpen(anchorX, anchorY, ctx.tmId, ctx.nightId, ctx.slotKey);
    },
    true  // capture phase
  );

})();
