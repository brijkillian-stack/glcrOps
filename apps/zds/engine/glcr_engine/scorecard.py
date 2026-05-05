"""
GLCR Multi-Objective Placement Scorecard (5/2/26)

Single source of truth for the engine's placement scoring. Used by:
  - fill_engine.py     — building the week's board
  - swap.py (Phase 2)  — proposing swap chains on call-offs
  - Future audit tools — explaining historical placements

Components scored per (TM, slot) candidate pair:
  - skill_match           skill_score vs slot_difficulty (with skill_priority boost)
  - preference_fit        soft preferences from TM Profiles
  - pair_affinity         soft pair affinities vs ADJACENT or SAME-AREA placements
  - within_repeat         penalty for same slot earlier this week
  - cross_week_rotation   bonus for slots not done recently (per archive)
  - area_diversity        penalty for same floor area as yesterday
  - fatigue_index         penalty for stretched TMs in heavy slots
  - soft_prefer_set       per-call-site bonus (Admin rockstars, etc.)

Hard preferences AND accommodations are NOT in the scorecard — they filter the
candidate pool before scoring runs. Override audit fires if a must-fill slot
empties as a result.

Use:
  from glcr_engine import scorecard
  scorecard.init(roster=..., tm_skill=..., slot_difficulty=..., ...)
  sc = scorecard.score_placement(rk, slot, day_name="Friday")
  sort_key = scorecard.rotation_key(rk, slot, day_name="Friday")
"""
from datetime import date, timedelta
from glcr_engine.config import SLOT_CATEGORY, SWEEPER_TAGGED_SLOTS

# ── Module state — populated by init() ───────────────────────────────
_state = {
    "roster": {},
    "tm_skill": {},
    "slot_difficulty": {},
    "tm_preferences": {},      # {dn: [pref dict, ...]}
    "tm_accommodations": {},   # {dn: [accommodation dict, ...]}
    "tm_pair_affinities": {},  # {dn: [pair dict, ...]}
    "slot_loads": {},
    "weights": {},
    "fatigue_window_days": 7,
    "slot_to_area": {},
    "zone_adjacency": {},
    # Per-week mutable state:
    "week_zone_history": {},   # {dn: set(slot, ...)}
    "archive_history": {},     # {dn: {slot: date}}
    "tm_areas_by_date": {},    # {iso_date: {dn: area}}
    "day_placements": {},      # {day_name: {slot: dn}}
    "day_dates": {},           # {day_name: date}
    "anchor_date": None,
    "current_day_iso": None,
}

DEFAULT_WEIGHTS = {
    "skill_match":         1.0,
    "preference_fit":      1.5,
    "pair_affinity":       1.0,
    "within_repeat":       1.0,
    "cross_week_rotation": 0.5,
    "area_diversity":      0.7,
    "fatigue_index":       0.8,
    "soft_prefer_set":     0.6,
}

# SLOT_CATEGORY + SWEEPER_TAGGED_SLOTS imported above from glcr_engine.config
# (consolidated 5/3/26 — was duplicated in fill_engine.py + here, now one source).


def init(*, roster, tm_skill, slot_difficulty,
         tm_preferences, tm_accommodations, tm_pair_affinities,
         slot_loads, weights, fatigue_window_days,
         slot_to_area, zone_adjacency,
         week_zone_history, archive_history, tm_areas_by_date,
         day_placements, day_dates, anchor_date):
    """Inject all config + state. Called once after the engine loads its data."""
    _state.update({
        "roster": roster,
        "tm_skill": tm_skill,
        "slot_difficulty": slot_difficulty,
        "tm_preferences": tm_preferences,
        "tm_accommodations": tm_accommodations,
        "tm_pair_affinities": tm_pair_affinities,
        "slot_loads": slot_loads,
        "weights": {**DEFAULT_WEIGHTS, **(weights or {})},
        "fatigue_window_days": fatigue_window_days or 7,
        "slot_to_area": slot_to_area,
        "zone_adjacency": zone_adjacency,
        "week_zone_history": week_zone_history,
        "archive_history": archive_history,
        "tm_areas_by_date": tm_areas_by_date,
        "day_placements": day_placements,
        "day_dates": day_dates,
        "anchor_date": anchor_date,
    })


def set_current_day(iso_date_str):
    """Engine calls this at the start of each day's fill loop."""
    _state["current_day_iso"] = iso_date_str


