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
        rx.foreach(ShiftState.zone_cards, shift_zone_card),
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


# ── Break schedule (3 groups × 3 waves = 9 cells) ────────────────────────────

def _break_status_pill(status: str) -> rx.Component:
    """Status pill for a break wave cell — driven by BreakSlot.status."""
    return rx.cond(
        status == "active",
        rx.el.span(
            "● Active",
            style={
                "fontSize": "9px",
                "fontWeight": "700",
                "letterSpacing": "0.08em",
                "color": "var(--blue)",
                "animation": "pulse 2s infinite",
            },
        ),
        rx.cond(
            status == "complete",
            rx.el.span(
                "✓ Complete",
                style={
                    "fontSize": "9px",
                    "fontWeight": "600",
                    "letterSpacing": "0.06em",
                    "color": "var(--ink3)",
                },
            ),
            rx.el.span(
                "—",
                style={"fontSize": "9px", "color": "var(--mute)"},
            ),
        ),
    )


def _break_wave_cell(w) -> rx.Component:
    """One cell in the break grid — click/tap to expand TM names."""
    is_active = w["status"] == "active"
    border = rx.cond(
        is_active,
        "1px solid var(--blue)",
        rx.cond(w["status"] == "complete", "1px solid var(--green)", "1px solid var(--line2)"),
    )
    bg = rx.cond(
        is_active, "var(--blue-dim)", "transparent",
    )
    time_str = rx.el.span(
        w["start_time"], "–", w["end_time"],
        style={"fontFamily": "var(--mono)", "fontSize": "10px", "color": "var(--ink2)"},
    )
    tm_count = rx.el.span(
        w["tms"].length().to_string(),
        rx.el.span(" TMs", style={"color": "var(--ink3)"}),
        style={"fontSize": "10px", "fontWeight": "600", "color": "var(--ink)"},
    )
    # TM name chips — shown inside <details> expand
    tm_chips = rx.el.div(
        rx.foreach(
            w["tms"],
            lambda name: rx.el.span(
                name,
                style={
                    "fontSize": "10px",
                    "padding": "2px 6px",
                    "borderRadius": "3px",
                    "background": "var(--panel2)",
                    "color": "var(--ink2)",
                    "fontWeight": "500",
                },
            ),
        ),
        style={
            "display": "flex",
            "flexWrap": "wrap",
            "gap": "3px",
            "paddingTop": "6px",
            "marginTop": "4px",
            "borderTop": "1px solid var(--line)",
        },
    )
    return rx.el.details(
        rx.el.summary(
            rx.el.div(
                time_str,
                rx.el.div(
                    tm_count,
                    _break_status_pill(w["status"]),
                    style={"display": "flex", "alignItems": "center",
                           "justifyContent": "space-between", "marginTop": "3px"},
                ),
                style={"display": "flex", "flexDirection": "column", "gap": "2px"},
            ),
            style={
                "listStyle": "none",
                "cursor": "pointer",
                "outline": "none",
            },
        ),
        tm_chips,
        style={
            "border": border,
            "borderRadius": "6px",
            "padding": "8px 10px",
            "background": bg,
            "flex": "1",
        },
    )


def _break_group_row(g) -> rx.Component:
    """One row in the break schedule: group label + 3 wave cells."""
    group_color = rx.cond(
        g["group_num"] == 1, "var(--group-1)",
        rx.cond(g["group_num"] == 2, "var(--group-2)", "var(--group-3)"),
    )
    group_bg = rx.cond(
        g["group_num"] == 1, "var(--group-1-dim)",
        rx.cond(g["group_num"] == 2, "var(--group-2-dim)", "var(--group-3-dim)"),
    )
    label_cell = rx.el.div(
        rx.el.span(
            "G", rx.el.span(g["group_num"].to_string()),
            style={
                "fontSize": "16px",
                "fontWeight": "700",
                "color": group_color,
            },
        ),
        rx.el.span(
            g["tm_count"].to_string(), " TMs",
            style={"fontSize": "9px", "color": "var(--ink3)", "marginTop": "2px"},
        ),
        style={
            "display": "flex",
            "flexDirection": "column",
            "alignItems": "center",
            "justifyContent": "center",
            "padding": "8px 6px",
            "borderRadius": "6px",
            "background": group_bg,
            "border": f"1px solid {group_color}",
            "minWidth": "52px",
        },
    )
    return rx.el.div(
        label_cell,
        rx.foreach(g["waves"], _break_wave_cell),
        style={
            "display": "grid",
            "gridTemplateColumns": "56px 1fr 1fr 1fr",
            "gap": "6px",
            "alignItems": "stretch",
        },
    )


