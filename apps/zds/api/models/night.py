"""Night-level response models for the Forge API (Next.js consumer).

These shapes are the canonical contract between the Forge API and the
Next.js ZDS frontend.  TypeScript types in apps/web/lib/sync.ts mirror
these exactly — keep them in sync.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, model_validator

GroupId = Literal["1", "2", "3"]
ZoneType = Literal["zone", "restroom", "auxiliary"]


# ── Break schedule — grave shift (11 PM → 7 AM) ──────────────────────────────
#
# Times are keyed by (group_num, break_wave) → (start_24h, end_24h, duration_min)
# group_num: which break group the TM is in (1 | 2 | 3)
# break_wave: which break in the night (1=first 15-min, 2=30-min, 3=last 15-min)
#
# Source: Brian's master prompt — committed to GLCR memory 2026-05-12.

_BREAK_SCHEDULE: dict[tuple[int, int], tuple[str, str, int]] = {
    # (group, wave): (start, end, duration_minutes)
    (1, 1): ("00:45", "01:00", 15),   # Group 1 — first 15 min (12:45 AM)
    (1, 2): ("02:30", "03:00", 30),   # Group 1 — 30 min
    (1, 3): ("05:00", "05:15", 15),   # Group 1 — last 15 min

    (2, 1): ("01:00", "01:15", 15),   # Group 2 — first 15 min (1:00 AM)
    (2, 2): ("03:00", "03:30", 30),   # Group 2 — 30 min
    (2, 3): ("05:00", "05:15", 15),   # Group 2 — last 15 min

    (3, 1): ("01:15", "01:30", 15),   # Group 3 — first 15 min (1:15 AM)
    (3, 2): ("03:30", "04:00", 30),   # Group 3 — 30 min
    (3, 3): ("05:15", "05:30", 15),   # Group 3 — last 15 min
}

# Wave-level labels
_WAVE_LABELS: dict[int, str] = {
    1: "First Break",
    2: "Main Break",
    3: "Last Break",
}


# ── Slot-type mapping from DB values to API values ────────────────────────────

_SLOT_TYPE_MAP: dict[str, ZoneType] = {
    "zone": "zone",
    "rr":   "restroom",
    "aux":  "auxiliary",
}


def _derive_initials(name: Optional[str]) -> Optional[str]:
    """'Joy Smith' → 'JS', 'Seth K.' → 'SK'."""
    if not name:
        return None
    parts = name.split()
    letters = [p[0].upper() for p in parts if p and p[0].isalpha()]
    return "".join(letters[:2]) or None


# ═════════════════════════════════════════════════════════════════════════════
# Response models
# ═════════════════════════════════════════════════════════════════════════════

class TMAssignment(BaseModel):
    """One placement slot for a night (zone, restroom, or auxiliary position)."""

    model_config = ConfigDict(from_attributes=True)

    slot_id: str            # zone_assignments.id (UUID)
    zone_id: str            # slot_key from DB, e.g. "zone_1", "rr_6", "admin"
    zone_label: str         # human-readable label, e.g. "Zone 1", "RR 6"
    zone_type: ZoneType     # "zone" | "restroom" | "auxiliary"
    rr_side: Optional[str] = None  # "mens" | "womens" | None

    tm_id: Optional[str] = None
    tm_name: Optional[str] = None
    tm_initials: Optional[str] = None

    group: Optional[GroupId] = None  # break group "1"|"2"|"3"
    tasks: list[str] = []
    is_override: bool = False
    is_filled: bool = False
    is_locked: bool = False

    @model_validator(mode="before")
    @classmethod
    def _derive(cls, data: dict) -> dict:
        """Derive computed fields from raw DB row if not already set."""
        if isinstance(data, dict):
            # Initials from name
            if data.get("tm_initials") is None:
                data["tm_initials"] = _derive_initials(data.get("tm_name"))
            # Slot type normalisation
            raw_type = data.get("zone_type") or data.get("slot_type", "")
            data["zone_type"] = _SLOT_TYPE_MAP.get(raw_type, "auxiliary")
            # Group: convert int 0/1/2/3 → str or None
            grp = data.get("group") or data.get("group_num") or 0
            data["group"] = str(grp) if grp in (1, 2, 3) else None
            # Slot ID alias
            if not data.get("slot_id") and data.get("id"):
                data["slot_id"] = data["id"]
            # Zone ID alias
            if not data.get("zone_id") and data.get("slot_key"):
                data["zone_id"] = data["slot_key"]
            # rr_side normalisation
            side = data.get("rr_side") or ""
            data["rr_side"] = side if side else None
            # Tasks from custom_tasks
            if "tasks" not in data:
                raw_tasks = data.get("custom_tasks") or []
                data["tasks"] = raw_tasks if isinstance(raw_tasks, list) else []
        return data


class BreakGroupSlot(BaseModel):
    """TMs in one break group within a wave, with their exact times."""

    model_config = ConfigDict(from_attributes=True)

    group: GroupId          # "1" | "2" | "3"
    start_time: str         # "HH:MM" 24h — e.g. "00:45" (12:45 AM)
    end_time: str           # "HH:MM" 24h
    duration_min: int       # 15 or 30
    tm_ids: list[str] = []
    tm_names: list[str] = []


class BreakWave(BaseModel):
    """One break sequence (first/main/last) — contains per-group timing and TMs.

    Each wave has three groups that go on break at staggered times.
    Use groups[] to render per-group break cards with correct times.
    """

    model_config = ConfigDict(from_attributes=True)

    wave: GroupId           # "1" | "2" | "3" (sequence in the night)
    label: str              # "First Break" | "Main Break" | "Last Break"
    groups: list[BreakGroupSlot]  # one entry per group, sorted by group


class NightPlacementsResponse(BaseModel):
    """Full placements payload for one night — consumed by the Next.js Daily Planner."""

    night_id: str
    date: str               # "YYYY-MM-DD"
    day_name: str           # "Friday" … "Thursday"
    fill_rate: float        # 0.0–1.0
    last_synced: str        # ISO-8601 timestamp
    placements: list[TMAssignment]
    break_waves: list[BreakWave]


# ── Builder helpers ───────────────────────────────────────────────────────────

def build_night_response(
    night: dict,
    zone_rows: list[dict],
    break_rows: list[dict],
    zone_labels: dict[str, str],
) -> NightPlacementsResponse:
    """Transform raw DB rows → NightPlacementsResponse.

    Args:
        night:       Raw night row from Supabase.
        zone_rows:   Rows from fetch_zone_assignments (already enriched by database.py).
        break_rows:  Rows from fetch_break_assignments (already enriched by database.py).
        zone_labels: ZONE_LABELS dict from apps/zds/styles.py.
    """
    # ── Zone / RR / Aux placements ────────────────────────────────────────────
    placements: list[TMAssignment] = []
    filled = 0

    for row in zone_rows:
        sk   = row.get("slot_key", "")
        st   = row.get("slot_type", "")
        side = row.get("rr_side") or ""
        tm_id   = row.get("tm_id") or None
        tm_name = row.get("tm_name") or None
        is_filled = bool(row.get("is_filled"))

        if is_filled:
            filled += 1

        placements.append(
            TMAssignment(
                slot_id    = row.get("id", ""),
                zone_id    = sk,
                zone_label = zone_labels.get(sk, sk.replace("_", " ").title()),
                zone_type  = _SLOT_TYPE_MAP.get(st, "auxiliary"),
                rr_side    = side or None,
                tm_id      = tm_id,
                tm_name    = tm_name,
                tm_initials= _derive_initials(tm_name),
                group      = str(row["group_num"]) if row.get("group_num") in (1, 2, 3) else None,
                tasks      = row.get("custom_tasks") or [],
                is_override= bool(row.get("is_override")),
                is_filled  = is_filled,
                is_locked  = bool(row.get("is_locked")),
            )
        )

    fill_rate = (filled / len(placements)) if placements else 0.0

    # ── Break waves (per-group timing) ───────────────────────────────────────
    # Structure: waves_map[break_wave][group_num] = {tm_ids, tm_names}
    waves_map: dict[int, dict[int, dict]] = {}

    for row in break_rows:
        bw  = int(row.get("break_wave") or 0)
        grp = int(row.get("group_num") or 0)
        if bw not in (1, 2, 3) or grp not in (1, 2, 3):
            continue
        if bw not in waves_map:
            waves_map[bw] = {}
        if grp not in waves_map[bw]:
            waves_map[bw][grp] = {"tm_ids": [], "tm_names": []}
        tid  = row.get("tm_id", "")
        tnam = row.get("tm_name", "")
        if tid:
            waves_map[bw][grp]["tm_ids"].append(tid)
        if tnam:
            waves_map[bw][grp]["tm_names"].append(tnam)

    break_waves: list[BreakWave] = []
    for bw in (1, 2, 3):
        group_slots: list[BreakGroupSlot] = []
        for grp in (1, 2, 3):
            start, end, dur = _BREAK_SCHEDULE.get((grp, bw), ("??:??", "??:??", 15))
            slot_data = (waves_map.get(bw) or {}).get(grp) or {}
            group_slots.append(BreakGroupSlot(
                group        = str(grp),   # type: ignore[arg-type]
                start_time   = start,
                end_time     = end,
                duration_min = dur,
                tm_ids       = slot_data.get("tm_ids", []),
                tm_names     = slot_data.get("tm_names", []),
            ))
        break_waves.append(BreakWave(
            wave   = str(bw),             # type: ignore[arg-type]
            label  = _WAVE_LABELS[bw],
            groups = group_slots,
        ))

    return NightPlacementsResponse(
        night_id    = night.get("id", ""),
        date        = night.get("night_date", ""),
        day_name    = night.get("day_name", ""),
        fill_rate   = round(fill_rate, 4),
        last_synced = datetime.now(timezone.utc).isoformat(),
        placements  = placements,
        break_waves = break_waves,
    )
