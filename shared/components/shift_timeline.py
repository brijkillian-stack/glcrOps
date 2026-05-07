"""
shared/components/shift_timeline.py — Shift timeline with live NOW marker.

Static structure rendered by Reflex; a small JS snippet ticks the NOW marker
every 60 s by updating a CSS custom property --hud-now-pct on the
.hud-timeline element.  No page reload needed.

Grave shift is 11 PM → 7 AM (8 hours).  The progress percentage is:
  pct = (minutes_since_2300) / 480 * 100   (clamped 0–100)

Phase labels (percentages of 8-hour window):
  Open   0–8%    (0–38 min)
  Wave 1 8–17%   (38–82 min)
  Mid    17–38%  (82–182 min)
  Wave 2 38–50%  (182–240 min)
  Late   50–75%  (240–360 min)
  Wave 3 75–88%  (360–422 min)
  Close  88–100% (422–480 min)

The NOW chip label is updated by the same JS tick.
"""

import reflex as rx

_PHASES = [
    {"label": "Open",   "start": 0,  "end": 8,   "wave": False},
    {"label": "Wave 1", "start": 8,  "end": 17,  "wave": True},
    {"label": "Mid",    "start": 17, "end": 38,  "wave": False},
    {"label": "Wave 2", "start": 38, "end": 50,  "wave": True},
    {"label": "Late",   "start": 50, "end": 75,  "wave": False},
    {"label": "Wave 3", "start": 75, "end": 88,  "wave": True},
    {"label": "Close",  "start": 88, "end": 100, "wave": False},
]

# Tick labels for the bottom row (shift start 11 PM → 7 AM)
_TICKS = ["11P", "12A", "1A", "2A", "3A", "4A", "5A", "6A", "7A"]

# JS injected once — updates --hud-now-pct every 60 s
_TIMELINE_JS = r"""
(function() {
  function nowPct() {
    var now = new Date();
    var h = now.getHours(), m = now.getMinutes();
    // Minutes since 23:00 (wrap around midnight)
    var mins = h >= 23 ? (h - 23) * 60 + m : (h + 1) * 60 + m;
    return Math.min(100, Math.max(0, mins / 480 * 100));
  }
  function nowLabel() {
    var now = new Date();
    var h = now.getHours(), m = now.getMinutes();
    var h12 = h % 12 || 12;
    var ampm = h < 12 ? "AM" : "PM";
    return "NOW · " + h12 + ":" + String(m).padStart(2,"0") + " " + ampm;
  }
  function tick() {
    var pct = nowPct();
    var tl = document.querySelector('.hud-timeline');
    if (tl) {
      tl.style.setProperty('--hud-now-pct', pct + '%');
      var chip = tl.querySelector('.hud-now-chip');
      if (chip) chip.textContent = nowLabel();
    }
  }
  tick();
  setInterval(tick, 60000);
})();
"""


def _phase_label_block(p: dict, idx: int) -> rx.Component:
    left_pct = f"{p['start']}%"
    width_pct = f"{p['end'] - p['start']}%"
    return rx.el.div(
        p["label"],
        style={
            "position": "absolute",
            "left": left_pct,
            "width": width_pct,
            "top": "0",
            "paddingLeft": "4px",
            "fontSize": "8px",
            "fontWeight": "700",
            "letterSpacing": "0.1em",
            "color": "var(--gold)" if p.get("_active") else (
                "var(--blue)" if p["wave"] else "var(--ink3)"
            ),
            "textTransform": "uppercase",
            "borderLeft": "1px solid var(--line2)" if idx > 0 else "none",
        },
    )


def _wave_fill(p: dict) -> rx.Component | None:
    if not p["wave"]:
        return rx.fragment()
    return rx.el.div(
        style={
            "position": "absolute",
            "left": f"{p['start']}%",
            "width": f"{p['end'] - p['start']}%",
            "top": "0",
            "bottom": "0",
            "background": "var(--blue-dim)",
        },
    )


def shift_timeline() -> rx.Component:
    """Shift timeline component with live JS NOW marker."""

    # Phase label row
    phase_labels = rx.el.div(
        *[_phase_label_block(p, i) for i, p in enumerate(_PHASES)],
        style={
            "position": "absolute",
            "left": "0",
            "right": "0",
            "top": "16px",
            "height": "10px",
        },
    )

    # Track with wave fills + progress fill
    track = rx.el.div(
        # Wave tint fills
        *[_wave_fill(p) for p in _PHASES],
        # Progress fill (driven by --hud-now-pct)
        rx.el.div(
            style={
                "position": "absolute",
                "left": "0",
                "top": "0",
                "bottom": "0",
                "width": "var(--hud-now-pct, 0%)",
                "background": "linear-gradient(90deg, rgba(224,203,182,0.6), var(--gold))",
                "transition": "width 0.5s linear",
            },
        ),
        style={
            "position": "absolute",
            "left": "0",
            "right": "0",
            "top": "28px",
            "height": "8px",
            "background": "var(--panel2)",
            "border": "1px solid var(--line)",
            "borderRadius": "999px",
            "overflow": "hidden",
        },
    )

    # NOW marker vertical line (driven by --hud-now-pct)
    now_line = rx.el.div(
        style={
            "position": "absolute",
            "left": "var(--hud-now-pct, 0%)",
            "top": "12px",
            "bottom": "0",
            "width": "2px",
            "background": "var(--gold)",
            "transform": "translateX(-1px)",
            "boxShadow": "0 0 12px var(--gold)",
            "transition": "left 0.5s linear",
        },
    )

    # NOW chip label (text updated by JS tick)
    now_chip = rx.el.div(
        "NOW",
        class_name="hud-now-chip",
        style={
            "position": "absolute",
            "left": "var(--hud-now-pct, 0%)",
            "top": "8px",
            "transform": "translateX(-50%)",
            "fontFamily": "var(--mono)",
            "fontSize": "9px",
            "color": "var(--gold)",
            "background": "var(--bg)",
            "padding": "1px 5px",
            "border": "1px solid var(--gold)",
            "borderRadius": "3px",
            "fontWeight": "600",
            "whiteSpace": "nowrap",
            "transition": "left 0.5s linear",
        },
    )

    # Tick row
    tick_row = rx.el.div(
        *[rx.el.span(t) for t in _TICKS],
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "marginTop": "8px",
            "fontFamily": "var(--mono)",
            "fontSize": "9px",
            "color": "var(--ink3)",
            "letterSpacing": "0.04em",
        },
    )

    return rx.el.div(
        # JS init script (runs once on mount via a hidden script tag)
        rx.el.script(_TIMELINE_JS),
        # Relative container for absolute children
        rx.el.div(
            phase_labels,
            track,
            now_line,
            now_chip,
            style={"position": "relative", "height": "60px"},
        ),
        tick_row,
        style={"paddingTop": "16px", "paddingBottom": "14px"},
        class_name="hud-timeline",
    )
