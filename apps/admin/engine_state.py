"""
apps/admin/engine_state.py — EngineConfiguratorState

Manages the 5-tab engine configurator at /admin/engine.

Tabs:
  0 — Weights        (15 weight sliders + number inputs)
  1 — Thresholds     (difficulty threshold, load threshold, fatigue window, rotation weeks)
  2 — Headcount      (grave target per day-of-week)
  3 — Slot Difficulty (list of slot/difficulty pairs — read-only display for now)
  4 — History        (engine_config_history rows)

Simulation runs fill_engine via engine_bridge.run_fill_engine(config_override=...).
Save commits changes to the DB active row + snapshots history.
"""

from __future__ import annotations

import asyncio
import reflex as rx

# ── Weight key order (matches DEFAULT_WEIGHTS in scorecard.py) ───────────────
WEIGHT_KEYS: list[str] = [
    "skill_match",
    "preference_fit",
    "pair_affinity",
    "within_repeat",
    "cross_week_rotation",
    "area_diversity",
    "fatigue_index",
    "soft_prefer_set",
    "sweeper_rotation_penalty",
    "skill_stretch_reward",
    "prior_run_continuity",
    "weekly_load_balance",
]

WEIGHT_LABELS: dict[str, str] = {
    "skill_match":             "Skill Match",
    "preference_fit":          "Preference Fit",
    "pair_affinity":           "Pair Affinity",
    "within_repeat":           "Within-Week Repeat Penalty",
    "cross_week_rotation":     "Cross-Week Rotation Bonus",
    "area_diversity":          "Area Diversity Penalty",
    "fatigue_index":           "Fatigue Index Penalty",
    "soft_prefer_set":         "Soft Prefer-Set Bonus",
    "sweeper_rotation_penalty":"Sweeper Rotation Penalty",
    "skill_stretch_reward":    "Skill Stretch Reward",
    "prior_run_continuity":    "Prior-Run Continuity Bonus",
    "weekly_load_balance":     "Weekly Load Balance Penalty",
}

