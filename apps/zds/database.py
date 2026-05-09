"""
Supabase data layer — all reads/writes go through here.
Every function returns plain Python dicts so Reflex state can serialize them cleanly.
"""

from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from supabase import create_client, Client

from .styles import (SLOT_ELIGIBILITY_MAP, ZONE_LABELS, ZONE_COLORS,
                     TASKS_ZONE, TASKS_RR, TASKS_AUX_SLOT,
                     BG_ZONE, BG_RR_M, BG_RR_W, BG_AUX)

# ── Task annotation ID helper (Phase 4k.7) ───────────────────────────────────

def _annot_id_for_task(task_id: str, row_label: str, name: str) -> str:
    """Stable annotation identifier for a task.

    Canonical tasks (have a UUID from zone_tasks): annot_id == task_id.
    Custom / hardcoded tasks (id=""): annot_id == "custom:{row_label}:{sha1(name)[:8]}".

    The sha1 truncation gives 8 hex chars — collision risk on a single card
    with one custom task is negligible. NEVER change this format without
    migrating existing zds_annotations rows.
    """
    if task_id:
        return task_id
    h = hashlib.sha1(name.strip().encode("utf-8")).hexdigest()[:8]
    return f"custom:{row_label}:{h}"


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
    rows = res.data or []
    # Phase R — stamp a human-readable date range on each row for the cards.
    for r in rows:
        r["date_range"] = format_week_date_range(r.get("week_ending", ""))
    return rows


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
    """Link an existing week to a schedule xlsx in Storage. Pass an empty
    string to unlink (writes NULL)."""
    try:
        value = schedule_path if (schedule_path or "").strip() else None
        (
            _client()
            .table("weeks")
            .update({"schedule_path": value})
            .eq("id", week_id)
            .execute()
        )
        return True
    except Exception:
        return False


def unlink_schedule_from_week(week_id: str) -> bool:
    """Phase P — clear the schedule_path on a week (one-click "Unlink")."""
    return update_week_schedule_path(week_id, "")


# ── Canonical slot template (27 rows per night) ───────────────────────────────
# Matches the sort_order / slot_type / rr_side schema verified against existing
# zone_assignment rows. Used by ensure_zone_slots_for_night().
_SLOT_TEMPLATE: list[tuple[str, str, Optional[str], int]] = [
    # (slot_type, slot_key,    rr_side,   sort_order)
    ("zone", "zone_1",    None,      1),
    ("zone", "zone_2",    None,      2),
    ("zone", "zone_3",    None,      3),
    ("zone", "zone_4",    None,      4),
    ("zone", "zone_5",    None,      5),
    ("zone", "zone_6",    None,      6),
    ("zone", "zone_7",    None,      7),
    ("zone", "zone_8",    None,      8),
    ("zone", "zone_9",    None,      9),
    ("zone", "zone_10",   None,     10),
    ("rr",   "rr_1_2",   "mens",   11),
    ("rr",   "rr_1_2",   "womens", 12),
    ("rr",   "rr_6",     "mens",   13),
    ("rr",   "rr_6",     "womens", 14),
    ("rr",   "rr_7",     "mens",   15),
    ("rr",   "rr_7",     "womens", 16),
    ("rr",   "rr_8",     "mens",   17),
    ("rr",   "rr_8",     "womens", 18),
    ("rr",   "rr_10",    "mens",   19),
    ("rr",   "rr_10",    "womens", 20),
    ("aux",  "z9_sr",    None,     21),
    ("aux",  "admin",    None,     22),
    ("aux",  "trash_1",  None,     23),
    ("aux",  "trash_2",  None,     24),
    ("aux",  "support_1",None,     25),
    ("aux",  "support_2",None,     26),
    ("aux",  "support_3",None,     27),
]


def ensure_zone_slots_for_night(night_id: str) -> int:
    """Idempotently create all 27 zone_assignment slot rows for a night.

    This is a no-op if rows already exist (skips existing slot_key/rr_side
    combinations). Returns the number of rows actually inserted (0 if already
    fully seeded).

    Called by sync_engine_to_week before building the slot_lookup so new
    weeks have rows to update rather than silently dropping placements as
    'unmapped'.
    """
    if not night_id:
        return 0
    try:
        sb = _client()
        # 1. Fetch existing (slot_key, rr_side) pairs for this night
        res = (
            sb.table("zone_assignments")
            .select("slot_key, rr_side")
            .eq("night_id", night_id)
            .execute()
        )
        existing: set[tuple] = set()
        for row in (res.data or []):
            existing.add((row["slot_key"], row.get("rr_side")))

        # 2. Insert missing slots
        to_insert = []
        for slot_type, slot_key, rr_side, sort_order in _SLOT_TEMPLATE:
            if (slot_key, rr_side) in existing:
                continue
            payload: dict = {
                "night_id":   night_id,
                "slot_type":  slot_type,
                "slot_key":   slot_key,
                "sort_order": sort_order,
                "is_filled":  False,
                "is_empty":   True,
                "is_locked":  False,
            }
            if rr_side:
                payload["rr_side"] = rr_side
            to_insert.append(payload)

        if to_insert:
            sb.table("zone_assignments").insert(to_insert).execute()
        return len(to_insert)
    except Exception as exc:
        print(f"[ensure_zone_slots_for_night] {exc}")
        return 0


