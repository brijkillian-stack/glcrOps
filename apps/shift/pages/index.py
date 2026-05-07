"""
apps/shift/pages/index.py — Shift HUD page (/shift)

Layout (matches shift-hud-hifi.jsx exactly):
  sticky header (eyebrow · greeting · pills · ShiftTimeline)
  body grid 1.55fr | 1fr
    LEFT: zone 5×2 grid | RR + Aux 2-col | break wave strip
    RIGHT: roster chips | ⚑ carried-over panel | tonight tasks | activity feed
  position:fixed thumb cluster (bottom-right)
"""

import reflex as rx
from ..state import ShiftState
from shared.components.shift_zone_card import shift_zone_card
from shared.components.shift_timeline import shift_timeline
from shared.components.thumb_cluster import thumb_cluster
from shared.components.capture_modals import capture_modals
from shared.components.capture_toast import capture_toast

# ── Palette helpers (dark HUD; ignores light-mode for now) ──────────────────

def _eb(text, color="var(--ink3)", extra_style: dict | None = None) -> rx.Component:
    """Eyebrow / label: 10px, 700, 0.14em, uppercase."""
    style = {
        "fontSize": "10px",
        "fontWeight": "700",
        "letterSpacing": "0.14em",
        "textTransform": "uppercase",
        "color": color,
    }
    if extra_style:
        style.update(extra_style)
    return rx.el.div(text, style=style)


def _pill(text, color: str, bg: str, border: str) -> rx.Component:
    return rx.el.span(
        text,
        style={
            "display": "inline-flex",
            "alignItems": "center",
            "gap": "5px",
            "fontSize": "10px",
            "fontWeight": "600",
            "letterSpacing": "0.06em",
            "textTransform": "uppercase",
            "padding": "3px 9px",
            "borderRadius": "999px",
            "color": color,
            "background": bg,
            "border": f"1px solid {border}",
            "lineHeight": "1.4",
        },
    )


def _dot(color: str, size: int = 6) -> rx.Component:
    return rx.el.span(
        style={
            "display": "inline-block",
            "width": f"{size}px",
            "height": f"{size}px",
            "borderRadius": "999px",
            "background": color,
        },
    )


def _section_head(title: str, count=None, action=None, accent="var(--gold)") -> rx.Component:
    title_row_children = [
        _eb(title, "var(--ink2)"),
    ]
    if count is not None:
        title_row_children.append(
            rx.el.span(str(count) if isinstance(count, str) else count,
                       style={"fontSize": "11px", "color": "var(--ink3)", "fontFamily": "var(--mono)"})
        )
    title_row = rx.el.div(
        *title_row_children,
        style={"display": "flex", "alignItems": "baseline", "gap": "8px"},
    )
    top_row_children = [title_row]
    if action is not None:
        top_row_children.append(action)
    return rx.el.div(
        rx.el.div(
            *top_row_children,
            style={"display": "flex", "alignItems": "baseline",
                   "justifyContent": "space-between", "gap": "8px"},
        ),
        rx.el.div(style={"height": "2px", "width": "22px",
                         "background": accent, "marginTop": "5px"}),
        style={"marginBottom": "10px"},
    )


# ── Header ────────────────────────────────────────────────────────────────────

def _shift_header() -> rx.Component:
    carry_pill = rx.cond(
        ShiftState.carry_count > 0,
        _pill(
            rx.el.span("⚑ ", rx.el.span(ShiftState.carry_count.to_string()),
                       rx.el.span(" carried over")),
            "var(--amber)", "var(--amber-dim)", "var(--amber)",
        ),
        rx.fragment(),
    )
    live_pill = _pill(
        rx.el.span(
            _dot("var(--green)"),
            rx.el.span(" live · "),
            rx.el.span(ShiftState.live_label),
        ),
        "var(--green)", "var(--green-dim)", "var(--green)",
    )

    return rx.el.div(
        # eyebrow + greeting
        rx.el.div(
            _eb(ShiftState.shift_date_label, "var(--gold)"),
            rx.el.div(
                ShiftState.greeting,
                style={
                    "fontFamily": "var(--serif)",
                    "fontSize": "26px",
                    "fontWeight": "400",
                    "fontStyle": "italic",
                    "letterSpacing": "-0.015em",
                    "marginTop": "4px",
                    "color": "var(--ink)",
                },
            ),
        ),
        # spacer + pills
        rx.el.div(style={"flex": "1"}),
        carry_pill,
        live_pill,
        # timeline (full-width below)
        style={
            "display": "flex",
            "alignItems": "flex-end",
            "gap": "16px",
        },
        class_name="hud-header-top-row",
    )


