"""
pages/people.py — People page + fully editable TM profile drawer.

Drawer tabs:
  Profile      — skill score (editable), status, score history
  Eligibility  — per-zone Y/N toggles grouped by area
  Preferences  — placement preferences + pair affinities
  Notes        — recent note history from Supabase
"""

import reflex as rx
from ..state.people import PeopleState
from shared.base import AppState
from shared.components.sidebar import sidebar
from shared.components.ui import empty_state
from shared.components.palette import command_palette
from shared.components.capture import capture_modal


# ═══════════════════════════════════════════════════════════════════════════════
# CONTROLS BAR (view toggle + sort + pool filter)
# ═══════════════════════════════════════════════════════════════════════════════

def _pool_chip(label: str, value: str) -> rx.Component:
    return rx.el.button(
        label,
        on_click=PeopleState.set_pool_filter(value),
        class_name=rx.cond(
            PeopleState.pool_filter == value,
            "people-pool-chip active",
            "people-pool-chip",
        ),
    )


def _shift_chip(label: str, value: str) -> rx.Component:
    """Phase O — shift filter chip (separate dimension from pool chip)."""
    return rx.el.button(
        label,
        on_click=PeopleState.set_shift_filter(value),
        class_name=rx.cond(
            PeopleState.shift_filter == value,
            "people-pool-chip active",
            "people-pool-chip",
        ),
    )


def people_controls() -> rx.Component:
    return rx.el.div(
        # Left: pool/status + shift filter chips
        rx.el.div(
            # Status row
            rx.el.div(
                _pool_chip("All",      "all"),
                _pool_chip("Active",   "active"),
                _pool_chip("Inactive", "inactive"),
                _pool_chip("LOA",      "loa"),
                _pool_chip("Accom",    "accom"),
                _pool_chip("Trainers", "trainer"),
                class_name="people-pool-chips",
            ),
            # Shift row
            rx.el.div(
                _shift_chip("All Shifts", "all"),
                _shift_chip("Graves",     "graves"),
                _shift_chip("Swings",     "swings"),
                _shift_chip("Days",       "days"),
                class_name="people-pool-chips",
                style={"marginTop": "6px"},
            ),
            style={"display": "flex", "flexDirection": "column", "gap": "2px"},
        ),
        # Right: sort + view toggle
        rx.el.div(
            rx.el.select(
                rx.el.option("Sort: Score",  value="score"),
                rx.el.option("Sort: Name",   value="name"),
                rx.el.option("Sort: Rank",   value="rank"),
                value=PeopleState.sort_by,
                on_change=PeopleState.set_sort_by,
                class_name="people-sort-select",
            ),
            rx.el.div(
                rx.el.button(
                    "▦",
                    on_click=PeopleState.set_view_mode("grid"),
                    class_name=rx.cond(
                        PeopleState.view_mode == "grid",
                        "view-toggle-btn active",
                        "view-toggle-btn",
                    ),
                    title="Grid view",
                ),
                rx.el.button(
                    "≡",
                    on_click=PeopleState.set_view_mode("list"),
                    class_name=rx.cond(
                        PeopleState.view_mode == "list",
                        "view-toggle-btn active",
                        "view-toggle-btn",
                    ),
                    title="List view",
                ),
                class_name="view-toggle-group",
            ),
            # Phase O.3 — Add Team Member entry point
            rx.el.button(
                "＋ Add Team Member",
                on_click=PeopleState.open_add_tm_modal,
                class_name="btn btn-primary",
                style={"fontSize": "12px", "padding": "6px 12px"},
            ),
            style={"display": "flex", "gap": "8px", "alignItems": "center"},
        ),
        class_name="people-controls-bar",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TM LIST ROW (compact list view)
# ═══════════════════════════════════════════════════════════════════════════════

def tm_list_row(item: dict) -> rx.Component:
    score_badge_cls = rx.cond(
        item["score_tier"] == "top",        "score-badge score-badge-top",
        rx.cond(item["score_tier"] == "solid",      "score-badge score-badge-solid",
        rx.cond(item["score_tier"] == "developing", "score-badge score-badge-developing",
                                                     "score-badge score-badge-standard")),
    )
    return rx.el.div(
        # Score badge
        rx.el.span(item["score_label"], class_name=score_badge_cls,
                   style={"width": "32px", "height": "32px", "fontSize": "12px",
                          "flexShrink": "0"}),
        # Name block
        rx.el.div(
            rx.el.span(item["name"], class_name="tm-list-name"),
            rx.cond(
                item["full_name"] != item["name"],
                rx.el.span(item["full_name"], class_name="tm-list-full"),
                rx.fragment(),
            ),
            class_name="tm-list-names",
        ),
        # Badges
        rx.el.div(
            rx.cond(item["has_no_sweeper"], rx.el.span("No Swp", class_name="chip chip-flag"),   rx.fragment()),
            rx.cond(item["has_am_only"],    rx.el.span("AM",      class_name="chip chip-flag"),   rx.fragment()),
            rx.cond(item["has_rr_pref"],    rx.el.span("RR",      class_name="chip chip-positive"), rx.fragment()),
            rx.cond(item["is_trainer"],     rx.el.span("Trainer", class_name="chip chip-blue"),   rx.fragment()),
            rx.cond(
                item["status"] == "loa",
                rx.el.span("LOA", class_name="chip chip-flag"),
                rx.fragment(),
            ),
            class_name="tm-list-badges",
        ),
        # Log button
        rx.el.button("+ Log", class_name="tm-list-log-btn",
                     on_click=AppState.open_capture_for(item["first_name"])),
        on_click=PeopleState.open_drawer(item["id"]),
        class_name="tm-list-row",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TM CARD (grid)
# ═══════════════════════════════════════════════════════════════════════════════

def tm_card(item: dict) -> rx.Component:
    score_badge_cls = rx.cond(
        item["score_tier"] == "top",    "score-badge score-badge-top",
        rx.cond(item["score_tier"] == "solid",   "score-badge score-badge-solid",
        rx.cond(item["score_tier"] == "developing", "score-badge score-badge-developing",
                "score-badge score-badge-standard")))
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.span(item["score_label"], class_name=score_badge_cls),
                rx.el.div(
                    # Phase P — display_name is canonical (big), legal name secondary.
                    rx.el.p(item["name"], class_name="tm-name"),
                    rx.cond(
                        item["full_name"] != item["name"],
                        rx.el.p(item["full_name"], class_name="tm-full-name"),
                        rx.fragment(),
                    ),
                ),
                class_name="tm-card-head",
            ),
            rx.cond(item["last_reason"] != "",
                rx.el.p(item["last_reason"], class_name="tm-excerpt"),
                rx.fragment()),
            rx.el.div(
                rx.cond(item["has_no_sweeper"], rx.el.span("No Sweeper", class_name="chip chip-flag"),   rx.fragment()),
                rx.cond(item["has_am_only"],    rx.el.span("AM Only",    class_name="chip chip-flag"),   rx.fragment()),
                rx.cond(item["has_rr_pref"],    rx.el.span("Prefers RR", class_name="chip chip-positive"), rx.fragment()),
                rx.cond(item["is_trainer"],     rx.el.span("Trainer",    class_name="chip chip-blue"),   rx.fragment()),
                class_name="tm-badges",
            ),
            rx.el.span("View profile →", class_name="tm-view-hint"),
            on_click=PeopleState.open_drawer(item["id"]),
            class_name="tm-card-body",
        ),
        rx.el.button("+ Log", class_name="tm-log-btn",
                     on_click=AppState.open_capture_for(item["first_name"])),
        class_name="tm-card",
    )