# ── Slot label / target matching ─────────────────────────────────────
def _slot_to_pref_label(slot_code):
    """Engine-internal slot code → human pref-target label (e.g., 'Zone 8')."""
    if slot_code.startswith("Zone") and slot_code not in ("Zone9SR", "Z9SRBuddy"):
        return f"Zone {slot_code[4:]}"
    if slot_code == "Zone9SR":   return "Z9 SR"
    if slot_code == "Z9SRBuddy": return "Z9 SR Buddy"
    if slot_code.startswith("MRR"): return "Mens 1 + 2" if slot_code == "MRR1" else f"Mens {slot_code[3:]}"
    if slot_code.startswith("WRR"): return "Womens 1 + 2" if slot_code == "WRR1" else f"Womens {slot_code[3:]}"
    if slot_code == "Admin":  return "Admin"
    if slot_code == "Trash1": return "Trash 1"
    if slot_code == "Trash2": return "Trash 2"
    if slot_code in ("MP1", "Support1"): return "Support 1"
    if slot_code in ("MP2", "Support2"): return "Support 2"
    if slot_code == "Support3": return "Support 3"
    return slot_code


def _matches_target(target, slot_code):
    """Does a preference/accommodation target match this slot?
    Supports: exact slot label, 'area:Foo', 'category:foo'.
    Special: 'category:sweeper' matches the SWEEPER_TAGGED_SLOTS set too."""
    if not target:
        return False
    t = target.strip()
    if t.startswith("area:"):
        return _state["slot_to_area"].get(slot_code) == t[5:].strip()
    if t.startswith("category:"):
        cat = t[9:].strip().lower()
        if cat == "sweeper":
            # Sweeper accommodations cover both the slots typically tagged with
            # sweeper task assignment AND the SLOT_CATEGORY-mapped 'sweeper' if any.
            return slot_code in SWEEPER_TAGGED_SLOTS or SLOT_CATEGORY.get(slot_code) == "sweeper"
        return SLOT_CATEGORY.get(slot_code) == cat
    return _slot_to_pref_label(slot_code).lower() == t.lower()


# ── Hard filters (accommodations + hard preferences) ────────────────
def has_hard_block(dn, slot_code):
    """Returns the blocking entry (accommodation or hard avoid pref) if this TM
    can't be placed in this slot. None if clear. Engine uses for pool filter."""
    # Accommodations — protected by design. Severity 'hard' or 'absolute' both filter.
    for acc in _state["tm_accommodations"].get(dn, []):
        if acc.get("status", "active") != "active":
            continue
        sev = acc.get("severity", "soft")
        if sev not in ("hard", "absolute"):
            continue
        if _matches_target(acc.get("target"), slot_code):
            return {"kind": "accommodation", **acc}
    # Hard preferences — same effect as accommodation but separately tracked.
    for pref in _state["tm_preferences"].get(dn, []):
        if pref.get("strength") != "hard":
            continue
        if pref.get("stance") != "avoid":
            continue
        if _matches_target(pref.get("target"), slot_code):
            return {"kind": "preference", **pref}
    return None


# ── Soft preference scoring ─────────────────────────────────────────
def preference_fit(dn, slot_code):
    """Soft preference penalty/bonus. -2 to +2.
    Hard preferences/accommodations are filtered before scoring (see has_hard_block)."""
    score = 0
    for pref in _state["tm_preferences"].get(dn, []):
        if pref.get("strength") == "hard":
            continue
        if not _matches_target(pref.get("target"), slot_code):
            continue
        if pref.get("stance") == "avoid":
            score += 1
        elif pref.get("stance") == "prefer":
            score -= 1
    return score


# ── Pair affinity scoring ───────────────────────────────────────────
def _adjacent_slots(slot_code):
    """Slots that count as adjacent for pair-affinity checks.
    Includes:
      - ZONE_ADJACENCY (e.g., Z6↔Z7)
      - RR mens/womens of same number (MRR8 ↔ WRR8)
      - Z9 SR ↔ Z9 SR Buddy
      - SAME AREA co-occupants (5/2/26 expansion — e.g., Z8 + WRR8 share area Z8)
    """
    adj = set(_state["zone_adjacency"].get(slot_code, []))
    if slot_code.startswith("MRR"):
        adj.add("WRR" + slot_code[3:])
    elif slot_code.startswith("WRR"):
        adj.add("MRR" + slot_code[3:])
    if slot_code == "Zone9SR":
        adj.add("Z9SRBuddy")
    elif slot_code == "Z9SRBuddy":
        adj.add("Zone9SR")
    # Same-area expansion (Brian, 5/2/26): all slots sharing the area code count
    # as adjacent for pair-affinity purposes. Catches Z8+WRR8, Lobby zones, etc.
    my_area = _state["slot_to_area"].get(slot_code)
    if my_area:
        for other_slot, other_area in _state["slot_to_area"].items():
            if other_area == my_area and other_slot != slot_code:
                adj.add(other_slot)
    return adj


