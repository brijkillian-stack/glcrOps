"""
shared/components/shift_zone_card.py — Read-only ZoneCard for the Shift HUD.

Receives one HudZoneSlot TypedDict from ShiftState.zone_slots via rx.foreach.
Status palette maps to CSS custom properties defined in assets/shift_hud.css:

  ok:   --line2 / --panel2 / --ink3
  lock: --gold  / --gold-dim
  warn: --amber / --amber-dim
  open: --red   / --red-dim
"""

import reflex as rx


def _status_badge(slot) -> rx.Component:
    """Status badge shown in the top-right of the card (lock / warn / open)."""
    return rx.el.span(
        rx.cond(
            slot["status"] == "lock", "⌶ LOCK",
            rx.cond(slot["status"] == "warn", "⚠ WARN",
            rx.cond(slot["status"] == "open", "● OPEN", "")),
        ),
        style={
            "fontSize": rx.cond(slot["status"] == "lock", "10px", "9px"),
            "color": rx.cond(
                slot["status"] == "lock", "var(--gold)",
                rx.cond(slot["status"] == "warn", "var(--amber)", "var(--red)"),
            ),
            "letterSpacing": "0.06em",
            "fontWeight": "700",
        },
    )


def shift_zone_card(slot) -> rx.Component:
    """Read-only zone card for the Shift HUD 5×2 zone grid."""
    border_color = rx.cond(
        slot["status"] == "ok",   "var(--line2)",
        rx.cond(slot["status"] == "lock", "var(--gold)",
        rx.cond(slot["status"] == "warn", "var(--amber)", "var(--red)")),
    )
    bg_color = rx.cond(
        slot["status"] == "ok",   "var(--panel2)",
        rx.cond(slot["status"] == "lock", "var(--gold-dim)",
        rx.cond(slot["status"] == "warn", "var(--amber-dim)", "var(--red-dim)")),
    )

    return rx.el.div(
        # Top row: slot key + status badge
        rx.el.div(
            rx.el.div(
                slot["slot_key"],
                style={
                    "fontSize": "10px",
                    "color": "var(--ink3)",
                    "letterSpacing": "0.1em",
                    "fontWeight": "600",
                },
            ),
            rx.cond(
                slot["status"] != "ok",
                _status_badge(slot),
                rx.fragment(),
            ),
            style={
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "space-between",
            },
        ),
        # TM name
        rx.el.div(
            slot["tm_name"],
            style={
                "fontSize": "14px",
                "fontWeight": "600",
                "marginTop": "4px",
                "letterSpacing": "-0.005em",
                "color": rx.cond(slot["tm_name"] == "—", "var(--mute)", "var(--ink)"),
            },
        ),
        # Position descriptor
        rx.el.div(
            slot["position"],
            style={"fontSize": "11px", "color": "var(--ink3)", "marginTop": "1px"},
        ),
        # Spacer
        rx.el.div(style={"flex": "1"}),
        # Footer: wave + time
        rx.el.div(
            rx.el.span("W", rx.el.span(slot["wave"].to_string())),
            rx.el.span(slot["wave_time"],
                       style={"fontFamily": "var(--mono)"}),
            style={
                "marginTop": "6px",
                "paddingTop": "6px",
                "borderTop": "1px solid var(--line)",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "space-between",
                "fontSize": "10px",
                "color": "var(--ink3)",
            },
        ),
        style={
            "background": bg_color,
            "border": f"1px solid {border_color}",
            "borderRadius": "8px",
            "padding": "10px 12px",
            "minHeight": "84px",
            "display": "flex",
            "flexDirection": "column",
            "position": "relative",
        },
    )