def people_skeleton() -> rx.Component:
    return rx.el.div(
        *[rx.el.div(
            rx.el.div(
                rx.el.div(class_name="skeleton", style={"width":"36px","height":"36px","borderRadius":"50%"}),
                rx.el.div(
                    rx.el.div(class_name="skeleton", style={"height":"14px","width":"80px","marginBottom":"6px"}),
                    rx.el.div(class_name="skeleton", style={"height":"11px","width":"120px"}),
                ),
                class_name="tm-card-head",
            ),
            rx.el.div(class_name="skeleton", style={"height":"11px","width":"90%","margin":"8px 0"}),
            rx.el.div(class_name="skeleton", style={"height":"28px","width":"100%","borderRadius":"var(--r-md)","marginTop":"10px"}),
            class_name="tm-card",
        ) for _ in range(12)],
        class_name="people-grid",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DRAWER — shared structure
# ═══════════════════════════════════════════════════════════════════════════════

def _tab_btn(label: str, tab: str, active_tab: rx.Var) -> rx.Component:
    return rx.el.button(
        label,
        on_click=PeopleState.set_drawer_tab(tab),
        class_name=rx.cond(active_tab == tab, "drawer-tab active", "drawer-tab"),
    )


def drawer_header() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(PeopleState.drawer_score_label, class_name=PeopleState.drawer_score_badge_cls,
                       style={"width":"44px","height":"44px","fontSize":"15px"}),
            rx.el.div(
                rx.el.h2(PeopleState.drawer_name,
                         style={"fontSize":"18px","fontWeight":"700","color":"var(--fg-1)","margin":"0 0 2px"}),
                rx.el.p(PeopleState.drawer_full_name,
                        style={"fontSize":"12px","color":"var(--fg-3)","margin":"0"}),
            ),
            style={"display":"flex","gap":"12px","alignItems":"flex-start"},
        ),
        rx.el.button("✕", on_click=PeopleState.close_drawer,
                     class_name="btn btn-ghost",
                     style={"fontSize":"14px","padding":"4px 8px","alignSelf":"flex-start"}),
        class_name="drawer-header",
    )


