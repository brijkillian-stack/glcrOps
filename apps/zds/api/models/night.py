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


# ── Break wave times (grave shift 11 PM → 7 AM) ───────────────────────────────

_BREAK_TIMES: dict[int, tuple[str, str]] = {
    1: ("01:00", "01:30"),
    2: ("02:30", "03:00"),
    3: ("04:00", "04:30"),
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


class BreakWave(BaseModel):
    """One break wave — all TMs going on break at the same time."""

    model_config = ConfigDict(from_attributes=True)

    wave: GroupId           # "1" | "2" | "3"
    label: str              # "Break 1" etc.
    start_time: str         # "HH:MM" (24h)
    end_time: str           # "HH:MM" (24h)
    tm_ids: list[str] = []
    tm_names: list[str] = []


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

    # ── Break waves ───────────────────────────────────────────────────────────
    waves_map: dict[int, dict] = {}
    for row in break_rows:
        bw = int(row.get("break_wave") or 0)
        if bw not in (1, 2, 3):
            continue
        if bw not in waves_map:
            start, end = _BREAK_TIMES.get(bw, ("??:??", "??:??"))
            waves_map[bw] = {
                "wave": str(bw),
                "label": f"Break {bw}",
                "start_time": start,
                "end_time": end,
                "tm_ids": [],
                "tm_names": [],
            }
        tid  = row.get("tm_id", "")
        tnam = row.get("tm_name", "")
        if tid:
            waves_map[bw]["tm_ids"].append(tid)
        if tnam:
            waves_map[bw]["tm_names"].append(tnam)

    break_waves = [
        BreakWave(**waves_map[bw]) for bw in sorted(waves_map)
    ]
    # Ensure all 3 waves exist even if no assignments yet
    existing = {w.wave for w in break_waves}
    for bw in (1, 2, 3):
        wstr = str(bw)
        if wstr not in existing:
            start, end = _BREAK_TIMES[bw]
            break_waves.append(BreakWave(
                wave=wstr, label=f"Break {bw}",
                start_time=start, end_time=end,
                tm_ids=[], tm_names=[],
            ))
    break_waves.sort(key=lambda w: w.wave)

    return NightPlacementsResponse(
        night_id    = night.get("id", ""),
        date        = night.get("night_date", ""),
        day_name    = night.get("day_name", ""),
        fill_rate   = round(fill_rate, 4),
        last_synced = datetime.now(timezone.utc).isoformat(),
        placements  = placements,
        break_waves = break_waves,
    )
