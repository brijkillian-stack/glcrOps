/**
 * undo_toast.js — MutationObserver auto-dismiss for the undo toast panel
 *
 * Strategy:
 *   • Observe document.body for DOM mutations (childList, subtree).
 *   • When .undo-toast-panel appears, start a 5-second timer.
 *   • If the panel disappears before the timer fires (user clicked Undo or ×),
 *     cancel the timer.
 *   • When the timer fires, dispatch undo_state.dismiss via _reflexDispatch.
 *
 * This keeps all timing logic in JS so Reflex state doesn't need a polling loop.
 */

(function () {
  'use strict';

  var _timer = null;

  function cancelTimer() {
    if (_timer !== null) {
      clearTimeout(_timer);
      _timer = null;
    }
  }

  function checkToast() {
    var panel = document.querySelector('.undo-toast-panel');
    if (panel) {
      // Panel is visible — arm the timer if not already armed
      if (_timer === null) {
        _timer = setTimeout(function () {
          _timer = null;
          if (window._reflexDispatch) {
            window._reflexDispatch('undo_state.dismiss', {});
          }
        }, 5000);
      }
    } else {
      // Panel gone — cancel any pending timer
      cancelTimer();
    }
  }

  function init() {
    var observer = new MutationObserver(checkToast);
    observer.observe(document.body, { childList: true, subtree: true });
    // Run once in case toast was already present when the script loaded
    checkToast();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}());
