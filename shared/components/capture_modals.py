"""
shared/components/capture_modals.py — All 4 Shift HUD capture modals.

Components:
  call_out_modal()       — ⚑ Call-Out (rx.dialog, dark styled)
  kudos_modal()          — ★ Kudos
  beo_modal()            — ⊟ BEO multi-select
  command_palette_modal()— + FAB / ⌘K palette
  capture_modals()       — mount all 4 at once (call once per page)

All modals use rx.dialog.root(open=State.open, on_open_change=State.close)
so Radix handles focus-trap + Escape key natively.
Dark styling via CSS vars from ops_tokens.css (works in both themes).
"""

from __future__ import annotations

import reflex as rx
from shared.state.call_out_modal import CallOutModalState, _NOTE_OPTIONS
from shared.state.kudos_modal import KudosModalState
from shared.state.beo_modal import BeoModalState
from shared.state.command_palette import CommandPaletteState

# ── Shared style helpers ──────────────────────────────────────────────────────

_MODAL_CONTENT_STYLE = {
    "background": "var(--panel)",
    "border": "1px solid var(--line2)",
    "borderRadius": "12px",
    "padding": "24px",
    "maxWidth": "480px",
    "width": "100%",
    "boxShadow": "0 24px 64px rgba(0,0,0,0.7)",
}

_TITLE_STYLE = {
    "fontSize": "15px",
    "fontWeight": "700",
    "color": "var(--ink)",
    "marginBottom": "4px",
    "letterSpacing": "-0.01em",
}

_LABEL_STYLE = {
    "fontSize": "10px",
    "fontWeight": "700",
    "letterSpacing": "0.12em",
    "textTransform": "uppercase",
    "color": "var(--ink3)",
    "marginBottom": "8px",
    "display": "block",
}

_INPUT_STYLE = {
    "width": "100%",
    "background": "var(--panel2)",
    "border": "1px solid var(--line2)",
    "borderRadius": "6px",
    "padding": "8px 12px",
    "color": "var(--ink)",
    "fontSize": "13px",
    "outline": "none",
}

_BTN_PRIMARY = {
    "padding": "8px 20px",
    "borderRadius": "6px",
    "background": "var(--blue)",
    "color": "#0B1A2A",
    "fontWeight": "700",
    "fontSize": "12px",
    "letterSpacing": "0.04em",
    "textTransform": "uppercase",
    "border": "none",
    "cursor": "pointer",
}

_BTN_GHOST = {
    "padding": "8px 16px",
    "borderRadius": "6px",
    "background": "transparent",
    "color": "var(--ink3)",
    "fontWeight": "600",
    "fontSize": "12px",
    "border": "1px solid var(--line2)",
    "cursor": "pointer",
}


def _tm_chip(name: str, tm_id: str, is_picked: bool, on_click) -> rx.Component:
    """Single selectable TM chip for the picker."""
    return rx.el.button(
        name,
        on_click=on_click,
        style={
            "padding": "5px 12px",
            "borderRadius": "999px",
            "fontSize": "12px",
            "fontWeight": "600",
            "cursor": "pointer",
            "border": rx.cond(is_picked, "1px solid var(--blue)", "1px solid var(--line2)"),
            "background": rx.cond(is_picked, "var(--blue-dim)", "var(--panel2)"),
            "color": rx.cond(is_picked, "var(--blue)", "var(--ink2)"),
            "transition": "all 0.12s ease",
        },
    )


# ── Call-Out Modal ────────────────────────────────────────────────────────────

def _call_out_tm_chip(tm) -> rx.Component:
    is_picked = CallOutModalState.picked_name == tm["name"]
    return _tm_chip(
        tm["name"], tm["tm_id"], is_picked,
        on_click=CallOutModalState.pick_tm(tm["name"], tm["tm_id"]),
    )