def reset_week_placements(week_id: str) -> int:
    """Phase P — clear every TM assignment on the week's nights so the user
    can re-run the engine fresh. Locked slots are also cleared (the user
    asked to start over). Returns the number of slots cleared."""
    if not week_id:
        return 0
    try:
        sb = _client()
        # Get all night ids for the week
        n_res = sb.table("nights").select("id").eq("week_id", week_id).execute()
        night_ids = [n["id"] for n in (n_res.data or [])]
        if not night_ids:
            return 0
        # Clear every zone_assignments row's tm_id for these nights
        za_res = (
            sb.table("zone_assignments")
            .update({
                "tm_id": None,
                "is_filled": False,
                "is_empty": True,
                "is_locked": False,
            })
            .in_("night_id", night_ids)
            .execute()
        )
        return len(za_res.data or [])
    except Exception as e:
        print(f"[reset_week_placements] {e}")
        return 0


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


def update_night_lock(night_id: str, is_locked: bool, locked_by: str = "") -> dict:
    """Set or clear the night-level lock.

    When locking, also stamps locked_by (editor email) and locked_at (now()).
    When unlocking, clears locked_by and locked_at.
    Returns the updated row.
    """
    import datetime as _dt
    if is_locked:
        payload: dict = {
            "is_locked": True,
            "locked_by": locked_by,
            "locked_at": _dt.datetime.utcnow().isoformat() + "Z",
        }
    else:
        payload = {
            "is_locked": False,
            "locked_by": None,
            "locked_at": None,
        }
    res = (
        _client()
        .table("nights")
        .update(payload)
        .eq("id", night_id)
        .execute()
    )
    return res.data[0] if res.data else {}


# ── NOTICES (Phase E) ────────────────────────────────────────────────────────
# Typed slot annotations shown as colored dots on zone cards.
# Types: "alert" | "info" | "training" | "meeting"

def fetch_notices(night_id: str) -> list[dict]:
    """Return all notice rows for a night, ordered oldest-first."""
    res = (
        _client()
        .table("notices")
        .select("*")
        .eq("night_id", night_id)
        .order("created_at")
        .execute()
    )
    return res.data or []


def create_notice(
    night_id: str,
    slot_key: str,
    notice_type: str,
    text: str,
    created_by: str = "",
) -> dict:
    """Insert a new notice. Returns the created row."""
    res = (
        _client()
        .table("notices")
        .insert({
            "night_id":   night_id,
            "slot_key":   slot_key,
            "type":       notice_type,
            "text":       text,
            "created_by": created_by,
        })
        .execute()
    )
    return res.data[0] if res.data else {}


def delete_notice(notice_id: str) -> None:
    """Delete a notice by its UUID."""
    _client().table("notices").delete().eq("id", notice_id).execute()


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


# ── ENTITY MANAGEMENT (Phase O) ───────────────────────────────────────────────
# TM creation, alias editing, and display_name uniqueness checks.

def is_display_name_taken(display_name: str, exclude_id: str = "") -> bool:
    """True if a TM with this display_name already exists.
    Pass `exclude_id` when validating during an edit (don't flag the same
    row as a conflict with itself)."""
    name = (display_name or "").strip()
    if not name:
        return False
    try:
        q = (
            _client()
            .table("entities")
            .select("id")
            .eq("entity_type", "tm")
            .eq("display_name", name)
        )
        if exclude_id:
            q = q.neq("id", exclude_id)
        res = q.limit(1).execute()
        return bool(res.data)
    except Exception as e:
        print(f"[is_display_name_taken] {e}")
        return False