def drawer_tabs() -> rx.Component:
    return rx.el.div(
        _tab_btn("Profile",      "profile",     PeopleState.drawer_tab),
        _tab_btn("Eligibility",  "eligibility", PeopleState.drawer_tab),
        _tab_btn("Preferences",  "preferences", PeopleState.drawer_tab),
        _tab_btn("Notes",        "notes",       PeopleState.drawer_tab),
        class_name="drawer-tab-bar",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB: PROFILE
# ═══════════════════════════════════════════════════════════════════════════════

def _score_history_row(entry: dict) -> rx.Component:
    return rx.el.div(
        rx.el.span(entry.get("date",""), class_name="hist-date"),
        rx.el.span(
            entry.get("old","?"), " → ", entry.get("new","?"),
            class_name="hist-delta",
        ),
        rx.el.span(entry.get("reason",""), class_name="hist-reason"),
        class_name="hist-row",
    )


def _status_badge(status) -> rx.Component:
    """Status pill — color + label vary by status. Phase O adds 'archived'."""
    cls = rx.match(
        status,
        ("loa",       "chip chip-flag"),
        ("separated", "chip chip-flag"),
        ("archived",  "chip"),
        ("active",    "chip chip-positive"),
        "chip",
    )
    label = rx.match(
        status,
        ("loa",       "LOA"),
        ("separated", "Separated"),
        ("archived",  "Archived"),
        ("active",    "Active"),
        status,
    )
    return rx.el.span(label, class_name=cls)


def _alias_chip(alias: str) -> rx.Component:
    """One alias as a removable chip."""
    return rx.el.span(
        alias,
        rx.el.button(
            "×",
            on_click=PeopleState.remove_alias(alias),
            style={
                "marginLeft": "4px", "background": "transparent",
                "border": "none", "color": "var(--fg-3)",
                "fontSize": "13px", "fontWeight": "700",
                "cursor": "pointer", "padding": "0 2px",
            },
            title="Remove alias",
        ),
        style={
            "display": "inline-flex", "alignItems": "center",
            "padding": "2px 8px",
            "background": "var(--accent-blue-bg)",
            "color": "var(--accent-blue)",
            "borderRadius": "999px",
            "fontSize": "11px", "fontWeight": "600",
            "letterSpacing": "0.02em",
        },
    )


def _role_chip(role: str) -> rx.Component:
    """One toggleable role chip. Active styling reflects whether `role` is
    in the current TM's drawer_roles. Tap toggles. Porter is shown but
    visually locked (cannot be removed)."""
    is_active = PeopleState.drawer_roles.contains(role)
    is_porter = role == "porter"
    label_map = {
        "porter":         "Porter",
        "utility_porter": "Utility Porter",
        "trainer":        "Trainer",
    }
    return rx.el.button(
        rx.el.span(
            rx.cond(is_active, "✓", "+"),
            style={"marginRight": "4px"},
        ),
        rx.el.span(label_map.get(role, role)),
        on_click=PeopleState.toggle_role(role),
        disabled=is_porter,
        title=rx.cond(
            is_porter,
            "Porter is the baseline role and can't be removed.",
            rx.cond(
                role == "utility_porter",
                "Utility porters are excluded from the ZDS scheduler.",
                "Trainer — eligible to mentor trainees.",
            ),
        ),
        style={
            "padding": "4px 10px",
            "borderRadius": "999px",
            "fontSize": "11px",
            "fontWeight": "600",
            "letterSpacing": "0.02em",
            "border": rx.cond(
                is_active,
                "1px solid var(--accent-blue)",
                "1px solid var(--border-subtle)",
            ),
            "background": rx.cond(
                is_active,
                "var(--accent-blue)",
                "var(--surface-card)",
            ),
            "color": rx.cond(
                is_active,
                "white",
                "var(--fg-2)",
            ),
            "cursor": rx.cond(is_porter, "default", "pointer"),
            "opacity": rx.cond(is_porter & ~is_active, "0.5", "1"),
            "marginRight": "6px",
        },
    )


def _roles_section() -> rx.Component:
    """Phase 2026-05-05 — Roles editor inside the Profile tab.

    Toggle chips for porter / utility_porter / trainer. Porter is always
    present as the baseline. utility_porter excludes the TM from the ZDS
    scheduler entirely. trainer marks them eligible to mentor.
    """
    return rx.el.div(
        rx.el.div(
            rx.el.span("Roles", class_name="drawer-section-title"),
            rx.cond(
                PeopleState.roles_status == "saved",
                rx.el.span("✓ saved",
                           style={"fontSize": "10px",
                                  "color": "var(--accent-positive)",
                                  "marginLeft": "8px"}),
                rx.fragment(),
            ),
            rx.cond(
                PeopleState.roles_status == "error",
                rx.el.span("⚠ failed",
                           style={"fontSize": "10px",
                                  "color": "var(--accent-flag)",
                                  "marginLeft": "8px"}),
                rx.fragment(),
            ),
            style={"display": "flex", "alignItems": "center"},
        ),
        rx.el.p(
            "Roles drive scheduler behavior. Utility porters are excluded "
            "from ZDS; trainers can be paired with trainees.",
            style={"fontSize": "11px", "color": "var(--fg-mute)",
                   "marginBottom": "8px"},
        ),
        rx.el.div(
            _role_chip("porter"),
            _role_chip("utility_porter"),
            _role_chip("trainer"),
            style={"display": "flex", "flexWrap": "wrap",
                   "gap": "4px", "marginBottom": "16px"},
        ),
    )


def _aliases_section() -> rx.Component:
    """Phase O.2 — Aliases editor inside the Profile tab."""
    return rx.el.div(
        rx.el.div(
            rx.el.span("Aliases", class_name="drawer-section-title"),
            rx.cond(
                PeopleState.aliases_status == "saved",
                rx.el.span("✓ saved",
                           style={"fontSize": "10px", "color": "var(--accent-positive)",
                                  "marginLeft": "8px"}),
                rx.fragment(),
            ),
            style={"display": "flex", "alignItems": "center"},
        ),
        rx.el.p(
            "First-name variants the schedule parser maps to this TM "
            "(e.g. Steve has alias 'stephen').",
            style={"fontSize": "11px", "color": "var(--fg-mute)",
                   "marginBottom": "8px"},
        ),
        rx.cond(
            PeopleState.drawer_aliases.length() > 0,
            rx.el.div(
                rx.foreach(PeopleState.drawer_aliases, _alias_chip),
                style={"display": "flex", "flexWrap": "wrap", "gap": "4px",
                       "marginBottom": "8px"},
            ),
            rx.el.p("No aliases yet.", style={"fontSize": "11px",
                                              "color": "var(--fg-mute)",
                                              "fontStyle": "italic",
                                              "marginBottom": "8px"}),
        ),
        rx.el.div(
            rx.el.input(
                type="text",
                placeholder="Add an alias (e.g. stephen)",
                value=PeopleState.new_alias_input,
                on_change=PeopleState.set_new_alias_input,
                style={
                    "flex": "1", "fontSize": "12px",
                    "padding": "5px 8px",
                    "border": "1px solid var(--border-subtle)",
                    "borderRadius": "var(--r-md)",
                    "background": "var(--surface-card)",
                    "color": "var(--fg-1)",
                    "outline": "none",
                },
            ),
            rx.el.button(
                "Add",
                on_click=PeopleState.add_alias,
                class_name="btn btn-ghost",
                style={"fontSize": "12px", "padding": "5px 12px"},
            ),
            style={"display": "flex", "gap": "6px", "marginBottom": "16px"},
        ),
    )


def add_tm_modal() -> rx.Component:
    """Phase O.3 — Add Team Member overlay."""
    return rx.cond(
        PeopleState.add_tm_open,
        rx.el.div(
            # Backdrop
            rx.el.div(
                on_click=PeopleState.close_add_tm_modal,
                style={
                    "position": "fixed", "inset": "0",
                    "background": "rgba(0,0,0,0.45)",
                    "zIndex": "60",
                },
            ),
            # Panel
            rx.el.div(
                rx.el.div(
                    rx.el.h3("Add Team Member",
                             style={"fontSize": "16px", "fontWeight": "700",
                                    "color": "var(--fg-1)"}),
                    rx.el.button(
                        "✕",
                        on_click=PeopleState.close_add_tm_modal,
                        style={"background": "transparent", "border": "none",
                               "fontSize": "18px", "color": "var(--fg-3)",
                               "cursor": "pointer"},
                    ),
                    style={"display": "flex", "justifyContent": "space-between",
                           "alignItems": "center", "marginBottom": "14px"},
                ),
                # Display name
                rx.el.label("Display Name", class_name="drawer-section-title"),
                rx.el.input(
                    type="text",
                    placeholder="e.g. Sam, Mike S, JT",
                    value=PeopleState.new_tm_display_name,
                    on_change=PeopleState.set_new_tm_display_name,
                    style={
                        "width": "100%", "fontSize": "14px",
                        "padding": "8px 10px", "marginTop": "4px",
                        "marginBottom": "10px",
                        "border": "1px solid var(--border-subtle)",
                        "borderRadius": "var(--r-md)",
                        "background": "var(--surface-card)",
                        "color": "var(--fg-1)",
                        "outline": "none",
                    },
                ),
                # Aliases (comma-separated)
                rx.el.label("Aliases (comma-separated)", class_name="drawer-section-title"),
                rx.el.input(
                    type="text",
                    placeholder="e.g. samantha, sammy",
                    value=PeopleState.new_tm_aliases_text,
                    on_change=PeopleState.set_new_tm_aliases_text,
                    style={
                        "width": "100%", "fontSize": "13px",
                        "padding": "8px 10px", "marginTop": "4px",
                        "marginBottom": "10px",
                        "border": "1px solid var(--border-subtle)",
                        "borderRadius": "var(--r-md)",
                        "background": "var(--surface-card)",
                        "color": "var(--fg-1)",
                        "outline": "none",
                    },
                ),
                # Grave pool
                rx.el.label("Pool", class_name="drawer-section-title"),
                rx.el.select(
                    rx.el.option("Grave",     value="Grave"),
                    rx.el.option("PM Overlap", value="PM"),
                    rx.el.option("AM Overlap", value="AM"),
                    rx.el.option("Other",     value="Other"),
                    value=PeopleState.new_tm_grave_pool,
                    on_change=PeopleState.set_new_tm_grave_pool,
                    style={
                        "width": "100%", "fontSize": "13px",
                        "padding": "7px 10px", "marginTop": "4px",
                        "marginBottom": "12px",
                        "border": "1px solid var(--border-subtle)",
                        "borderRadius": "var(--r-md)",
                        "background": "var(--surface-card)",
                        "color": "var(--fg-1)",
                        "outline": "none",
                    },
                ),
                # Error
                rx.cond(
                    PeopleState.new_tm_error != "",
                    rx.el.p(
                        PeopleState.new_tm_error,
                        style={"fontSize": "12px", "color": "var(--accent-flag)",
                               "marginBottom": "10px"},
                    ),
                    rx.fragment(),
                ),
                # Actions
                rx.el.div(
                    rx.el.button(
                        "Cancel",
                        on_click=PeopleState.close_add_tm_modal,
                        class_name="btn btn-ghost",
                        style={"fontSize": "13px"},
                    ),
                    rx.el.button(
                        rx.cond(PeopleState.new_tm_saving, "Saving…", "Add Team Member"),
                        on_click=PeopleState.save_new_tm,
                        disabled=PeopleState.new_tm_saving,
                        class_name="btn btn-primary",
                        style={"fontSize": "13px"},
                    ),
                    style={"display": "flex", "justifyContent": "flex-end",
                           "gap": "8px"},
                ),
                style={
                    "position": "fixed",
                    "top": "50%", "left": "50%",
                    "transform": "translate(-50%, -50%)",
                    "width": "min(420px, calc(100vw - 32px))",
                    "background": "var(--surface-card)",
                    "border": "1px solid var(--border-subtle)",
                    "borderRadius": "var(--r-lg)",
                    "padding": "20px",
                    "boxShadow": "0 24px 64px rgba(0,0,0,0.32)",
                    "zIndex": "61",
                },
            ),
        ),
        rx.fragment(),
    )


def _merge_option_row(opt: dict) -> rx.Component:
    """One option in the merge dropdown — display + legal name."""
    return rx.el.option(
        opt["display_name"],
        " — ",
        opt["full_name"],
        value=opt["id"],
    )


def merge_modal() -> rx.Component:
    """Phase Q — Merge profiles overlay."""
    return rx.cond(
        PeopleState.merge_open,
        rx.el.div(
            # Backdrop
            rx.el.div(
                on_click=PeopleState.close_merge_modal,
                style={
                    "position": "fixed", "inset": "0",
                    "background": "rgba(0,0,0,0.45)",
                    "zIndex": "60",
                },
            ),
            # Panel
            rx.el.div(
                rx.el.div(
                    rx.el.h3("Merge Profiles",
                             style={"fontSize": "16px", "fontWeight": "700",
                                    "color": "var(--fg-1)"}),
                    rx.el.button(
                        "✕",
                        on_click=PeopleState.close_merge_modal,
                        style={"background": "transparent", "border": "none",
                               "fontSize": "18px", "color": "var(--fg-3)",
                               "cursor": "pointer"},
                    ),
                    style={"display": "flex", "justifyContent": "space-between",
                           "alignItems": "center", "marginBottom": "12px"},
                ),
                rx.el.p(
                    "Pick a TM to merge ", rx.el.b("into "),
                    rx.el.span(PeopleState.drawer_name,
                               style={"color": "var(--accent-blue)",
                                      "fontWeight": "700"}),
                    ". The selected TM's aliases, score history, "
                    "preferences, and FK references will fold into this one. "
                    "The selected TM is then deleted.",
                    style={"fontSize": "12px", "color": "var(--fg-3)",
                           "marginBottom": "10px", "lineHeight": "1.5"},
                ),
                rx.el.label("Merge from", class_name="drawer-section-title"),
                rx.el.select(
                    rx.el.option("— select a TM —", value=""),
                    rx.foreach(PeopleState.merge_options, _merge_option_row),
                    value=PeopleState.merge_drop_id,
                    on_change=PeopleState.set_merge_drop_id,
                    style={
                        "width": "100%", "fontSize": "13px",
                        "padding": "8px 10px", "marginTop": "4px",
                        "marginBottom": "10px",
                        "border": "1px solid var(--border-subtle)",
                        "borderRadius": "var(--r-md)",
                        "background": "var(--surface-card)",
                        "color": "var(--fg-1)",
                        "outline": "none",
                    },
                ),
                rx.el.div(
                    rx.el.p(
                        "⚠ This is irreversible — the selected TM is deleted "
                        "after the merge. Aliases and history are combined; "
                        "any conflicting fields default to ", rx.el.b(PeopleState.drawer_name), ".",
                        style={"fontSize": "11px",
                               "color": "var(--accent-flag)",
                               "lineHeight": "1.5"},
                    ),
                    style={"padding": "8px 10px",
                           "background": "var(--accent-flag-bg)",
                           "border": "1px solid var(--accent-flag)",
                           "borderRadius": "var(--r-md)",
                           "marginBottom": "12px"},
                ),
                rx.cond(
                    PeopleState.merge_error != "",
                    rx.el.p(PeopleState.merge_error,
                            style={"fontSize": "12px",
                                   "color": "var(--accent-flag)",
                                   "marginBottom": "10px"}),
                    rx.fragment(),
                ),
                rx.el.div(
                    rx.el.button(
                        "Cancel",
                        on_click=PeopleState.close_merge_modal,
                        class_name="btn btn-ghost",
                        style={"fontSize": "13px"},
                    ),
                    rx.el.button(
                        rx.cond(PeopleState.merge_saving, "Merging…", "Merge"),
                        on_click=PeopleState.confirm_merge,
                        disabled=PeopleState.merge_saving,
                        class_name="btn btn-primary",
                        style={"fontSize": "13px",
                               "background": "var(--accent-flag)",
                               "borderColor": "var(--accent-flag)"},
                    ),
                    style={"display": "flex", "justifyContent": "flex-end",
                           "gap": "8px"},
                ),
                style={
                    "position": "fixed",
                    "top": "50%", "left": "50%",
                    "transform": "translate(-50%, -50%)",
                    "width": "min(480px, calc(100vw - 32px))",
                    "background": "var(--surface-card)",
                    "border": "1px solid var(--border-subtle)",
                    "borderRadius": "var(--r-lg)",
                    "padding": "20px",
                    "boxShadow": "0 24px 64px rgba(0,0,0,0.32)",
                    "zIndex": "61",
                },
            ),
        ),
        rx.fragment(),
    )


def profile_view() -> rx.Component:
    """Read-only profile view."""
    return rx.el.div(
        # Score row
        rx.el.div(
            rx.el.div(
                rx.el.span("Skill Score", class_name="drawer-section-title"),
                rx.el.span(PeopleState.drawer_score_label,
                           style={"fontSize":"28px","fontWeight":"700","color":"var(--fg-1)","lineHeight":"1"}),
                rx.el.span(" / 10", style={"fontSize":"14px","color":"var(--fg-3)"}),
                style={"display":"flex","alignItems":"baseline","gap":"6px"},
            ),
            _status_badge(PeopleState.drawer_status),
            style={"display":"flex","justifyContent":"space-between","alignItems":"flex-end",
                   "marginBottom":"12px"},
        ),
        # LOA note if set
        rx.cond(
            PeopleState.drawer_loa_note != "",
            rx.el.p(PeopleState.drawer_loa_note,
                    style={"fontSize":"12px","color":"var(--accent-flag)","fontStyle":"italic",
                           "marginBottom":"12px","padding":"8px","background":"var(--accent-flag-bg)",
                           "borderRadius":"var(--r-md)"}),
            rx.fragment(),
        ),
        # Score sparkline (only visible when there's history)
        rx.cond(
            PeopleState.sparkline_svg != "",
            rx.el.div(
                rx.html(PeopleState.sparkline_svg),
                style={"marginBottom":"12px","marginTop":"4px","opacity":"0.85"},
            ),
            rx.fragment(),
        ),
        # Edit + Archive controls
        rx.el.div(
            rx.el.button("Edit Profile", class_name="btn btn-ghost",
                         on_click=PeopleState.start_edit_profile,
                         style={"fontSize":"12px","padding":"6px 12px"}),
            # Phase O follow-up — Archive / Restore (visible based on status)
            rx.cond(
                PeopleState.drawer_status == "archived",
                rx.el.button(
                    "↩ Restore",
                    class_name="btn btn-ghost",
                    on_click=PeopleState.unarchive_current_tm,
                    style={"fontSize":"12px","padding":"6px 12px",
                           "color":"var(--accent-positive)"},
                    title="Restore this TM to active",
                ),
                rx.el.button(
                    "🗄 Archive",
                    class_name="btn btn-ghost",
                    on_click=PeopleState.archive_current_tm,
                    style={"fontSize":"12px","padding":"6px 12px",
                           "color":"var(--fg-3)"},
                    title="Archive this TM — hides from picker, schedule editor, "
                          "and active People views. Restorable any time.",
                ),
            ),
            # Phase Q — Merge into another TM
            rx.el.button(
                "⇆ Merge…",
                class_name="btn btn-ghost",
                on_click=PeopleState.open_merge_modal,
                style={"fontSize":"12px","padding":"6px 12px",
                       "color":"var(--fg-3)"},
                title="Merge this TM into another (combines aliases, history, "
                      "and FK references; deletes this row).",
            ),
            style={"display":"flex","gap":"8px","marginBottom":"16px",
                   "flexWrap":"wrap"},
        ),
        # Phase 2026-05-05 — Roles editor (above aliases since roles drive
        # scheduler behavior and aliases drive name resolution).
        _roles_section(),
        # Phase O.2 — Aliases editor
        _aliases_section(),
        # Score history
        rx.cond(
            PeopleState.drawer_score_history.length() > 0,
            rx.el.div(
                rx.el.p("Score History", class_name="drawer-section-title",
                        style={"marginBottom":"8px"}),
                rx.foreach(PeopleState.drawer_score_history, _score_history_row),
                style={"marginBottom":"16px"},
            ),
            rx.el.p("No score history yet.", style={"fontSize":"12px","color":"var(--fg-mute)"}),
        ),
        class_name="drawer-tab-content",
    )


def profile_edit_form() -> rx.Component:
    """Editable profile form."""
    return rx.el.div(
        rx.el.p("Edit Profile", style={"fontWeight":"600","fontSize":"14px","color":"var(--fg-1)","marginBottom":"14px"}),
        # Phase Q — Display name (canonical reference everywhere)
        rx.el.div(
            rx.el.label("Display Name", class_name="nt-label"),
            rx.el.input(
                type="text",
                value=PeopleState.edit_display_name,
                on_change=PeopleState.set_edit_display_name,
                class_name="nt-input",
                placeholder="e.g. Steve",
            ),
            class_name="nt-field", style={"marginBottom":"10px"},
        ),
        rx.el.div(
            rx.el.label("Legal / Full Name", class_name="nt-label"),
            rx.el.input(
                type="text",
                value=PeopleState.edit_full_name,
                on_change=PeopleState.set_edit_full_name,
                class_name="nt-input",
                placeholder="e.g. Stephen Edmunds",
            ),
            class_name="nt-field", style={"marginBottom":"10px"},
        ),
        # Skill score input
        rx.el.div(
            rx.el.label("Skill Score (1–10)", class_name="nt-label"),
            rx.el.input(type="number", min="0.5", max="10", step="0.5",
                        value=PeopleState.edit_score,
                        on_change=PeopleState.set_edit_score,
                        class_name="nt-input",
                        style={"width":"100px"}),
            class_name="nt-field", style={"marginBottom":"10px"},
        ),
        # Score change reason
        rx.el.div(
            rx.el.label("Reason for change (optional)", class_name="nt-label"),
            rx.el.input(placeholder="e.g. solid week, great Z9 coverage",
                        value=PeopleState.edit_score_reason,
                        on_change=PeopleState.set_edit_score_reason,
                        class_name="nt-input"),
            class_name="nt-field", style={"marginBottom":"10px"},
        ),
        # Status
        rx.el.div(
            rx.el.label("Status", class_name="nt-label"),
            rx.el.select(
                rx.el.option("Active",    value="active"),
                rx.el.option("LOA",       value="loa"),
                rx.el.option("Separated", value="separated"),
                value=PeopleState.edit_status,
                on_change=PeopleState.set_edit_status,
                class_name="nt-select",
            ),
            class_name="nt-field", style={"marginBottom":"10px"},
        ),
        # LOA note
        rx.cond(
            PeopleState.edit_status == "loa",
            rx.el.div(
                rx.el.label("LOA Note", class_name="nt-label"),
                rx.el.input(placeholder="e.g. Out until 6/1, returning after surgery",
                            value=PeopleState.edit_loa_note,
                            on_change=PeopleState.set_edit_loa_note,
                            class_name="nt-input"),
                class_name="nt-field", style={"marginBottom":"10px"},
            ),
            rx.fragment(),
        ),
        # Save status feedback
        rx.cond(
            PeopleState.profile_status == "saved",
            rx.el.p("✓ Saved", style={"fontSize":"12px","color":"var(--accent-positive)","margin":"0 0 8px"}),
            rx.cond(
                PeopleState.profile_status == "error",
                rx.el.p(
                    rx.cond(
                        PeopleState.profile_error != "",
                        PeopleState.profile_error,
                        "Save failed — check connection",
                    ),
                    style={"fontSize":"12px","color":"var(--accent-flag)","margin":"0 0 8px"},
                ),
                rx.fragment(),
            ),
        ),
        # Buttons
        rx.el.div(
            rx.el.button(
                rx.cond(PeopleState.profile_saving, "Saving…", "Save"),
                class_name="btn btn-primary",
                on_click=PeopleState.save_profile,
                disabled=~PeopleState.can_save_profile,
                style={"fontSize":"13px","padding":"7px 16px"},
            ),
            rx.el.button("Cancel", class_name="btn btn-ghost",
                         on_click=PeopleState.cancel_edit_profile,
                         style={"fontSize":"13px","padding":"7px 12px"}),
            style={"display":"flex","gap":"8px"},
        ),
        class_name="drawer-tab-content",
    )


def profile_tab() -> rx.Component:
    return rx.cond(
        PeopleState.editing_profile,
        profile_edit_form(),
        profile_view(),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB: ELIGIBILITY
# ═══════════════════════════════════════════════════════════════════════════════

def _elig_slot_row(item: dict) -> rx.Component:
    return rx.el.div(
        rx.el.span(item["slot"],
                   style={"fontSize":"12px","color":"var(--fg-2)","flex":"1"}),
        rx.el.div(
            on_click=PeopleState.toggle_elig(item["slot"]),
            class_name=rx.cond(
                item["eligible"],
                "elig-toggle elig-toggle-yes",
                "elig-toggle elig-toggle-no",
            ),
            style={"cursor":"pointer"},
        ),
        style={"display":"flex","alignItems":"center","justifyContent":"space-between",
               "padding":"5px 0","borderBottom":"1px solid var(--border-subtle)"},
    )


def _elig_group(group_name: str) -> rx.Component:
    """Render all items in one eligibility group via filtered foreach."""
    return rx.el.div(
        rx.el.p(group_name, class_name="drawer-section-title",
                style={"marginBottom":"6px","marginTop":"12px"}),
        rx.foreach(
            PeopleState.drawer_eligibility,
            lambda item: rx.cond(
                item["group"] == group_name,
                _elig_slot_row(item),
                rx.fragment(),
            ),
        ),
    )


def eligibility_tab() -> rx.Component:
    return rx.el.div(
        # Stats + save button row
        rx.el.div(
            rx.el.span(
                PeopleState.drawer_elig_count.to_string(), " slots eligible",
                style={"fontSize":"13px","color":"var(--fg-2)"},
            ),
            rx.cond(
                PeopleState.elig_dirty,
                rx.el.button(
                    rx.cond(PeopleState.elig_saving, "Saving…", "Save Changes"),
                    class_name="btn btn-primary",
                    on_click=PeopleState.save_eligibility,
                    disabled=PeopleState.elig_saving,
                    style={"fontSize":"12px","padding":"5px 12px"},
                ),
                rx.cond(
                    PeopleState.elig_status == "saved",
                    rx.el.span("✓ Saved", style={"fontSize":"12px","color":"var(--accent-positive)"}),
                    rx.fragment(),
                ),
            ),
            style={"display":"flex","justifyContent":"space-between","alignItems":"center",
                   "marginBottom":"4px"},
        ),
        # Groups
        _elig_group("Zones"),
        _elig_group("Men's RR"),
        _elig_group("Women's RR"),
        _elig_group("Support"),
        class_name="drawer-tab-content",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB: PREFERENCES & AFFINITIES
# ═══════════════════════════════════════════════════════════════════════════════

def _pref_row(item: dict, idx: int) -> rx.Component:
    stance_cls = rx.cond(item["stance"] == "avoid", "chip chip-flag", "chip chip-positive")
    strength_cls = rx.cond(item["strength"] == "hard", "chip chip-flag", "chip chip-blue")
    return rx.el.div(
        rx.el.div(
            rx.el.span(item["stance"],   class_name=stance_cls),
            rx.el.span(item["strength"], class_name=strength_cls),
            rx.el.span(item.get("target",""), style={"fontSize":"12px","color":"var(--fg-2)","flex":"1"}),
            rx.el.button("✕", on_click=PeopleState.remove_pref(idx),
                         style={"background":"none","border":"none","color":"var(--fg-mute)",
                                "cursor":"pointer","fontSize":"11px","padding":"0 2px"}),
            style={"display":"flex","gap":"6px","alignItems":"center","flexWrap":"wrap"},
        ),
        rx.cond(item.get("note","") != "",
            rx.el.p(item.get("note",""), style={"fontSize":"11px","color":"var(--fg-3)","margin":"3px 0 0","fontStyle":"italic"}),
            rx.fragment()),
        class_name="pref-row",
    )


def _add_pref_form() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.label("Stance", class_name="nt-label"),
                rx.el.select(
                    rx.el.option("Avoid",  value="avoid"),
                    rx.el.option("Prefer", value="prefer"),
                    value=PeopleState.new_pref_stance,
                    on_change=PeopleState.set_pref_stance,
                    class_name="nt-select",
                ),
                class_name="nt-field",
            ),
            rx.el.div(
                rx.el.label("Strength", class_name="nt-label"),
                rx.el.select(
                    rx.el.option("Soft", value="soft"),
                    rx.el.option("Hard", value="hard"),
                    value=PeopleState.new_pref_strength,
                    on_change=PeopleState.set_pref_strength,
                    class_name="nt-select",
                ),
                class_name="nt-field",
            ),
            class_name="nt-row",style={"marginBottom":"8px"},
        ),
        rx.el.input(placeholder="Target slot/area (e.g. Zone 9 SR, area:Lobby)",
                    value=PeopleState.new_pref_target,
                    on_change=PeopleState.set_pref_target,
                    class_name="nt-input",style={"marginBottom":"6px"}),
        rx.el.input(placeholder="Note (optional)",
                    value=PeopleState.new_pref_note,
                    on_change=PeopleState.set_pref_note,
                    class_name="nt-input nt-input-sm",style={"marginBottom":"10px"}),
        rx.el.div(
            rx.el.button(rx.cond(PeopleState.pref_saving, "Saving…", "Add"),
                         class_name="btn btn-primary",on_click=PeopleState.save_pref,
                         style={"fontSize":"12px","padding":"5px 12px"}),
            rx.el.button("Cancel", class_name="btn btn-ghost",on_click=PeopleState.close_pref_form,
                         style={"fontSize":"12px","padding":"5px 10px"}),
            style={"display":"flex","gap":"6px"},
        ),
        class_name="add-form-inset",
    )