def _header_block() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            _shift_header(),
            shift_timeline(),
            style={"padding": "16px 28px 0"},
        ),
        style={
            "borderBottom": "1px solid var(--line)",
            "background": "linear-gradient(180deg, var(--panel) 0%, var(--bg) 100%)",
        },
        class_name="hud-header",
    )


# ── Deployment hero (left panel) ──────────────────────────────────────────────

def _deploy_bar() -> rx.Component:
    fill_pct = rx.cond(
        ShiftState.deploy_total > 0,
        (ShiftState.deploy_filled * 100 / ShiftState.deploy_total).to_string() + "%",
        "0%",
    )
    return rx.el.div(
        rx.el.div(
            rx.el.div(style={"width": fill_pct, "height": "100%",
                             "background": "linear-gradient(90deg, var(--gold), var(--green))"}),
            style={
                "height": "5px",
                "background": "var(--panel2)",
                "borderRadius": "999px",
                "overflow": "hidden",
                "border": "1px solid var(--line)",
            },
        ),
        rx.el.div(
            rx.el.span("● ", rx.el.span(ShiftState.deploy_locked.to_string()), " LOCKED",
                       style={"color": "var(--gold)"}),
            rx.el.span("● ", rx.el.span(ShiftState.deploy_warn.to_string()), " WARN",
                       style={"color": "var(--amber)"}),
            rx.el.span("● ", rx.el.span(ShiftState.deploy_open.to_string()), " OPEN",
                       style={"color": "var(--red)"}),
            rx.el.span("● ", rx.el.span(ShiftState.deploy_ok.to_string()), " OK",
                       style={"color": "var(--ink3)"}),
            style={
                "display": "flex",
                "justifyContent": "space-between",
                "marginTop": "6px",
                "fontSize": "10px",
                "letterSpacing": "0.06em",
            },
        ),
        style={"flex": "1"},
    )


def _deploy_headline() -> rx.Component:
    return rx.el.div(
        _section_head(
            "Tonight's deployment",
            action=rx.el.a(
                "Open in ZDS →",
                href="/zds",
                style={"fontSize": "11px", "color": "var(--blue)",
                       "fontWeight": "600", "letterSpacing": "0.02em"},
            ),
        ),
        rx.el.div(
            rx.el.div(
                rx.el.span(ShiftState.deploy_filled.to_string(),
                           style={"fontSize": "34px", "fontWeight": "700",
                                  "letterSpacing": "-0.02em",
                                  "fontVariantNumeric": "tabular-nums"}),
                rx.el.span(
                    rx.el.span(" / "),
                    rx.el.span(ShiftState.deploy_total.to_string()),
                    style={"color": "var(--ink3)", "fontWeight": "400", "fontSize": "22px"},
                ),
            ),
            _deploy_bar(),
            style={"display": "flex", "alignItems": "baseline", "gap": "14px",
                   "marginBottom": "10px"},
        ),
    )


def _zone_grid() -> rx.Component:
    return rx.el.div(
        rx.foreach(ShiftState.zone_slots, shift_zone_card),
        style={
            "display": "grid",
            "gridTemplateColumns": "repeat(5, 1fr)",
            "gap": "6px",
        },
    )


# ── RR + Aux ──────────────────────────────────────────────────────────────────

