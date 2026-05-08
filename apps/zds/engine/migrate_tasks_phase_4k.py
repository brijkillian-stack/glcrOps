"""
migrate_tasks_phase_4k.py — Phase 4k.1 seed script
====================================================
Extends the Phase 4i zone_tasks rows with:
  • code         — short stable identifier (e.g. Z1_OUTDOOR_SMOKE)
  • display_order — sort key for UI and renderer

Also inserts overlap tasks (PM + AM) sourced from Rules/Overlap Tasks.json,
and seeds the task_day_overrides table from the _per_day_overrides block.

Idempotent — safe to re-run:
  • Zone/RR/aux updates use UPDATE WHERE name=… AND default_zone=…
  • Overlap inserts use INSERT … ON CONFLICT (code) DO UPDATE
  • Overrides use INSERT … ON CONFLICT (task_id, override_date) DO UPDATE

Sources documented here:
  A. Existing Phase 4i zone/rr/aux rows — updated in-place with code + display_order
  B. Rules/Overlap Tasks.json — PM slots PMOL1-6, AM slots AMOL1-6 + per_day_overrides
  C. No rotation task text constants found in fill_engine.py (BACKTOBACK_SLOTS is a
     placement constraint set, not task copy). Nothing to migrate.
  D. No sweeper task text constants found — sweeper strings are computed at runtime
     as "Sweeper – {route}" in fill_engine.py. Nothing to migrate.

Run from repo root:
    python -m apps.zds.engine.migrate_tasks_phase_4k
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from shared.db import get_client

# ---------------------------------------------------------------------------
# Source A: code + display_order for Phase 4i rows
# Keyed by (name, default_zone) — matches the unique indexes
# ---------------------------------------------------------------------------

ZONE_CODES: dict[tuple[str, str], tuple[str, int]] = {
    # (task_name, default_zone): (code, display_order)
    # --- Zone 1 ---
    ("Outdoor Smoking Area",   "zone_1"):  ("Z1_OUTDOOR_SMOKE",  10),
    ("Elevators & Stairwells", "zone_1"):  ("Z1_ELEVATORS",      11),
    ("Family Restroom",        "zone_1"):  ("Z1_FAMILY_RR",      12),
    # --- Zone 2 ---
    ("Lobby Trash Pull",       "zone_2"):  ("Z2_LOBBY_TRASH",    20),
    ("Lobby Restrooms",        "zone_2"):  ("Z2_LOBBY_RR",       21),
    # --- Zone 3 (no tasks in Phase 4i) ---
    # --- Zone 4 ---
    ("Poker Room Drink Trays", "zone_4"):  ("Z4_POKER_TRAYS",    40),
    # --- Zone 5 ---
    ("High Limit Table Games", "zone_5"):  ("Z5_HIGH_LIMIT_TG",  50),
    ("Indoor TM Smoking Room", "zone_5"):  ("Z5_INDOOR_SMOKE",   51),
    # --- Zone 6 ---
    ("Outdoor Smoking Area",   "zone_6"):  ("Z6_OUTDOOR_SMOKE",  60),
    # --- Zone 7 ---
    ("Smoking Room",           "zone_7"):  ("Z7_SMOKE_ROOM",     70),
    ("Pit 1 & 2",              "zone_7"):  ("Z7_PIT12",          71),
    ("South Door Glass",       "zone_7"):  ("Z7_SOUTH_GLASS",    72),
    # --- Zone 8 ---
    ("Restrooms",              "zone_8"):  ("Z8_RESTROOMS",      80),
    ("Pit 3",                  "zone_8"):  ("Z8_PIT3",           81),
    # --- Zone 9 ---
    ("Assist with Smoking Room","zone_9"): ("Z9_ASSIST_SMOKE",   90),
    ("Social Bar Tables",       "zone_9"): ("Z9_SOCIAL_TABLES",  91),
    # --- Zone 10 ---
    ("High Limit Slots",       "zone_10"): ("Z10_HIGH_LIMIT_SLOTS", 100),
    ("East Door Glass",        "zone_10"): ("Z10_EAST_GLASS",    101),
    ("Outdoor Smoking Area",   "zone_10"): ("Z10_OUTDOOR_SMOKE", 102),
    ("Pit 4",                  "zone_10"): ("Z10_PIT4",          103),
    # --- RR tasks ---
    ("Buffet RR",              "rr_1"):    ("RR1_BUFFET",        210),
    ("Family RR",              "rr_1"):    ("RR1_FAMILY",        211),
    ("131 Restroom",           "rr_6"):    ("RR6_131",           260),
    ("Assist with Smoking Room","rr_7"):   ("RR7_ASSIST_SMOKE",  270),
    ("Family Restroom",        "rr_8"):    ("RR8_FAMILY",        280),
    ("TDR Restroom",           "rr_8"):    ("RR8_TDR",           281),
    ("TMBR Locker Room",       "rr_8"):    ("RR8_TMBR",          282),
    ("CBK Kitchen",            "rr_10"):   ("RR10_CBK_KITCHEN",  300),
    # --- Aux tasks (actual DB names post Phase 4i manual edits) ---
    ("Zones 1–5",         "trash_1"): ("AUX_TRASH1",        310),
    ("Annex after 5am",        "trash_1"): ("AUX_TRASH1_ANNEX",  311),
    ("Zones 6–10",        "trash_2"): ("AUX_TRASH2",        320),
    ("Smoking Room",           "z9_sr"):   ("AUX_Z9_SR",         330),
    ("Smoking Room (paired)",  "z9_sr_buddy"): ("AUX_Z9_SR_BUDDY", 331),
    ("Overflow",               "support_3"): ("AUX_OVERFLOW",    340),
}

# ---------------------------------------------------------------------------
# Source B: Overlap tasks from Rules/Overlap Tasks.json
# ---------------------------------------------------------------------------

OVERLAP_JSON_PATH = Path(__file__).parent / "Rules" / "Overlap Tasks.json"

# Overlap task rows to insert (category drives how renderer + fill_engine uses them)
# default_zone = slot code (PMOL1, AMOL1, etc.) — no collision with zone_N keys
OVERLAP_TASKS_PM = {
    "PMOL1": "Vacuum, Bottles & Glass",
    "PMOL2": "Glass & Counters, Trash",
    "PMOL3": "Tables & Restroom, Bottles & Glass",
    "PMOL4": "Trash",
    "PMOL5": "Trash",
    "PMOL6": "Trash",
}

OVERLAP_TASKS_AM = {
    "AMOL1": "CBK / Shkodé",
    "AMOL2": "CBK / Shkodé Restrooms",
    "AMOL3": "Hotel Offices",
    "AMOL4": "Sandhill / Lobby Bar",
    "AMOL5": "131 / Group Room / CBK Office",
    "AMOL6": "Trash",
}

# Slot → (code, display_order)
OVERLAP_PM_META: dict[str, tuple[str, int]] = {
    "PMOL1": ("OL_PM1", 410),
    "PMOL2": ("OL_PM2", 411),
    "PMOL3": ("OL_PM3", 412),
    "PMOL4": ("OL_PM4", 413),
    "PMOL5": ("OL_PM5", 414),
    "PMOL6": ("OL_PM6", 415),
}
OVERLAP_AM_META: dict[str, tuple[str, int]] = {
    "AMOL1": ("OL_AM1", 510),
    "AMOL2": ("OL_AM2", 511),
    "AMOL3": ("OL_AM3", 512),
    "AMOL4": ("OL_AM4", 513),
    "AMOL5": ("OL_AM5", 514),
    "AMOL6": ("OL_AM6", 515),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_overlap_json() -> dict:
    with open(OVERLAP_JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _build_overlap_rows() -> list[dict]:
    rows = []
    for slot, name in OVERLAP_TASKS_PM.items():
        code, order = OVERLAP_PM_META[slot]
        rows.append({
            "name": name,
            "code": code,
            "default_zone": slot,           # PMOL1 … PMOL6
            "target_codes": [slot],
            "category": "overlap_pm",
            "display_order": order,
            "active": True,
        })
    for slot, name in OVERLAP_TASKS_AM.items():
        code, order = OVERLAP_AM_META[slot]
        rows.append({
            "name": name,
            "code": code,
            "default_zone": slot,           # AMOL1 … AMOL6
            "target_codes": [slot],
            "category": "overlap_am",
            "display_order": order,
            "active": True,
        })
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    client = get_client()

    # ── Step A: UPDATE existing Phase 4i rows with code + display_order ─────
    print("Step A: Applying codes + display_order to Phase 4i rows …")
    updated = 0
    skipped = 0
    for (name, default_zone), (code, order) in ZONE_CODES.items():
        resp = (
            client.table("zone_tasks")
            .select("id,code")
            .eq("name", name)
            .eq("default_zone", default_zone)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            print(f"  WARN: ({name!r}, {default_zone!r}) not found in DB — skipping")
            skipped += 1
            continue
        row_id = rows[0]["id"]
        existing_code = rows[0]["code"]
        if existing_code == code:
            skipped += 1
            continue
        client.table("zone_tasks").update({
            "code": code,
            "display_order": order,
        }).eq("id", row_id).execute()
        updated += 1

    print(f"  Updated: {updated}  |  Already set / not found: {skipped}")

    # ── Step B: INSERT overlap tasks (idempotent via code unique index) ──────
    print("Step B: Inserting overlap tasks …")
    overlap_rows = _build_overlap_rows()

    # Fetch existing codes to diff
    existing_codes_resp = (
        client.table("zone_tasks")
        .select("code")
        .in_("code", [r["code"] for r in overlap_rows])
        .execute()
    )
    existing_codes = {r["code"] for r in (existing_codes_resp.data or [])}

    new_overlap = [r for r in overlap_rows if r["code"] not in existing_codes]
    print(f"  New overlap rows to insert: {len(new_overlap)}  |  Already exist: {len(existing_codes)}")

    if new_overlap:
        ins_resp = client.table("zone_tasks").insert(new_overlap).execute()
        print(f"  Inserted: {len(ins_resp.data or [])}")
    else:
        print("  All overlap rows already present — nothing to insert.")

    # ── Step C: Seed task_day_overrides from JSON _per_day_overrides ─────────
    print("Step C: Seeding task_day_overrides …")
    ol_json = _load_overlap_json()
    per_day = ol_json.get("_per_day_overrides", {})

    # Build a code→id map for overlap tasks (need task_id FK)
    all_ol_codes = list(OVERLAP_PM_META.values()) + list(OVERLAP_AM_META.values())
    all_ol_code_strs = [c for c, _ in all_ol_codes]
    code_map_resp = (
        client.table("zone_tasks")
        .select("id,code")
        .in_("code", all_ol_code_strs)
        .execute()
    )
    code_to_id: dict[str, str] = {
        r["code"]: r["id"] for r in (code_map_resp.data or [])
    }

    # Slot-label → code string lookup
    slot_to_code: dict[str, str] = {}
    for slot, (code, _) in OVERLAP_PM_META.items():
        slot_to_code[slot] = code
    for slot, (code, _) in OVERLAP_AM_META.items():
        slot_to_code[slot] = code

    override_rows_inserted = 0
    override_rows_skipped = 0

    for iso_date, period_map in per_day.items():
        if iso_date.startswith("_"):
            continue  # skip _comment keys
        for period, slot_map in period_map.items():
            for slot, description in slot_map.items():
                code = slot_to_code.get(slot)
                if not code:
                    print(f"  WARN: No code mapping for slot {slot!r} on {iso_date}")
                    override_rows_skipped += 1
                    continue
                task_id = code_to_id.get(code)
                if not task_id:
                    print(f"  WARN: task_id not found for code {code!r} (slot {slot})")
                    override_rows_skipped += 1
                    continue

                # Check if override already exists
                existing_resp = (
                    client.table("task_day_overrides")
                    .select("id,description")
                    .eq("task_id", task_id)
                    .eq("override_date", iso_date)
                    .execute()
                )
                existing = existing_resp.data or []
                if existing:
                    if existing[0]["description"] == description:
                        override_rows_skipped += 1
                        continue
                    # Update if description changed
                    client.table("task_day_overrides").update({
                        "description": description,
                    }).eq("id", existing[0]["id"]).execute()
                    print(f"  Updated override: {slot} on {iso_date} → {description!r}")
                    override_rows_inserted += 1
                else:
                    client.table("task_day_overrides").insert({
                        "task_id": task_id,
                        "override_date": iso_date,
                        "description": description,
                    }).execute()
                    print(f"  Inserted override: {slot} on {iso_date} → {description!r}")
                    override_rows_inserted += 1

    print(f"  Overrides inserted/updated: {override_rows_inserted}  |  Skipped: {override_rows_skipped}")

    # ── Final verification ───────────────────────────────────────────────────
    count_resp = (
        client.table("zone_tasks")
        .select("id", count="exact")
        .execute()
    )
    total = count_resp.count if count_resp.count is not None else "?"

    coded_resp = (
        client.table("zone_tasks")
        .select("id", count="exact")
        .not_.is_("code", "null")
        .execute()
    )
    coded = coded_resp.count if coded_resp.count is not None else "?"

    override_count_resp = (
        client.table("task_day_overrides")
        .select("id", count="exact")
        .execute()
    )
    override_total = override_count_resp.count if override_count_resp.count is not None else "?"

    print(f"\nSummary:")
    print(f"  zone_tasks total rows : {total}")
    print(f"  zone_tasks with code  : {coded}")
    print(f"  task_day_overrides    : {override_total}")
    print("Done.")


if __name__ == "__main__":
    main()
