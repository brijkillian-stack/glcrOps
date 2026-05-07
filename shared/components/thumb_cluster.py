"""
shared/components/thumb_cluster.py — Thumb cluster FAB for the Shift HUD.

Fixed bottom-right stack:
  ⚑ Call-out  (red)
  ★ Kudos     (gold)
  ⊟ BEO       (blue)
  + FAB       (blue radial gradient, 64×64)

Phase 3 ships read-only (no capture wiring yet).  Each button will
trigger the shared capture modal in a follow-on phase.
"""

import reflex as rx


_CLUSTER_BUTTONS = [
    {"icon": "⚑", "label": "Call-out", "color": "var(--red)"},
    {"icon": "★", "label": "Kudos",    "color": "var(--gold)"},
    {"icon": "⊟", "label": "BEO",      "color": "var(--blue)"},
]


def _cluster_btn(icon: str, label: str, color: str) -> rx.Component:
    return rx.el.button(
        rx.el.span(icon, style={"fontSize": "13px"}),
        rx.el.span(label),
        style={
            "display": "flex",
            "alignItems": "center",
            "gap": "8px",
            "padding": "8px 14px 8px 12px",
            "borderRadius": "999px",
            "background": "var(--panel)",
            "border": f"1px solid {color}",
            "color": color,
            "fontSize": "11px",
            "fontWeight": "600",
            "letterSpacing": "0.04em",
            "textTransform": "uppercase",
            "boxShadow": "0 6px 20px rgba(0,0,0,0.5), 0 0 0 1px rgba(0,0,0,0.4)",
            "cursor": "pointer",
            "fontFamily": "var(--font)",
        },
    )


def _fab() -> rx.Component:
    return rx.el.button(
        "+",
        style={
            "width": "64px",
            "height": "64px",
            "borderRadius": "999px",
            "marginTop": "4px",
            "background": (
                "radial-gradient(circle at 35% 30%, #8AD3FF, var(--blue) 60%, #2A89C9)"
            ),
            "color": "#0B1A2A",
            "fontSize": "32px",
            "fontWeight": "300",
            "boxShadow": (
                "0 12px 32px rgba(92,192,255,0.5), 0 0 0 1px rgba(92,192,255,0.3)"
            ),
            "border": "none",
            "cursor": "pointer",
            "display": "grid",
            "placeItems": "center",
        },
    )


def thumb_cluster() -> rx.Component:
    """Fixed bottom-right thumb cluster."""
    return rx.el.div(
        _cluster_btn("⚑", "Call-out", "var(--red)"),
        _cluster_btn("★", "Kudos",    "var(--gold)"),
        _cluster_btn("⊟", "BEO",      "var(--blue)"),
        _fab(),
        style={
            "position": "fixed",
            "bottom": "24px",
            "right": "24px",
            "display": "flex",
            "flexDirection": "column",
            "alignItems": "flex-end",
            "gap": "8px",
            "zIndex": "100",
        },
        class_name="hud-thumb-cluster",
    )