def _rr_slot_card(s) -> rx.Component:
    is_open = s["status"] == "open"
    return rx.el.div(
        rx.el.div(s["slot_key"],
                  style={"fontSize": "9px", "color": "var(--ink3)", "letterSpacing": "0.06em"}),
        rx.el.div(
            rx.el.div("M", style={"fontSize": "9px", "color": "var(--ink3)",
                                   "letterSpacing": "0.04em"}),
            rx.el.div(s["mens_name"],
                      style={"fontSize": "11px", "fontWeight": "600",
                             "color": rx.cond(s["mens_name"] == "—",
                                              "var(--mute)", "var(--ink)")}),
            rx.el.div("W", style={"fontSize": "9px", "color": "var(--ink3)",
                                   "letterSpacing": "0.04em", "marginTop": "2px"}),
            rx.el.div(s["womens_name"],
                      style={"fontSize": "11px", "fontWeight": "600",
                             "color": rx.cond(s["womens_name"] == "—",
                                              "var(--mute)", "var(--ink)")}),
            style={"display": "flex", "flexDirection": "column", "gap": "1px", "marginTop": "2px"},
        ),
        style={
            "background": rx.cond(is_open, "var(--red-dim)", "var(--panel2)"),
            "border": rx.cond(is_open, "1px solid var(--red)", "1px solid var(--line2)"),
            "borderRadius": "5px",
            "padding": "7px 8px",
        },
    )


def _rr_section() -> rx.Component:
    # NOTE: previously computed an `open_count` here via
    # `length() - rx.Var.create("0")` — but the variable was never
    # rendered AND Reflex 0.9 rejects Number - String Var math at
    # compile time. The unfilled-RR count belongs on ShiftState
    # (see ShiftState.rr_unfilled_count for a future addition);
    # for now the section header just shows total / total which is
    # accurate for the read-only HUD.
    return rx.el.div(
        _section_head(
            "Restrooms",
            count=rx.el.span(
                ShiftState.rr_slots.length().to_string(),
                " / ",
                ShiftState.rr_slots.length().to_string(),
            ),
        ),
        rx.el.div(
            rx.foreach(ShiftState.rr_slots, _rr_slot_card),
            style={"display": "grid", "gridTemplateColumns": "repeat(5, 1fr)", "gap": "4px"},
        ),
    )


def _aux_slot_card(s) -> rx.Component:
    is_open = s["status"] == "open"
    return rx.el.div(
        rx.el.div(s["slot_key"],
                  style={"fontSize": "9px", "color": "var(--ink3)", "letterSpacing": "0.06em"}),
        rx.el.div(s["tm_name"],
                  style={"fontSize": "11px", "fontWeight": "600", "marginTop": "2px",
                         "color": rx.cond(s["tm_name"] == "—", "var(--mute)", "var(--ink)")}),
        style={
            "background": rx.cond(is_open, "var(--red-dim)", "var(--panel2)"),
            "border": rx.cond(is_open, "1px solid var(--red)", "1px solid var(--line)"),
            "borderRadius": "5px",
            "padding": "6px 8px",
        },
    )


def _aux_section() -> rx.Component:
    return rx.el.div(
        _section_head("Auxiliary"),
        rx.el.div(
            rx.foreach(ShiftState.aux_slots, _aux_slot_card),
            style={"display": "grid", "gridTemplateColumns": "repeat(4, 1fr)", "gap": "4px"},
        ),
    )


# ── Break waves ───────────────────────────────────────────────────────────────

def _wave_name_chip(name: str, wave_state: str) -> rx.Component:
    return rx.el.span(
        name,
        style={
            "fontSize": "10px",
            "padding": "2px 6px",
            "borderRadius": "3px",
            "background": rx.cond(wave_state == "active",
                                  "rgba(0,0,0,0.25)", "var(--panel2)"),
            "color": rx.cond(wave_state == "done", "var(--ink3)",
                    rx.cond(wave_state == "active", "var(--blue)", "var(--ink3)")),
            "textDecoration": rx.cond(wave_state == "done", "line-through", "none"),
            "opacity": rx.cond(wave_state == "done", "0.7", "1"),
            "fontWeight": "500",
        },
    )


