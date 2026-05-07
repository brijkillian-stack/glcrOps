"""
shared/components/shift_zone_card.py — Read-only ZoneCard for the Shift HUD.

Receives one ZoneCardData TypedDict from ShiftState.zone_cards via rx.foreach.

Card anatomy:
  ┌─────────────────────────────────┐
  │  Z3          ● OPEN / ⌶ LOCK   │  ← zone label + status badge
  │  Joy Smith                      │  ← TM name (large)
  │  South Wing Restrooms           │  ← zone area name
  │                                 │
  │  Sweep cycle · empty pad check  │  ← current task (or placeholder)
  │ ─────────────────────────────── │
  │  G2  (group badge, bottom-left) │  ← break group badge
  └─────────────────────────────────┘

Status border palette (CSS custom properties from assets/ops_tokens.css):
  ok:   --line2 / --panel2
  lock: --gold  / --gold-dim
  warn: --amber / --amber-dim
  open: --red   / --red-dim

Group badge colors (from ops_tokens.css):
  G1: --group-1      G2: --group-2      G3: --group-3
"""

import reflex as rx


def _status_badge(slot) -> rx.Component:
    """Top-right status badge — only rendered when status != 'ok'."""
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


def _group_badge(slot) -> rx.Component:
    """Small pill showing break group (G1/G2/G3) — hidden when group_num == 0."""
    group_color = rx.cond(
        slot["group_num"] == 1, "var(--group-1)",
        rx.cond(slot["group_num"] == 2, "var(--group-2)", "var(--group-3)"),
    )
    group_bg = rx.cond(
        slot["group_num"] == 1, "var(--group-1-dim)",
        rx.cond(slot["group_num"] == 2, "var(--group-2-dim)", "var(--group-3-dim)"),
    )
    return rx.cond(
        slot["group_num"] > 0,
        rx.el.span(
            "G",
            rx.el.span(slot["group_num"].to_string()),
            style={
                "fontSize": "10px",
                "fontWeight": "700",
                "letterSpacing": "0.04em",
                "padding": "2px 7px",
                "borderRadius": "999px",
                "color": group_color,
                "background": group_bg,
                "border": f"1px solid {group_color}",
                "lineHeight": "1.4",
            },
        ),
        rx.fragment(),
    )


def shift_zone_card(slot) -> rx.Component:
    """Read-only zone card for the Shift HUD zone grid. Accepts ZoneCardData."""
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
        # Top row: zone label (large) + status badge
        rx.el.div(
            rx.el.div(
                slot["zone_label"],
                style={
                    "fontSize": "13px",
                    "fontWeight": "700",
                    "color": "var(--ink3)",
                    "letterSpacing": "0.08em",
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
        # TM name — prominent
        rx.el.div(
            slot["tm_name"],
            style={
                "fontSize": "15px",
                "fontWeight": "600",
                "marginTop": "3px",
                "letterSpacing": "-0.01em",
                "color": rx.cond(slot["tm_name"] == "—", "var(--mute)", "var(--ink)"),
                "lineHeight": "1.25",
            },
        ),
        # Zone area name
        rx.el.div(
            slot["zone_area"],
            style={
                "fontSize": "10px",
                "color": "var(--ink3)",
                "marginTop": "2px",
                "lineHeight": "1.3",
            },
        ),
        # Current task — rendered only when non-empty
        rx.cond(
            slot["current_task"] != "",
            rx.el.div(
                slot["current_task"],
                style={
                    "fontSize": "10px",
                    "color": "var(--ink3)",
                    "marginTop": "4px",
                    "fontStyle": "italic",
                    "lineHeight": "1.3",
                },
            ),
            rx.fragment(),
        ),
        # Spacer
        rx.el.div(style={"flex": "1"}),
        # Footer: group badge
        rx.el.div(
            _group_badge(slot),
            style={
                "marginTop": "6px",
                "paddingTop": "6px",
                "borderTop": "1px solid var(--line)",
                "display": "flex",
                "alignItems": "center",
            },
        ),
        style={
            "background": bg_color,
            "border": f"1px solid {border_color}",
            "borderRadius": "8px",
            "padding": "10px 12px",
            "minHeight": "90px",
            "display": "flex",
            "flexDirection": "column",
            "position": "relative",
        },
    )
