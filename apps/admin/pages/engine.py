"""
apps/admin/pages/engine.py — Engine Configurator (Phase 4c).

Route: /admin/engine
5-tab configurator: Weights | Thresholds | Headcount | Slot Difficulty | History
+ Simulation pane (on Weights tab).
"""

import reflex as rx
from shared.components.admin_section_head import admin_breadcrumb
from apps.admin.engine_state import EngineConfiguratorState, WEIGHT_KEYS, WEIGHT_LABELS, DOW_KEYS


# ── Reusable btn style helpers ──────────────────────────────────────────────

def _btn(label: str, on_click, variant: str = "default") -> rx.Component:
    """Small action button."""
    base = {
        "padding": "7px 18px",
        "fontSize": "13px",
        "fontWeight": "600",
        "borderRadius": "6px",
        "border": "1px solid var(--border-subtle)",
        "cursor": "pointer",
        "fontFamily": "var(--font)",
        "transition": "opacity 0.12s",
    }
    if variant == "primary":
        base.update({
            "background": "var(--accent-blue)",
            "color": "#fff",
            "border": "none",
        })
    elif variant == "danger":
        base.update({
            "background": "transparent",
            "color": "var(--ink3)",
        })
    else:
        base.update({
            "background": "var(--surface-card)",
            "color": "var(--ink2)",
        })
    return rx.el.button(label, on_click=on_click, style=base)


# ── Tab strip ───────────────────────────────────────────────────────────────

TAB_LABELS = ["Weights", "Thresholds", "Headcount", "Slot Difficulty", "History"]


def _tab_strip() -> rx.Component:
    def _tab(label: str, idx: int) -> rx.Component:
        return rx.el.button(
            label,
            on_click=EngineConfiguratorState.set_tab(idx),
            class_name=rx.cond(
                EngineConfiguratorState.active_tab == idx,
                "engine-tab-btn active",
                "engine-tab-btn",
            ),
        )
    return rx.el.div(
        *[_tab(label, i) for i, label in enumerate(TAB_LABELS)],
        class_name="engine-tab-strip",
    )


# ── Weights tab ──────────────────────────────────────────────────────────────

def _weight_row(key: str) -> rx.Component:
    label = WEIGHT_LABELS.get(key, key)
    attr  = f"w_{key}"
    # Phase 4e hotfix: slider max bumped from 1 → 3. Production weights include
    # preference_fit=1.5 and override_* at 1.5 — max=1 was clipping visible values.
    return rx.el.div(
        rx.el.div(label, class_name="engine-weight-label"),
        rx.el.div(
            rx.el.input(
                type="range",
                min="0",
                max="3",
                step="0.05",
                value=getattr(EngineConfiguratorState, attr),
                on_change=lambda v: EngineConfiguratorState.set_weight(key, v),
                class_name="engine-weight-slider",
            ),
            rx.el.input(
                type="number",
                min="0",
                max="3",
                step="0.05",
                value=getattr(EngineConfiguratorState, attr),
                on_change=lambda v: EngineConfiguratorState.set_weight(key, v),
                class_name="engine-weight-number",
            ),
            class_name="engine-weight-controls",
        ),
        class_name="engine-weight-row",
    )


def _weights_tab() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            *[_weight_row(k) for k in WEIGHT_KEYS],
            class_name="engine-weight-grid",
        ),
        _sim_pane(),
    )


# ── Thresholds tab ───────────────────────────────────────────────────────────

def _threshold_field(label: str, value_var, on_change, type_: str = "number") -> rx.Component:
    return rx.el.div(
        rx.el.div(label, class_name="engine-threshold-label"),
        rx.el.input(
            type=type_,
            value=value_var,
            on_change=on_change,
            class_name="engine-threshold-input",
        ),
        class_name="engine-threshold-row",
    )