def call_out_modal() -> rx.Component:
    confirm_label = rx.cond(
        CallOutModalState.picked_name != "",
        rx.el.span("Mark ", CallOutModalState.picked_name, " called off"),
        rx.el.span("Mark called off"),
    )
    return rx.dialog.root(
        rx.dialog.content(
            # Title
            rx.el.div(
                rx.el.div("⚑ Log Call-Out", style={**_TITLE_STYLE, "color": "var(--red)"}),
                rx.dialog.close(
                    rx.el.button("×", style={**_BTN_GHOST, "border": "none",
                                             "fontSize": "18px", "padding": "0 4px"}),
                    on_click=CallOutModalState.close,
                ),
                style={"display": "flex", "justifyContent": "space-between",
                       "alignItems": "center", "marginBottom": "20px"},
            ),
            # TM picker
            rx.el.div(
                rx.el.span("Select TM", style=_LABEL_STYLE),
                rx.el.div(
                    rx.foreach(CallOutModalState.avail_tms, _call_out_tm_chip),
                    style={"display": "flex", "flexWrap": "wrap", "gap": "6px"},
                ),
                style={"marginBottom": "16px"},
            ),
            # Points
            rx.el.div(
                rx.el.span("Points (optional)", style=_LABEL_STYLE),
                rx.el.input(
                    type="number",
                    step="0.5",
                    min="0",
                    default_value="0",
                    on_change=CallOutModalState.set_points,
                    style=_INPUT_STYLE,
                ),
                style={"marginBottom": "16px"},
            ),
            # Note dropdown
            rx.el.div(
                rx.el.span("Note (optional)", style=_LABEL_STYLE),
                rx.el.select(
                    *[rx.el.option(opt, value=opt) for opt in _NOTE_OPTIONS],
                    on_change=CallOutModalState.set_note,
                    style=_INPUT_STYLE,
                ),
                style={"marginBottom": "24px"},
            ),
            # Footer
            rx.el.div(
                rx.dialog.close(
                    rx.el.button("Cancel", style=_BTN_GHOST,
                                 on_click=CallOutModalState.close),
                ),
                rx.el.button(
                    confirm_label,
                    on_click=CallOutModalState.confirm,
                    disabled=CallOutModalState.picked_name == "",
                    style={**_BTN_PRIMARY, "background": "var(--red)",
                           "opacity": rx.cond(CallOutModalState.submitting, "0.6", "1")},
                ),
                style={"display": "flex", "justifyContent": "flex-end",
                       "gap": "8px", "alignItems": "center"},
            ),
            style=_MODAL_CONTENT_STYLE,
        ),
        open=CallOutModalState.open,
        on_open_change=CallOutModalState.close,
    )


# ── Kudos Modal ───────────────────────────────────────────────────────────────

def _kudos_tm_chip(tm) -> rx.Component:
    is_picked = KudosModalState.picked_name == tm["name"]
    return _tm_chip(
        tm["name"], tm["tm_id"], is_picked,
        on_click=KudosModalState.pick_tm(tm["name"], tm["tm_id"]),
    )


