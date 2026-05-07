"""
pages/deployment.py — Eligibility Roster grid + Tonight's Crew selector

All active TMs × all 28 slots.  Slot-group tabs narrow the columns.
Active-only toggle hides inactive TMs.  Clicking any Y/N cell toggles
eligibility and saves to Supabase immediately.

Tonight's Crew panel: click TM name chips to mark who's working tonight.
Crew rows are highlighted in the eligibility grid.
"""

import reflex as rx
from ..state.deployment import DeploymentState
from shared.base import AppState
from shared.components.palette import command_palette
from shared.components.capture import capture_modal
from shared.db import ELIGIBILITY_SLOTS, SLOT_GROUPS


# ── Static slot → group map (built at import time) ────────────────────────────

_SLOT_GROUP_MAP: dict[str, str] = {
    slot: group
    for group, slots in SLOT_GROUPS.items()
    for slot in slots
}

_GROUP_ORDER = ["Zones", "Men's RR", "Women's RR", "Support", "All"]


# ── Page header ───────────────────────────────────────────────────────────────

def page_header() -> rx.Component:
    return rx.el.header(
        rx.el.div(
            rx.el.div(
                rx.el.div("Deployment", class_name="page-eyebrow"),
                rx.el.h1("Eligibility Roster", class_name="page-title"),
            ),
            rx.el.div(
                rx.el.span(
                    DeploymentState.tm_count.to_string(),
                    " TMs",
                    class_name="dep-tm-count",
                ),
                rx.el.button(
                    "⟳ Refresh",
                    on_click=DeploymentState.load_roster,
                    class_name="btn-ghost btn-sm",
                ),
                style={"display": "flex", "alignItems": "center", "gap": "12px"},
            ),
        ),
        style={
            "display": "flex",
            "alignItems": "flex-end",
            "justifyContent": "space-between",
            "marginBottom": "16px",
        },
        class_name="page-head",
    )


# ── Controls bar ──────────────────────────────────────────────────────────────

def _group_tab(label: str) -> rx.Component:
    return rx.el.button(
        label,
        on_click=DeploymentState.set_slot_group(label),
        class_name=rx.cond(
            DeploymentState.slot_group == label,
            "dep-group-tab active",
            "dep-group-tab",
        ),
    )


def controls_bar() -> rx.Component:
    return rx.el.div(
        # Left: slot group tabs
        rx.el.div(
            _group_tab("Zones"),
            _group_tab("Men's RR"),
            _group_tab("Women's RR"),
            _group_tab("Support"),
            _group_tab("All"),
            class_name="dep-group-tabs",
        ),
        # Right: search + active-only toggle
        rx.el.div(
            rx.el.input(
                placeholder="Filter by name…",
                value=DeploymentState.search_query,
                on_change=DeploymentState.set_search,
                class_name="dep-search",
            ),
            rx.el.label(
                rx.el.input(
                    type="checkbox",
                    checked=DeploymentState.active_only,
                    on_change=DeploymentState.set_active_only,
                    style={"marginRight": "6px"},
                ),
                "Active only",
                class_name="dep-toggle-label",
            ),
            style={"display": "flex", "alignItems": "center", "gap": "12px"},
        ),
        class_name="dep-controls",
    )


# ── Tonight's Crew panel ──────────────────────────────────────────────────────

def _crew_chip(row: dict) -> rx.Component:
    """A clickable chip representing one TM — active = on tonight's crew."""
    is_crew = DeploymentState.tonight_crew.contains(row["id"])
    return rx.el.button(
        row["name"],
        on_click=DeploymentState.toggle_crew(row["id"]),
        class_name=rx.cond(is_crew, "crew-chip crew-chip-on", "crew-chip"),
        title=rx.cond(is_crew, "Remove from tonight's crew", "Add to tonight's crew"),
    )