def _placement_method_toggle() -> rx.Component:
    """Phase 4f: radio toggle for greedy vs LAP placement algorithm."""
    return rx.el.div(
        rx.el.div("Placement Algorithm", class_name="engine-threshold-label",
                  style={"margin_bottom": "8px", "font_weight": "600"}),
        rx.el.div(
            # Greedy radio
            rx.el.label(
                rx.el.input(
                    type="radio",
                    name="placement_method",
                    value="greedy",
                    checked=EngineConfiguratorState.placement_method == "greedy",
                    on_change=lambda _: EngineConfiguratorState.set_placement_method("greedy"),
                    style={"margin_right": "6px"},
                ),
                rx.el.span("Greedy", style={"margin_right": "4px"}),
                rx.el.span("(default — sequential fill)",
                           style={"color": "var(--ops-text-muted)", "font_size": "0.78rem"}),
                style={"display": "flex", "align_items": "center",
                       "gap": "2px", "cursor": "pointer", "margin_bottom": "6px"},
            ),
            # LAP radio
            rx.el.label(
                rx.el.input(
                    type="radio",
                    name="placement_method",
                    value="lap",
                    checked=EngineConfiguratorState.placement_method == "lap",
                    on_change=lambda _: EngineConfiguratorState.set_placement_method("lap"),
                    style={"margin_right": "6px"},
                ),
                rx.el.span("LAP / Hungarian solver", style={"margin_right": "4px"}),
                rx.el.span("(global 22-slot optimize — improves Z8 fill)",
                           style={"color": "var(--ops-text-muted)", "font_size": "0.78rem"}),
                style={"display": "flex", "align_items": "center",
                       "gap": "2px", "cursor": "pointer"},
            ),
            style={"padding": "10px 14px",
                   "border": "1px solid var(--ops-border)",
                   "border_radius": "6px",
                   "background": "var(--ops-surface-raised)"},
        ),
        class_name="engine-threshold-row",
        style={"flex_direction": "column", "align_items": "flex-start"},
    )


def _thresholds_tab() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            _threshold_field(
                "Difficulty Threshold",
                EngineConfiguratorState.t_override_difficulty_threshold,
                EngineConfiguratorState.set_difficulty_threshold,
            ),
            _threshold_field(
                "Load Threshold",
                EngineConfiguratorState.t_override_load_threshold,
                EngineConfiguratorState.set_load_threshold,
            ),
            _threshold_field(
                "Fatigue Window (days)",
                EngineConfiguratorState.t_fatigue_window_days,
                EngineConfiguratorState.set_fatigue_window,
            ),
            _threshold_field(
                "Rotation Window (weeks)",
                EngineConfiguratorState.t_rotation_weeks,
                EngineConfiguratorState.set_rotation_weeks,
            ),
            _placement_method_toggle(),
            class_name="engine-threshold-grid",
        ),
    )


# ── Headcount tab ────────────────────────────────────────────────────────────

def _hc_cell(dow: str) -> rx.Component:
    attr = f"hc_{dow.lower()}"
    return rx.el.div(
        rx.el.div(dow[:3].upper(), class_name="engine-headcount-dow"),
        rx.el.input(
            type="number",
            min="0",
            max="30",
            value=getattr(EngineConfiguratorState, attr),
            on_change=lambda v: EngineConfiguratorState.set_headcount(dow, v),
            class_name="engine-headcount-input",
        ),
        class_name="engine-headcount-cell",
    )


def _headcount_tab() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            *[_hc_cell(dow) for dow in DOW_KEYS],
            class_name="engine-headcount-grid",
        ),
    )


# ── Slot difficulty tab ───────────────────────────────────────────────────────

def _slot_difficulty_tab() -> rx.Component:
    def _row(item: dict) -> rx.Component:
        return rx.el.tr(
            rx.el.td(item["slot"]),
            rx.el.td(
                item["priority"],
                class_name=rx.cond(
                    item["priority"] == "high",
                    "engine-slot-priority-high",
                    "engine-slot-priority-low",
                ),
            ),
        )
    return rx.el.div(
        rx.el.table(
            rx.el.thead(
                rx.el.tr(
                    rx.el.th("Slot"),
                    rx.el.th("Priority"),
                ),
            ),
            rx.el.tbody(
                rx.foreach(EngineConfiguratorState.slot_difficulty_rows, _row),
            ),
            class_name="engine-slot-table",
        ),
    )


# ── History tab ───────────────────────────────────────────────────────────────

def _history_tab() -> rx.Component:
    def _hist_row(item: dict) -> rx.Component:
        return rx.el.div(
            rx.el.span(
                item["created_at"].to(str)[:16],
                class_name="engine-history-ts",
            ),
            rx.el.span(
                item["changed_by"],
                class_name="engine-history-by",
            ),
            class_name="engine-history-row",
        )
    return rx.cond(
        EngineConfiguratorState.history_loading,
        rx.el.div("Loading…", style={"color": "var(--ink3)", "fontSize": "13px"}),
        rx.cond(
            EngineConfiguratorState.history_rows.length() == 0,
            rx.el.div("No history yet.", style={"color": "var(--ink3)", "fontSize": "13px"}),
            rx.el.div(
                rx.foreach(EngineConfiguratorState.history_rows, _hist_row),
                class_name="engine-history-list",
            ),
        ),
    )