def _aff_row(item: dict, idx: int) -> rx.Component:
    stance_cls = rx.cond(item["stance"] == "avoid", "chip chip-flag", "chip chip-positive")
    return rx.el.div(
        rx.el.div(
            rx.el.span(item["stance"], class_name=stance_cls),
            rx.el.span(item.get("with",""), style={"fontSize":"13px","fontWeight":"600","color":"var(--fg-1)","flex":"1"}),
            rx.el.span(item.get("strength","soft"), style={"fontSize":"11px","color":"var(--fg-3)"}),
            rx.el.button("✕", on_click=PeopleState.remove_aff(idx),
                         style={"background":"none","border":"none","color":"var(--fg-mute)",
                                "cursor":"pointer","fontSize":"11px","padding":"0 2px"}),
            style={"display":"flex","gap":"6px","alignItems":"center"},
        ),
        rx.cond(item.get("note","") != "",
            rx.el.p(item.get("note",""), style={"fontSize":"11px","color":"var(--fg-3)","margin":"3px 0 0","fontStyle":"italic"}),
            rx.fragment()),
        class_name="pref-row",
    )


def _add_aff_form() -> rx.Component:
    return rx.el.div(
        rx.el.input(placeholder="Team member name (e.g. Joy, Melissa)",
                    value=PeopleState.new_aff_with,
                    on_change=PeopleState.set_aff_with,
                    class_name="nt-input",style={"marginBottom":"8px"}),
        rx.el.div(
            rx.el.div(
                rx.el.label("Stance",   class_name="nt-label"),
                rx.el.select(
                    rx.el.option("Avoid",  value="avoid"),
                    rx.el.option("Prefer", value="prefer"),
                    value=PeopleState.new_aff_stance,
                    on_change=PeopleState.set_aff_stance,class_name="nt-select",
                ),
                class_name="nt-field",
            ),
            rx.el.div(
                rx.el.label("Strength", class_name="nt-label"),
                rx.el.select(
                    rx.el.option("Soft", value="soft"),
                    rx.el.option("Hard", value="hard"),
                    value=PeopleState.new_aff_strength,
                    on_change=PeopleState.set_aff_strength,class_name="nt-select",
                ),
                class_name="nt-field",
            ),
            class_name="nt-row",style={"marginBottom":"8px"},
        ),
        rx.el.input(placeholder="Note (optional)",
                    value=PeopleState.new_aff_note,
                    on_change=PeopleState.set_aff_note,
                    class_name="nt-input nt-input-sm",style={"marginBottom":"10px"}),
        rx.el.div(
            rx.el.button(rx.cond(PeopleState.aff_saving, "Saving…", "Add"),
                         class_name="btn btn-primary",on_click=PeopleState.save_aff,
                         style={"fontSize":"12px","padding":"5px 12px"}),
            rx.el.button("Cancel", class_name="btn btn-ghost",on_click=PeopleState.close_aff_form,
                         style={"fontSize":"12px","padding":"5px 10px"}),
            style={"display":"flex","gap":"6px"},
        ),
        class_name="add-form-inset",
    )