def kudos_modal() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.el.div(
                rx.el.div("★ Log Kudos", style={**_TITLE_STYLE, "color": "var(--gold)"}),
                rx.dialog.close(
                    rx.el.button("×", style={**_BTN_GHOST, "border": "none",
                                             "fontSize": "18px", "padding": "0 4px"}),
                    on_click=KudosModalState.close,
                ),
                style={"display": "flex", "justifyContent": "space-between",
                       "alignItems": "center", "marginBottom": "20px"},
            ),
            rx.el.div(
                rx.el.span("Select TM", style=_LABEL_STYLE),
                rx.el.div(
                    rx.foreach(KudosModalState.avail_tms, _kudos_tm_chip),
                    style={"display": "flex", "flexWrap": "wrap", "gap": "6px"},
                ),
                style={"marginBottom": "16px"},
            ),
            rx.el.div(
                rx.el.span("Observation", style=_LABEL_STYLE),
                rx.el.textarea(
                    placeholder="Joy crushed Z9 SR — best walk of the month…",
                    on_change=KudosModalState.set_text,
                    rows="3",
                    style={**_INPUT_STYLE, "resize": "vertical"},
                ),
                style={"marginBottom": "24px"},
            ),
            rx.el.div(
                rx.dialog.close(
                    rx.el.button("Cancel", style=_BTN_GHOST,
                                 on_click=KudosModalState.close),
                ),
                rx.el.button(
                    "Capture",
                    on_click=KudosModalState.submit,
                    disabled=rx.cond(
                        (KudosModalState.picked_name == "") | (KudosModalState.text == ""),
                        True, False,
                    ),
                    style={**_BTN_PRIMARY, "background": "var(--gold)", "color": "#1a1200",
                           "opacity": rx.cond(KudosModalState.submitting, "0.6", "1")},
                ),
                style={"display": "flex", "justifyContent": "flex-end",
                       "gap": "8px", "alignItems": "center"},
            ),
            style=_MODAL_CONTENT_STYLE,
        ),
        open=KudosModalState.open,
        on_open_change=KudosModalState.close,
    )


# ── BEO Modal ─────────────────────────────────────────────────────────────────

def _beo_tm_chip(tm) -> rx.Component:
    return rx.el.button(
        tm["name"],
        on_click=BeoModalState.toggle_tm(tm["name"]),
        style={
            "padding": "5px 12px",
            "borderRadius": "999px",
            "fontSize": "12px",
            "fontWeight": "600",
            "cursor": "pointer",
            "border": rx.cond(tm["selected"], "1px solid var(--blue)", "1px solid var(--line2)"),
            "background": rx.cond(tm["selected"], "var(--blue-dim)", "var(--panel2)"),
            "color": rx.cond(tm["selected"], "var(--blue)", "var(--ink2)"),
        },
    )


def beo_modal() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.el.div(
                rx.el.div("⊟ Log BEO", style={**_TITLE_STYLE, "color": "var(--blue)"}),
                rx.dialog.close(
                    rx.el.button("×", style={**_BTN_GHOST, "border": "none",
                                             "fontSize": "18px", "padding": "0 4px"}),
                    on_click=BeoModalState.close,
                ),
                style={"display": "flex", "justifyContent": "space-between",
                       "alignItems": "center", "marginBottom": "20px"},
            ),
            rx.el.div(
                rx.el.span("Select TMs (multi-select)", style=_LABEL_STYLE),
                rx.el.div(
                    rx.foreach(BeoModalState.avail_tms, _beo_tm_chip),
                    style={"display": "flex", "flexWrap": "wrap", "gap": "6px"},
                ),
                style={"marginBottom": "16px"},
            ),
            rx.el.div(
                rx.el.span("Time", style=_LABEL_STYLE),
                rx.el.input(
                    default_value=BeoModalState.beo_time,
                    placeholder="e.g. 6am",
                    on_change=BeoModalState.set_beo_time,
                    style={**_INPUT_STYLE, "width": "140px"},
                ),
                style={"marginBottom": "24px"},
            ),
            rx.el.div(
                rx.dialog.close(
                    rx.el.button("Cancel", style=_BTN_GHOST,
                                 on_click=BeoModalState.close),
                ),
                rx.el.button(
                    "Log BEO",
                    on_click=BeoModalState.submit,
                    style={**_BTN_PRIMARY,
                           "opacity": rx.cond(BeoModalState.submitting, "0.6", "1")},
                ),
                style={"display": "flex", "justifyContent": "flex-end",
                       "gap": "8px", "alignItems": "center"},
            ),
            style=_MODAL_CONTENT_STYLE,
        ),
        open=BeoModalState.open,
        on_open_change=BeoModalState.close,
    )


# ── Command Palette Modal ─────────────────────────────────────────────────────