def _break_wave_card(w) -> rx.Component:
    state_color = rx.cond(
        w["state"] == "done",   "var(--green)",
        rx.cond(w["state"] == "active", "var(--blue)", "var(--ink3)"),
    )
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                w["wave_label"],
                style={"fontSize": "18px", "fontWeight": "700", "color": state_color,
                       "fontVariantNumeric": "tabular-nums", "width": "26px"},
            ),
            rx.el.div(
                rx.el.div(w["time_range"],
                          style={"fontFamily": "var(--mono)", "fontSize": "11px",
                                 "color": "var(--ink2)"}),
                rx.el.div(w["state"],
                          style={"fontSize": "9px", "color": state_color,
                                 "letterSpacing": "0.1em", "textTransform": "uppercase",
                                 "fontWeight": "700", "marginTop": "1px"}),
                style={"flex": "1"},
            ),
            rx.el.div(
                rx.el.span(w["on_count"].to_string()),
                rx.el.span(" / "),
                rx.el.span(w["total_count"].to_string()),
                style={"fontFamily": "var(--mono)", "fontSize": "12px", "color": "var(--ink3)"},
            ),
            style={"display": "flex", "alignItems": "center", "gap": "10px"},
        ),
        rx.el.div(
            rx.foreach(w["names"], lambda name: _wave_name_chip(name, w["state"])),
            style={
                "display": "flex",
                "flexWrap": "wrap",
                "gap": "3px",
                "paddingTop": "6px",
                "borderTop": rx.cond(
                    w["state"] == "active",
                    "1px solid rgba(92,192,255,0.2)",
                    "1px solid var(--line)",
                ),
            },
        ),
        style={
            "border": rx.cond(
                w["state"] == "done",   "1px solid var(--green)",
                rx.cond(w["state"] == "active", "1px solid var(--blue)",
                        "1px solid var(--ink3)"),
            ),
            "borderRadius": "6px",
            "padding": "8px 12px",
            "background": rx.cond(w["state"] == "active", "var(--blue-dim)", "transparent"),
            "display": "flex",
            "flexDirection": "column",
            "gap": "6px",
        },
    )


def _break_section() -> rx.Component:
    return rx.el.div(
        _section_head(
            "Break waves",
            action=rx.el.span(
                "● W2 ACTIVE",
                style={"fontSize": "10px", "color": "var(--blue)", "fontWeight": "600"},
            ),
        ),
        rx.el.div(
            rx.foreach(ShiftState.break_waves, _break_wave_card),
            style={"display": "grid", "gridTemplateColumns": "repeat(3, 1fr)", "gap": "8px"},
        ),
    )


# ── Left panel (deployment hero) ──────────────────────────────────────────────

def _left_panel() -> rx.Component:
    return rx.el.div(
        _deploy_headline(),
        _zone_grid(),
        rx.el.div(
            _rr_section(),
            _aux_section(),
            style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px"},
        ),
        _break_section(),
        style={
            "background": "var(--bg)",
            "padding": "18px 24px",
            "overflowY": "auto",
            "display": "flex",
            "flexDirection": "column",
            "gap": "16px",
        },
        class_name="hud-left",
    )


# ── Right panel ───────────────────────────────────────────────────────────────