def insert_tm_entity(
    display_name: str,
    grave_pool: str = "Grave",
    aliases: Optional[list[str]] = None,
) -> dict:
    """Create a new TM entity. Returns the inserted row dict.

    Raises ValueError if display_name is empty or already taken.
    """
    name = (display_name or "").strip()
    if not name:
        raise ValueError("display_name is required.")
    if is_display_name_taken(name):
        raise ValueError(f"A TM named '{name}' already exists.")

    import uuid
    metadata = {
        "active":      True,
        "grave_pool":  grave_pool or "Grave",
        "display_name": name,
        "skill_score": 5,
        "aliases":     [a.strip().lower() for a in (aliases or []) if a.strip()],
        "eligibility": {},
    }
    row = {
        "id":           f"tm_{uuid.uuid4().hex[:12]}",
        "name":         name,
        "display_name": name,
        "entity_type":  "tm",
        "status":       "active",
        "metadata":     metadata,
    }
    res = _client().table("entities").insert(row).execute()
    return (res.data or [row])[0]


def set_tm_status(tm_id: str, status: str) -> bool:
    """Phase O — set a TM's status. Updates BOTH the top-level `status`
    column (which fetch_all_tms filters on) and metadata.status (which
    get_people reads), so archived TMs disappear from the picker and
    schedule resolver in one shot.

    Common values:
      'active'    — visible everywhere (default)
      'archived'  — hidden from all active views; still in DB for history
      'loa'       — leave-of-absence; visible with LOA filter
      'separated' — left the company
    """
    if not (tm_id and status):
        return False
    try:
        # Fetch current metadata, update its status, write back along with column
        res = (
            _client()
            .table("entities")
            .select("metadata")
            .eq("id", tm_id)
            .single()
            .execute()
        )
        meta = (res.data or {}).get("metadata") or {}
        meta["status"] = status
        # Postgres `status` column is the source of truth fetch_all_tms filters on.
        # We treat anything other than 'active' as not active.
        (
            _client()
            .table("entities")
            .update({
                "status":   "active" if status == "active" else status,
                "metadata": meta,
            })
            .eq("id", tm_id)
            .execute()
        )
        return True
    except Exception as e:
        print(f"[set_tm_status] {e}")
        return False


def archive_tm(tm_id: str) -> bool:
    """Convenience — set status='archived'."""
    return set_tm_status(tm_id, "archived")


def unarchive_tm(tm_id: str) -> bool:
    """Convenience — set status back to 'active'."""
    return set_tm_status(tm_id, "active")


def update_tm_display_name(tm_id: str, display_name: str, full_name: Optional[str] = None) -> dict:
    """Phase Q — rename a TM. Updates BOTH the canonical column and
    metadata.display_name. Validates uniqueness (excluding self).

    Returns {"ok": bool, "error": str}.
    """
    name = (display_name or "").strip()
    if not (tm_id and name):
        return {"ok": False, "error": "TM id + display name required."}
    # Uniqueness — allow keeping the same name (no-op rename)
    try:
        clash = (
            _client()
            .table("entities")
            .select("id")
            .eq("entity_type", "tm")
            .eq("display_name", name)
            .neq("id", tm_id)
            .limit(1)
            .execute()
        )
        if clash.data:
            return {"ok": False, "error": f"A TM named '{name}' already exists."}
    except Exception as e:
        return {"ok": False, "error": f"Uniqueness check failed: {e}"}

    try:
        # Read current metadata so we can also update display_name inside it.
        cur = (
            _client()
            .table("entities")
            .select("metadata, name")
            .eq("id", tm_id)
            .single()
            .execute()
        )
        meta = (cur.data or {}).get("metadata") or {}
        meta["display_name"] = name

        update_payload: dict = {
            "display_name": name,
            "metadata":     meta,
        }
        # Only touch full legal name if explicitly provided
        if full_name is not None:
            update_payload["name"] = (full_name or "").strip()

        (
            _client()
            .table("entities")
            .update(update_payload)
            .eq("id", tm_id)
            .execute()
        )
        return {"ok": True, "error": ""}
    except Exception as e:
        return {"ok": False, "error": f"Save failed: {e}"}