def pair_affinity_score(dn, slot_code, day_name):
    """Penalty/bonus from pair affinities vs currently-placed adjacent TMs.
    Also: returns a large penalty if this TM is already placed elsewhere on
    this day — defensive guard against intra-day duplicates that bypass
    placed_today (5/3/26 #12)."""
    if not day_name:
        return 0
    today_pl = _state["day_placements"].get(day_name, {})
    # Intra-day duplicate guard — if this TM is already in another slot today,
    # nuke the score so they don't get scored as a candidate elsewhere.
    for s, placed in today_pl.items():
        if s != slot_code and placed and placed.lower() == dn.lower():
            return 999
    score = 0
    for adj_slot in _adjacent_slots(slot_code):
        adj_dn = today_pl.get(adj_slot)
        if not adj_dn:
            continue
        # Symmetric: check this TM's affinities, then the other's affinities for this TM
        for src_dn, other_dn in ((dn, adj_dn), (adj_dn, dn)):
            for pair in _state["tm_pair_affinities"].get(src_dn, []):
                target_with = pair.get("with") or ""
                if target_with.lower() == other_dn.lower():
                    if pair.get("stance") == "avoid":
                        score += 1
                    elif pair.get("stance") == "prefer":
                        score -= 1
    return score


# ── Fatigue ─────────────────────────────────────────────────────────
def fatigue_index(dn, today_iso=None):
    """Sum of slot loads for this TM across the trailing fatigue window."""
    today_iso = today_iso or _state.get("current_day_iso")
    if not _state["slot_loads"] or not today_iso:
        return 0
    try:
        today = date.fromisoformat(today_iso)
    except (ValueError, TypeError):
        return 0
    cutoff = today - timedelta(days=_state["fatigue_window_days"])
    total = 0
    for slot, last_d in _state["archive_history"].get(dn, {}).items():
        if last_d and last_d >= cutoff:
            total += _state["slot_loads"].get(slot, 2)
    return total


def fatigue_penalty(dn, slot_code, today_iso=None):
    """Soft penalty: stretched TMs cost more for high-load slots."""
    fi = fatigue_index(dn, today_iso)
    slot_load = _state["slot_loads"].get(slot_code, 2)
    return (fi / 8.0) * (slot_load / 5.0)


# ── Core scorer ─────────────────────────────────────────────────────
def score_placement(rk, slot_code, *, skill_priority=False,
                    soft_prefer_set=None, day_name=None):
    """Return {total, components, rank, dn, fatigue_pts}.
    Lower total = better candidate."""
    roster = _state["roster"]
    if rk not in roster:
        return {"total": 9999, "components": {}, "rank": 9999, "dn": "?", "fatigue_pts": 0}

    dn   = roster[rk]["display_name"]
    rank = roster[rk]["rank"]

    # Skill match
    skill = _state["tm_skill"].get(dn, 5)
    diff  = _state["slot_difficulty"].get(slot_code, 5)
    skill_pen = 1 if (diff - skill) > 2 else 0
    if skill_priority:
        skill_pen = skill_pen - (skill / 20.0)  # boost for high skill

    # Within-week rotation
    within = 1 if slot_code in _state["week_zone_history"].get(dn, set()) else 0

    # Cross-week rotation
    last_date = _state["archive_history"].get(dn, {}).get(slot_code)
    days_ago = (_state["anchor_date"] - last_date).days if (last_date and _state["anchor_date"]) else 9999
    cross_week = -min(days_ago, 60) / 60.0

    # Area diversity
    area_rep = 0
    today_iso = (_state["day_dates"].get(day_name) or _state.get("anchor_date"))
    today_iso_str = today_iso.isoformat() if today_iso else _state.get("current_day_iso")
    if today_iso_str:
        area = _state["slot_to_area"].get(slot_code)
        if area:
            try:
                yest = (date.fromisoformat(today_iso_str) - timedelta(days=1)).isoformat()
                if _state["tm_areas_by_date"].get(yest, {}).get(dn) == area:
                    area_rep = 1
            except (ValueError, TypeError):
                pass

    # Soft prefer set (rockstars for Admin, etc.)
    soft_set = 0 if (soft_prefer_set and dn in soft_prefer_set) else 1

    # New components
    pref_fit  = preference_fit(dn, slot_code)
    pair_aff  = pair_affinity_score(dn, slot_code, day_name)
    fatigue_p = fatigue_penalty(dn, slot_code, today_iso_str)

    components = {
        "skill_match":         skill_pen,
        "within_repeat":       within,
        "cross_week_rotation": cross_week,
        "area_diversity":      area_rep,
        "soft_prefer_set":     soft_set,
        "preference_fit":      pref_fit,
        "pair_affinity":       pair_aff,
        "fatigue_index":       fatigue_p,
    }
    w = _state["weights"]
    total = sum(w.get(k, 1.0) * v for k, v in components.items())
    return {
        "total": total,
        "components": components,
        "rank": rank,
        "dn": dn,
        "fatigue_pts": fatigue_index(dn, today_iso_str),
    }


def rotation_key(rk, slot_code, skill_priority=False, soft_prefer_set=None, day_name=None):
    """Sort-key wrapper. Returns (total, rank). Lower wins."""
    sc = score_placement(rk, slot_code, skill_priority=skill_priority,
                         soft_prefer_set=soft_prefer_set, day_name=day_name)
    return (sc["total"], sc["rank"])