def _accom_row(item: dict, idx: int) -> rx.Component:
    sev_cls = rx.cond(item["severity"] == "absolute", "chip chip-flag",
                  rx.cond(item["severity"] == "hard", "chip chip-flag", "chip chip-blue"))
    return rx.el.div(
        rx.el.div(
            rx.el.span(item["type"],     class_name="chip"),
            rx.el.span(item["severity"], class_name=sev_cls),
            rx.cond(item.get("target","") != "",
                rx.el.span(item.get("target",""), style={"fontSize":"11px","color":"var(--fg-3)","flex":"1"}),
                rx.el.span(style={"flex":"1"})),
            rx.el.button("✕", on_click=PeopleState.remove_accom(idx),
                         style={"background":"none","border":"none","color":"var(--fg-mute)",
                                "cursor":"pointer","fontSize":"11px","padding":"0 2px"}),
            style={"display":"flex","gap":"6px","alignItems":"center","flexWrap":"wrap"},
        ),
        rx.cond(item.get("note","") != "",
            rx.el.p(item.get("note",""), style={"fontSize":"11px","color":"var(--fg-3)","margin":"3px 0 0","fontStyle":"italic"}),
            rx.fragment()),
        class_name="pref-row",
    )


def _add_accom_form() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.label("Type",     class_name="nt-label"),
                rx.el.select(
                    rx.el.option("Physical",  value="physical"),
                    rx.el.option("Sensory",   value="sensory"),
                    rx.el.option("Medical",   value="medical"),
                    rx.el.option("Temporary", value="temporary"),
                    rx.el.option("AM Overlap Only", value="am_overlap_only"),
                    rx.el.option("Other",     value="other"),
                    value=PeopleState.new_accom_type,
                    on_change=PeopleState.set_accom_type,class_name="nt-select",
                ),
                class_name="nt-field",
            ),
            rx.el.div(
                rx.el.label("Severity", class_name="nt-label"),
                rx.el.select(
                    rx.el.option("Soft",     value="soft"),
                    rx.el.option("Hard",     value="hard"),
                    rx.el.option("Absolute", value="absolute"),
                    value=PeopleState.new_accom_severity,
                    on_change=PeopleState.set_accom_severity,class_name="nt-select",
                ),
                class_name="nt-field",
            ),
            class_name="nt-row",style={"marginBottom":"8px"},
        ),
        rx.el.input(placeholder="Target (e.g. category:sweeper, Zone 9 SR)",
                    value=PeopleState.new_accom_target,
                    on_change=PeopleState.set_accom_target,
                    class_name="nt-input",style={"marginBottom":"6px"}),
        rx.el.input(placeholder="Note describing the accommodation",
                    value=PeopleState.new_accom_note,
                    on_change=PeopleState.set_accom_note,
                    class_name="nt-input nt-input-sm",style={"marginBottom":"10px"}),
        rx.el.div(
            rx.el.button(rx.cond(PeopleState.accom_saving, "Saving…", "Add"),
                         class_name="btn btn-primary",on_click=PeopleState.save_accom,
                         style={"fontSize":"12px","padding":"5px 12px"}),
            rx.el.button("Cancel", class_name="btn btn-ghost",on_click=PeopleState.close_accom_form,
                         style={"fontSize":"12px","padding":"5px 10px"}),
            style={"display":"flex","gap":"6px"},
        ),
        class_name="add-form-inset",
    )


