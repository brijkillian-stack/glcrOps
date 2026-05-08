"""
migrate_tasks_to_db.py — Phase 4i.1 seed script
=================================================
Populates the `zone_tasks` table from the hardcoded TASKS_ZONE, TASKS_RR,
and TASKS_AUX_SLOT lists defined in render_deployment_book.py and styles.py.

Idempotent: uses INSERT … ON CONFLICT DO NOTHING so it is safe to re-run.
The unique indexes are:
  - (name, default_zone) WHERE default_zone IS NOT NULL
  - (name) WHERE default_zone IS NULL

Run from the brijkillian-stack repo root:
    python -m apps.zds.engine.migrate_tasks_to_db

Or directly:
    python apps/zds/engine/migrate_tasks_to_db.py
"""

from __future__ import annotations

import sys
import os

# Allow running as a script from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from shared.db import get_client

# ---------------------------------------------------------------------------
# Source data — mirrors render_deployment_book.py constants
# ---------------------------------------------------------------------------

TASKS_ZONE = {
    1:  ["Outdoor Smoking Area", "Elevators & Stairwells", "Family Restroom"],
    2:  ["Lobby Trash Pull", "Lobby Restrooms"],
    3:  [],
    4:  ["Poker Room Drink Trays"],
    5:  ["High Limit Table Games", "Indoor TM Smoking Room"],
    6:  ["Outdoor Smoking Area"],
    7:  ["Smoking Room", "Pit 1 & 2", "South Door Glass"],
    8:  ["Restrooms", "Pit 3"],
    9:  ["Assist with Smoking Room", "Social Bar Tables"],
    10: ["High Limit Slots", "East Door Glass", "Outdoor Smoking Area", "Pit 4"],
}

TASKS_RR = {
    1:  ["Buffet RR", "Family RR"],
    6:  ["131 Restroom"],
    7:  ["Assist with Smoking Room"],
    8:  ["Family Restroom", "TDR Restroom", "TMBR Locker Room"],
    10: ["CBK Kitchen"],
}

# Aux slot key → task name (we ignore the description for zone_tasks rows)
TASKS_AUX = {
    "trash_1_5":   "Trash 1 (Zones 1–5)",
    "trash_6_10":  "Trash 2 (Zones 6–10)",
    "admin":       "Admin",
    "z9_sr":       "Z9 SR (Smoking Room)",
    "support_1":   "Support 1",
    "support_2":   "Support 2",
    "support_3":   "Support 3",
    "z9_sr_buddy": "Z9 SR Buddy",
}

# Aux slot key → default_zone value stored in DB
AUX_SLOT_ZONE_KEY = {
    "trash_1_5":   "trash_1",
    "trash_6_10":  "trash_2",
    "admin":       "admin",
    "z9_sr":       "z9_sr",
    "support_1":   "support_1",
    "support_2":   "support_2",
    "support_3":   "support_3",
    "z9_sr_buddy": "z9_sr_buddy",
}


def build_rows() -> list[dict]:
    rows: list[dict] = []

    # Zone tasks — default_zone = 'zone_1' .. 'zone_10'
    for zone_num, task_names in TASKS_ZONE.items():
        default_zone = f"zone_{zone_num}"
        for name in task_names:
            rows.append({
                "name": name,
                "default_zone": default_zone,
                "category": "zone",
                "active": True,
            })

    # RR (restroom runner) tasks — default_zone = 'rr_1', 'rr_6', etc.
    for zone_num, task_names in TASKS_RR.items():
        default_zone = f"rr_{zone_num}"
        for name in task_names:
            rows.append({
                "name": name,
                "default_zone": default_zone,
                "category": "rr",
                "active": True,
            })

    # Aux slot tasks
    for slot_key, name in TASKS_AUX.items():
        rows.append({
            "name": name,
            "default_zone": AUX_SLOT_ZONE_KEY[slot_key],
            "category": "aux",
            "active": True,
        })

    return rows


def main() -> None:
    client = get_client()
    rows = build_rows()

    print(f"Building {len(rows)} zone_tasks rows …")

    # Fetch existing (name, default_zone) pairs to avoid duplicate inserts
    existing_resp = (
        client.table("zone_tasks")
        .select("name,default_zone")
        .execute()
    )
    existing = {
        (r["name"], r["default_zone"])
        for r in (existing_resp.data or [])
    }
    print(f"  Already in DB: {len(existing)}")

    new_rows = [
        r for r in rows
        if (r["name"], r["default_zone"]) not in existing
    ]
    print(f"  New rows to insert: {len(new_rows)}")

    if new_rows:
        insert_resp = (
            client.table("zone_tasks")
            .insert(new_rows)
            .execute()
        )
        inserted = insert_resp.data or []
        print(f"  Inserted: {len(inserted)}")
    else:
        print("  Nothing to insert — already seeded.")

    # Verify final count
    count_resp = (
        client.table("zone_tasks")
        .select("id", count="exact")
        .execute()
    )
    total = count_resp.count if count_resp.count is not None else "?"
    print(f"  Total zone_tasks rows now: {total}")
    print("Done.")


if __name__ == "__main__":
    main()