def _roster_chip(chip) -> rx.Component:
    kind = chip["kind"]
    # Map kind to CSS class for color
    color_var = rx.cond(
        kind == "g", "var(--green)",
        rx.cond(kind == "p", "var(--amber)",
        rx.cond(kind == "a", "var(--blue)", "var(--red)")),
    )
    bg_var = rx.cond(
        kind == "g", "var(--green-dim)",
        rx.cond(kind == "p", "var(--amber-dim)",
        rx.cond(kind == "a", "var(--blue-dim)", "var(--red-dim)")),
    )
    return rx.el.span(
        rx.el.span(chip["name"], style={"fontWeight": "600"}),
        rx.el.span(
            chip["zone"],
            style={"fontSize": "9px", "padding": "1px 4px", "borderRadius": "2px",
                   "background": "rgba(0,0,0,0.3)", "color": color_var,
                   "fontFamily": "var(--mono)"},
        ),
        style={
            "display": "inline-flex",
            "alignItems": "center",
            "gap": "5px",
            "fontSize": "11px",
            "padding": "3px 4px 3px 8px",
            "borderRadius": "4px",
            "background": bg_var,
            "color": color_var,
            "border": f"1px solid {color_var}",
            "textDecoration": rx.cond(kind == "x", "line-through", "none"),
            "opacity": rx.cond(kind == "x", "0.6", "1"),
        },
    )


def _roster_legend() -> rx.Component:
    return rx.el.div(
        rx.el.span(
            _dot("var(--green)"),
            rx.el.span(" ", ShiftState.roster_grave_count.to_string(), " GRAVE"),
        ),
        rx.el.span(
            _dot("var(--amber)"),
            rx.el.span(" ", ShiftState.roster_pmol_count.to_string(), " PM OL"),
        ),
        rx.el.span(
            _dot("var(--blue)"),
            rx.el.span(" ", ShiftState.roster_amol_count.to_string(), " AM OL"),
        ),
        rx.el.span(
            _dot("var(--red)"),
            rx.el.span(" ", ShiftState.roster_off_count.to_string(), " OFF"),
        ),
        style={
            "display": "flex",
            "gap": "12px",
            "marginTop": "10px",
            "fontSize": "10px",
            "color": "var(--ink3)",
            "letterSpacing": "0.06em",
        },
    )


def _roster_section() -> rx.Component:
    on_count = (
        ShiftState.roster_grave_count
        + ShiftState.roster_pmol_count
        + ShiftState.roster_amol_count
    )
    return rx.el.div(
        _section_head(
            "Roster",
            count=rx.el.span(
                on_count.to_string(),
                " on floor · ",
                ShiftState.roster_off_count.to_string(),
                " off",
            ),
        ),
        rx.el.div(
            rx.foreach(ShiftState.roster_chips, _roster_chip),
            style={"display": "flex", "flexWrap": "wrap", "gap": "4px"},
        ),
        _roster_legend(),
    )


def _carry_over_row(item) -> rx.Component:
    return rx.el.div(
        _dot("var(--amber)", 6),
        rx.el.div(
            rx.el.div(item["text"],
                      style={"fontSize": "12px", "color": "var(--ink)", "lineHeight": "1.35"}),
            rx.el.div(item["from_label"],
                      style={"fontSize": "10px", "color": "var(--ink3)", "marginTop": "1px"}),
            style={"flex": "1"},
        ),
        style={
            "display": "flex",
            "alignItems": "flex-start",
            "gap": "8px",
            "padding": "6px 0",
        },
    )


def _carry_over_section() -> rx.Component:
    return rx.cond(
        ShiftState.carry_count > 0,
        rx.el.div(
            rx.el.div(
                _eb("⚑ Carried over", "var(--amber)"),
                rx.el.span(ShiftState.carry_count.to_string(),
                           style={"fontSize": "10px", "color": "var(--amber)",
                                  "fontWeight": "600"}),
                style={"display": "flex", "alignItems": "center",
                       "justifyContent": "space-between", "marginBottom": "8px"},
            ),
            rx.foreach(ShiftState.carry_over_items, _carry_over_row),
            style={
                "background": "var(--amber-dim)",
                "border": "1px solid var(--amber)",
                "borderRadius": "8px",
                "padding": "12px 14px",
            },
        ),
        rx.fragment(),
    )