# ── Simulation pane ───────────────────────────────────────────────────────────

def _sim_mode_toggle() -> rx.Component:
    """Single-shot vs Multi-week toggle pills."""
    def _pill(label: str, mode: str) -> rx.Component:
        return rx.el.button(
            label,
            on_click=EngineConfiguratorState.set_sim_mode(mode),
            style={
                "padding": "4px 12px",
                "fontSize": "11px",
                "fontWeight": "600",
                "borderRadius": "999px",
                "border": "1px solid var(--border-subtle)",
                "cursor": "pointer",
                "background": rx.cond(
                    EngineConfiguratorState.sim_mode == mode,
                    "var(--accent-amber)",
                    "transparent",
                ),
                "color": rx.cond(
                    EngineConfiguratorState.sim_mode == mode,
                    "#000",
                    "var(--ink2)",
                ),
                "transition": "background 0.15s",
            },
        )
    return rx.el.div(
        _pill("Single-shot", "single"),
        _pill("Multi-week", "multi"),
        style={
            "display": "flex",
            "gap": "6px",
            "background": "var(--surface2)",
            "borderRadius": "999px",
            "padding": "3px",
            "border": "1px solid var(--border-subtle)",
        },
    )


def _msim_config_row(label: str, control: rx.Component) -> rx.Component:
    """Compact label + control row for multi-week sim settings."""
    return rx.el.div(
        rx.el.span(label, style={
            "fontSize": "11px",
            "color": "var(--ink2)",
            "minWidth": "120px",
        }),
        control,
        style={"display": "flex", "alignItems": "center", "gap": "10px"},
    )


def _msim_stat(label: str, value: rx.Component, warn: bool = False) -> rx.Component:
    return rx.el.div(
        rx.el.div(label, class_name="engine-sim-stat-label"),
        rx.el.div(
            value,
            class_name=rx.cond(
                warn,
                "engine-sim-stat-value engine-sim-unresolved-badge",
                "engine-sim-stat-value",
            ),
        ),
        class_name="engine-sim-stat",
    )


