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


def _load_active_config() -> dict:
    """Fetch the currently active engine_config weights/thresholds from DB."""
    try:
        sb = _get_db_client()
        row = (
            sb.table("engine_config")
            .select("weights, thresholds, headcount")
            .eq("is_active", True)
            .maybe_single()
            .execute()
        )
        data = (row.data or {}) if row else {}
        return {
            "weights":    data.get("weights")    or {},
            "thresholds": data.get("thresholds") or {},
            "headcount":  data.get("headcount")  or {},
        }
    except Exception as e:
        print(f"  [sim][warn] Active config load failed ({e}) — using empty dict")
        return {}


# ── Schedule discovery ────────────────────────────────────────────────────────

def _find_schedules(n: int) -> list[Path]:
    """Return the N most recently modified schedule xlsx files."""
    candidates = sorted(
        SCHEDULE_DIR.glob("*.xlsx"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
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

def _extract_metrics(audit: dict, simulated_unavailable: list[str]) -> dict:
    """Distil an audit JSON into summary metrics for the simulation report."""
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

    return {
        "filled":                filled,
        "total_slots":           total_slots,
        "unresolved":            summary.get("unfilled", 0),
        "critical":              critical,
        "fill_rate":             round(fill_rate, 4),
        "load_variance":         round(load_std, 4),
        "simulated_call_offs":   len(simulated_unavailable),
        "per_day":               per_day,
    }


# ── Aggregation ───────────────────────────────────────────────────────────────

def _aggregate(run_metrics: list[dict]) -> dict:
    """Compute mean + p95 across a list of per-run metrics dicts."""
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
    """Write human-readable sim_report.md."""

    def _fmt(v):
        if isinstance(v, float):
            return f"{v:.4f}"
        return str(v)

    lines = [
        f"# GLCR Stochastic Simulation Report",
        f"",
        f"**Run:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Seed:** {args.seed}  **Callout rate (λ):** {args.callout_rate}  ",
        f"**Schedules:** {len(schedules)}  **Runs/schedule:** {args.runs}  ",
        f"**Total runs:** {len(proposed_results)}  **Elapsed:** {elapsed_s:.1f}s",
        f"",
        f"## Config",
        f"",
        f"| | Proposed | Baseline |" if baseline_results else "| | Proposed |",
        f"|---|---|---|" if baseline_results else "|---|---|",
    ]
    proposed_cfg = proposed_results[0].get("config_used", {}) if proposed_results else {}
    baseline_cfg = baseline_results[0].get("config_used", {}) if baseline_results else {}

    metric_rows = [
        ("fill_rate_mean",       "Fill rate (mean)"),
        ("fill_rate_p95",        "Fill rate (p95)"),
        ("unresolved_mean",      "Unresolved (mean)"),
        ("critical_mean",        "Critical unresolved (mean)"),
        ("critical_p95",         "Critical unresolved (p95)"),
        ("load_variance_mean",   "Load variance σ (mean)"),
        ("simulated_call_offs_mean", "Simulated call-offs (mean)"),
    ]
    lines.append("")
    lines.append("## Aggregated Results")
    lines.append("")
    if baseline_results:
        lines.append("| Metric | Proposed | Baseline | Δ |")
        lines.append("|--------|----------|----------|---|")
        for key, label in metric_rows:
            p_val = agg_proposed.get(key, 0)
            b_val = (agg_baseline or {}).get(key, 0)
            delta = round(p_val - b_val, 4)
            sign  = "+" if delta > 0 else ""
            lines.append(f"| {label} | {_fmt(p_val)} | {_fmt(b_val)} | {sign}{_fmt(delta)} |")
    else:
        lines.append("| Metric | Proposed |")
        lines.append("|--------|----------|")
        for key, label in metric_rows:
            lines.append(f"| {label} | {_fmt(agg_proposed.get(key, 0))} |")

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

    # Load baseline config (DB active) when --baseline
    baseline_cfg: dict | None = None
    if args.baseline:
        baseline_cfg = _load_active_config()
        print(f"[sim] Baseline config: DB active weights")

    # Discover schedule files
    schedules = _find_schedules(args.weeks)
    if not schedules:
        print(f"[error] No schedule files found in {SCHEDULE_DIR}")
        sys.exit(1)
    print(f"[sim] Schedules ({len(schedules)}): {', '.join(s.name for s in schedules)}\n")

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

            m_p = _extract_metrics(audit_p, unavailable)
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
                    m_b = _extract_metrics(audit_b, unavailable)
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