def _task_row(task) -> rx.Component:
    return rx.el.div(
        _dot("var(--blue)", 6),
        rx.el.div(
            rx.el.div(task["title"],
                      style={"fontSize": "12px", "color": "var(--ink)", "fontWeight": "500"}),
            rx.el.div(
                rx.el.span(task["due_label"],
                           style={"fontFamily": "var(--mono)"}),
                rx.el.span(" · "),
                rx.el.span(task["tag"]),
                style={"display": "flex", "gap": "8px", "marginTop": "2px",
                       "fontSize": "10px", "color": "var(--ink3)",
                       "letterSpacing": "0.04em"},
            ),
            style={"flex": "1"},
        ),
        rx.el.div(
            "✓",
            style={
                "width": "22px",
                "height": "22px",
                "borderRadius": "999px",
                "border": "1px solid var(--line2)",
                "display": "grid",
                "placeItems": "center",
                "fontSize": "11px",
                "color": "var(--ink3)",
            },
        ),
        style={
            "display": "flex",
            "alignItems": "center",
            "gap": "10px",
            "padding": "8px 0",
            "borderBottom": "1px solid var(--line)",
        },
    )


def _tasks_section() -> rx.Component:
    return rx.el.div(
        _section_head(
            "Tonight",
            count=rx.el.span(
                ShiftState.tasks.length().to_string(),
                " open",
            ),
            action=rx.el.a(
                "All →",
                href="/tasks",
                style={"fontSize": "11px", "color": "var(--blue)", "fontWeight": "600"},
            ),
        ),
        rx.foreach(ShiftState.tasks, _task_row),
    )


def _activity_row(entry) -> rx.Component:
    color = rx.cond(
        entry["color_key"] == "gold",   "var(--gold)",
        rx.cond(entry["color_key"] == "green",  "var(--green)",
        rx.cond(entry["color_key"] == "red",    "var(--red)",
        rx.cond(entry["color_key"] == "blue",   "var(--blue)",
        rx.cond(entry["color_key"] == "ink3",   "var(--ink3)",
                "var(--ink2)")))),
    )
    return rx.el.div(
        rx.el.span(entry["ts_display"],
                   style={"color": "var(--ink3)", "fontFamily": "var(--mono)",
                          "width": "38px", "fontSize": "10px"}),
        rx.el.span(entry["who"],
                   style={"color": "var(--ink3)", "width": "44px"}),
        rx.el.span(entry["what"], style={"color": color, "flex": "1"}),
        style={"display": "flex", "gap": "10px", "padding": "5px 0", "fontSize": "11px"},
    )


def _activity_section() -> rx.Component:
    return rx.el.div(
        _section_head("Activity"),
        rx.foreach(ShiftState.activity, _activity_row),
    )


def _right_panel() -> rx.Component:
    return rx.el.div(
        _roster_section(),
        _carry_over_section(),
        _tasks_section(),
        _activity_section(),
        style={
            "background": "var(--bg)",
            "padding": "18px 22px",
            "overflowY": "auto",
            "display": "flex",
            "flexDirection": "column",
            "gap": "18px",
        },
        class_name="hud-right",
    )


# ── Body grid ─────────────────────────────────────────────────────────────────

def _body_grid() -> rx.Component:
    return rx.el.div(
        _left_panel(),
        _right_panel(),
        style={
            "flex": "1",
            "display": "grid",
            "gridTemplateColumns": "1.55fr 1fr",
            "gap": "1px",
            "background": "var(--line)",
            "overflow": "hidden",
            "minHeight": "0",
        },
        class_name="hud-body",
    )


# ── Page ──────────────────────────────────────────────────────────────────────

def shift_page() -> rx.Component:
    return rx.el.div(
        _header_block(),
        _body_grid(),
        # Fixed overlays — order matters: cluster < toast < modals (modal z-index wins)
        thumb_cluster(),
        capture_toast(),
        capture_modals(),
        style={
            "display": "flex",
            "flexDirection": "column",
            "height": "100vh",
            "background": "var(--bg)",
            "color": "var(--ink)",
            "fontFamily": "var(--font)",
            "position": "relative",
            "overflow": "hidden",
        },
        class_name="shift-hud",
    )