def _sim_pane() -> rx.Component:
    return rx.el.div(
        # ── Header row: title + mode toggle ─────────────────────────────
        rx.el.div(
            rx.el.span("Simulation", class_name="engine-sim-title"),
            _sim_mode_toggle(),
            style={"display": "flex", "alignItems": "center",
                   "justifyContent": "space-between", "marginBottom": "12px"},
        ),

        # ── SINGLE-SHOT mode ─────────────────────────────────────────────
        rx.cond(
            EngineConfiguratorState.sim_mode == "single",
            rx.el.div(
                _btn(
                    rx.cond(EngineConfiguratorState.simulating, "Running…", "Run Simulation"),
                    EngineConfiguratorState.run_simulation,
                    variant="default",
                ),
                rx.cond(
                    EngineConfiguratorState.sim_error != "",
                    rx.el.div(EngineConfiguratorState.sim_error, class_name="engine-sim-error"),
                    rx.fragment(),
                ),
                rx.cond(
                    EngineConfiguratorState.sim_ran,
                    rx.el.div(
                        rx.el.div(
                            _msim_stat("Placed",
                                       EngineConfiguratorState.sim_placements.length().to(str)),
                            _msim_stat("Unresolved",
                                       EngineConfiguratorState.sim_unresolved.length().to(str),
                                       warn=EngineConfiguratorState.sim_unresolved.length() > 0),
                            class_name="engine-sim-stats",
                        ),
                    ),
                    rx.fragment(),
                ),
                style={"display": "flex", "flexDirection": "column", "gap": "10px"},
            ),

            # ── MULTI-WEEK mode ──────────────────────────────────────────
            rx.el.div(
                # Config controls
                rx.el.div(
                    _msim_config_row("Schedules (weeks)",
                        rx.el.input(
                            type="number", min="1", max="8",
                            value=EngineConfiguratorState.msim_weeks.to(str),
                            on_change=EngineConfiguratorState.set_msim_weeks,
                            style={"width": "60px", "fontSize": "12px",
                                   "padding": "2px 6px", "borderRadius": "4px",
                                   "border": "1px solid var(--border-subtle)",
                                   "background": "var(--surface2)", "color": "var(--ink1)"},
                        ),
                    ),
                    _msim_config_row("Runs / schedule",
                        rx.el.input(
                            type="number", min="1", max="20",
                            value=EngineConfiguratorState.msim_runs.to(str),
                            on_change=EngineConfiguratorState.set_msim_runs,
                            style={"width": "60px", "fontSize": "12px",
                                   "padding": "2px 6px", "borderRadius": "4px",
                                   "border": "1px solid var(--border-subtle)",
                                   "background": "var(--surface2)", "color": "var(--ink1)"},
                        ),
                    ),
                    _msim_config_row("Call-off rate (λ)",
                        rx.el.input(
                            type="number", min="0", max="10", step="0.5",
                            value=EngineConfiguratorState.msim_callout_rate.to(str),
                            on_change=EngineConfiguratorState.set_msim_callout_rate,
                            style={"width": "70px", "fontSize": "12px",
                                   "padding": "2px 6px", "borderRadius": "4px",
                                   "border": "1px solid var(--border-subtle)",
                                   "background": "var(--surface2)", "color": "var(--ink1)"},
                        ),
                    ),
                    _msim_config_row("RNG seed",
                        rx.el.input(
                            type="number",
                            value=EngineConfiguratorState.msim_seed.to(str),
                            on_change=EngineConfiguratorState.set_msim_seed,
                            style={"width": "80px", "fontSize": "12px",
                                   "padding": "2px 6px", "borderRadius": "4px",
                                   "border": "1px solid var(--border-subtle)",
                                   "background": "var(--surface2)", "color": "var(--ink1)"},
                        ),
                    ),
                    _msim_config_row("Compare baseline",
                        rx.el.input(
                            type="checkbox",
                            checked=EngineConfiguratorState.msim_compare_baseline,
                            on_change=EngineConfiguratorState.set_msim_compare_baseline,
                            style={"accentColor": "var(--accent-amber)"},
                        ),
                    ),
                    style={"display": "flex", "flexDirection": "column", "gap": "8px",
                           "marginBottom": "12px"},
                ),
                # Run button — Phase 4e UX: inline spinner + disabled while running
                rx.el.button(
                    rx.cond(
                        EngineConfiguratorState.msim_running,
                        rx.el.span(class_name="ops-spinner"),
                        rx.fragment(),
                    ),
                    rx.cond(
                        EngineConfiguratorState.msim_running,
                        "Simulating… (this can take 30–90s)",
                        "Run Multi-Week Sim",
                    ),
                    on_click=EngineConfiguratorState.run_multi_week_simulation,
                    disabled=EngineConfiguratorState.msim_running,
                    style={
                        "padding": "7px 18px",
                        "fontSize": "13px",
                        "fontWeight": "600",
                        "borderRadius": "6px",
                        "border": "1px solid var(--border-subtle)",
                        "background": "var(--surface-card)",
                        "color": "var(--ink2)",
                        "fontFamily": "var(--font)",
                        "transition": "opacity 0.12s",
                        "display": "inline-flex",
                        "alignItems": "center",
                        "justifyContent": "center",
                        "gap": "6px",
                        "width": "100%",
                    },
                    cursor=rx.cond(EngineConfiguratorState.msim_running, "wait", "pointer"),
                ),
                # Error
                rx.cond(
                    EngineConfiguratorState.msim_error != "",
                    rx.el.div(EngineConfiguratorState.msim_error, class_name="engine-sim-error"),
                    rx.fragment(),
                ),
                # Results
                rx.cond(
                    EngineConfiguratorState.msim_ran,
                    rx.el.div(
                        # Proposed aggregate stats
                        rx.el.div(
                            rx.el.div("Proposed Config",
                                      style={"fontSize": "10px", "fontWeight": "700",
                                             "color": "var(--accent-amber)",
                                             "textTransform": "uppercase",
                                             "letterSpacing": "0.1em", "marginBottom": "8px"}),
                            rx.el.div(
                                _msim_stat("Fill rate (mean)",
                                    EngineConfiguratorState.msim_agg_proposed["fill_rate_mean"].to(str)),
                                _msim_stat("Critical (mean)",
                                    EngineConfiguratorState.msim_agg_proposed["critical_mean"].to(str),
                                    # Phase 4e hotfix: dict["key"] returns an untyped
                                    # ObjectItemOperation in Reflex 0.9 — explicit .to(float)
                                    # is required before comparing to a Python int/float.
                                    warn=EngineConfiguratorState.msim_agg_proposed["critical_mean"].to(float) > 0),
                                _msim_stat("Load σ (mean)",
                                    EngineConfiguratorState.msim_agg_proposed["load_variance_mean"].to(str)),
                                _msim_stat("Runs",
                                    EngineConfiguratorState.msim_agg_proposed["n_runs"].to(str)),
                                # Phase 4e.2D: two new stat cards
                                _msim_stat(
                                    "Z1/4/5/8 covered",
                                    EngineConfiguratorState.msim_agg_proposed["must_fill_avg"].to(str),
                                    warn=EngineConfiguratorState.msim_agg_proposed["must_fill_avg"].to(float) < 0.9,
                                ),
                                _msim_stat(
                                    "Trainee runs/wk",
                                    EngineConfiguratorState.msim_agg_proposed["trainee_support_total"].to(str),
                                ),
                                class_name="engine-sim-stats",
                            ),
                        ),
                        # Baseline stats (shown only if comparison was actually
                        # run AND we got real numbers back). Phase 4f hotfix:
                        # check msim_compare_baseline AND that fill_rate_mean
                        # is present — `dict_var != {}` evaluates True for any
                        # dict in Reflex 0.9 even when truly empty, so baseline
                        # was rendering with blank values when it shouldn't.
                        rx.cond(
                            EngineConfiguratorState.msim_compare_baseline,
                            rx.el.div(
                                rx.el.div("Baseline Config",
                                          style={"fontSize": "10px", "fontWeight": "700",
                                                 "color": "var(--ink2)",
                                                 "textTransform": "uppercase",
                                                 "letterSpacing": "0.1em",
                                                 "marginBottom": "8px", "marginTop": "12px"}),
                                rx.el.div(
                                    _msim_stat("Fill rate (mean)",
                                        EngineConfiguratorState.msim_agg_baseline["fill_rate_mean"].to(str)),
                                    _msim_stat("Critical (mean)",
                                        EngineConfiguratorState.msim_agg_baseline["critical_mean"].to(str),
                                        # Phase 4e hotfix — see line 446 note. Same dict-Var
                                        # ObjectItemOperation issue applies to baseline pane.
                                        warn=EngineConfiguratorState.msim_agg_baseline["critical_mean"].to(float) > 0),
                                    _msim_stat("Load σ (mean)",
                                        EngineConfiguratorState.msim_agg_baseline["load_variance_mean"].to(str)),
                                    class_name="engine-sim-stats",
                                ),
                            ),
                            rx.fragment(),
                        ),
                        # Phase 4e.1: collapsible inline report disclosure
                        rx.cond(
                            EngineConfiguratorState.msim_report_md != "",
                            rx.el.details(
                                rx.el.summary(
                                    "View full report",
                                    style={
                                        "fontSize": "11px",
                                        "fontWeight": "600",
                                        "color": "var(--accent-amber)",
                                        "cursor": "pointer",
                                        "userSelect": "none",
                                        "marginTop": "10px",
                                        "display": "block",
                                    },
                                ),
                                rx.el.div(
                                    rx.markdown(EngineConfiguratorState.msim_report_md),
                                    class_name="ops-sim-report-body",
                                ),
                            ),
                            rx.fragment(),
                        ),
                        # Output paths
                        rx.el.div(
                            rx.el.span("Report: ", style={"fontSize": "11px", "color": "var(--ink3)"}),
                            rx.el.span(
                                EngineConfiguratorState.msim_md_path,
                                style={"fontSize": "11px", "color": "var(--ink2)",
                                       "wordBreak": "break-all"},
                            ),
                            style={"marginTop": "10px"},
                        ),
                        # Phase 4f hotfix #5: collapsible engine-output tail —
                        # always present after a sim run, even on success.
                        # Surfaces "Placement method: lap (scipy_available=...)"
                        # plus per-run engine warnings so silent fallbacks
                        # (LAP-degrading-to-greedy when scipy is missing) are
                        # visible without digging into Render logs.
                        rx.cond(
                            EngineConfiguratorState.msim_stdout_tail != "",
                            rx.el.details(
                                rx.el.summary(
                                    "Engine output (tail)",
                                    style={
                                        "fontSize": "11px",
                                        "color": "var(--ink3)",
                                        "cursor": "pointer",
                                        "padding": "6px 0",
                                        "marginTop": "6px",
                                    },
                                ),
                                rx.el.pre(
                                    EngineConfiguratorState.msim_stdout_tail,
                                    style={
                                        "fontSize": "10.5px",
                                        "color": "var(--ink2)",
                                        "background": "var(--surface-card)",
                                        "border": "1px solid var(--border-subtle)",
                                        "borderRadius": "4px",
                                        "padding": "10px",
                                        "maxHeight": "300px",
                                        "overflow": "auto",
                                        "whiteSpace": "pre-wrap",
                                        "fontFamily": "var(--font-mono, monospace)",
                                    },
                                ),
                            ),
                            rx.fragment(),
                        ),
                        style={"display": "flex", "flexDirection": "column", "gap": "4px"},
                    ),
                    rx.fragment(),
                ),
                style={"display": "flex", "flexDirection": "column", "gap": "10px"},
            ),
        ),
        class_name="engine-sim-pane",
    )