def merge_tm(keep_id: str, drop_id: str) -> dict:
    """Phase Q — merge two TM entities.

    keep_id wins everything (display_name, status, skill_score). drop_id's
    aliases / score_history / accommodations / preferences / pair_affinities
    are unioned into keep_id, then every FK reference is repointed
    (zone_assignments, break_assignments, overlap_assignments, call_offs,
    area_checks, schedule_overrides, note_entities), then drop_id is deleted.

    Returns {"ok": bool, "error": str, "moved": dict}.
    """
    if not (keep_id and drop_id) or keep_id == drop_id:
        return {"ok": False, "error": "Pick two different TMs to merge.",
                "moved": {}}
    try:
        sb = _client()
        # 1. Pull both entities so we can merge metadata
        keep_res = sb.table("entities").select("*").eq("id", keep_id).single().execute()
        drop_res = sb.table("entities").select("*").eq("id", drop_id).single().execute()
        keep = keep_res.data or {}
        drop = drop_res.data or {}
        if not keep or not drop:
            return {"ok": False, "error": "Couldn't load one of the TMs.", "moved": {}}

        keep_meta = keep.get("metadata") or {}
        drop_meta = drop.get("metadata") or {}

        # Union helpers — preserve order, dedupe
        def _union_dict_lists(a: list, b: list, key_fn) -> list:
            seen = set()
            out = []
            for item in (a or []) + (b or []):
                if not isinstance(item, dict):
                    continue
                k = key_fn(item)
                if k in seen:
                    continue
                seen.add(k)
                out.append(item)
            return out

        merged_meta = dict(keep_meta)
        # Aliases — also include drop's display first-name token so the
        # resolver still finds keep when seeing the dropped name.
        merged_aliases = list(keep_meta.get("aliases") or [])
        for a in (drop_meta.get("aliases") or []):
            if a and a.lower() not in [x.lower() for x in merged_aliases]:
                merged_aliases.append(a.lower())
        drop_first = (drop.get("display_name") or "").strip().split()[0].lower()
        if drop_first and drop_first not in [x.lower() for x in merged_aliases]:
            merged_aliases.append(drop_first)
        merged_meta["aliases"] = merged_aliases

        merged_meta["score_history"] = _union_dict_lists(
            keep_meta.get("score_history") or [],
            drop_meta.get("score_history") or [],
            key_fn=lambda d: (d.get("date", ""), d.get("reason", "")),
        )
        merged_meta["accommodations"] = _union_dict_lists(
            keep_meta.get("accommodations") or [],
            drop_meta.get("accommodations") or [],
            key_fn=lambda d: (d.get("type", ""), d.get("target", "")),
        )
        merged_meta["preferences"] = _union_dict_lists(
            keep_meta.get("preferences") or [],
            drop_meta.get("preferences") or [],
            key_fn=lambda d: (d.get("stance", ""), d.get("target", "")),
        )
        merged_meta["pair_affinities"] = _union_dict_lists(
            keep_meta.get("pair_affinities") or [],
            drop_meta.get("pair_affinities") or [],
            key_fn=lambda d: d.get("with", ""),
        )

        # 2. Write merged metadata
        sb.table("entities").update({"metadata": merged_meta}).eq("id", keep_id).execute()

        # 3. Repoint FK references — every table that references entities.id
        moved = {}
        for table, col in [
            ("zone_assignments",     "tm_id"),
            ("break_assignments",    "tm_id"),
            ("overlap_assignments",  "tm_id"),
            ("call_offs",            "tm_id"),
            ("area_checks",          "tm_id"),
            ("schedule_overrides",   "tm_id"),
            ("note_entities",        "entity_id"),
        ]:
            try:
                upd = (
                    sb.table(table)
                    .update({col: keep_id})
                    .eq(col, drop_id)
                    .execute()
                )
                moved[table] = len(upd.data or [])
            except Exception as ex:
                # Continue on failure of any single table — partial merge is
                # better than total failure.
                print(f"[merge_tm] {table}.{col}: {ex}")
                moved[table] = -1

        # 4. Delete drop entity
        sb.table("entities").delete().eq("id", drop_id).execute()

        return {"ok": True, "error": "", "moved": moved}
    except Exception as e:
        return {"ok": False, "error": f"Merge failed: {e}", "moved": {}}


def update_entity_aliases(entity_id: str, aliases: list[str]) -> bool:
    """Replace the metadata.aliases array on an entity."""
    if not entity_id:
        return False
    try:
        # Fetch current metadata so we can preserve other keys
        res = (
            _client()
            .table("entities")
            .select("metadata")
            .eq("id", entity_id)
            .single()
            .execute()
        )
        meta = (res.data or {}).get("metadata") or {}
        meta["aliases"] = [a.strip().lower() for a in (aliases or []) if a.strip()]
        (
            _client()
            .table("entities")
            .update({"metadata": meta})
            .eq("id", entity_id)
            .execute()
        )
        return True
    except Exception as e:
        print(f"[update_entity_aliases] {e}")
        return False


# ── SCHEDULE OVERRIDES (Phase N.3) ────────────────────────────────────────────
# Cell-level edits on top of an uploaded schedule xlsx. The parser layer
# applies these on top of the raw xlsx values when building rosters.

