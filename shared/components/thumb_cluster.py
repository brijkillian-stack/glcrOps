"""
shared/components/thumb_cluster.py — Thumb cluster FAB for the Shift HUD.

Fixed bottom-right stack:
  ⚑ Call-out  (red)   → opens CallOutModalState
  ★ Kudos     (gold)  → opens KudosModalState
  ⊟ BEO       (blue)  → opens BeoModalState
  + FAB       (blue radial gradient, 64×64) → toggles CommandPaletteState

Phase 4a: all four buttons are wired to their respective capture handlers.
"""

import reflex as rx
from shared.state.call_out_modal import CallOutModalState
from shared.state.kudos_modal import KudosModalState
from shared.state.beo_modal import BeoModalState
from shared.state.command_palette import CommandPaletteState


def _cluster_btn(icon: str, label: str, color: str, on_click) -> rx.Component:
    return rx.el.button(
        rx.el.span(icon, style={"fontSize": "13px"}),
        rx.el.span(label),
        on_click=on_click,
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
        on_click=CommandPaletteState.toggle,
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
    """Fixed bottom-right thumb cluster — all buttons wired (Phase 4a)."""
    return rx.el.div(
        _cluster_btn("⚑", "Call-out", "var(--red)",  CallOutModalState.open_modal),
        _cluster_btn("★", "Kudos",    "var(--gold)", KudosModalState.open_modal),
        _cluster_btn("⊟", "BEO",      "var(--blue)", BeoModalState.open_modal),
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