def tonight_crew_panel() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span("Tonight's Crew", class_name="crew-panel-title"),
            rx.el.span(
                DeploymentState.crew_count.to_string(),
                " working",
                class_name="crew-panel-count",
            ),
            rx.cond(
                DeploymentState.crew_count > 0,
                rx.el.button(
                    "Clear",
                    on_click=DeploymentState.clear_crew,
                    class_name="btn-ghost btn-sm",
                    style={"fontSize": "11px", "padding": "3px 8px"},
                ),
                rx.fragment(),
            ),
            style={"display": "flex", "alignItems": "center", "gap": "10px",
                   "marginBottom": "10px"},
        ),
        rx.cond(
            ~DeploymentState.loading,
            rx.el.div(
                rx.foreach(DeploymentState.filtered_roster, _crew_chip),
                class_name="crew-chip-wrap",
            ),
            rx.el.div(class_name="skel skel-sm",
                      style={"height": "32px", "width": "100%"}),
        ),
        class_name="crew-panel",
    )


# ── Skeleton loading ──────────────────────────────────────────────────────────

def loading_skeleton() -> rx.Component:
    return rx.cond(
        DeploymentState.loading,
        rx.el.div(
            rx.el.div(class_name="skel skel-md", style={"width": "100%", "height": "32px", "marginBottom": "8px"}),
            rx.el.div(class_name="skel skel-sm", style={"width": "100%", "height": "48px", "marginBottom": "6px"}),
            rx.el.div(class_name="skel skel-sm", style={"width": "100%", "height": "48px", "marginBottom": "6px"}),
            rx.el.div(class_name="skel skel-sm", style={"width": "100%", "height": "48px", "marginBottom": "6px"}),
            rx.el.div(class_name="skel skel-sm", style={"width": "100%", "height": "48px"}),
            style={"padding": "8px 0"},
        ),
        rx.fragment(),
    )


# ── Table header ──────────────────────────────────────────────────────────────

def _slot_th(slot: str) -> rx.Component:
    group = _SLOT_GROUP_MAP.get(slot, "Support")
    # Abbrev for narrow columns
    short = (
        slot
        .replace("Zone ", "Z")
        .replace("Mens ", "M")
        .replace("Womens ", "W")
        .replace(" + ", "+")
        .replace("Zone 9 SR", "Z9SR")
        .replace("Admin", "Adm")
        .replace("PM OL", "PMOL")
        .replace("AM OL", "AMOL")
        .replace("Trash ", "Tr")
        .replace("MP ", "MP")
    )
    return rx.el.th(
        rx.el.span(short, title=slot),
        class_name="dep-th",
        style=rx.cond(
            (DeploymentState.slot_group == "All") | (DeploymentState.slot_group == group),
            {"display": "table-cell"},
            {"display": "none"},
        ),
    )


def table_header() -> rx.Component:
    return rx.el.thead(
        rx.el.tr(
            rx.el.th("Rank", class_name="dep-th dep-th-rank"),
            rx.el.th("Name", class_name="dep-th dep-th-name"),
            rx.el.th("Score", class_name="dep-th dep-th-score"),
            *[_slot_th(slot) for slot in ELIGIBILITY_SLOTS],
            class_name="dep-tr-head",
        )
    )


# ── Table row ─────────────────────────────────────────────────────────────────
# Slot cells are rendered at component-build time via Python list comprehension
# (not rx.foreach) to avoid iterating over Var[Any] from an untyped dict value.

def _slot_cell_for(slot: str, group: str) -> rx.Component:
    """
    Return a component factory that renders one eligibility cell for `slot`.
    Called once per slot at build time; `row` is a Var supplied by the outer foreach.
    """
    elig_key = f"elig_{slot}"

    def _cell(row: dict) -> rx.Component:
        is_saving = DeploymentState.saving_cell == f"{row['id'].to(str)}:{slot}"
        return rx.el.td(
            rx.el.div(
                rx.cond(
                    is_saving,
                    rx.el.span("…", class_name="elig-cell-saving"),
                    rx.cond(
                        row[elig_key],
                        rx.el.span("Y", class_name="elig-cell yes"),
                        rx.el.span("—", class_name="elig-cell no"),
                    ),
                ),
                on_click=DeploymentState.toggle_elig(row["id"], slot),
                class_name="dep-cell-wrap",
                title=slot,
            ),
            class_name="dep-td",
            style=rx.cond(
                (DeploymentState.slot_group == "All") | (DeploymentState.slot_group == group),
                {"display": "table-cell"},
                {"display": "none"},
            ),
        )
    return _cell