DOW_KEYS: list[str] = ["Friday", "Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]


class EngineConfiguratorState(rx.State):
    """State for the engine configurator at /admin/engine."""

    # ── Active tab ──────────────────────────────────────────────────────
    active_tab: int = 0

    # ── Loading / saving / simulating flags ─────────────────────────────
    loading: bool = False
    saving: bool = False
    simulating: bool = False
    dirty: bool = False          # True when local edits differ from saved
    save_error: str = ""
    save_success: bool = False

    # ── Weight vars (15 floats) ──────────────────────────────────────────
    w_skill_match: float = 0.0
    w_preference_fit: float = 0.0
    w_pair_affinity: float = 0.0
    w_within_repeat: float = 0.0
    w_cross_week_rotation: float = 0.0
    w_area_diversity: float = 0.0
    w_fatigue_index: float = 0.0
    w_soft_prefer_set: float = 0.0
    w_sweeper_rotation_penalty: float = 0.0
    w_skill_stretch_reward: float = 0.0
    w_prior_run_continuity: float = 0.0
    w_weekly_load_balance: float = 0.0

    # ── Threshold vars ───────────────────────────────────────────────────
    t_override_difficulty_threshold: float = 6.0
    t_override_load_threshold: float = 6.0
    t_fatigue_window_days: int = 7
    t_rotation_weeks: int = 8

    # ── Placement method (Phase 4f) ──────────────────────────────────────
    # "greedy" = default sequential fill (byte-identical to original)
    # "lap"    = Hungarian/LAP solver for constrained 22-slot block
    placement_method: str = "greedy"

    # ── Headcount vars (grave target by DOW) ────────────────────────────
    hc_friday: int = 0
    hc_saturday: int = 0
    hc_sunday: int = 0
    hc_monday: int = 0
    hc_tuesday: int = 0
    hc_wednesday: int = 0
    hc_thursday: int = 0

    # ── Slot difficulty display (read-only list) ─────────────────────────
    slot_difficulty_rows: list[dict] = []

    # ── History ─────────────────────────────────────────────────────────
    history_rows: list[dict] = []
    history_loading: bool = False

    # ── Single-shot simulation results ──────────────────────────────────
    sim_placements: list[dict] = []
    sim_unresolved: list[dict] = []
    sim_error: str = ""
    sim_config_used: dict = {}
    sim_ran: bool = False

    # ── Multi-week stochastic simulation (Phase 4e Part B) ───────────────
    # Toggle between single-shot dry run and multi-week stochastic sim
    sim_mode: str = "single"          # "single" | "multi"
    # Multi-week sim config
    msim_weeks: int = 2               # number of historical schedules to iterate
    msim_runs: int = 5                # simulation runs per schedule
    msim_callout_rate: float = 2.0   # Poisson λ: avg grave call-offs per night
    msim_seed: int = 42               # RNG seed for reproducibility
    msim_compare_baseline: bool = False  # also run DB active config for comparison
    # Multi-week sim results
    msim_running: bool = False
    msim_error: str = ""
    msim_ran: bool = False
    msim_agg_proposed: dict = {}      # aggregated metrics for proposed config
    msim_agg_baseline: dict = {}      # aggregated metrics for baseline (if --baseline)
    msim_run_rows: list[dict] = []    # per-run flat rows for table display
    msim_json_path: str = ""          # path to sim_results.json
    msim_md_path: str = ""            # path to sim_report.md
    msim_elapsed_s: float = 0.0
    msim_report_md: str = ""          # Phase 4e.1: inline markdown for <details> disclosure

    # ── Saved baseline (for diff) ────────────────────────────────────────
    _saved_weights: dict = {}
    _saved_thresholds: dict = {}
    _saved_headcount: dict = {}

    # ── Internal: active config row id ──────────────────────────────────
    _config_id: str = ""

    # ── Helpers ──────────────────────────────────────────────────────────

    def _weights_dict(self) -> dict:
        return {
            "skill_match":              self.w_skill_match,
            "preference_fit":           self.w_preference_fit,
            "pair_affinity":            self.w_pair_affinity,
            "within_repeat":            self.w_within_repeat,
            "cross_week_rotation":      self.w_cross_week_rotation,
            "area_diversity":           self.w_area_diversity,
            "fatigue_index":            self.w_fatigue_index,
            "soft_prefer_set":          self.w_soft_prefer_set,
            "sweeper_rotation_penalty": self.w_sweeper_rotation_penalty,
            "skill_stretch_reward":     self.w_skill_stretch_reward,
            "prior_run_continuity":     self.w_prior_run_continuity,
            "weekly_load_balance":      self.w_weekly_load_balance,
        }

    def _thresholds_dict(self) -> dict:
        return {
            "override_difficulty_threshold": self.t_override_difficulty_threshold,
            "override_load_threshold":       self.t_override_load_threshold,
            "fatigue_window_days":           self.t_fatigue_window_days,
            "rotation_weeks":                self.t_rotation_weeks,
        }

    def _placement_method_str(self) -> str:
        """Return the current placement method as a safe lowercase string."""
        return str(self.placement_method).lower() if self.placement_method else "greedy"

    def _headcount_dict(self) -> dict:
        return {
            "Friday":    self.hc_friday,
            "Saturday":  self.hc_saturday,
            "Sunday":    self.hc_sunday,
            "Monday":    self.hc_monday,
            "Tuesday":   self.hc_tuesday,
            "Wednesday": self.hc_wednesday,
            "Thursday":  self.hc_thursday,
        }

    def _apply_config_row(self, row: dict) -> None:
        """Unpack a DB config row into all state vars."""
        w = row.get("weights", {})
        self.w_skill_match              = float(w.get("skill_match", 0.0))
        self.w_preference_fit           = float(w.get("preference_fit", 0.0))
        self.w_pair_affinity            = float(w.get("pair_affinity", 0.0))
        self.w_within_repeat            = float(w.get("within_repeat", 0.0))
        self.w_cross_week_rotation      = float(w.get("cross_week_rotation", 0.0))
        self.w_area_diversity           = float(w.get("area_diversity", 0.0))
        self.w_fatigue_index            = float(w.get("fatigue_index", 0.0))
        self.w_soft_prefer_set          = float(w.get("soft_prefer_set", 0.0))
        self.w_sweeper_rotation_penalty = float(w.get("sweeper_rotation_penalty", 0.0))
        self.w_skill_stretch_reward     = float(w.get("skill_stretch_reward", 0.0))
        self.w_prior_run_continuity     = float(w.get("prior_run_continuity", 0.0))
        self.w_weekly_load_balance      = float(w.get("weekly_load_balance", 0.0))

        th = row.get("thresholds", {})
        self.t_override_difficulty_threshold = float(th.get("override_difficulty_threshold", 6.0))
        self.t_override_load_threshold       = float(th.get("override_load_threshold", 6.0))
        self.t_fatigue_window_days           = int(th.get("fatigue_window_days", 7))
        self.t_rotation_weeks                = int(th.get("rotation_weeks", 8))

        hc = row.get("headcount", {})
        self.hc_friday    = int(hc.get("Friday", 0))
        self.hc_saturday  = int(hc.get("Saturday", 0))
        self.hc_sunday    = int(hc.get("Sunday", 0))
        self.hc_monday    = int(hc.get("Monday", 0))
        self.hc_tuesday   = int(hc.get("Tuesday", 0))
        self.hc_wednesday = int(hc.get("Wednesday", 0))
        self.hc_thursday  = int(hc.get("Thursday", 0))

        sp = row.get("slot_priority", {})
        self.slot_difficulty_rows = [
            {"slot": k, "priority": v} for k, v in sorted(sp.items())
        ]

        # Phase 4f: placement_method
        self.placement_method = str(row.get("placement_method", "greedy")).lower()

        self._config_id = row.get("id", "")
        self._saved_weights    = self._weights_dict()
        self._saved_thresholds = self._thresholds_dict()
        self._saved_headcount  = self._headcount_dict()
        self.dirty = False

    # ── Events ───────────────────────────────────────────────────────────

    @rx.event
    async def load_config(self):
        """on_load: fetch active engine_config from DB and populate state."""
        self.loading = True
        self.save_error = ""
        self.save_success = False
        try:
            from shared.db import get_active_engine_config
            row = await asyncio.get_event_loop().run_in_executor(
                None, get_active_engine_config
            )
            # Phase 4e hotfix: distinguish "load returned None" (DB ok, no
            # active row) from "exception thrown" (DB error). Both used to
            # leave sliders at zero defaults silently.
            if row is None:
                self.save_error = (
                    "No active engine_config row found in DB. Sliders showing defaults. "
                    "Save a config to create an active row."
                )
            else:
                self._apply_config_row(row)
        except Exception as exc:
            self.save_error = f"Load error: {exc}"
            print(f"[engine_state.load_config] {exc!r}")
        finally:
            self.loading = False

    @rx.event
    def set_tab(self, tab: int):
        self.active_tab = tab
        if tab == 4 and not self.history_rows:
            return EngineConfiguratorState.load_history

    @rx.event
    async def load_history(self):
        self.history_loading = True
        try:
            from shared.db import list_engine_config_history
            rows = await asyncio.get_event_loop().run_in_executor(
                None, list_engine_config_history, 20
            )
            self.history_rows = rows or []
        except Exception:
            pass
        finally:
            self.history_loading = False

    # ── Weight setters ───────────────────────────────────────────────────

    @rx.event
    def set_weight(self, key: str, value: float):
        """Generic weight setter — called by slider/input on_change."""
        attr = f"w_{key}"
        if hasattr(self, attr):
            setattr(self, attr, float(value))
            self.dirty = True

    # ── Threshold setters ────────────────────────────────────────────────

    @rx.event
    def set_difficulty_threshold(self, v: float):
        self.t_override_difficulty_threshold = float(v)
        self.dirty = True

    @rx.event
    def set_load_threshold(self, v: float):
        self.t_override_load_threshold = float(v)
        self.dirty = True

    # Phase 4e hotfix: rx.input(type="number") emits float on_change values
    # even for integer fields. Accept v: float and cast inside to silence the
    # "expects float but got int" warnings at compile.
    @rx.event
    def set_fatigue_window(self, v: float):
        self.t_fatigue_window_days = int(v)
        self.dirty = True

    @rx.event
    def set_rotation_weeks(self, v: float):
        self.t_rotation_weeks = int(v)
        self.dirty = True

    # ── Placement method setter (Phase 4f) ───────────────────────────────

    @rx.event
    def set_placement_method(self, v: str):
        """Toggle between 'greedy' and 'lap' placement algorithms."""
        v = str(v).lower()
        if v in ("greedy", "lap"):
            self.placement_method = v
            self.dirty = True

    # ── Headcount setters ────────────────────────────────────────────────

    @rx.event
    def set_headcount(self, dow: str, v: float):
        # Phase 4e hotfix — same float-vs-int Reflex on_change quirk.
        attr = f"hc_{dow.lower()}"
        if hasattr(self, attr):
            setattr(self, attr, int(v))
            self.dirty = True

    # ── Discard ──────────────────────────────────────────────────────────

    @rx.event
    async def discard_changes(self):
        """Reload from DB, resetting all local edits."""
        yield EngineConfiguratorState.load_config

    # ── Save ─────────────────────────────────────────────────────────────

    @rx.event
    async def save_config(self):
        """Persist current state to the active engine_config row."""
        self.saving = True
        self.save_error = ""
        self.save_success = False
        try:
            from shared.db import save_engine_config_active
            weights    = self._weights_dict()
            thresholds = self._thresholds_dict()
            headcount  = self._headcount_dict()
            slot_prio  = {row["slot"]: row["priority"] for row in self.slot_difficulty_rows}
            pm         = self._placement_method_str()

            ok = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: save_engine_config_active(weights, thresholds, headcount, slot_prio,
                                                  placement_method=pm)
            )
            if ok:
                self._saved_weights    = weights
                self._saved_thresholds = thresholds
                self._saved_headcount  = headcount
                self.dirty = False
                self.save_success = True
                # Refresh history list if on that tab
                if self.active_tab == 4:
                    yield EngineConfiguratorState.load_history
            else:
                self.save_error = "Save failed — check server logs."
        except Exception as exc:
            self.save_error = f"Save error: {exc}"
        finally:
            self.saving = False

    # ── Simulate ─────────────────────────────────────────────────────────

    @rx.event
    async def run_simulation(self):
        """Dry-run the engine with current (unsaved) config and populate sim results."""
        self.simulating = True
        self.sim_error = ""
        self.sim_ran = False
        self.sim_placements = []
        self.sim_unresolved = []
        self.sim_config_used = {}

        config_override = {
            "weights":          self._weights_dict(),
            "thresholds":       self._thresholds_dict(),
            "headcount":        self._headcount_dict(),
            "slot_priority":    {row["slot"]: row["priority"] for row in self.slot_difficulty_rows},
            "placement_method": self._placement_method_str(),
        }

        try:
            from apps.zds.engine_bridge import run_fill_engine
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: run_fill_engine(config_override=config_override)
            )
            if result.get("error"):
                self.sim_error = result["error"]
            else:
                self.sim_placements  = result.get("placements", [])
                self.sim_unresolved  = result.get("unresolved", [])
                self.sim_config_used = result.get("config_used") or {}
                self.sim_ran = True
        except Exception as exc:
            self.sim_error = f"Simulation error: {exc}"
        finally:
            self.simulating = False

    # ── Multi-week sim setters ───────────────────────────────────────────

    @rx.event
    def set_sim_mode(self, mode: str):
        self.sim_mode = mode

    # Phase 4e hotfix: Reflex's rx.input(type="number") emits float on_change
    # values even for integer fields. Declaring the setters as `v: int` triggers
    # a type-mismatch warning at compile that the framework "ignores intentionally"
    # but it pollutes startup logs. Accept v: float and cast inside.
    @rx.event
    def set_msim_weeks(self, v: float):
        self.msim_weeks = max(1, int(v))

    @rx.event
    def set_msim_runs(self, v: float):
        self.msim_runs = max(1, int(v))

    @rx.event
    def set_msim_callout_rate(self, v: float):
        self.msim_callout_rate = max(0.0, float(v))

    @rx.event
    def set_msim_seed(self, v: float):
        self.msim_seed = int(v)

    @rx.event
    def set_msim_compare_baseline(self, v: bool):
        self.msim_compare_baseline = bool(v)

    # ── Multi-week stochastic simulation ─────────────────────────────────

    @rx.event
    async def run_multi_week_simulation(self):
        """Run the Phase 4e multi-week stochastic simulator.

        Invokes simulate_weeks.py as a library call (not subprocess) so we
        stay in-process and can return structured results to the UI.
        Runs on the executor to keep the event loop free.
        """
        self.msim_running = True
        self.msim_error   = ""
        self.msim_ran     = False
        self.msim_run_rows = []
        self.msim_agg_proposed = {}
        self.msim_agg_baseline = {}
        self.msim_report_md = ""      # Phase 4e.1: reset before each run

        config_override = {
            "weights":          self._weights_dict(),
            "thresholds":       self._thresholds_dict(),
            "headcount":        self._headcount_dict(),
            "slot_priority":    {row["slot"]: row["priority"] for row in self.slot_difficulty_rows},
            "placement_method": self._placement_method_str(),
        }
        weeks        = self.msim_weeks
        runs         = self.msim_runs
        callout_rate = self.msim_callout_rate
        seed         = self.msim_seed
        compare_bl   = self.msim_compare_baseline

        # Phase 4e hotfix #4: Run simulate_weeks.py as a SUBPROCESS, not via
        # in-process importlib + run_in_executor. The previous in-process
        # pattern caused Granian's Tokio worker to panic with:
        #   "Cannot drop pointer into Python heap without the thread being
        #    attached" (pyo3-0.27.2/src/internal/state.rs:322)
        # because Python objects created by sim_mod.main() in the executor
        # thread were getting garbage-collected on a Rust thread that hadn't
        # acquired the GIL. Subprocess isolates Python state in a child
        # process that exits cleanly — no shared Python heap, no panic.
        # Matches the pattern fill_engine uses via engine_bridge.
        def _do_sim():
            import sys, subprocess, tempfile, json as _json
            from pathlib import Path
            _engine_dir = Path(__file__).resolve().parent.parent / "zds" / "engine"
            sim_script  = _engine_dir / "simulate_weeks.py"

            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                cfg_file = tmp_path / "proposed.json"
                cfg_file.write_text(_json.dumps(config_override))
                cmd = [
                    sys.executable, str(sim_script),
                    "--weeks",        str(weeks),
                    "--runs",         str(runs),
                    "--seed",         str(seed),
                    "--callout-rate", str(callout_rate),
                    "--config",       str(cfg_file),
                ]
                if compare_bl:
                    cmd.append("--baseline")

                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=str(_engine_dir),
                    timeout=600,  # 10-minute hard cap
                )
                if proc.returncode != 0:
                    # Phase 4e hotfix #5: simulator prints its diagnostic
                    # output (including [error] lines) to STDOUT, not stderr.
                    # Surface both, with the last 1500 chars truncated to fit
                    # in the UI banner — Brian needs to see WHY the sim exited
                    # ("No schedule files found in ...", "Bad config", etc.).
                    out_tail = (proc.stdout or "")[-1500:].strip()
                    err_tail = (proc.stderr or "")[-1500:].strip()
                    detail = err_tail or out_tail or "(no output)"
                    return {
                        "error":  f"simulate_weeks.py exited {proc.returncode}",
                        "stderr": detail,
                    }
                # Parse the simulator's printed output paths so we can read
                # sim_results.json + sim_report.md.
                json_path = ""
                md_path   = ""
                for line in (proc.stdout or "").splitlines():
                    s = line.strip()
                    if s.endswith("sim_results.json"):
                        json_path = s
                    elif s.endswith("sim_report.md"):
                        md_path = s
                if not json_path or not Path(json_path).exists():
                    return {"error": "simulate_weeks.py finished but sim_results.json was not found"}
                with open(json_path, "r", encoding="utf-8") as f:
                    data = _json.load(f)
                # Read markdown body up-front so the UI can render it inline.
                md_body = ""
                if md_path and Path(md_path).exists():
                    try:
                        md_body = Path(md_path).read_text(encoding="utf-8")
                    except Exception as _md_exc:
                        print(f"[engine_state] sim report read failed: {_md_exc!r}")
                return {
                    "json":         json_path,
                    "md":           md_path,
                    "md_body":      md_body,
                    "agg_proposed": data.get("agg_proposed") or {},
                    "agg_baseline": data.get("agg_baseline") or {},
                }

        try:
            result = await asyncio.get_event_loop().run_in_executor(None, _do_sim)
            if not result:
                self.msim_error = "Simulation returned no results."
            elif result.get("error"):
                self.msim_error = (
                    f"Multi-week sim error: {result['error']}\n"
                    f"{result.get('stderr', '')}"
                )
            else:
                self.msim_agg_proposed = result.get("agg_proposed") or {}
                self.msim_agg_baseline = result.get("agg_baseline") or {}
                self.msim_json_path    = result.get("json") or ""
                self.msim_md_path      = result.get("md") or ""
                self.msim_report_md    = result.get("md_body") or ""
                self.msim_ran = True
        except Exception as exc:
            self.msim_error = f"Multi-week sim error: {exc}"
        finally:
            self.msim_running = False
