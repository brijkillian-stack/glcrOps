"""
shared/components/capture_toast.py — 3-second auto-dismiss capture toast.

Mount capture_toast() once in apps/shift/pages/index.py.
The JS snippet embedded via rx.el.script auto-dismisses by dispatching
CaptureToastState.dismiss after 3s whenever the toast becomes visible.
"""

import reflex as rx
from shared.state.capture_toast import CaptureToastState

_AUTO_DISMISS_JS = """
(function() {
  var _captureTimer = null;
  function watchCaptureToast() {
    var panel = document.querySelector('.capture-toast-panel');
    if (panel && !_captureTimer) {
      _captureTimer = setTimeout(function() {
        window._reflexDispatch && window._reflexDispatch('capture_toast_state.dismiss', {});
        _captureTimer = null;
      }, 3000);
    }
    if (!panel && _captureTimer) {
      clearTimeout(_captureTimer);
      _captureTimer = null;
    }
  }
  var obs = new MutationObserver(watchCaptureToast);
  obs.observe(document.body, { childList: true, subtree: true });
  watchCaptureToast();
})();
"""


def capture_toast() -> rx.Component:
    """Fixed bottom-center toast that auto-dismisses after 3s.

    Mount once at the page root. Shows when CaptureToastState.visible is True.
    """
    return rx.el.div(
        rx.el.script(_AUTO_DISMISS_JS),
        rx.cond(
            CaptureToastState.visible,
            rx.el.div(
                rx.el.span("✓", style={
                    "color": "var(--green)",
                    "fontWeight": "700",
                    "fontSize": "14px",
                }),
                rx.el.span(
                    CaptureToastState.message,
                    style={"color": "var(--ink)", "fontSize": "13px", "flex": "1"},
                ),
                rx.el.button(
                    "×",
                    on_click=CaptureToastState.dismiss,
                    style={
                        "background": "none",
                        "border": "none",
                        "color": "var(--ink3)",
                        "cursor": "pointer",
                        "fontSize": "16px",
                        "lineHeight": "1",
                        "padding": "0 2px",
                    },
                ),
                class_name="capture-toast-panel",
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "gap": "10px",
                    "padding": "10px 16px",
                    "background": "var(--panel)",
                    "border": "1px solid var(--green)",
                    "borderRadius": "8px",
                    "boxShadow": "0 8px 24px rgba(0,0,0,0.5)",
                    "maxWidth": "360px",
                    "minWidth": "220px",
                },
            ),
            rx.fragment(),
        ),
        style={
            "position": "fixed",
            "bottom": "24px",
            "left": "50%",
            "transform": "translateX(-50%)",
            "zIndex": "200",
            "pointerEvents": rx.cond(CaptureToastState.visible, "auto", "none"),
        },
    )
