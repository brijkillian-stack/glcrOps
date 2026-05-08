/**
 * task_annotation.js — right-click / long-press handler for the ZDS annotation
 * context menu (Phase 4k.3 tasks + Phase 4k.4 TM chips + Phase 4k.5 cards).
 *
 * Three trigger classes are handled:
 *
 *   .task-ctx-trigger  — task list rows inside zone/RR/aux cards (Phase 4k.3)
 *     data-task-id   — UUID of the task (or "" for custom/hardcoded tasks)
 *     data-task-name — display name of the task
 *     Dispatches: zds_state.open_task_menu(x, y, task_id, task_name)
 *
 *   .tm-annot-trigger  — TM name chips in zone/RR/aux cards (Phase 4k.4)
 *     data-tm-annot-id   — tm_id (UUID)
 *     data-tm-annot-name — display name of the TM
 *     Dispatches: zds_state.open_tm_menu(tm_id, tm_name, x, y)
 *
 *   .card-annot-trigger — zone/RR/aux card outer wrappers (Phase 4k.5)
 *     data-card-annot-code — zone label / card code ("Z9", "RR1+2 M", etc.)
 *     Dispatches: zds_state.open_card_menu(card_code, x, y)
 *
 * All three run in capture phase with e.stopPropagation() so context_menu.js
 * (bubble phase) does NOT also fire for the same element.
 */

