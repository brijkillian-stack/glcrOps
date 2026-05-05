"""
engine_bridge.py — Bridge between the GLCR fill engine and the Supabase web app.

Runs fill_engine.py as a subprocess, parses its audit JSON output, and
returns structured placement data that sync_engine_to_week() can apply to
Supabase zone_assignments while respecting is_locked flags.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Vendored engine lives alongside this file at apps/zds/engine/.
# Contains fill_engine.py, glcr_engine package, Rules/, Templates/, Archive/,
# Inputs/, Outputs/. Path resolves the same locally and on Render.
GLCR_BASE = Path(__file__).resolve().parent / "engine"
FILL_ENGINE = GLCR_BASE / "fill_engine.py"

# ── Slot mapping: fill_engine code → (Supabase slot_key, rr_side) ────────────
# Covers all primary slots. PMOL/AMOL/Z9SRBuddy are intentionally omitted —
# they are not zone_assignment rows (overlaps live in overlap_assignments).
ENGINE_TO_SUPABASE: dict[str, tuple[str, str | None]] = {
    "Zone1":    ("zone_1",    None),
    "Zone2":    ("zone_2",    None),
    "Zone3":    ("zone_3",    None),
    "Zone4":    ("zone_4",    None),
    "Zone5":    ("zone_5",    None),
    "Zone6":    ("zone_6",    None),
    "Zone7":    ("zone_7",    None),
    "Zone8":    ("zone_8",    None),
    "Zone9":    ("zone_9",    None),
    "Zone10":   ("zone_10",   None),
    "Zone9SR":  ("z9_sr",     None),
    "MRR1":     ("rr_1_2",    "mens"),
    "WRR1":     ("rr_1_2",    "womens"),
    "MRR6":     ("rr_6",      "mens"),
    "WRR6":     ("rr_6",      "womens"),
    "MRR7":     ("rr_7",      "mens"),
    "WRR7":     ("rr_7",      "womens"),
    "MRR8":     ("rr_8",      "mens"),
    "WRR8":     ("rr_8",      "womens"),
    "MRR10":    ("rr_10",     "mens"),
    "WRR10":    ("rr_10",     "womens"),
    "Admin":    ("admin",     None),
    "Trash1":   ("trash_1",   None),
    "Trash2":   ("trash_2",   None),
    "MP1":      ("support_1", None),
    "MP2":      ("support_2", None),
    "Support3": ("support_3", None),
}

# Slots that don't map to zone_assignments (overlaps, buddy seat, etc.)
_SKIP_SLOTS = frozenset({
    "PMOL1", "PMOL2", "PMOL3", "PMOL4", "PMOL5", "PMOL6",
    "AMOL1", "AMOL2", "AMOL3", "AMOL4", "AMOL5", "AMOL6",
    "Z9SRBuddy",
})


def run_fill_engine(schedule_file: str | None = None) -> dict:
    """
    Run fill_engine.py as a subprocess and return its results.

    Args:
        schedule_file: Optional filename (not full path) of the schedule xlsx
                       inside GLCR/Inputs/Weekly Schedules/. If None the
                       engine auto-detects the most recent file.

    Returns a dict with keys:
        week_ending   str          ISO date string (e.g. "2026-04-30")
        placements    list[dict]   [{date, zone_slot, tm_display_name, ...}, ...]
        unresolved    list[dict]   [{date, zone_slot, priority}, ...]
        stdout        str          Full engine stdout (for debug / error display)
        error         str | None   Set if the engine failed or output couldn't be parsed
    """
    if not FILL_ENGINE.exists():
        return {
            "week_ending": "", "placements": [], "unresolved": [],
            "stdout": "", "stderr": "",
            "error": f"fill_engine.py not found at {FILL_ENGINE}",
        }

    # Sync schedules from Supabase Storage into the local Inputs/ folder.
    # On Render the local folder is wiped on each container restart, so
    # without this the engine would see an empty Inputs/ even though the
    # user uploaded a schedule earlier this week.
    try:
        from shared import storage
        inputs_dir = GLCR_BASE / "Inputs" / "Weekly Schedules"
        storage.sync_schedules_to(inputs_dir)
    except Exception as exc:
        # Don't fail the engine run if Storage is briefly unavailable —
        # the engine will still try the local Inputs/ directory.
        print(f"[engine_bridge] Storage sync warning: {exc}")

    cmd = [sys.executable, str(FILL_ENGINE)]
    if schedule_file:
        cmd.append(schedule_file)

    try:
        result = subprocess.run(
            cmd,
            cwd=str(GLCR_BASE),
            capture_output=True,
            text=True,
            timeout=180,   # 3-minute ceiling — engine normally finishes in <20s
        )
    except subprocess.TimeoutExpired:
        return {
            "week_ending": "", "placements": [], "unresolved": [],
            "stdout": "", "stderr": "",
            "error": "Deployment engine timed out after 3 minutes.",
        }
    except Exception as exc:
        return {
            "week_ending": "", "placements": [], "unresolved": [],
            "stdout": "", "stderr": "",
            "error": f"Failed to launch engine: {exc}",
        }

    stdout = result.stdout or ""
    stderr = result.stderr or ""

    if result.returncode != 0:
        snippet = (stderr or stdout)[:600]
        return {
            "week_ending": "", "placements": [], "unresolved": [],
            "stdout": stdout, "stderr": stderr,
            "error": f"Engine exited with code {result.returncode}:\n{snippet}",
        }

    # ── Parse week_ending from the "Week ending YYYY-MM-DD" line in stdout ──
    week_ending = None
    for line in stdout.splitlines():
        if "Week ending" in line:
            # "GLCR Grave Deployment v8  |  Week ending 2026-04-30"
            parts = line.split("Week ending")
            if len(parts) > 1:
                candidate = parts[1].strip()[:10]
                if len(candidate) == 10 and candidate[4] == "-":
                    week_ending = candidate
                    break

    if not week_ending:
        return {
            "week_ending": "", "placements": [], "unresolved": [],
            "stdout": stdout, "stderr": stderr,
            "error": "Could not determine week_ending from engine output.\n"
                     f"Stdout:\n{stdout[:400]}",
        }

    # ── Read the audit JSON produced by the engine ─────────────────────
    audit_path = (
        GLCR_BASE / "Outputs" / week_ending
        / f"Grave Deployment Audit - {week_ending}.json"
    )
    if not audit_path.exists():
        return {
            "week_ending": week_ending, "placements": [], "unresolved": [],
            "stdout": stdout, "stderr": stderr,
            "error": f"Audit JSON not found: {audit_path}",
        }

    try:
        with open(audit_path) as f:
            audit = json.load(f)
    except Exception as exc:
        return {
            "week_ending": week_ending, "placements": [], "unresolved": [],
            "stdout": stdout, "stderr": stderr,
            "error": f"Could not parse audit JSON: {exc}",
        }

    return {
        "week_ending": week_ending,
        "placements":  audit.get("placements", []),
        "unresolved":  audit.get("unresolved_slots", []),
        "stdout": stdout,
        "stderr": stderr,
        "error": None,
    }
