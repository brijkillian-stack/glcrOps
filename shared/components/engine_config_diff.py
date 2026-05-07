"""
shared/components/engine_config_diff.py — Engine config diff renderer.

Compares two engine_config dicts (before, after) and renders a
side-by-side table showing what changed, with +/- deltas.

Used in:
  1. The simulator pane: draft config vs active config
  2. The history view: a snapshot vs its predecessor
  3. (Future) compare two engine runs

Both dicts must have the same top-level structure:
  { "weights": {...}, "thresholds": {...}, "headcount": {...} }

Usage:
  engine_config_diff(before=old_config_dict, after=new_config_dict)

  # For Reflex state-var dicts, pass them as Var arguments — this
  # component renders them via rx.cond / rx.foreach.
"""

from __future__ import annotations

import reflex as rx


# ── Python-side diff helper (called server-side in event handlers) ────────────

def compute_diff(before: dict, after: dict) -> dict:
    """Compare two engine_config dicts and return a structured diff.

    Returns:
        {
          "weights":    list of {key, before, after, delta, changed}
          "thresholds": list of {key, before, after, delta, changed}
          "headcount":  list of {key, before, after, delta, changed}
          "n_changed":  int  total changed fields
        }
    """
    def _compare_section(b: dict, a: dict) -> list[dict]:
        all_keys = sorted(set(list(b.keys()) + list(a.keys())))
        rows = []
        for k in all_keys:
            bv = b.get(k, 0)
            av = a.get(k, 0)
            try:
                bv_f = float(bv)
                av_f = float(av)
                delta = round(av_f - bv_f, 4)
                changed = abs(delta) > 0.0001
            except (TypeError, ValueError):
                delta = 0.0
                changed = str(bv) != str(av)
            rows.append({
                "key":     k,
                "before":  bv,
                "after":   av,
                "delta":   delta,
                "changed": changed,
            })
        return rows

    w_rows  = _compare_section(before.get("weights", {}), after.get("weights", {}))
    th_rows = _compare_section(before.get("thresholds", {}), after.get("thresholds", {}))
    hc_rows = _compare_section(before.get("headcount", {}), after.get("headcount", {}))

    n_changed = (
        sum(1 for r in w_rows  if r["changed"])
        + sum(1 for r in th_rows if r["changed"])
        + sum(1 for r in hc_rows if r["changed"])
    )

    return {
        "weights":    w_rows,
        "thresholds": th_rows,
        "headcount":  hc_rows,
        "n_changed":  n_changed,
    }


# ── Reflex component — renders a pre-computed diff dict ───────────────────────

def _diff_section(title: str, rows: list[dict]) -> rx.Component:
    """Render one section (weights / thresholds / headcount) of the diff."""

    def _row(item: dict) -> rx.Component:
        delta_str = rx.cond(
            item["delta"] > 0,
            "+" + item["delta"].to(str),
            item["delta"].to(str),
        )
        return rx.el.tr(
            rx.el.td(
                item["key"],
                style={"fontSize": "12px", "color": "var(--ink2)", "padding": "5px 8px"},
            ),
            rx.el.td(
                item["before"].to(str),
                style={"fontSize": "12px", "color": "var(--ink3)", "padding": "5px 8px",
                       "textAlign": "right", "fontFamily": "var(--font-mono, monospace)"},
            ),
            rx.el.td(
                item["after"].to(str),
                style={"fontSize": "12px", "padding": "5px 8px",
                       "textAlign": "right", "fontFamily": "var(--font-mono, monospace)",
                       "color": rx.cond(item["changed"], "var(--ink1)", "var(--ink3)"),
                       "fontWeight": rx.cond(item["changed"], "600", "400")},
            ),
            rx.el.td(
                rx.cond(
                    item["changed"],
                    rx.el.span(
                        delta_str,
                        style={
                            "fontSize": "11px",
                            "fontWeight": "600",
                            "color": rx.cond(
                                item["delta"] > 0,
                                "var(--accent-amber)",
                                "var(--accent-blue)",
                            ),
                            "fontFamily": "var(--font-mono, monospace)",
                        },
                    ),
                    rx.el.span("—", style={"color": "var(--ink3)", "fontSize": "11px"}),
                ),
                style={"padding": "5px 8px", "textAlign": "right"},
            ),
            style={
                "background": rx.cond(
                    item["changed"],
                    "color-mix(in srgb, var(--accent-amber) 6%, transparent)",
                    "transparent",
                ),
            },
        )

    return rx.el.div(
        rx.el.div(
            title,
            style={
                "fontSize": "10px",
                "fontWeight": "700",
                "letterSpacing": "0.10em",
                "textTransform": "uppercase",
                "color": "var(--ink3)",
                "padding": "8px 8px 4px",
            },
        ),
        rx.el.table(
            rx.el.thead(
                rx.el.tr(
                    rx.el.th("Key",    style={"textAlign": "left",  "padding": "4px 8px", "fontSize": "10px", "color": "var(--ink3)", "fontWeight": "600", "textTransform": "uppercase"}),
                    rx.el.th("Before", style={"textAlign": "right", "padding": "4px 8px", "fontSize": "10px", "color": "var(--ink3)", "fontWeight": "600", "textTransform": "uppercase"}),
                    rx.el.th("After",  style={"textAlign": "right", "padding": "4px 8px", "fontSize": "10px", "color": "var(--ink3)", "fontWeight": "600", "textTransform": "uppercase"}),
                    rx.el.th("Δ",      style={"textAlign": "right", "padding": "4px 8px", "fontSize": "10px", "color": "var(--ink3)", "fontWeight": "600", "textTransform": "uppercase"}),
                ),
            ),
            rx.el.tbody(rx.foreach(rows, _row)),
            style={"width": "100%", "borderCollapse": "collapse"},
        ),
        style={
            "border": "1px solid var(--border-subtle)",
            "borderRadius": "6px",
            "overflow": "hidden",
            "marginBottom": "12px",
        },
    )


def engine_config_diff(
    diff: dict,
    show_unchanged: bool = False,
) -> rx.Component:
    """Render a pre-computed diff dict (from compute_diff()).

    Args:
        diff:           Output of compute_diff() stored in a Reflex state var.
        show_unchanged: If True, render all rows including unchanged ones.
                        Default False (only changed rows).

    The diff dict is expected to have keys: weights, thresholds, headcount,
    n_changed.  Pass it as a Reflex state var (e.g. EngineConfiguratorState.sim_diff).
    """
    return rx.el.div(
        # Summary header
        rx.el.div(
            rx.cond(
                diff["n_changed"] > 0,
                rx.el.span(
                    diff["n_changed"].to(str) + " field" +
                    rx.cond(diff["n_changed"] == 1, "", "s") + " changed",
                    style={
                        "fontSize": "12px",
                        "fontWeight": "600",
                        "color": "var(--accent-amber)",
                        "padding": "6px 10px",
                        "background": "color-mix(in srgb, var(--accent-amber) 10%, transparent)",
                        "borderRadius": "4px",
                        "display": "inline-block",
                    },
                ),
                rx.el.span(
                    "No changes",
                    style={
                        "fontSize": "12px",
                        "color": "var(--ink3)",
                        "padding": "6px 10px",
                        "display": "inline-block",
                    },
                ),
            ),
            style={"marginBottom": "12px"},
        ),
        _diff_section("Weights",    diff["weights"]),
        _diff_section("Thresholds", diff["thresholds"]),
        _diff_section("Headcount",  diff["headcount"]),
    )
