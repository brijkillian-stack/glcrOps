"""
simulate_weeks.py — Phase 4e Part B
GLCR Grave Deployment Multi-Week Stochastic Simulator.

Runs fill_engine N×M times (N simulations per week-slot, across M historical
week schedules), each time injecting Poisson-distributed simulated call-offs.
Aggregates placement quality metrics and writes JSON + Markdown output.

Usage:
  python simulate_weeks.py [options]

Options:
  --weeks N            Number of historical schedule files to run over [default: 3]
  --runs N             Simulation runs per schedule [default: 5]
  --seed N             RNG seed for reproducibility [default: 42]
  --callout-rate F     Average grave call-offs per night [default: 2.0]
  --config PATH        Proposed config JSON file (Phase 4e weights/thresholds)
  --baseline           Also run each scenario against the DB active config
                       (comparison mode — uses same RNG seed, different weights)
  --output DIR         Output directory [default: Outputs/sim_<timestamp>/]
  --verbose            Print fill_engine stdout during simulation runs
  --max-pool-pct F     Cap simulated unavailable at this fraction of grave pool
                       [default: 0.30] — prevents unrealistic full-team call-outs

Examples:
  # Quick test: current schedule, 5 runs, proposed weights vs baseline
  python simulate_weeks.py --runs 5 --config proposed.json --baseline

  # Full 3-week sweep
  python simulate_weeks.py --weeks 3 --runs 8 --seed 99 --config new_weights.json

Output files:
  sim_results.json   — Full per-run data + aggregated metrics
  sim_report.md      — Human-readable summary with comparison table
"""
from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from datetime import datetime

# Resolve repo root so we can import shared helpers
_ENGINE_DIR = Path(__file__).resolve().parent
_REPO_ROOT  = _ENGINE_DIR.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared.db import get_engine_roster_from_db, get_client as _get_db_client

# ── Must-fill zones + support slot definitions ────────────────────────────────
MUST_FILL_ZONES = {"Zone1", "Zone4", "Zone5", "Zone8"}
SUPPORT_SLOTS   = {"Support1", "Support2", "Support3", "MP1", "MP2"}

FILL_ENGINE    = _ENGINE_DIR / "fill_engine.py"
SCHEDULE_DIR   = _ENGINE_DIR / "Inputs" / "Weekly Schedules"
OUTPUTS_ROOT   = _ENGINE_DIR / "Outputs"

# ── CLI ──────────────────────────────────────────────────────────────────────

def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="GLCR stochastic placement simulator")
    p.add_argument("--weeks",        type=int,   default=3,   help="Schedule files to iterate")
    p.add_argument("--runs",         type=int,   default=5,   help="Simulation runs per schedule")
    p.add_argument("--seed",         type=int,   default=42,  help="Master RNG seed")
    p.add_argument("--callout-rate", type=float, default=2.0, help="Avg grave call-offs / night")
    p.add_argument("--config",       type=str,   default=None, help="Proposed config JSON path")
    p.add_argument("--baseline",     action="store_true",      help="Also run DB active config")
    p.add_argument("--output",       type=str,   default=None, help="Output directory path")
    p.add_argument("--verbose",      action="store_true",      help="Show fill_engine output")
    p.add_argument("--max-pool-pct", type=float, default=0.30, help="Max fraction of pool to remove")
    return p.parse_args(argv)


# ── RNG ──────────────────────────────────────────────────────────────────────

def _poisson_draw(lam: float, rng: random.Random) -> int:
    """Draw from Poisson(lam) using the Knuth/Junhao algorithm."""
    if lam <= 0:
        return 0
    if lam < 30:
        L, k, p = math.exp(-lam), 0, 1.0
        while p > L:
            k += 1
            p *= rng.random()
        return k - 1
    # Normal approximation for large lambda
    return max(0, round(rng.gauss(lam, math.sqrt(lam))))


# ── Roster helpers ────────────────────────────────────────────────────────────

def _load_grave_pool() -> list[str]:
    """Return display_names of all active grave-pool TMs from the DB roster."""
    try:
        roster, _ = get_engine_roster_from_db()
        return [info["display_name"] for info in roster.values()
                if info.get("display_name")]
    except Exception as e:
        print(f"  [sim][warn] Roster load failed ({e}) — using empty pool")
        return []