(function () {
  "use strict";

  var LONG_PRESS_MS     = 500;
  var MOVE_TOLERANCE_PX = 8;

  // ── Dispatch helper ──────────────────────────────────────────────────────────

  function dispatchOpen(x, y, taskId, taskName) {
    if (!window._reflexDispatch) return;
    window._reflexDispatch("zds_state.open_task_menu", {
      args: [Math.round(x), Math.round(y), taskId || "", taskName || ""],
    });
  }

  function readContext(trigger) {
    var ds = trigger.dataset || {};
    return { taskId: ds.taskId || "", taskName: ds.taskName || "" };
  }

  // ── Desktop: contextmenu event (right-click) ─────────────────────────────────

  document.addEventListener("contextmenu", function (e) {
    var trigger = e.target && e.target.closest && e.target.closest(".task-ctx-trigger");
    if (!trigger) return;
    e.preventDefault();
    // stopPropagation blocks bubble (context_menu.js).
    // stopImmediatePropagation blocks our OWN later capture listeners
    // (.tm-annot-trigger and .card-annot-trigger), which would otherwise
    // also match because closest() walks up to ancestors. Task is the
    // most specific match — it wins.
    e.stopPropagation();
    e.stopImmediatePropagation();
    var ctx = readContext(trigger);
    dispatchOpen(e.clientX, e.clientY, ctx.taskId, ctx.taskName);
  }, true);  // capture phase so we run before context_menu.js bubble handler

  // ── Touch: long-press (~500ms hold) ──────────────────────────────────────────

  var pressState = null;

  function startPress(e) {
    if (e.pointerType !== "touch" && e.pointerType !== "pen") return;
    var trigger = e.target && e.target.closest && e.target.closest(".task-ctx-trigger");
    if (!trigger) return;
    cancelPress();
    var ctx = readContext(trigger);
    pressState = {
      x: e.clientX,
      y: e.clientY,
      startX: e.clientX,
      startY: e.clientY,
      pointerId: e.pointerId,
      taskId:   ctx.taskId,
      taskName: ctx.taskName,
      timer: setTimeout(function () {
        if (pressState) {
          dispatchOpen(pressState.x, pressState.y, pressState.taskId, pressState.taskName);
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

  // ── Phase 4k.4: TM chip annotation trigger (.tm-annot-trigger) ───────────────
  // Runs in capture phase (before context_menu.js bubble handler) so that
  // right-clicking a TM name opens the ZDS annotation menu, NOT the operational
  // ContextMenuState menu. e.stopPropagation() ensures only one menu opens.

  function dispatchOpenTmMenu(x, y, tmId, tmName) {
    if (!window._reflexDispatch) return;
    window._reflexDispatch("zds_state.open_tm_menu", {
      args: [tmId || "", tmName || "", Math.round(x), Math.round(y)],
    });
  }

  function readTmContext(trigger) {
    var ds = trigger.dataset || {};
    return { tmId: ds.tmAnnotId || "", tmName: ds.tmAnnotName || "" };
  }

  // Desktop right-click
  document.addEventListener("contextmenu", function (e) {
    var trigger = e.target && e.target.closest && e.target.closest(".tm-annot-trigger");
    if (!trigger) return;
    e.preventDefault();
    // See stopImmediatePropagation note on the .task-ctx-trigger handler above —
    // blocks our OWN later card-annot-trigger listener since the TM chip is
    // inside a card-annot-trigger ancestor.
    e.stopPropagation();
    e.stopImmediatePropagation();
    var ctx = readTmContext(trigger);
    dispatchOpenTmMenu(e.clientX, e.clientY, ctx.tmId, ctx.tmName);
  }, true);  // capture phase

  // Touch long-press
  var tmPressState = null;

  function tmStartPress(e) {
    if (e.pointerType !== "touch" && e.pointerType !== "pen") return;
    var trigger = e.target && e.target.closest && e.target.closest(".tm-annot-trigger");
    if (!trigger) return;
    tmCancelPress();
    var ctx = readTmContext(trigger);
    tmPressState = {
      x: e.clientX,
      y: e.clientY,
      startX: e.clientX,
      startY: e.clientY,
      pointerId: e.pointerId,
      tmId:   ctx.tmId,
      tmName: ctx.tmName,
      timer: setTimeout(function () {
        if (tmPressState) {
          dispatchOpenTmMenu(tmPressState.x, tmPressState.y,
                             tmPressState.tmId, tmPressState.tmName);
          tmPressState = null;
        }
      }, LONG_PRESS_MS),
    };
  }

  function tmMovePress(e) {
    if (!tmPressState || e.pointerId !== tmPressState.pointerId) return;
    tmPressState.x = e.clientX;
    tmPressState.y = e.clientY;
    if (Math.abs(e.clientX - tmPressState.startX) > MOVE_TOLERANCE_PX ||
        Math.abs(e.clientY - tmPressState.startY) > MOVE_TOLERANCE_PX) {
      tmCancelPress();
    }
  }

  function tmCancelPress() {
    if (tmPressState && tmPressState.timer) clearTimeout(tmPressState.timer);
    tmPressState = null;
  }

  document.addEventListener("pointerdown",   tmStartPress,  { passive: true });
  document.addEventListener("pointermove",   tmMovePress,   { passive: true });
  document.addEventListener("pointerup",     tmCancelPress, { passive: true });
  document.addEventListener("pointercancel", tmCancelPress, { passive: true });

  // ── Phase 4k.5: Card annotation trigger (.card-annot-trigger) ────────────────
  // Right-click (or long-press) on the outer zone/RR/aux card wrapper opens the
  // card annotation menu. Runs capture phase with stopPropagation so the
  // operational context menu (bubble phase) does NOT also fire.

  function dispatchOpenCardMenu(x, y, cardCode) {
    if (!window._reflexDispatch) return;
    window._reflexDispatch("zds_state.open_card_menu", {
      args: [cardCode || "", Math.round(x), Math.round(y)],
    });
  }

  function readCardContext(trigger) {
    var ds = trigger.dataset || {};
    return { cardCode: ds.cardAnnotCode || "" };
  }

  // Desktop right-click — card wrapper
  document.addEventListener("contextmenu", function (e) {
    var trigger = e.target && e.target.closest && e.target.closest(".card-annot-trigger");
    if (!trigger) return;
    e.preventDefault();
    // Card is the LEAST specific match (registered last). If task or tm
    // listeners ahead of this one matched first, they already called
    // stopImmediatePropagation and we never run. Calling it here too as
    // defense-in-depth + to block any future capture listener registered
    // on the same node.
    e.stopPropagation();
    e.stopImmediatePropagation();
    var ctx = readCardContext(trigger);
    dispatchOpenCardMenu(e.clientX, e.clientY, ctx.cardCode);
  }, true);  // capture phase

  // Touch long-press — card wrapper
  var cardPressState = null;

  function cardStartPress(e) {
    if (e.pointerType !== "touch" && e.pointerType !== "pen") return;
    var trigger = e.target && e.target.closest && e.target.closest(".card-annot-trigger");
    if (!trigger) return;
    cardCancelPress();
    var ctx = readCardContext(trigger);
    cardPressState = {
      x: e.clientX,
      y: e.clientY,
      startX: e.clientX,
      startY: e.clientY,
      pointerId: e.pointerId,
      cardCode: ctx.cardCode,
      timer: setTimeout(function () {
        if (cardPressState) {
          dispatchOpenCardMenu(cardPressState.x, cardPressState.y, cardPressState.cardCode);
          cardPressState = null;
        }
      }, LONG_PRESS_MS),
    };
  }

  function cardMovePress(e) {
    if (!cardPressState || e.pointerId !== cardPressState.pointerId) return;
    cardPressState.x = e.clientX;
    cardPressState.y = e.clientY;
    if (Math.abs(e.clientX - cardPressState.startX) > MOVE_TOLERANCE_PX ||
        Math.abs(e.clientY - cardPressState.startY) > MOVE_TOLERANCE_PX) {
      cardCancelPress();
    }
  }

  function cardCancelPress() {
    if (cardPressState && cardPressState.timer) clearTimeout(cardPressState.timer);
    cardPressState = null;
  }

  document.addEventListener("pointerdown",   cardStartPress,  { passive: true });
  document.addEventListener("pointermove",   cardMovePress,   { passive: true });
  document.addEventListener("pointerup",     cardCancelPress, { passive: true });
  document.addEventListener("pointercancel", cardCancelPress, { passive: true });

})();