def preferences_tab() -> rx.Component:
    return rx.el.div(
        # Accommodations section
        rx.el.div(
            rx.el.div(
                rx.el.span("Accommodations", class_name="drawer-section-title"),
                rx.cond(
                    ~PeopleState.accom_adding,
                    rx.el.button("+ Add", class_name="btn btn-ghost",
                                 on_click=PeopleState.open_accom_form,
                                 style={"fontSize":"11px","padding":"3px 8px"}),
                    rx.fragment(),
                ),
                class_name="drawer-section-head",
            ),
            rx.cond(
                PeopleState.accom_adding,
                _add_accom_form(),
                rx.fragment(),
            ),
            rx.cond(
                PeopleState.drawer_accommodations.length() > 0,
                rx.foreach(PeopleState.drawer_accommodations,
                           lambda item, idx: _accom_row(item, idx)),
                rx.el.p("No accommodations recorded.",
                        style={"fontSize":"12px","color":"var(--fg-mute)","padding":"6px 0"}),
            ),
        ),
        rx.el.div(class_name="pref-section-divider"),
        # Placement Preferences section
        rx.el.div(
            rx.el.div(
                rx.el.span("Placement Preferences", class_name="drawer-section-title"),
                rx.cond(
                    ~PeopleState.pref_adding,
                    rx.el.button("+ Add", class_name="btn btn-ghost",
                                 on_click=PeopleState.open_pref_form,
                                 style={"fontSize":"11px","padding":"3px 8px"}),
                    rx.fragment(),
                ),
                class_name="drawer-section-head",
            ),
            rx.cond(
                PeopleState.pref_adding,
                _add_pref_form(),
                rx.fragment(),
            ),
            rx.cond(
                PeopleState.drawer_preferences.length() > 0,
                rx.foreach(PeopleState.drawer_preferences,
                           lambda item, idx: _pref_row(item, idx)),
                rx.el.p("No placement preferences recorded.",
                        style={"fontSize":"12px","color":"var(--fg-mute)","padding":"6px 0"}),
            ),
        ),
        rx.el.div(class_name="pref-section-divider"),
        # Pair Affinities section
        rx.el.div(
            rx.el.div(
                rx.el.span("Pair Affinities", class_name="drawer-section-title"),
                rx.cond(
                    ~PeopleState.aff_adding,
                    rx.el.button("+ Add", class_name="btn btn-ghost",
                                 on_click=PeopleState.open_aff_form,
                                 style={"fontSize":"11px","padding":"3px 8px"}),
                    rx.fragment(),
                ),
                class_name="drawer-section-head",
            ),
            rx.cond(
                PeopleState.aff_adding,
                _add_aff_form(),
                rx.fragment(),
            ),
            rx.cond(
                PeopleState.drawer_affinities.length() > 0,
                rx.foreach(PeopleState.drawer_affinities,
                           lambda item, idx: _aff_row(item, idx)),
                rx.el.p("No pair affinities recorded.",
                        style={"fontSize":"12px","color":"var(--fg-mute)","padding":"6px 0"}),
            ),
        ),
        class_name="drawer-tab-content",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB: NOTES
# ═══════════════════════════════════════════════════════════════════════════════

def drawer_note_row(note: dict) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(note["icon"],             class_name="drawer-note-icon"),
            rx.el.span(note["note_type"],        class_name="drawer-note-type"),
            rx.el.span(note["timestamp_display"],class_name="drawer-note-ts"),
            class_name="drawer-note-meta",
        ),
        rx.el.p(note["text"], class_name="drawer-note-text"),
        class_name="drawer-note-row",
    )