# Build one cell-renderer per slot at module load time
_SLOT_CELLS: list[tuple[str, str]] = [
    (slot, _SLOT_GROUP_MAP.get(slot, "Support"))
    for slot in ELIGIBILITY_SLOTS
]


def _roster_row(row: dict) -> rx.Component:
    is_crew = DeploymentState.tonight_crew.contains(row["id"])
    row_cls = rx.cond(is_crew, "dep-tr dep-tr-crew", "dep-tr")
    return rx.el.tr(
        # Rank
        rx.el.td(
            rx.el.span(row["rank_label"], class_name="dep-rank"),
            class_name="dep-td dep-td-rank",
        ),
        # Name
        rx.el.td(
            rx.el.div(
                rx.el.span(row["name"], class_name="dep-name"),
                rx.cond(
                    row["status"] == "loa",
                    rx.el.span("LOA", class_name="status-badge loa"),
                    rx.fragment(),
                ),
                style={"display": "flex", "alignItems": "center", "gap": "6px"},
            ),
            class_name="dep-td dep-td-name",
        ),
        # Score
        rx.el.td(
            rx.el.span(
                row["score_label"],
                class_name=rx.cond(
                    row["score_tier"] == "top",        "score-badge score-badge-top",
                    rx.cond(
                        row["score_tier"] == "solid",       "score-badge score-badge-solid",
                        rx.cond(
                            row["score_tier"] == "developing", "score-badge score-badge-developing",
                            "score-badge score-badge-standard",
                        ),
                    ),
                ),
            ),
            class_name="dep-td dep-td-score",
        ),
        # Eligibility cells — one per slot, built at component-build time
        *[_slot_cell_for(slot, group)(row) for slot, group in _SLOT_CELLS],
        class_name=row_cls,
    )


# ── Empty state ───────────────────────────────────────────────────────────────

def empty_state() -> rx.Component:
    return rx.cond(
        ~DeploymentState.loading & (DeploymentState.tm_count == 0),
        rx.el.div(
            rx.el.p(
                "No TMs match the current filter.",
                style={"color": "var(--fg-3)", "fontSize": "14px", "padding": "40px 0"},
            ),
        ),
        rx.fragment(),
    )


# ── Main grid ─────────────────────────────────────────────────────────────────

def roster_grid() -> rx.Component:
    return rx.cond(
        ~DeploymentState.loading,
        rx.el.div(
            rx.el.table(
                table_header(),
                rx.el.tbody(
                    rx.foreach(DeploymentState.filtered_roster, _roster_row),
                ),
                class_name="dep-table",
            ),
            empty_state(),
            class_name="dep-table-wrap",
        ),
        rx.fragment(),
    )


# ── Page ──────────────────────────────────────────────────────────────────────

def deployment_page() -> rx.Component:
    return rx.el.div(
        rx.el.main(
            page_header(),
            tonight_crew_panel(),
            controls_bar(),
            loading_skeleton(),
            roster_grid(),
            class_name="main main-single",
            style={"maxWidth": "unset", "overflowX": "auto", "padding": "32px 24px"},
        ),
        rx.el.button(
            "+",
            class_name="fab",
            on_click=AppState.open_capture,
            title="Capture (⌘N)",
            aria_label="Quick capture",
        ),
        command_palette(),
        capture_modal(),
        class_name=AppState.app_class_name,
    )