def _load_slot_loads() -> dict[str, float]:
    """Fetch slot_load_scores from DB. Returns {slot_id: load}.
    Used to weight per-TM load in simulation metrics."""
    try:
        sb = _get_db_client()
        rows = sb.table("slot_load_scores").select("slot_id, load").execute()
        return {r["slot_id"]: float(r["load"]) for r in (rows.data or [])}
    except Exception as e:
        print(f"  [sim][warn] slot_load_scores load failed ({e}) — using empty dict")
        return {}


def _load_active_config() -> dict:
    """Fetch the currently active engine_config weights/thresholds from DB."""
    try:
        sb = _get_db_client()
        row = (
            sb.table("engine_config")
            .select("weights, thresholds, headcount, placement_method")
            .eq("is_active", True)
            .maybe_single()
            .execute()
        )
        data = (row.data or {}) if row else {}
        return {
            "weights":          data.get("weights")           or {},
            "thresholds":       data.get("thresholds")        or {},
            "headcount":        data.get("headcount")         or {},
            "placement_method": data.get("placement_method")  or "greedy",
        }
    except Exception as e:
        print(f"  [sim][warn] Active config load failed ({e}) — using empty dict")
        return {}


# ── Schedule discovery ────────────────────────────────────────────────────────

def _find_schedules(n: int) -> list[Path]:
    """Return the N most recently uploaded schedule xlsx files.

    Phase 4e hotfix #5: previously sorted local files by mtime, but on the
    Render container the local Inputs/Weekly Schedules/ folder is empty
    after every redeploy (xlsx files are gitignored — they live in Supabase
    Storage). Now:
      1. List the bucket to get the canonical upload-order (newest first
         by `updated_at`).
      2. Download the top N into the local SCHEDULE_DIR if not already
         present, mirroring fill_engine's get_latest_schedule_path() pattern.
      3. Fall back to local-mtime ordering if the bucket isn't reachable —
         that lets the simulator still work in dev environments where
         schedules are only on local disk.
    """
    SCHEDULE_DIR.mkdir(parents=True, exist_ok=True)

    # Tier 1 — pull upload order from Supabase Storage and ensure local copies.
    try:
        # Late import: storage.py pulls in shared.db which the engine doesn't
        # need on every run, and we want a clean fallback if anything's wrong.
        from shared import storage  # type: ignore
        remote_rows = storage.list_schedules()
    except Exception as exc:
        print(f"[sim] Storage list failed ({exc}) — falling back to local mtime")
        remote_rows = []

    if remote_rows:
        # Newest first; cap at n.
        top = remote_rows[:n]
        ordered: list[Path] = []
        for row in top:
            name = row.get("name")
            if not name:
                continue
            local = SCHEDULE_DIR / name
            if not local.exists():
                try:
                    from shared.db import get_client
                    sb = get_client()
                    blob = sb.storage.from_(storage.SCHEDULES_BUCKET).download(name)
                    local.write_bytes(blob)
                    print(f"[sim] Synced {name} from Storage")
                except Exception as exc:
                    print(f"[sim][warn] Failed to sync {name}: {exc} — skipping")
                    continue
            ordered.append(local)
        if ordered:
            return ordered
        # If sync worked but produced no usable files, fall through to local.

    # Tier 2 — fallback: local files by mtime (dev environments).
    candidates = sorted(
        SCHEDULE_DIR.glob("*.xlsx"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[:n]


# ── Engine runner ─────────────────────────────────────────────────────────────

def _run_engine_with_config(
    config: dict,
    schedule_path: Path,
    verbose: bool = False,
) -> dict | None:
    """Write config to a temp JSON file and invoke fill_engine.py as a subprocess.
    Returns the parsed audit JSON dict, or None if the run failed."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg_path = Path(tmp) / "sim_cfg.json"
        cfg_path.write_text(json.dumps(config, indent=2))
        cmd = [
            sys.executable, str(FILL_ENGINE),
            schedule_path.name,            # explicit schedule name
            "--config-override", str(cfg_path),
        ]
        result = subprocess.run(
            cmd,
            capture_output=not verbose,
            text=True,
            cwd=str(FILL_ENGINE.parent),
        )
        if result.returncode != 0 and not verbose:
            # Surface the first 300 chars of stderr for debugging
            snippet = (result.stderr or "")[:300].strip()
            print(f"    [sim][warn] Engine exit {result.returncode}: {snippet}")

    # fill_engine writes its audit JSON into Outputs/<WEEK_ENDING>/
    # Find the newest audit file across all output subdirectories.
    audits = sorted(
        OUTPUTS_ROOT.glob("*/Grave Deployment Audit - *.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not audits:
        return None
    try:
        return json.loads(audits[0].read_text())
    except Exception as e:
        print(f"    [sim][warn] Audit parse failed: {e}")
        return None


# ── Metrics extraction ────────────────────────────────────────────────────────

def _extract_metrics(
    audit: dict,
    simulated_unavailable: list[str],
    slot_loads: dict | None = None,
) -> dict:
    """Distil an audit JSON into summary metrics for the simulation report.

    Phase 4e.2A additions:
      per_tm_load              — {dn: weighted_load_sum} using slot_load_scores
      per_must_fill            — {zone: {filled_nights, total_nights}} for Z1/4/5/8
      trainee_support_placements — {dn: count} for TMs with tm_skill ≤ 3 in support slots
    """
    if slot_loads is None:
        slot_loads = {}

    summary    = audit.get("summary", {})
    unresolved = audit.get("unresolved_slots", [])
    placements = audit.get("placements", [])

    filled      = summary.get("filled", 0)
    total_slots = summary.get("total_slots", 0)
    critical    = sum(1 for u in unresolved if u.get("severity") == "critical")
    fill_rate   = filled / max(total_slots, 1)

    # Per-TM grave placement count → load variance (std dev)
    grave_counts: dict[str, int] = {}
    for p in placements:
        if p.get("pool_type") == "grave":
            dn = p.get("tm_display_name", "")
            if dn:
                grave_counts[dn] = grave_counts.get(dn, 0) + 1
    counts = list(grave_counts.values())
    if counts:
        mean_c = sum(counts) / len(counts)
        load_std = math.sqrt(sum((c - mean_c) ** 2 for c in counts) / len(counts))
    else:
        load_std = 0.0

    # Per-day breakdown
    per_day: dict[str, dict] = {}
    for u in unresolved:
        dt = u.get("date", "unknown")
        per_day.setdefault(dt, {"unresolved": 0, "critical": 0})
        per_day[dt]["unresolved"] += 1
        if u.get("severity") == "critical":
            per_day[dt]["critical"] += 1

    # ── Phase 4e.2A: enriched metrics ────────────────────────────────────────

    # All distinct dates (covers nights with 0 placements via unresolved)
    all_dates: set[str] = set()
    for p in placements:
        dt = p.get("date", "")
        if dt:
            all_dates.add(dt)
    for u in unresolved:
        dt = u.get("date", "")
        if dt:
            all_dates.add(dt)
    total_nights = max(len(all_dates), 1)

    # Per-TM weighted load sum (slot_load_scores values)
    per_tm_load: dict[str, float] = {}
    for p in placements:
        dn   = p.get("tm_display_name", "")
        slot = p.get("zone_slot", "")
        if dn and slot:
            per_tm_load[dn] = per_tm_load.get(dn, 0.0) + slot_loads.get(slot, 0.0)

    # Must-fill zone coverage (Zone1, Zone4, Zone5, Zone8)
    per_must_fill: dict[str, dict] = {}
    for zone in MUST_FILL_ZONES:
        filled_dates = set(
            p.get("date", "") for p in placements
            if p.get("zone_slot") == zone and p.get("date")
        )
        per_must_fill[zone] = {
            "filled_nights": len(filled_dates),
            "total_nights":  total_nights,
        }

    # Trainee support exposure (tm_skill ≤ 3 placed in support slots)
    trainee_support: dict[str, int] = {}
    for p in placements:
        dn    = p.get("tm_display_name", "")
        slot  = p.get("zone_slot", "")
        skill = p.get("tm_skill", 99)
        if dn and slot in SUPPORT_SLOTS:
            try:
                if float(skill) <= 3:
                    trainee_support[dn] = trainee_support.get(dn, 0) + 1
            except (TypeError, ValueError):
                pass

    return {
        "filled":                      filled,
        "total_slots":                 total_slots,
        "unresolved":                  summary.get("unfilled", 0),
        "critical":                    critical,
        "fill_rate":                   round(fill_rate, 4),
        "load_variance":               round(load_std, 4),
        "simulated_call_offs":         len(simulated_unavailable),
        "per_day":                     per_day,
        # Phase 4e.2A
        "per_tm_load":                 per_tm_load,
        "per_must_fill":               per_must_fill,
        "trainee_support_placements":  trainee_support,
    }


# ── Aggregation ───────────────────────────────────────────────────────────────

def _aggregate(run_metrics: list[dict]) -> dict:
    """Compute mean + p95 across a list of per-run metrics dicts.

    Phase 4e.2B additions:
      per_tm_load_mean      — {dn: mean_weighted_load} across runs
      must_fill_rate        — {zone: mean_fill_rate} for Z1/4/5/8
      must_fill_avg         — scalar average of the 4 must-fill rates (UI stat card)
      trainee_support_mean  — {dn: mean_support_placements} across runs
      trainee_support_total — sum across all trainees (UI stat card)
    """
    if not run_metrics:
        return {}

    def _p95(vals):
        s = sorted(vals)
        idx = max(0, int(len(s) * 0.95) - 1)
        return round(s[idx], 4)

    keys = ["fill_rate", "unresolved", "critical", "load_variance", "simulated_call_offs"]
    result = {}
    for k in keys:
        vals = [m.get(k, 0) for m in run_metrics]
        result[f"{k}_mean"] = round(sum(vals) / len(vals), 4)
        result[f"{k}_p95"]  = _p95(vals)
    result["n_runs"] = len(run_metrics)

    # ── Phase 4e.2B: enriched aggregations ───────────────────────────────────

    # Per-TM weighted load mean across runs
    all_tms: set[str] = set()
    for m in run_metrics:
        all_tms.update(m.get("per_tm_load", {}).keys())
    tm_load_means: dict[str, float] = {}
    for dn in all_tms:
        vals = [m.get("per_tm_load", {}).get(dn, 0.0) for m in run_metrics]
        tm_load_means[dn] = round(sum(vals) / len(vals), 2)
    result["per_tm_load_mean"] = tm_load_means

    # Must-fill zone coverage (mean fill_rate per zone across runs)
    must_fill_rates: dict[str, float] = {}
    for zone in sorted(MUST_FILL_ZONES):
        zone_rates = []
        for m in run_metrics:
            mf = m.get("per_must_fill", {}).get(zone, {})
            fn = mf.get("filled_nights", 0)
            tn = mf.get("total_nights", 1)
            zone_rates.append(fn / max(tn, 1))
        must_fill_rates[zone] = round(sum(zone_rates) / len(zone_rates), 4)
    result["must_fill_rate"] = must_fill_rates
    result["must_fill_avg"]  = round(
        sum(must_fill_rates.values()) / max(len(must_fill_rates), 1), 4
    )

    # Trainee support exposure (mean support placements per trainee across runs)
    all_trainees: set[str] = set()
    for m in run_metrics:
        all_trainees.update(m.get("trainee_support_placements", {}).keys())
    trainee_means: dict[str, float] = {}
    for dn in all_trainees:
        vals = [m.get("trainee_support_placements", {}).get(dn, 0) for m in run_metrics]
        trainee_means[dn] = round(sum(vals) / len(vals), 2)
    result["trainee_support_mean"]  = trainee_means
    result["trainee_support_total"] = round(sum(trainee_means.values()), 2)

    return result


# ── Report writer ─────────────────────────────────────────────────────────────

def _write_markdown(
    output_dir: Path,
    schedules: list[Path],
    args,
    proposed_results: list[dict],
    baseline_results: list[dict] | None,
    agg_proposed: dict,
    agg_baseline: dict | None,
    elapsed_s: float,
) -> Path:
    """Write human-readable sim_report.md.

    Phase 4e.2C section order:
      1. Header
      2. Aggregated Results
      3. Comparison Delta (if baseline) — ✓/✗/≈ indicators
      4. Must-Fill Zone Coverage
      5. TM Load Distribution (top 10 / bottom 10)
      6. Trainee Support Exposure
      7. Per-Run Details (Proposed)
      8. Per-Run Details (Baseline, if run)
    """

    def _fmt(v):
        if isinstance(v, float):
            return f"{v:.4f}"
        return str(v)

    def _pct(v):
        """Format a 0-1 rate as percentage string."""
        try:
            return f"{float(v)*100:.1f}%"
        except (TypeError, ValueError):
            return str(v)

    def _delta_signal(key: str, delta: float) -> str:
        """Return ✓/✗/≈ based on metric direction and magnitude."""
        # lower-is-better metrics
        lower_is_better = {"unresolved_mean", "critical_mean", "critical_p95",
                           "load_variance_mean", "unresolved_p95"}
        threshold_map = {
            "fill_rate_mean":      0.005,
            "fill_rate_p95":       0.005,
            "unresolved_mean":     0.10,
            "unresolved_p95":      0.10,
            "critical_mean":       0.05,
            "critical_p95":        0.05,
            "load_variance_mean":  0.001,
        }
        thr = threshold_map.get(key, 0.005)
        if key in lower_is_better:
            if delta < -thr:
                return "✓"
            elif delta > thr:
                return "✗"
        else:
            if delta > thr:
                return "✓"
            elif delta < -thr:
                return "✗"
        return "≈"

    lines = [
        "# GLCR Stochastic Simulation Report",
        "",
        f"**Run:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Seed:** {args.seed}  **Callout rate (λ):** {args.callout_rate}  ",
        f"**Schedules:** {len(schedules)}  **Runs/schedule:** {args.runs}  ",
        f"**Total runs:** {len(proposed_results)}  **Elapsed:** {elapsed_s:.1f}s",
        "",
    ]

    # ── Section 1: Aggregated Results ─────────────────────────────────────────
    metric_rows = [
        ("fill_rate_mean",           "Fill rate (mean)"),
        ("fill_rate_p95",            "Fill rate (p95)"),
        ("unresolved_mean",          "Unresolved (mean)"),
        ("critical_mean",            "Critical unresolved (mean)"),
        ("critical_p95",             "Critical unresolved (p95)"),
        ("load_variance_mean",       "Load variance σ (mean)"),
        ("simulated_call_offs_mean", "Simulated call-offs (mean)"),
    ]

    lines += ["## Aggregated Results", ""]
    if baseline_results:
        lines += ["| Metric | Proposed | Baseline | Δ |",
                  "|--------|----------|----------|---|"]
        for key, label in metric_rows:
            p_val = agg_proposed.get(key, 0)
            b_val = (agg_baseline or {}).get(key, 0)
            delta = round(p_val - b_val, 4)
            sign  = "+" if delta > 0 else ""
            lines.append(
                f"| {label} | {_fmt(p_val)} | {_fmt(b_val)} | {sign}{_fmt(delta)} |"
            )
    else:
        lines += ["| Metric | Proposed |", "|--------|----------|"]
        for key, label in metric_rows:
            lines.append(f"| {label} | {_fmt(agg_proposed.get(key, 0))} |")

    # ── Section 2: Comparison Delta (baseline only) ───────────────────────────
    if baseline_results and agg_baseline:
        lines += [
            "",
            "## Comparison Delta",
            "",
            "Signals: **✓** proposed improves on baseline · **✗** proposed regresses · **≈** within threshold",
            "",
            "| Metric | Proposed | Baseline | Δ | Signal |",
            "|--------|----------|----------|---|--------|",
        ]
        for key, label in metric_rows:
            p_val = agg_proposed.get(key, 0)
            b_val = agg_baseline.get(key, 0)
            delta = round(p_val - b_val, 4)
            sign  = "+" if delta > 0 else ""
            sig   = _delta_signal(key, delta)
            lines.append(
                f"| {label} | {_fmt(p_val)} | {_fmt(b_val)} | {sign}{_fmt(delta)} | {sig} |"
            )

    # ── Section 3: Must-Fill Zone Coverage ────────────────────────────────────
    lines += ["", "## Must-Fill Zone Coverage", ""]
    mf_rates = agg_proposed.get("must_fill_rate", {})
    if mf_rates:
        lines += ["| Zone | Mean Fill Rate | Signal |",
                  "|------|----------------|--------|"]
        for zone in sorted(MUST_FILL_ZONES):
            rate = mf_rates.get(zone, 0.0)
            sig  = "✓" if rate >= 0.90 else "✗"
            lines.append(f"| {zone} | {_pct(rate)} | {sig} |")
        must_avg = agg_proposed.get("must_fill_avg", 0.0)
        lines.append(f"| **Average** | **{_pct(must_avg)}** | {'✓' if must_avg >= 0.90 else '✗'} |")
    else:
        lines.append("_No must-fill data available — slot_load_scores may be empty._")

    # ── Section 4: TM Load Distribution ──────────────────────────────────────
    tm_load = agg_proposed.get("per_tm_load_mean", {})
    if tm_load:
        sorted_load = sorted(tm_load.items(), key=lambda x: x[1], reverse=True)
        top10    = sorted_load[:10]
        bottom10 = sorted_load[-10:][::-1]   # lightest 10, ascending

        lines += ["", "## TM Load Distribution (Mean Weighted Load Across Runs)", ""]
        lines += ["**Top 10 Most Loaded**", "",
                  "| TM | Mean Load |",
                  "|----|-----------|"]
        for dn, load in top10:
            lines.append(f"| {dn} | {load:.1f} |")

        lines += ["", "**Bottom 10 Least Loaded**", "",
                  "| TM | Mean Load |",
                  "|----|-----------|"]
        for dn, load in bottom10:
            lines.append(f"| {dn} | {load:.1f} |")
    else:
        lines += ["", "## TM Load Distribution", "",
                  "_No weighted load data — slot_load_scores may be empty._"]

    # ── Section 5: Trainee Support Exposure ───────────────────────────────────
    trainee_means = agg_proposed.get("trainee_support_mean", {})
    lines += ["", "## Trainee Support Exposure (Skill ≤ 3)", ""]
    if trainee_means:
        sorted_trainees = sorted(trainee_means.items(), key=lambda x: x[1], reverse=True)
        lines += ["| TM | Mean Support Placements/Week |",
                  "|----|------------------------------|"]
        for dn, count in sorted_trainees:
            lines.append(f"| {dn} | {count:.1f} |")
        total = agg_proposed.get("trainee_support_total", 0.0)
        lines.append(f"| **Total** | **{total:.1f}** |")
        lines.append(
            f"\n_Support slots: {', '.join(sorted(SUPPORT_SLOTS))}_"
        )
    else:
        lines.append("_No trainees (skill ≤ 3) placed in support slots during this simulation._")

    # ── Section 6: Per-Run Details (Proposed) ────────────────────────────────
    lines += [
        "",
        "## Per-Run Details (Proposed)",
        "",
        "| Run | Schedule | Call-offs | Fill rate | Critical | Load σ |",
        "|-----|----------|-----------|-----------|----------|--------|",
    ]
    for m in proposed_results:
        lines.append(
            f"| {m['run']} | {m['schedule']} | {m.get('simulated_call_offs',0)} |"
            f" {m.get('fill_rate',0):.4f} | {m.get('critical',0)} |"
            f" {m.get('load_variance',0):.4f} |"
        )

    # ── Section 7: Per-Run Details (Baseline) ────────────────────────────────
    if baseline_results:
        lines += [
            "",
            "## Per-Run Details (Baseline)",
            "",
            "| Run | Schedule | Fill rate | Critical | Load σ |",
            "|-----|----------|-----------|----------|--------|",
        ]
        for m in baseline_results:
            lines.append(
                f"| {m['run']} | {m['schedule']} |"
                f" {m.get('fill_rate',0):.4f} | {m.get('critical',0)} |"
                f" {m.get('load_variance',0):.4f} |"
            )

    md_path = output_dir / "sim_report.md"
    md_path.write_text("\n".join(lines))
    return md_path


# ── Main ──────────────────────────────────────────────────────────────────────

def main(argv=None):
    args = _parse_args(argv)
    t0   = time.time()

    # Resolve output directory
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output) if args.output else (OUTPUTS_ROOT / f"sim_{ts}")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"GLCR Stochastic Simulator  |  seed={args.seed}  λ={args.callout_rate}")
    print(f"Schedules: {args.weeks}  Runs/schedule: {args.runs}  "
          f"Total runs: {args.weeks * args.runs}")
    # Phase 4f hotfix #6: surface scipy availability up-front. If LAP mode is
    # enabled but scipy is missing, lap_solver returns all-None and fill_engine
    # silently falls back to greedy slot-by-slot — making LAP runs produce the
    # same numbers as greedy. This print makes that diagnosable in one glance.
    try:
        from scipy.optimize import linear_sum_assignment  # noqa: F401
        _scipy_ok = True
        try:
            import scipy
            _scipy_ver = scipy.__version__
        except Exception:
            _scipy_ver = "?"
    except ImportError as _exc:
        _scipy_ok = False
        _scipy_ver = f"missing ({_exc})"
    print(f"[sim] scipy: available={_scipy_ok}  version={_scipy_ver}")
    print(f"{'='*60}\n")

    # Load proposed config
    proposed_base: dict = {}
    if args.config:
        cfg_path = Path(args.config)
        if not cfg_path.exists():
            print(f"[error] Config file not found: {cfg_path}")
            sys.exit(1)
        proposed_base = json.loads(cfg_path.read_text())
        print(f"[sim] Proposed config: {cfg_path.name}")
    else:
        print("[sim] No --config specified — will run with DB active config for both legs")
        proposed_base = _load_active_config()

    # Load baseline config when --baseline.
    # Phase 4f: this is the A/B harness for placement_method. If the proposed
    # config opts into LAP, force the baseline to greedy (and vice versa) so
    # the sim actually compares the two algorithms — otherwise both legs run
    # the same method and every Δfill is +0.000, which is what just bit us.
    # If the proposed config doesn't specify placement_method, we fall back to
    # DB active which is fine.
    baseline_cfg: dict | None = None
    if args.baseline:
        baseline_cfg = _load_active_config()
        prop_method = str(proposed_base.get("placement_method", "greedy")).lower()
        if prop_method == "lap":
            baseline_cfg["placement_method"] = "greedy"
            print("[sim] Baseline config: DB active weights, placement_method=greedy (forced for A/B vs proposed lap)")
        elif prop_method == "greedy":
            baseline_cfg["placement_method"] = "lap"
            print("[sim] Baseline config: DB active weights, placement_method=lap (forced for A/B vs proposed greedy)")
        else:
            print(f"[sim] Baseline config: DB active weights (placement_method={baseline_cfg.get('placement_method', 'greedy')})")

    # Discover schedule files
    schedules = _find_schedules(args.weeks)
    if not schedules:
        print(f"[error] No schedule files found in {SCHEDULE_DIR}")
        sys.exit(1)
    print(f"[sim] Schedules ({len(schedules)}): {', '.join(s.name for s in schedules)}\n")

    # Load slot load scores once (used by _extract_metrics for weighted TM load)
    slot_loads = _load_slot_loads()
    print(f"[sim] Slot load scores: {len(slot_loads)} entries loaded")

    # Load grave pool for call-off sampling
    grave_pool = _load_grave_pool()
    if not grave_pool:
        print("[warn] Empty grave pool — simulation will have 0 call-offs")
    max_calloffs = max(1, int(len(grave_pool) * args.max_pool_pct))
    print(f"[sim] Grave pool: {len(grave_pool)} TMs  Max call-offs/night: {max_calloffs}")

    # Seed the master RNG — child runs get deterministic sub-seeds
    master_rng = random.Random(args.seed)

    proposed_results: list[dict] = []
    baseline_results: list[dict] = []

    run_num = 0
    for sched in schedules:
        for run_i in range(args.runs):
            run_num += 1
            # Each run gets a deterministic sub-seed derived from master
            run_seed = master_rng.randint(0, 2**31 - 1)
            run_rng  = random.Random(run_seed)

            # Draw Poisson call-offs per day (7 nights in the week)
            # We pick globally and inject; fill_engine removes them from all pools
            n_calloffs_total = sum(_poisson_draw(args.callout_rate, run_rng) for _ in range(7))
            n_calloffs_total = min(n_calloffs_total, max_calloffs)
            unavailable = run_rng.sample(grave_pool, min(n_calloffs_total, len(grave_pool)))

            print(f"  Run {run_num:>3} | {sched.name:30s} | {len(unavailable):2d} call-off(s)", end="")

            # ── Proposed run ──────────────────────────────────────────────
            proposed_cfg_run = dict(proposed_base)
            proposed_cfg_run["simulated_unavailable"] = unavailable
            t_run = time.time()
            audit_p = _run_engine_with_config(proposed_cfg_run, sched, verbose=args.verbose)
            elapsed_run = time.time() - t_run

            if audit_p is None:
                print(f"  [FAILED]")
                continue

            m_p = _extract_metrics(audit_p, unavailable, slot_loads=slot_loads)
            m_p.update({
                "run":      run_num,
                "schedule": sched.name,
                "run_seed": run_seed,
                "elapsed_s": round(elapsed_run, 1),
                "config_used": audit_p.get("config_used", {}),
            })
            proposed_results.append(m_p)
            print(f"  → fill={m_p['fill_rate']:.3f}  crit={m_p['critical']}  "
                  f"σ={m_p['load_variance']:.3f}  ({elapsed_run:.1f}s)", end="")

            # ── Baseline run (same unavailables, same seed effect) ────────
            if baseline_cfg is not None:
                baseline_cfg_run = dict(baseline_cfg)
                baseline_cfg_run["simulated_unavailable"] = unavailable
                audit_b = _run_engine_with_config(baseline_cfg_run, sched, verbose=False)
                if audit_b:
                    m_b = _extract_metrics(audit_b, unavailable, slot_loads=slot_loads)
                    m_b.update({
                        "run":      run_num,
                        "schedule": sched.name,
                        "run_seed": run_seed,
                        "config_used": audit_b.get("config_used", {}),
                    })
                    baseline_results.append(m_b)
                    delta_fill = m_p["fill_rate"] - m_b["fill_rate"]
                    print(f"  Δfill={delta_fill:+.3f}", end="")

            print()  # newline

    elapsed_total = time.time() - t0
    print(f"\n{'='*60}")
    print(f"Simulation complete.  {run_num} run(s) in {elapsed_total:.1f}s")

    if not proposed_results:
        print("[error] No successful runs — check fill_engine output with --verbose")
        sys.exit(1)

    # Aggregate
    agg_proposed = _aggregate(proposed_results)
    agg_baseline = _aggregate(baseline_results) if baseline_results else None

    print(f"\nProposed:  fill_rate={agg_proposed.get('fill_rate_mean',0):.4f}  "
          f"critical_mean={agg_proposed.get('critical_mean',0):.2f}  "
          f"load_σ={agg_proposed.get('load_variance_mean',0):.4f}")
    if agg_baseline:
        print(f"Baseline:  fill_rate={agg_baseline.get('fill_rate_mean',0):.4f}  "
              f"critical_mean={agg_baseline.get('critical_mean',0):.2f}  "
              f"load_σ={agg_baseline.get('load_variance_mean',0):.4f}")

    # Write output files
    json_path = out_dir / "sim_results.json"
    json_path.write_text(json.dumps({
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "seed":         args.seed,
            "callout_rate": args.callout_rate,
            "weeks":        args.weeks,
            "runs":         args.runs,
            "schedules":    [s.name for s in schedules],
            "elapsed_s":    round(elapsed_total, 1),
        },
        "aggregated": {
            "proposed":  agg_proposed,
            "baseline":  agg_baseline,
        },
        "runs": {
            "proposed": proposed_results,
            "baseline": baseline_results,
        },
    }, indent=2))

    md_path = _write_markdown(
        out_dir, schedules, args,
        proposed_results, baseline_results or None,
        agg_proposed, agg_baseline,
        elapsed_total,
    )

    print(f"\nOutputs:")
    print(f"  {json_path}")
    print(f"  {md_path}")
    print(f"{'='*60}\n")
    return {
        "json": str(json_path),
        "md":   str(md_path),
        "agg_proposed": agg_proposed,
        "agg_baseline": agg_baseline,
    }


if __name__ == "__main__":
    main()