def _break_section() -> rx.Component:
    return rx.el.div(
        _section_head("Break schedule"),
        # Column headers
        rx.el.div(
            rx.el.div(""),  # group label column spacer
            _eb("Wave 1", "var(--ink3)",
                {"textAlign": "center", "paddingLeft": "10px"}),
            _eb("Wave 2", "var(--ink3)",
                {"textAlign": "center", "paddingLeft": "10px"}),
            _eb("Wave 3", "var(--ink3)",
                {"textAlign": "center", "paddingLeft": "10px"}),
            style={
                "display": "grid",
                "gridTemplateColumns": "56px 1fr 1fr 1fr",
                "gap": "6px",
                "marginBottom": "6px",
            },
        ),
        # Group rows
        rx.el.div(
            rx.foreach(ShiftState.break_groups, _break_group_row),
            style={"display": "flex", "flexDirection": "column", "gap": "6px"},
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
            on_click=ShiftState.complete_task(task["id"]),
            style={
                "width": "22px",
                "height": "22px",
                "borderRadius": "999px",
                "border": "1px solid var(--line2)",
                "display": "grid",
                "placeItems": "center",
                "fontSize": "11px",
                "color": "var(--ink3)",
                "cursor": "pointer",
                "transition": "all 0.15s ease",
            },
            _hover={
                "background": "var(--green, #10b981)",
                "borderColor": "var(--green, #10b981)",
                "color": "white",
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


# ── Zone Tasks floating drawer (Phase 4i.5) ──────────────────────────────────

def _zone_task_row_hud(r: dict) -> rx.Component:
    cat_color = rx.match(
        r["category"],
        ("zone", "#3b82f6"),
        ("rr",   "#a78bfa"),
        ("aux",  "#fbbf24"),
        "#9ca3af",
    )
    return rx.el.div(
        rx.el.span(
            r["zone_slot"],
            style={
                "fontSize":     "10px",
                "fontWeight":   "700",
                "padding":      "2px 6px",
                "borderRadius": "3px",
                "background":   cat_color,
                "color":        "#fff",
                "minWidth":     "48px",
                "textAlign":    "center",
                "flexShrink":   "0",
            },
        ),
        rx.el.span(
            r["task_name"],
            style={"fontSize": "12px", "color": "#f1f5f9", "flex": "1",
                   "fontWeight": "500"},
        ),
        rx.el.span(
            r["tm_name"],
            style={"fontSize": "11px", "color": "#94a3b8",
                   "textAlign": "right", "minWidth": "80px", "flexShrink": "0"},
        ),
        style={
            "display":      "flex",
            "alignItems":   "center",
            "gap":          "8px",
            "padding":      "5px 6px",
            "borderRadius": "4px",
            "_hover":       {"background": "rgba(255,255,255,0.05)"},
        },
    )


def _zone_tasks_drawer() -> rx.Component:
    """Fixed right-side drawer for zone task assignments. Phase 4i.5."""
    count = ShiftState.zone_task_rows.length()
    return rx.cond(
        ShiftState.zone_tasks_drawer_open,
        rx.el.div(
            # Backdrop
            rx.el.div(
                on_click=ShiftState.close_zone_tasks_drawer,
                style={
                    "position": "fixed", "inset": "0",
                    "background": "rgba(0,0,0,0.5)",
                    "zIndex": "800",
                },
            ),
            # Drawer
            rx.el.div(
                # Header
                rx.el.div(
                    rx.el.div(
                        rx.el.span("Zone Tasks Tonight",
                                   style={"fontSize": "14px", "fontWeight": "700",
                                          "color": "#f1f5f9"}),
                        rx.el.span(
                            count.to_string() + " assignments",
                            style={"fontSize": "11px", "color": "#64748b",
                                   "marginLeft": "8px"},
                        ),
                        style={"display": "flex", "alignItems": "baseline", "gap": "0"},
                    ),
                    rx.el.button(
                        "✕",
                        on_click=ShiftState.close_zone_tasks_drawer,
                        style={
                            "background": "none", "border": "none", "color": "#64748b",
                            "cursor": "pointer", "fontSize": "16px", "lineHeight": "1",
                        },
                    ),
                    style={
                        "display":        "flex",
                        "justifyContent": "space-between",
                        "alignItems":     "center",
                        "paddingBottom":  "12px",
                        "borderBottom":   "1px solid #1e293b",
                        "marginBottom":   "12px",
                    },
                ),
                # Content
                rx.cond(
                    count == 0,
                    rx.el.div(
                        "No zone task assignments for tonight. Run the engine first.",
                        style={"fontSize": "12px", "color": "#64748b",
                               "fontStyle": "italic", "padding": "12px 0"},
                    ),
                    rx.el.div(
                        rx.foreach(ShiftState.zone_task_rows, _zone_task_row_hud),
                        style={"display": "flex", "flexDirection": "column", "gap": "2px"},
                    ),
                ),
                style={
                    "position":   "fixed",
                    "top":        "0",
                    "right":      "0",
                    "width":      "380px",
                    "height":     "100vh",
                    "background": "#0f172a",
                    "borderLeft": "1px solid #1e293b",
                    "boxShadow":  "-4px 0 20px rgba(0,0,0,0.4)",
                    "zIndex":     "801",
                    "padding":    "24px 18px",
                    "overflowY":  "auto",
                    "boxSizing":  "border-box",
                },
            ),
        ),
        rx.el.span(""),
    )


def _zone_tasks_fab() -> rx.Component:
    """Floating action button to open the zone tasks drawer. Positioned bottom-left."""
    return rx.el.button(
        "📋",
        rx.el.span("Tasks", style={"fontSize": "11px", "fontWeight": "600",
                                   "marginLeft": "5px"}),
        on_click=ShiftState.open_zone_tasks_drawer,
        style={
            "position":     "fixed",
            "bottom":       "24px",
            "left":         "24px",
            "display":      "flex",
            "alignItems":   "center",
            "background":   "#1e293b",
            "border":       "1px solid #334155",
            "borderRadius": "20px",
            "color":        "#94a3b8",
            "padding":      "8px 14px",
            "cursor":       "pointer",
            "fontSize":     "13px",
            "fontFamily":   "var(--font)",
            "boxShadow":    "0 4px 12px rgba(0,0,0,0.3)",
            "zIndex":       "700",
            "transition":   "all 0.15s",
            "_hover":       {"color": "#e2e8f0", "borderColor": "#475569"},
        },
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
        # Phase 4i.5 — Zone Tasks FAB + drawer
        _zone_tasks_fab(),
        _zone_tasks_drawer(),
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