def notes_tab() -> rx.Component:
    return rx.el.div(
        rx.cond(
            PeopleState.drawer_note_count > 0,
            rx.foreach(PeopleState.drawer_notes, drawer_note_row),
            rx.el.p("No notes found for this team member.",
                    style={"color":"var(--fg-3)","fontSize":"13px","padding":"20px 0","textAlign":"center"}),
        ),
        class_name="drawer-tab-content",
        style={"padding":"0"},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# FULL DRAWER
# ═══════════════════════════════════════════════════════════════════════════════

def profile_drawer() -> rx.Component:
    return rx.cond(
        PeopleState.drawer_open,
        rx.el.div(
            rx.el.div(on_click=PeopleState.close_drawer, class_name="drawer-scrim"),
            rx.el.div(
                drawer_header(),
                drawer_tabs(),
                # Loading state
                rx.cond(
                    PeopleState.drawer_loading,
                    rx.el.div(
                        *[rx.el.div(
                            rx.el.div(class_name="skel skel-sm",
                                      style={"width":"120px","marginBottom":"8px"}),
                            rx.el.div(class_name="skel skel-md",
                                      style={"width":"85%","marginBottom":"6px"}),
                            rx.el.div(class_name="skel skel-sm",
                                      style={"width":"60%"}),
                            style={"padding":"16px 20px","borderBottom":"1px solid var(--border-subtle)"},
                          ) for _ in range(4)],
                    ),
                    # Tab router
                    rx.cond(
                        PeopleState.drawer_tab == "profile",      profile_tab(),
                        rx.cond(
                        PeopleState.drawer_tab == "eligibility",  eligibility_tab(),
                        rx.cond(
                        PeopleState.drawer_tab == "preferences",  preferences_tab(),
                        notes_tab()))),
                ),
                # Footer: Log button
                rx.el.div(
                    rx.el.button(
                        "+ Log observation for ",
                        rx.el.strong(PeopleState.drawer_name),
                        class_name="btn btn-primary",
                        on_click=AppState.open_capture_for(PeopleState.drawer_name),
                        style={"width":"100%","justifyContent":"center","fontSize":"13px"},
                    ),
                    class_name="drawer-footer",
                ),
                class_name="drawer-panel",
                style={"width":"460px"},
            ),
            class_name="drawer-root",
        ),
        rx.fragment(),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE
# ═══════════════════════════════════════════════════════════════════════════════

def people_page() -> rx.Component:
    return rx.el.div(
        sidebar(),
        rx.el.main(
            rx.el.header(
                rx.el.div("Team", class_name="page-eyebrow"),
                rx.el.h1("People", class_name="page-title"),
                class_name="page-head",
            ),
            # Search
            rx.el.div(
                rx.el.input(
                    placeholder="Search team members…",
                    value=PeopleState.search_query,
                    on_change=PeopleState.set_search,
                    class_name="people-search-input",
                ),
                class_name="people-search-wrap",
            ),
            # Controls: pool filter + sort + view toggle
            people_controls(),
            # Content
            rx.cond(
                PeopleState.loading,
                people_skeleton(),
                rx.cond(
                    PeopleState.people_count > 0,
                    rx.cond(
                        PeopleState.view_mode == "list",
                        # List view
                        rx.el.div(
                            rx.foreach(PeopleState.filtered_people, tm_list_row),
                            class_name="people-list",
                        ),
                        # Grid view (default)
                        rx.el.div(
                            rx.foreach(PeopleState.filtered_people, tm_card),
                            class_name="people-grid",
                        ),
                    ),
                    empty_state("No team members found", "Try a different filter or search term."),
                ),
            ),
            class_name="main",
        ),
        rx.el.button("+", class_name="fab", on_click=AppState.open_capture,
                     title="Capture (⌘N)", aria_label="Quick capture"),
        profile_drawer(),
        # Phase O.3 — Add TM modal
        add_tm_modal(),
        # Phase Q — Merge Profiles modal
        merge_modal(),
        command_palette(),
        capture_modal(),
        class_name=AppState.app_class_name,
    )