def fetch_schedule_overrides(schedule_path: str) -> list[dict]:
    """Every override row attached to a given schedule file."""
    if not schedule_path:
        return []
    res = (
        _client()
        .table("schedule_overrides")
        .select("*")
        .eq("schedule_path", schedule_path)
        .execute()
    )
    return res.data or []


def upsert_schedule_override(
    schedule_path: str,
    tm_id: str,
    shift: str,
    cell_date: str,
    override_value: str,
    note: Optional[str] = None,
) -> bool:
    """Set or replace a cell override. Idempotent via UNIQUE constraint."""
    if not (schedule_path and tm_id and shift and cell_date and override_value):
        return False
    try:
        (
            _client()
            .table("schedule_overrides")
            .upsert(
                {
                    "schedule_path":  schedule_path,
                    "tm_id":          tm_id,
                    "shift":          shift,
                    "cell_date":      cell_date,
                    "override_value": override_value,
                    "note":           (note or "").strip() or None,
                },
                on_conflict="schedule_path,tm_id,cell_date",
            )
            .execute()
        )
        return True
    except Exception as e:
        print(f"[upsert_schedule_override] {e}")
        return False


def delete_schedule_override(
    schedule_path: str, tm_id: str, cell_date: str,
) -> bool:
    """Remove a single cell override (Reset to original)."""
    try:
        (
            _client()
            .table("schedule_overrides")
            .delete()
            .eq("schedule_path", schedule_path)
            .eq("tm_id", tm_id)
            .eq("cell_date", cell_date)
            .execute()
        )
        return True
    except Exception as e:
        print(f"[delete_schedule_override] {e}")
        return False


def delete_overrides_for_schedule(schedule_path: str) -> bool:
    """Wipe all overrides for a given schedule (used when the file is deleted
    from Storage)."""
    try:
        (
            _client()
            .table("schedule_overrides")
            .delete()
            .eq("schedule_path", schedule_path)
            .execute()
        )
        return True
    except Exception as e:
        print(f"[delete_overrides_for_schedule] {e}")
        return False


# ── TM PLACEMENT HISTORY (Phase K.2) ──────────────────────────────────────────

# Friendly labels for slot_keys — used in the TM picker history badge.
_SLOT_LABEL_SHORT: dict[str, str] = {
    "zone_1": "Z1", "zone_2": "Z2", "zone_3": "Z3", "zone_4": "Z4",
    "zone_5": "Z5", "zone_6": "Z6", "zone_7": "Z7", "zone_8": "Z8",
    "zone_9": "Z9", "zone_10": "Z10",
    "rr_1_2": "RR1+2", "rr_6": "RR6", "rr_7": "RR7", "rr_8": "RR8", "rr_10": "RR10",
    "z9_sr": "Z9 SR", "admin": "Adm",
    "trash_1": "Trash 1", "trash_2": "Trash 2",
    "support_1": "Supp 1", "support_2": "Supp 2", "support_3": "Supp 3",
}


def _short_slot_label(slot_key: str, rr_side: Optional[str]) -> str:
    """Compact label for picker history. RR slots get an M/W suffix."""
    base = _SLOT_LABEL_SHORT.get(slot_key, slot_key)
    if rr_side == "mens":
        return f"{base} M"
    if rr_side == "womens":
        return f"{base} W"
    return base


def fetch_recent_placements_bulk(
    tm_ids: list[str],
    before_date: str,
    max_per_tm: int = 3,
) -> dict[str, list[dict]]:
    """Return recent zone placements for multiple TMs in one query.

    Args:
        tm_ids:      List of entity IDs to look up.
        before_date: ISO date string — only nights strictly before this date
                     are considered (so you don't see tonight's placement).
        max_per_tm:  Cap per TM (default 3).

    Returns:
        {tm_id: [{date, slot_label, weekday}, ...newest first], ...}
    """
    if not tm_ids:
        return {}
    # Single query: join zone_assignments with nights for night_date
    res = (
        _client()
        .table("zone_assignments")
        .select("tm_id, slot_key, rr_side, nights(night_date, day_name)")
        .in_("tm_id", tm_ids)
        .lt("nights.night_date", before_date)
        .not_.is_("tm_id", "null")
        .execute()
    )
    rows = res.data or []
    # Drop rows where the joined night was filtered out (lt date constraint
    # against an inner table can return rows with nights=None depending on
    # the join — defensive filter).
    rows = [r for r in rows if r.get("nights") and r["nights"].get("night_date")]

    # Sort newest first per tm_id
    rows.sort(key=lambda r: r["nights"]["night_date"], reverse=True)

    grouped: dict[str, list[dict]] = {tid: [] for tid in tm_ids}
    for r in rows:
        tid = r["tm_id"]
        if tid not in grouped:
            grouped[tid] = []
        if len(grouped[tid]) >= max_per_tm:
            continue
        n = r["nights"] or {}
        # Three-letter weekday for compact display
        weekday = (n.get("day_name") or "")[:3]
        grouped[tid].append({
            "date":       n["night_date"],
            "weekday":    weekday,
            "slot_label": _short_slot_label(r["slot_key"], r.get("rr_side")),
        })
    return grouped