def command_palette_modal() -> rx.Component:
    quick_btn_style_base = {
        "display": "flex",
        "alignItems": "center",
        "gap": "6px",
        "padding": "10px 14px",
        "borderRadius": "8px",
        "background": "var(--panel2)",
        "border": "1px solid var(--line2)",
        "fontSize": "12px",
        "fontWeight": "600",
        "cursor": "pointer",
        "letterSpacing": "0.04em",
        "textTransform": "uppercase",
    }

    return rx.dialog.root(
        rx.dialog.content(
            # Title row
            rx.el.div(
                rx.el.div("+ Quick Capture", style={**_TITLE_STYLE}),
                rx.dialog.close(
                    rx.el.button("×", style={**_BTN_GHOST, "border": "none",
                                             "fontSize": "18px", "padding": "0 4px"}),
                    on_click=CommandPaletteState.close,
                ),
                style={"display": "flex", "justifyContent": "space-between",
                       "alignItems": "center", "marginBottom": "20px"},
            ),
            # Quick-action row
            rx.el.div(
                rx.el.button(
                    rx.el.span("⚑"), rx.el.span("Call-out"),
                    on_click=CommandPaletteState.open_call_out,
                    style={**quick_btn_style_base, "color": "var(--red)"},
                ),
                rx.el.button(
                    rx.el.span("★"), rx.el.span("Kudos"),
                    on_click=CommandPaletteState.open_kudos,
                    style={**quick_btn_style_base, "color": "var(--gold)"},
                ),
                rx.el.button(
                    rx.el.span("⊟"), rx.el.span("BEO"),
                    on_click=CommandPaletteState.open_beo,
                    style={**quick_btn_style_base, "color": "var(--blue)"},
                ),
                rx.el.a(
                    rx.el.span("📋"), rx.el.span("Recap"),
                    href="/recap",
                    on_click=CommandPaletteState.close,
                    style={**quick_btn_style_base, "color": "var(--ink2)",
                           "textDecoration": "none"},
                ),
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(4, 1fr)",
                    "gap": "8px",
                    "marginBottom": "20px",
                },
            ),
            # Divider
            rx.el.div(
                style={"height": "1px", "background": "var(--line)",
                       "marginBottom": "16px"},
            ),
            # Free-text area
            rx.el.div(
                rx.el.span("Or type a command…", style=_LABEL_STYLE),
                rx.el.textarea(
                    placeholder="log Eric called off, 5 points\nlog Joy crushed Z9 SR\ncompile recap",
                    on_change=CommandPaletteState.set_raw_text,
                    value=CommandPaletteState.raw_text,
                    rows="4",
                    style={**_INPUT_STYLE, "resize": "none", "fontFamily": "var(--mono)",
                           "fontSize": "12px"},
                ),
                style={"marginBottom": "16px"},
            ),
            rx.el.div(
                rx.dialog.close(
                    rx.el.button("Cancel", style=_BTN_GHOST,
                                 on_click=CommandPaletteState.close),
                ),
                rx.el.button(
                    "Capture",
                    on_click=CommandPaletteState.submit_raw,
                    disabled=CommandPaletteState.raw_text == "",
                    style={**_BTN_PRIMARY,
                           "opacity": rx.cond(CommandPaletteState.submitting, "0.6", "1")},
                ),
                style={"display": "flex", "justifyContent": "flex-end",
                       "gap": "8px", "alignItems": "center"},
            ),
            style={**_MODAL_CONTENT_STYLE, "maxWidth": "540px"},
        ),
        open=CommandPaletteState.open,
        on_open_change=CommandPaletteState.close,
    )


# ── Mount all 4 at once ───────────────────────────────────────────────────────

def capture_modals() -> rx.Component:
    """Render all 4 capture modals + toast. Call once at the page root."""
    return rx.fragment(
        call_out_modal(),
        kudos_modal(),
        beo_modal(),
        command_palette_modal(),
    )