# ── Action bar ────────────────────────────────────────────────────────────────

def _action_bar() -> rx.Component:
    return rx.el.div(
        # Dirty indicator
        rx.cond(
            EngineConfiguratorState.dirty,
            rx.el.span(
                rx.el.span(class_name="engine-dirty-dot"),
                "Unsaved changes",
                style={"fontSize": "12px", "color": "var(--accent-amber)", "fontWeight": "500"},
            ),
            rx.fragment(),
        ),
        # Save success / error
        rx.cond(
            EngineConfiguratorState.save_success,
            rx.el.span("Saved.", class_name="engine-save-success"),
            rx.fragment(),
        ),
        rx.cond(
            EngineConfiguratorState.save_error != "",
            rx.el.span(EngineConfiguratorState.save_error, class_name="engine-save-error"),
            rx.fragment(),
        ),
        rx.el.div(style={"flex": "1"}),  # spacer
        _btn(
            "Discard",
            EngineConfiguratorState.discard_changes,
            variant="danger",
        ),
        _btn(
            rx.cond(EngineConfiguratorState.saving, "Saving…", "Save Config"),
            EngineConfiguratorState.save_config,
            variant="primary",
        ),
        class_name="engine-action-bar",
    )


# ── Page root ─────────────────────────────────────────────────────────────────