# ── ZONE ASSIGNMENTS ──────────────────────────────────────────────────────────

def format_week_date_range(week_ending: str) -> str:
    """Phase R — Given a week_ending ISO date string (e.g. "2026-05-07"),
    return a human-readable range "Fri May 1 – Thu May 7" covering the
    7-day grave-shift week (Thursday end, working back to the prior Friday).
    Falls back to the input string if parsing fails.
    """
    try:
        from datetime import date as _date, timedelta as _td
        if not week_ending:
            return ""
        y, m, d = (int(p) for p in week_ending.split("-"))
        end = _date(y, m, d)
        start = end - _td(days=6)
        # Same month: "Fri May 1 – Thu May 7"
        # Cross month: "Fri Apr 25 – Thu May 1"
        if start.month == end.month:
            return f"{start.strftime('%a %b %-d')} – {end.strftime('%a %b %-d')}"
        return f"{start.strftime('%a %b %-d')} – {end.strftime('%a %b %-d')}"
    except Exception:
        return week_ending or ""


def fetch_week_night_stats(week_id: str) -> dict:
    """Phase R — at-a-glance stats per night for the week overview cards.

    Returns {night_id: {filled, total, locked, called_off}} for every night
    in the week. One-shot query; cheap.
    """
    out: dict = {}
    if not week_id:
        return out
    try:
        sb = _client()
        # 1. nights for this week
        n_res = sb.table("nights").select("id, night_date").eq("week_id", week_id).execute()
        nights = n_res.data or []
        if not nights:
            return out
        night_ids   = [n["id"] for n in nights]
        date_by_id  = {n["id"]: n.get("night_date", "") for n in nights}

        # 2. all zone_assignments for those nights
        za_res = (
            sb.table("zone_assignments")
            .select("night_id, tm_id, is_filled, is_locked")
            .in_("night_id", night_ids)
            .execute()
        )
        rows = za_res.data or []

        # 3. all call_offs for those night_dates (so warning count picks up
        #    TMs marked off who happen to be assigned to a slot)
        unique_dates = list({d for d in date_by_id.values() if d})
        called_off_by_date: dict[str, set] = {}
        if unique_dates:
            co_res = (
                sb.table("call_offs")
                .select("tm_id, night_date")
                .in_("night_date", unique_dates)
                .execute()
            )
            for c in (co_res.data or []):
                called_off_by_date.setdefault(c.get("night_date", ""), set()).add(c.get("tm_id"))

        for nid in night_ids:
            n_rows = [r for r in rows if r.get("night_id") == nid]
            filled = sum(1 for r in n_rows if r.get("is_filled"))
            locked = sum(1 for r in n_rows if r.get("is_locked"))
            total  = len(n_rows)
            night_date = date_by_id.get(nid, "")
            co_set = called_off_by_date.get(night_date, set())
            warnings = sum(
                1 for r in n_rows
                if r.get("tm_id") and r["tm_id"] in co_set
            )
            out[nid] = {
                "filled":     filled,
                "total":      total,
                "unfilled":   total - filled,
                "locked":     locked,
                "called_off": warnings,
            }
        return out
    except Exception as e:
        print(f"[fetch_week_night_stats] {e}")
        return {}


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
    # Phase 4i.2 — load zone tasks from DB once; fall back to hardcoded below
    try:
        from shared.db import get_zone_tasks_for_engine as _gzte
        _db_zone_tasks: dict = _gzte()
    except Exception:
        _db_zone_tasks = {}
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
        # Filled slots: leave empty so the .card-tm-name CSS class controls
        # color (Reflex's color="" doesn't emit an inline style, letting CSS
        # win). Unfilled stays inline gray — works on both light and dark.
        # Without this, the inline #111827 beat dark-mode CSS and TM names
        # rendered nearly invisible against the dark surface.
        row["name_color"]   = "" if row["is_filled"] else "#d1d5db"
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
        # ── display_tasks: custom_tasks → DB zone_tasks → hardcoded constants ──
        _lbl    = row.get("label", sk)   # row["label"] already set above
        custom  = row.get("custom_tasks")
        if custom is not None:
            # custom_tasks in DB are list[str] — wrap as TaskItem dicts with stable annot_id
            row["display_tasks"] = [
                {"id": "", "name": t,
                 "annot_id": _annot_id_for_task("", _lbl, t)}
                for t in custom
            ]
        else:
            # Resolve DB lookup key from slot type + slot_key
            if st == "zone":
                _db_key = sk                    # "zone_1" .. "zone_10"
                _num    = int(sk.rsplit("_", 1)[-1])
            elif st == "rr":
                _num    = 1 if sk == "rr_1_2" else int(sk.rsplit("_", 1)[-1])
                _db_key = f"rr_{_num}"
            else:
                _db_key = sk                    # aux: "admin", "trash_1", etc.
                _num    = 0
            _db_rows = _db_zone_tasks.get(_db_key, [])
            if _db_rows:
                # Canonical tasks: annot_id == UUID (same as id)
                row["display_tasks"] = [
                    {"id": t["id"], "name": t["name"],
                     "annot_id": _annot_id_for_task(t["id"], _lbl, t["name"])}
                    for t in _db_rows
                ]
            elif st == "zone":
                row["display_tasks"] = [
                    {"id": "", "name": t,
                     "annot_id": _annot_id_for_task("", _lbl, t)}
                    for t in TASKS_ZONE.get(_num, [])
                ]
            elif st == "rr":
                row["display_tasks"] = [
                    {"id": "", "name": t,
                     "annot_id": _annot_id_for_task("", _lbl, t)}
                    for t in TASKS_RR.get(_num, [])
                ]
            else:
                row["display_tasks"] = [
                    {"id": "", "name": t,
                     "annot_id": _annot_id_for_task("", _lbl, t)}
                    for t in TASKS_AUX_SLOT.get(sk, [])
                ]
        # ── Sweeper task: always appended on top (never stored in custom_tasks) ──
        if row.get("is_sweeper") and row.get("sweeper_route"):
            sweeper_label = f"Sweeper – {row['sweeper_route']}"
            _existing_names = [t["name"] for t in row["display_tasks"]]
            if sweeper_label not in _existing_names:
                row["display_tasks"] = list(row["display_tasks"]) + [
                    {"id": "", "name": sweeper_label,
                     "annot_id": _annot_id_for_task("", _lbl, sweeper_label)}
                ]
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
        .select("id, group_num, break_wave, sort_order, slot_ref, is_wave_locked, entities(id, display_name)")
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
        row["group_num"]       = int(row.get("group_num") or 1)
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
    """All active TMs with their eligibility maps, EXCLUDING utility porters.

    Filters to entity_type='tm' so areas and other entity types are excluded.
    Includes aliases + raw metadata so the schedule parser's alias resolver
    can find them without re-querying.

    Phase 2026-05-05: TMs whose metadata.roles array contains 'utility_porter'
    are excluded from this list — they're not part of the regular zone-
    deployment rotation. The People page (apps/glcr/) still surfaces them;
    only the ZDS engine-facing roster filters them out.

    ── Dual-storage note (2026-05-05) ───────────────────────────────────────
    This function reads from entities.metadata (legacy operational store).
    The ZDS fill engine (fill_engine.py) now reads from the canonical TM
    domain tables (tm_profiles, tm_eligibility, etc.) via shared.db engine
    helpers. This web-facing ZDS reader has NOT migrated yet.

    The roles filter above uses entities.metadata.roles for backwards compat.
    See shared.db.get_people() for the full dual-storage migration plan.
    ─────────────────────────────────────────────────────────────────────────
    """
    res = (
        _client()
        .table("entities")
        .select("id, name, display_name, metadata, status")
        .eq("entity_type", "tm")
        .eq("status", "active")
        .order("display_name")
        .execute()
    )
    tms = []
    for row in (res.data or []):
        meta  = row.get("metadata") or {}
        roles = list(meta.get("roles") or [])
        # Roles filter — drop utility porters entirely from ZDS roster.
        if "utility_porter" in roles:
            continue
        score = meta.get("skill_score", 0) or 0
        tms.append({
            "id":           row["id"],
            # Legal full name ("Aurora Fox-Stone") — needed by the schedule
            # parser to match xlsx rows whose `first` cell is the legal name
            # rather than the display nickname. Without this, build_entity_lookup
            # only keys on display_name's first token ("Alistair") and the parser
            # misses every nicknamed TM (Aurora→Alistair, Rebecca→Becca,
            # Jeremy→JT, Andrew→Drew, Lee→LeeAnn, Michael→Mike, Melissa→Missy,
            # etc.) — they show up correctly placed by the engine but
            # incorrectly flagged "NOT SCHEDULED" in the deployment grid.
            "name":         row.get("name") or "",
            "display_name": row["display_name"],
            "skill_score":  score,
            "skill_str":    str(score),   # Reflex can't call str() on Vars
            "skill_color":  ("#065f46" if score >= 8 else
                             "#1d4ed8" if score >= 5 else "#6b7280"),
            "grave_pool":   meta.get("grave_pool", "") or "",
            "eligibility":  meta.get("eligibility", {}),
            "preferences":  meta.get("preferences", []),
            "roles":        roles,           # surface roles for downstream callers
            # Phase O — surface aliases + raw metadata so the schedule parser's
            # resolver and any alias-aware code can use them.
            "aliases":      list(meta.get("aliases") or []),
            "metadata":     meta,
            "status":       row.get("status", "active"),
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

    # 2a. Ensure every night in this week has its 27 slot rows seeded.
    #     No-op if rows already exist; creates them on first engine run for a
    #     new week so sync_engine_to_week doesn't silently drop placements.
    for nid in night_ids:
        ensure_zone_slots_for_night(nid)

    # 2b. Fetch all zone_assignments for the week: build lookup
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

    # 6. Sync PMOL/AMOL overlap placements → overlap_assignments (Phase E)
    #    Engine emits these with zone_slot like "PMOL1"…"PMOL6" / "AMOL1"…"AMOL6".
    #    Two-pass:
    #      6a. Upsert all positions present in the audit (placement happened).
    #      6b. Clear any existing overlap_assignments rows for the week that
    #          this run did NOT place — without 6b, stale tm_ids from a prior
    #          engine run linger when pool size shrinks (e.g. Thu pool=0
    #          but DB still shows Thu AMOL1=Eric from yesterday's run).
    overlap_updated = 0
    overlap_cleared = 0
    seen_overlap_keys: set[tuple[str, str, int]] = set()  # (night_id, window, position)

    for p in engine_result.get("placements", []):
        engine_slot = p.get("zone_slot", "")
        date_str    = p.get("date", "")
        tm_name     = p.get("tm_display_name", "")

        if engine_slot.startswith("PMOL"):
            ov_window = "pm"
            try:
                position = int(engine_slot[4:])
            except ValueError:
                continue
        elif engine_slot.startswith("AMOL"):
            ov_window = "am"
            try:
                position = int(engine_slot[4:])
            except ValueError:
                continue
        else:
            continue

        night_id = date_to_night.get(date_str)
        if not night_id:
            continue
        if target_night_id and night_id != target_night_id:
            continue

        tm_id = name_to_id.get(tm_name)  # None → unfilled slot
        try:
            sb.table("overlap_assignments").upsert(
                {
                    "night_id":       night_id,
                    "overlap_window": ov_window,
                    "position":       position,
                    "tm_id":          tm_id,
                    "is_filled":      bool(tm_id),
                },
                on_conflict="night_id,overlap_window,position",
            ).execute()
            seen_overlap_keys.add((night_id, ov_window, position))
            overlap_updated += 1
        except Exception as ov_exc:
            print(f"[sync_engine_to_week] overlap upsert failed: {ov_exc}")

    # 6b. Clear stale overlap rows: any existing row for nights this run
    # touched but at a (window, position) not present in the audit gets its
    # tm_id wiped + is_filled=false. Only clears rows for nights actually in
    # this engine run (date_to_night domain), so a single-night sync doesn't
    # nuke other nights' overlap data.
    touched_nights = (
        {target_night_id} if target_night_id
        else {nid for nid in date_to_night.values() if nid}
    )
    if touched_nights:
        try:
            existing_overlaps = (
                sb.table("overlap_assignments")
                .select("id, night_id, overlap_window, position, tm_id, is_filled")
                .in_("night_id", list(touched_nights))
                .execute()
                .data
                or []
            )
            for row in existing_overlaps:
                key = (row["night_id"], row["overlap_window"], row["position"])
                if key in seen_overlap_keys:
                    continue
                # Stale: only update if it currently has a tm_id (idempotent)
                if row.get("tm_id") or row.get("is_filled"):
                    sb.table("overlap_assignments").update(
                        {"tm_id": None, "is_filled": False}
                    ).eq("id", row["id"]).execute()
                    overlap_cleared += 1
        except Exception as clear_exc:
            print(f"[sync_engine_to_week] overlap stale-clear failed: {clear_exc}")

    return {
        "updated":            updated,
        "skipped_locked":     skipped_locked,
        "unmapped":           unmapped,
        "unresolved_cleared": unresolved_cleared,
        "overlap_updated":    overlap_updated,
        "overlap_cleared":    overlap_cleared,
        "error":              None,
    }
