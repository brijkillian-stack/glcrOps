"""
Supabase data layer — all reads/writes go through here.
Every function returns plain Python dicts so Reflex state can serialize them cleanly.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from supabase import create_client, Client

from .styles import (SLOT_ELIGIBILITY_MAP, ZONE_LABELS, ZONE_COLORS,
                     TASKS_ZONE, TASKS_RR, TASKS_AUX_SLOT,
                     BG_ZONE, BG_RR_M, BG_RR_W, BG_AUX)

# ── Break-sheet slot-ref helpers ─────────────────────────────────────────────
# Maps the canonical slot_ref label (stored by the engine) → hex color and section.
_SLOT_REF_COLORS: dict[str, str] = {
    "Z1":  ZONE_COLORS["zone_1"],  "Z2":  ZONE_COLORS["zone_2"],
    "Z3":  ZONE_COLORS["zone_3"],  "Z4":  ZONE_COLORS["zone_4"],
    "Z5":  ZONE_COLORS["zone_5"],  "Z6":  ZONE_COLORS["zone_6"],
    "Z7":  ZONE_COLORS["zone_7"],  "Z8":  ZONE_COLORS["zone_8"],
    "Z9":  ZONE_COLORS["zone_9"],  "Z10": ZONE_COLORS["zone_10"],
    "RR1+2 M": ZONE_COLORS["rr_1_2"], "RR6 M": ZONE_COLORS["rr_6"],
    "RR7 M":   ZONE_COLORS["rr_7"],   "RR8 M": ZONE_COLORS["rr_8"],
    "RR10 M":  ZONE_COLORS["rr_10"],
    "RR1+2 W": ZONE_COLORS["rr_1_2"], "RR6 W": ZONE_COLORS["rr_6"],
    "RR7 W":   ZONE_COLORS["rr_7"],   "RR8 W": ZONE_COLORS["rr_8"],
    "RR10 W":  ZONE_COLORS["rr_10"],
    "Z9 SR":   ZONE_COLORS["z9_sr"],  "Admin":   ZONE_COLORS["admin"],
    "Trash 1": ZONE_COLORS["trash_1"],"Trash 2": ZONE_COLORS["trash_2"],
    "Supp 1":  ZONE_COLORS["support_1"], "Supp 2": ZONE_COLORS["support_2"],
    "Supp 3":  ZONE_COLORS["support_3"],
}

# Map the short labels the engine writes for each slot_key + side
ENGINE_SLOT_LABEL: dict[str, str] = {
    "zone_1": "Z1", "zone_2": "Z2", "zone_3": "Z3", "zone_4": "Z4",
    "zone_5": "Z5", "zone_6": "Z6", "zone_7": "Z7", "zone_8": "Z8",
    "zone_9": "Z9", "zone_10": "Z10",
    "rr_1_2_mens":  "RR1+2 M", "rr_6_mens":  "RR6 M",
    "rr_7_mens":    "RR7 M",   "rr_8_mens":  "RR8 M",
    "rr_10_mens":   "RR10 M",
    "rr_1_2_womens":"RR1+2 W", "rr_6_womens":"RR6 W",
    "rr_7_womens":  "RR7 W",   "rr_8_womens":"RR8 W",
    "rr_10_womens": "RR10 W",
    "z9_sr":   "Z9 SR",  "admin":   "Admin",
    "trash_1": "Trash 1","trash_2": "Trash 2",
    "support_1":"Supp 1","support_2":"Supp 2","support_3":"Supp 3",
}


def _slot_ref_color(ref: str) -> str:
    return _SLOT_REF_COLORS.get(ref, "#6b7280")


def _slot_ref_section(ref: str) -> str:
    if ref.startswith("RR"):
        return "Restrooms"
    # "Z1"–"Z10" → Zones; "Z9 SR" → Auxiliary (has a space)
    if ref.startswith("Z") and " " not in ref:
        return "Zones"
    return "Auxiliary"

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")


@lru_cache(maxsize=1)
def _client() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env"
        )
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ── WEEKS ─────────────────────────────────────────────────────────────────────

def fetch_weeks() -> list[dict]:
    res = (
        _client()
        .table("weeks")
        .select("*")
        .order("week_ending", desc=True)
        .execute()
    )
    return res.data or []


def create_week(week_ending: str, label: str, schedule_path: Optional[str] = None) -> dict:
    payload = {"week_ending": week_ending, "label": label, "status": "draft"}
    if schedule_path:
        payload["schedule_path"] = schedule_path
    res = (
        _client()
        .table("weeks")
        .insert(payload)
        .execute()
    )
    return res.data[0] if res.data else {}


def update_week_schedule_path(week_id: str, schedule_path: str) -> bool:
    """Link an existing week to a schedule xlsx in Storage."""
    try:
        (
            _client()
            .table("weeks")
            .update({"schedule_path": schedule_path})
            .eq("id", week_id)
            .execute()
        )
        return True
    except Exception:
        return False


def list_unlinked_schedules() -> list[dict]:
    """Return schedules in Storage that aren't yet linked to a Week record.

    For each storage file that has parseable dates, returns:
        {
          "filename":     "Weekly TM EOW 5-07.xlsx",
          "week_ending":  "2026-05-07",
          "dates":        ["2026-05-01", ..., "2026-05-07"],
          "matching_week": {"id": "...", "label": "..."} | None,
        }

    A schedule is shown if:
      - No Week with that week_ending exists, OR
      - A Week exists for that week_ending but its schedule_path is NULL/empty.
    Schedules already linked to their week are filtered out.
    """
    from shared import storage
    from . import schedule_parser

    schedules = storage.list_schedules()
    if not schedules:
        return []

    # Index existing weeks by week_ending for O(1) lookup
    weeks_by_date: dict[str, dict] = {
        w["week_ending"]: w for w in fetch_weeks()
    }
    # Also index schedule_paths already in use so we never double-list
    linked_paths: set[str] = {
        w.get("schedule_path") for w in weeks_by_date.values()
        if w.get("schedule_path")
    }

    unlinked: list[dict] = []
    sb = _client()
    for s in schedules:
        name = s["name"]
        if name in linked_paths:
            continue   # this xlsx is already the canonical schedule for some week

        # Download just enough bytes to peek the dates. The whole file is
        # only ~30KB so just fetch it all rather than range-requesting.
        try:
            blob: bytes = sb.storage.from_("schedules").download(name)
        except Exception:
            continue
        peek = schedule_parser.peek_schedule_dates(blob)
        if not peek:
            continue

        we = peek["week_ending"]
        match = weeks_by_date.get(we)
        # If a week exists for this date AND it's already linked to a different
        # schedule_path, skip (don't surface as a "create" option).
        if match and match.get("schedule_path") and match["schedule_path"] != name:
            continue

        unlinked.append({
            "filename":     name,
            "week_ending":  we,
            "dates":        peek["dates"],
            "matching_week": (
                {"id": match["id"], "label": match.get("label") or ""}
                if match else None
            ),
        })

    # Sort by week_ending ascending so upcoming weeks bubble up first
    unlinked.sort(key=lambda u: u["week_ending"])
    return unlinked


def create_week_with_nights(
    week_ending: str,
    dates: list[str],
    schedule_path: Optional[str] = None,
    label: str = "",
) -> dict:
    """Atomically create a Week + its 7 Night rows, optionally linked to a
    schedule xlsx in Storage. Returns the new Week dict."""
    sb = _client()
    payload = {"week_ending": week_ending, "label": label, "status": "draft"}
    if schedule_path:
        payload["schedule_path"] = schedule_path

    # 1. Insert the week
    week_res = sb.table("weeks").insert(payload).execute()
    if not week_res.data:
        raise RuntimeError(f"Failed to create week ending {week_ending}")
    week = week_res.data[0]
    week_id = week["id"]

    # 2. Insert 7 nights — one per date in the schedule
    DAY_NAMES = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday",
                 4: "Friday", 5: "Saturday", 6: "Sunday"}
    night_rows = []
    from datetime import date as _date
    for idx, d_str in enumerate(sorted(dates)):
        try:
            y, m, d = (int(p) for p in d_str.split("-"))
            d_obj = _date(y, m, d)
            day_name = DAY_NAMES[d_obj.weekday()]
        except Exception:
            day_name = ""
        night_rows.append({
            "week_id":    week_id,
            "night_date": d_str,
            "day_name":   day_name,
            "day_num":    idx + 1,
            "page_num":   idx + 1,
            "in_rotation": 0,
            "break_mode": "BY_BREAK_WAVE",
            "status":     "draft",
        })

    if night_rows:
        sb.table("nights").insert(night_rows).execute()

    return week


def fetch_week(week_id: str) -> dict:
    res = (
        _client()
        .table("weeks")
        .select("*")
        .eq("id", week_id)
        .single()
        .execute()
    )
    return res.data or {}


def update_week_status(week_id: str, status: str) -> None:
    _client().table("weeks").update({"status": status}).eq("id", week_id).execute()


# ── NIGHTS ────────────────────────────────────────────────────────────────────

def fetch_nights(week_id: str) -> list[dict]:
    res = (
        _client()
        .table("nights")
        .select("*")
        .eq("week_id", week_id)
        .order("day_num")
        .execute()
    )
    return res.data or []


def create_night(week_id: str, night_date: str, day_name: str,
                 day_num: int, page_num: int) -> dict:
    res = (
        _client()
        .table("nights")
        .insert({
            "week_id": week_id,
            "night_date": night_date,
            "day_name": day_name,
            "day_num": day_num,
            "page_num": page_num,
        })
        .execute()
    )
    return res.data[0] if res.data else {}


# ── CALL-OFFS (Phase J) ───────────────────────────────────────────────────────
# A call_off row marks a TM as unavailable for one specific night. Drives:
#   - Schedule tab strikethrough on that TM's name
#   - Deployment slot warning indicator if the TM is currently assigned anywhere
# UNIQUE(tm_id, night_date) prevents double-marking.

def fetch_call_offs_for_night(night_date: str) -> list[dict]:
    """All call_offs for the given night_date, joined with display_name.

    Returns list of: {tm_id, display_name, reason, created_at}
    """
    res = (
        _client()
        .table("call_offs")
        .select("tm_id, reason, created_at, entities(display_name)")
        .eq("night_date", night_date)
        .execute()
    )
    out: list[dict] = []
    for row in (res.data or []):
        ent = row.get("entities") or {}
        out.append({
            "tm_id":       row["tm_id"],
            "display_name": ent.get("display_name", ""),
            "reason":      row.get("reason") or "",
            "created_at":  row.get("created_at") or "",
        })
    return out


def fetch_called_off_names_for_night(night_date: str) -> list[str]:
    """Just the display_names called off for this night — fast lookup for the
    UI strikethrough check."""
    return [c["display_name"] for c in fetch_call_offs_for_night(night_date) if c["display_name"]]


def add_call_off(tm_id: str, night_date: str, reason: str = "") -> bool:
    """Mark a TM called off for a night. Idempotent (UNIQUE constraint dedupes)."""
    try:
        (
            _client()
            .table("call_offs")
            .upsert(
                {
                    "tm_id":      tm_id,
                    "night_date": night_date,
                    "reason":     reason or None,
                },
                on_conflict="tm_id,night_date",
            )
            .execute()
        )
        return True
    except Exception as e:
        print(f"[add_call_off] {e}")
        return False


def remove_call_off(tm_id: str, night_date: str) -> bool:
    """Un-mark a TM as called off for a night."""
    try:
        (
            _client()
            .table("call_offs")
            .delete()
            .eq("tm_id", tm_id)
            .eq("night_date", night_date)
            .execute()
        )
        return True
    except Exception as e:
        print(f"[remove_call_off] {e}")
        return False


# ── ZONE ASSIGNMENTS ──────────────────────────────────────────────────────────

def fetch_zone_assignments(night_id: str) -> list[dict]:
    """Returns all slot assignments for a night, joined with TM display name."""
    res = (
        _client()
        .table("zone_assignments")
        .select(
            "id, slot_type, slot_key, rr_side, is_filled, is_empty,"
            "group_num, has_alert, alert_target,"
            "is_sweeper, sweeper_route, is_locked,"
            "is_crowded, is_extra_crowded, has_trainee, trainee_name,"
            "sort_order, custom_tasks,"
            "entities(id, display_name, metadata)"
        )
        .eq("night_id", night_id)
        .order("sort_order")
        .execute()
    )
    rows = res.data or []
    # Flatten the joined entity into top-level keys + pre-compute display fields
    for row in rows:
        entity = row.pop("entities", None) or {}
        row["tm_id"]    = entity.get("id")
        row["tm_name"]  = entity.get("display_name") or ""
        row["tm_skill"] = (entity.get("metadata") or {}).get("skill_score")
        # Pre-compute display fields so Reflex components never need Python dict lookups on Vars
        sk = row["slot_key"]
        st = row["slot_type"]
        row["label"]        = ZONE_LABELS.get(sk, sk.replace("_", " ").title())
        row["color"]        = ZONE_COLORS.get(sk, "#6b7280")
        row["display_name"] = row["tm_name"] or "Unfilled"
        row["name_color"]   = "#111827" if row["is_filled"] else "#d1d5db"
        row["name_style"]   = "normal"  if row["is_filled"] else "italic"
        # Crowding-based font size (for zone cards)
        if row.get("is_extra_crowded"):
            row["name_size"] = "16px"
        elif row.get("is_crowded"):
            row["name_size"] = "20px"
        else:
            row["name_size"] = "24px"
        # Ensure all optional boolean flags are present and non-None
        for flag in ("has_alert", "is_sweeper", "is_crowded", "is_extra_crowded", "has_trainee"):
            row[flag] = bool(row.get(flag))
        row["alert_target"]  = row.get("alert_target")  or ""
        row["sweeper_route"] = row.get("sweeper_route") or ""
        row["trainee_name"]  = row.get("trainee_name")  or ""
        # ── group_num: DB value if set; otherwise fall back to BG_* defaults ──
        db_grp = row.get("group_num") or 0
        if db_grp:
            row["group_num"] = db_grp
        elif st == "zone":
            n = int(sk.rsplit("_", 1)[-1])
            row["group_num"] = BG_ZONE.get(n, 0)
        elif st == "rr":
            num     = 1 if sk == "rr_1_2" else int(sk.rsplit("_", 1)[-1])
            rr_side = row.get("rr_side", "")
            tbl     = BG_RR_M if rr_side == "mens" else BG_RR_W
            row["group_num"] = tbl.get(num, 0)
        else:
            row["group_num"] = BG_AUX.get(sk, 0)
        row["has_group"] = bool(row["group_num"])
        # ── display_tasks: custom overrides, otherwise defaults from constants
        custom = row.get("custom_tasks")
        if custom is not None:
            row["display_tasks"] = list(custom)
        elif st == "zone":
            n = int(sk.rsplit("_", 1)[-1])
            row["display_tasks"] = list(TASKS_ZONE.get(n, []))
        elif st == "rr":
            num = 1 if sk == "rr_1_2" else int(sk.rsplit("_", 1)[-1])
            row["display_tasks"] = list(TASKS_RR.get(num, []))
        else:
            row["display_tasks"] = list(TASKS_AUX_SLOT.get(sk, []))
        # ── Sweeper task: always appended on top (never stored in custom_tasks) ──
        if row.get("is_sweeper") and row.get("sweeper_route"):
            sweeper_label = f"Sweeper – {row['sweeper_route']}"
            if sweeper_label not in row["display_tasks"]:
                row["display_tasks"] = list(row["display_tasks"]) + [sweeper_label]
        # ── Normalise is_locked ──
        row["is_locked"] = bool(row.get("is_locked"))

    # ── Duplicate TM detection (across all slot types for this night) ──────────
    from collections import Counter
    tm_counts = Counter(
        r["tm_id"] for r in rows if r.get("tm_id")
    )
    dup_ids = {tid for tid, cnt in tm_counts.items() if cnt > 1}
    for row in rows:
        row["has_duplicate"] = row.get("tm_id") in dup_ids

    return rows


def update_zone_assignment(assignment_id: str, tm_id: Optional[str]) -> None:
    _client().table("zone_assignments").update({
        "tm_id": tm_id,
        "is_filled": tm_id is not None,
        "is_empty": tm_id is None,
    }).eq("id", assignment_id).execute()


def update_slot_tasks(slot_id: str, tasks: list[str]) -> None:
    """Persist a custom task list for a single slot (overrides defaults)."""
    _client().table("zone_assignments").update(
        {"custom_tasks": tasks}
    ).eq("id", slot_id).execute()


def update_break_wave(assignment_id: str, new_wave: int) -> None:
    """Move a TM to a different break wave."""
    _client().table("break_assignments").update(
        {"break_wave": new_wave}
    ).eq("id", assignment_id).execute()


def upsert_zone_assignment(night_id: str, slot_type: str, slot_key: str,
                            rr_side: Optional[str], sort_order: int,
                            tm_id: Optional[str] = None, **kwargs) -> dict:
    payload = {
        "night_id": night_id,
        "slot_type": slot_type,
        "slot_key": slot_key,
        "rr_side": rr_side,
        "sort_order": sort_order,
        "tm_id": tm_id,
        "is_filled": tm_id is not None,
        **kwargs,
    }
    res = (
        _client()
        .table("zone_assignments")
        .upsert(payload, on_conflict="night_id,slot_type,slot_key,rr_side")
        .execute()
    )
    return res.data[0] if res.data else {}


# ── BREAK ASSIGNMENTS ─────────────────────────────────────────────────────────

def fetch_break_assignments(night_id: str) -> list[dict]:
    res = (
        _client()
        .table("break_assignments")
        .select("id, break_wave, sort_order, slot_ref, is_wave_locked, entities(id, display_name)")
        .eq("night_id", night_id)
        .order("sort_order")
        .execute()
    )
    rows = res.data or []
    for row in rows:
        entity = row.pop("entities", None) or {}
        row["tm_id"]   = entity.get("id") or ""
        row["tm_name"] = entity.get("display_name") or ""
        ref = row.get("slot_ref") or ""
        row["slot_ref"]        = ref
        row["slot_label"]      = ref
        row["slot_color"]      = _slot_ref_color(ref)
        row["section"]         = _slot_ref_section(ref)
        row["is_wave_locked"]  = bool(row.get("is_wave_locked"))
        # show_section_header is computed per-wave in state.py
        row["show_section_header"] = False
    return rows


def replace_break_assignments(night_id: str, rows: list[dict]) -> None:
    """Delete all break assignments for a night and insert fresh engine-generated rows.

    Locked waves (is_wave_locked=True) are preserved — the engine re-inserts those
    rows using the saved wave value instead of the BG_* default.
    """
    sb = _client()

    # Save any wave-locked assignments before wiping
    locked_res = (
        sb.table("break_assignments")
        .select("slot_ref, break_wave")
        .eq("night_id", night_id)
        .eq("is_wave_locked", True)
        .execute()
    )
    locked_map: dict[str, int] = {
        r["slot_ref"]: r["break_wave"] for r in (locked_res.data or [])
    }

    # Wipe the night
    sb.table("break_assignments").delete().eq("night_id", night_id).execute()

    # Re-insert, overriding waves for locked slots
    if rows:
        for row in rows:
            if row["slot_ref"] in locked_map:
                row["break_wave"]    = locked_map[row["slot_ref"]]
                row["is_wave_locked"] = True
        sb.table("break_assignments").insert(rows).execute()


def update_slot_lock(assignment_id: str, locked: bool) -> None:
    """Toggle the position lock on a zone/RR/aux slot."""
    _client().table("zone_assignments").update(
        {"is_locked": locked}
    ).eq("id", assignment_id).execute()


def update_wave_lock(assignment_id: str, locked: bool) -> None:
    """Toggle the wave lock on a break assignment."""
    _client().table("break_assignments").update(
        {"is_wave_locked": locked}
    ).eq("id", assignment_id).execute()


# ── OVERLAP ASSIGNMENTS ───────────────────────────────────────────────────────

def fetch_overlap_assignments(night_id: str) -> list[dict]:
    res = (
        _client()
        .table("overlap_assignments")
        .select("id, overlap_window, position, is_filled, task, entities(id, display_name)")
        .eq("night_id", night_id)
        .order("overlap_window")
        .order("position")
        .execute()
    )
    rows = res.data or []
    for row in rows:
        entity = row.pop("entities", None) or {}
        row["tm_id"]   = entity.get("id")
        row["tm_name"] = entity.get("display_name") or ""
        row["task"]    = row.get("task") or ""
    return rows


# ── TM ROSTER (for picker) ────────────────────────────────────────────────────

def fetch_all_tms() -> list[dict]:
    """All active TMs with their eligibility maps."""
    res = (
        _client()
        .table("entities")
        .select("id, display_name, metadata")
        .eq("status", "active")
        .order("display_name")
        .execute()
    )
    tms = []
    for row in (res.data or []):
        meta  = row.get("metadata") or {}
        score = meta.get("skill_score", 0) or 0
        tms.append({
            "id":           row["id"],
            "display_name": row["display_name"],
            "skill_score":  score,
            "skill_str":    str(score),   # Reflex can't call str() on Vars
            "skill_color":  ("#065f46" if score >= 8 else
                             "#1d4ed8" if score >= 5 else "#6b7280"),
            "grave_pool":   meta.get("grave_pool", "") or "",
            "eligibility":  meta.get("eligibility", {}),
            "preferences":  meta.get("preferences", []),
            # Annotated by state.open_picker at pick-time; defaults keep TypedDict valid
            "is_assigned":  False,
            "assigned_to":  "",
            "on_schedule":  False,
            "schedule_pool": "off",
        })
    return tms


def fetch_eligible_tms_for_slot(slot_key: str, rr_side: Optional[str] = None) -> list[dict]:
    """
    Return TMs eligible for the given slot.
    slot_key: e.g. 'zone_10', 'rr_1_2'
    rr_side:  'mens' | 'womens' | None
    """
    # Build the eligibility lookup key
    if rr_side:
        lookup = f"{slot_key}_{rr_side}"
    else:
        lookup = slot_key

    elg_key = SLOT_ELIGIBILITY_MAP.get(lookup)

    all_tms = fetch_all_tms()

    # Always exclude TMs with no grave pool assignment (wrong shift / inactive)
    grave_tms = [tm for tm in all_tms if tm["grave_pool"]]

    if elg_key is None:
        # No eligibility gate (e.g. support slots) — return all grave-pool TMs
        return grave_tms

    return [
        tm for tm in grave_tms
        if tm["eligibility"].get(elg_key, False)
    ]


# ── ZONE DEPLOYMENT ENGINE SYNC ───────────────────────────────────────────────

def sync_engine_to_week(
    week_id: str,
    engine_result: dict,
    target_night_id: Optional[str] = None,
) -> dict:
    """
    Write fill-engine placements into Supabase zone_assignments.

    Rules:
    • Locked slots (is_locked=True) are NEVER overwritten.
    • Filled placements → set tm_id to the engine's chosen TM (by display_name lookup).
    • Unresolved slots  → clear tm_id (unless locked).
    • PM/AM overlap slots are skipped (they go in overlap_assignments, not here).
    • If target_night_id is provided, only that night's slots are touched.

    Returns a summary dict:
        {updated, skipped_locked, unmapped, unresolved_cleared, error}
    """
    from .engine_bridge import ENGINE_TO_SUPABASE, _SKIP_SLOTS

    if engine_result.get("error"):
        return {"updated": 0, "skipped_locked": 0, "unmapped": 0,
                "unresolved_cleared": 0, "error": engine_result["error"]}

    sb = _client()

    # 1. Build date → night_id map for this week
    nights = fetch_nights(week_id)
    date_to_night: dict[str, str] = {n["night_date"]: n["id"] for n in nights}
    night_ids = [n["id"] for n in nights]

    if not night_ids:
        return {"updated": 0, "skipped_locked": 0, "unmapped": 0,
                "unresolved_cleared": 0, "error": "No nights found for this week."}

    # 2. Fetch all zone_assignments for the week: build lookup
    #    Key: (night_id, slot_key, rr_side)  →  {id, is_locked}
    slot_lookup: dict[tuple, dict] = {}
    for nid in night_ids:
        res = (
            sb.table("zone_assignments")
            .select("id, slot_key, rr_side, is_locked, tm_id")
            .eq("night_id", nid)
            .execute()
        )
        for row in (res.data or []):
            rr_side = row.get("rr_side")  # None for non-RR slots
            key = (nid, row["slot_key"], rr_side)
            slot_lookup[key] = {
                "id":        row["id"],
                "is_locked": bool(row.get("is_locked")),
            }

    # 3. Build TM display_name → UUID map from entities table
    tm_res = sb.table("entities").select("id, display_name").execute()
    name_to_id: dict[str, str] = {
        r["display_name"]: r["id"] for r in (tm_res.data or [])
    }

    # 4. Process filled placements
    updated = skipped_locked = unmapped = 0
    touched_slots: set[tuple] = set()   # tracks which slots the engine addressed

    for p in engine_result.get("placements", []):
        engine_slot = p.get("zone_slot", "")
        date_str    = p.get("date", "")
        tm_name     = p.get("tm_display_name", "")

        # Skip overlap/buddy slots — they don't map to zone_assignments
        if engine_slot in _SKIP_SLOTS or engine_slot.startswith(("PMOL", "AMOL")):
            continue

        night_id = date_to_night.get(date_str)
        if not night_id:
            unmapped += 1
            continue

        # If targeting a specific night, skip all others
        if target_night_id and night_id != target_night_id:
            continue

        supabase_slot = ENGINE_TO_SUPABASE.get(engine_slot)
        if not supabase_slot:
            unmapped += 1
            continue

        slot_key, rr_side = supabase_slot
        lookup_key = (night_id, slot_key, rr_side)
        slot_rec = slot_lookup.get(lookup_key)
        if not slot_rec:
            unmapped += 1
            continue

        touched_slots.add(lookup_key)

        if slot_rec["is_locked"]:
            skipped_locked += 1
            continue

        tm_id = name_to_id.get(tm_name)
        update_zone_assignment(slot_rec["id"], tm_id)
        updated += 1

    # 5. Process unresolved slots — clear them (unless locked)
    unresolved_cleared = 0
    for u in engine_result.get("unresolved", []):
        engine_slot = u.get("zone_slot", "")
        date_str    = u.get("date", "")

        if engine_slot in _SKIP_SLOTS or engine_slot.startswith(("PMOL", "AMOL")):
            continue

        night_id = date_to_night.get(date_str)
        if not night_id:
            continue

        if target_night_id and night_id != target_night_id:
            continue

        supabase_slot = ENGINE_TO_SUPABASE.get(engine_slot)
        if not supabase_slot:
            continue

        slot_key, rr_side = supabase_slot
        lookup_key = (night_id, slot_key, rr_side)
        slot_rec = slot_lookup.get(lookup_key)
        if not slot_rec:
            continue

        touched_slots.add(lookup_key)

        if slot_rec["is_locked"]:
            skipped_locked += 1
            continue

        update_zone_assignment(slot_rec["id"], None)
        unresolved_cleared += 1

    return {
        "updated":            updated,
        "skipped_locked":     skipped_locked,
        "unmapped":           unmapped,
        "unresolved_cleared": unresolved_cleared,
        "error":              None,
    }