def admin_engine_page() -> rx.Component:
    return rx.el.div(
        admin_breadcrumb(section="Workflows", page_title="Engine Config"),
        rx.el.div(
            # Eyebrow
            rx.el.div(
                "ENGINE · CONFIGURATOR",
                style={
                    "fontSize": "10px",
                    "fontWeight": "700",
                    "letterSpacing": "0.14em",
                    "textTransform": "uppercase",
                    "color": "var(--gold)",
                    "fontFamily": "var(--font)",
                    "marginBottom": "8px",
                },
            ),
            # Title
            rx.el.div(
                "Engine Configurator",
                style={
                    "fontFamily": "var(--serif)",
                    "fontSize": "26px",
                    "fontWeight": "400",
                    "fontStyle": "italic",
                    "letterSpacing": "-0.015em",
                    "color": "var(--ink)",
                    "marginBottom": "24px",
                },
            ),
            rx.cond(
                EngineConfiguratorState.loading,
                rx.el.div(
                    "Loading config…",
                    style={"fontSize": "14px", "color": "var(--ink3)", "padding": "40px 0"},
                ),
                rx.el.div(
                    _tab_strip(),
                    # Tab content
                    rx.cond(
                        EngineConfiguratorState.active_tab == 0,
                        _weights_tab(),
                        rx.cond(
                            EngineConfiguratorState.active_tab == 1,
                            _thresholds_tab(),
                            rx.cond(
                                EngineConfiguratorState.active_tab == 2,
                                _headcount_tab(),
                                rx.cond(
                                    EngineConfiguratorState.active_tab == 3,
                                    _slot_difficulty_tab(),
                                    _history_tab(),
                                ),
                            ),
                        ),
                    ),
                    _action_bar(),
                ),
            ),
            # Phase 4e UX: full-screen scrim while multi-week sim runs.
            # Sim takes 30–90s; without this, the page looks frozen. Sibling
            # of the loading rx.cond above (rx.cond takes max 3 args, so this
            # has to live outside that call, not as a 4th argument).
            rx.cond(
                EngineConfiguratorState.msim_running,
                rx.el.div(
                    rx.el.div(
                        rx.el.span(class_name="ops-spinner lg"),
                        rx.el.span("Running multi-week simulation…"),
                        class_name="ops-engine-running-card",
                    ),
                    class_name="ops-engine-running-scrim",
                ),
                rx.fragment(),
            ),
            class_name="engine-config-page",
            style={
                "minHeight": "calc(100vh - 40px)",
                "background": "var(--bg)",
                "fontFamily": "var(--font)",
                "color": "var(--ink)",
            },
        ),
        class_name="admin-subpage-wrapper",
    )
