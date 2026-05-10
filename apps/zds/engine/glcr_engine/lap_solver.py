"""
GLCR Engine — LAP (Hungarian) Solver  Phase 4f
===============================================
Provides `solve_constrained_block()` which replaces the sequential greedy
fill for the 22-slot constrained block (10 restrooms + Admin + Zone9SR +
Z1 + Z4 + Z5 + Z8) with a globally-optimal Linear Assignment Problem
solution via scipy's `linear_sum_assignment`.

Why LAP fixes Z8's ~68.6% fill rate
-------------------------------------
In the greedy engine the 22 slots are filled one at a time (RRs → Admin →
Z9SR → Z1 → Z4 → Z5 → Z8). By the time Z8 is reached (~15th placement)
the candidate pool is already depleted of highly eligible TMs. LAP sees
all 22 slots simultaneously and finds the assignment that minimises total
cost across the board — Z8 gets a viable candidate because the solver
reserves one during the global solve rather than leaving leftovers.

Cost matrix design
------------------
  Rows: eligible pool members (padded to square with dummy rows)
  Cols: constrained slots    (padded to square with dummy cols)

  Cell cost = score_fn(rk, slot_code)["total"]  — lower is better (as in
  the scorecard; rotation_key sorts ascending).

  HARD_BLOCK_COST = 1e9  — used when a TM is flat-ineligible, physically
                            restricted, or has an unoverridable hard-avoid.
  SOFT_BLOCK_COST = 1e6  — used when a TM fails the back-to-back guard or
                            a hard-preference avoid (keeps the solver from
                            assigning them here, but if the pool is tiny it
                            will still pick the least-bad option).

  Dummy pool rows are filled with HARD_BLOCK_COST so dummy TMs are never
  matched to real slots. Dummy slot cols are filled with 0.0 so real TMs
  can match dummy slots without penalty.

Audit trail
-----------
Any slot that ends up unresolvable (all pool members HARD_BLOCK_COST) is
returned with value None and the caller logs an LAP_FALLBACK audit item.
The `fallback_detail` list returned alongside the assignment dict carries
{"slot_code": ..., "reason": ...} for each such slot so the caller can
append them to audit_items.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable

try:
    from scipy.optimize import linear_sum_assignment
    _SCIPY_OK = True
except ImportError:
    _SCIPY_OK = False

HARD_BLOCK_COST = 1e9   # ineligible / physically restricted / unoverridable
SOFT_BLOCK_COST = 1e6   # back-to-back or hard-preference violation (last resort)


@dataclass
class SlotSpec:
    """Descriptor for one slot in the constrained block."""
    slot_code: str          # fill_engine internal key, e.g. "Zone8"
    elig_col: str           # roster eligibility column, e.g. "Zone 8"
    priority: str           # audit priority label, e.g. "Zone"
    skill_priority: bool = False           # True → skill-match penalty active
    soft_prefer_set: set = field(default_factory=set)   # display_names to soft-prefer
    prefer_elig: str | None = None        # secondary elig for sub-preference (Zone 1 → Womens 1+2)
    prefer_names: set = field(default_factory=set)      # hard-prefer names (e.g. Z9SR wknd)
    avoid_names: set = field(default_factory=set)       # AVOID_PHYSICAL etc.
    skip_trainees: bool = True
    pool_type: str = "grave"


def solve_constrained_block(
    specs: list[SlotSpec],
    pool_list: list,               # grave pool rkeys (ordered, unfiltered)
    placed_today: set,             # already-placed display_names (training pre-pass)
    day_iso: str,                  # ISO date string for BTB guard
    *,
    roster: dict,
    elig_fn: Callable,             # elig_fn(rk, elig_col) -> bool
    has_hard_block_fn: Callable,   # has_hard_block_fn(dn, slot_code) -> dict|None
    score_fn: Callable,            # score_fn(rk, slot_code, skill_priority, soft_prefer_set, day_name) -> {total: float}
    tm_slots_by_date: dict,        # {date_iso: {dn: set(slot_codes)}} — for BTB guard
    backtoback_slots: set,         # slots where BTB guard applies
    slot_avoid_by_tm: dict,        # {dn: set(slot_codes)} — per-TM avoidance
    trainee_display: set,          # display_names of trainees (skill_score ≤ 3)
    cell_map_day: dict,            # cell_map[day] — slots present today
    day_name: str | None = None,   # "Friday", "Monday", etc. for score_fn
) -> tuple[dict[str, str | None], list[dict]]:
    """
    Solve the constrained block globally with LAP.

    Returns
    -------
    assignment : dict[slot_code → display_name | None]
        None means the slot could not be filled (all pool members blocked).
    fallback_detail : list[dict]
        {"slot_code": str, "reason": str} for every slot that fell back to
        HARD or SOFT or was left None — for appending to audit_items.
    """
    if not _SCIPY_OK:
        # scipy not installed — degrade to None assignments so fill_engine
        # falls back to greedy for every slot individually.
        import sys
        print(
            "\n"
            "┌─────────────────────────────────────────────────────────────┐\n"
            "│  LAP SOLVER DISABLED — scipy not installed                  │\n"
            "│                                                             │\n"
            "│  All 22 constrained-block slots will return None and fall   │\n"
            "│  back to greedy fill, which degrades Z8 fill rate to ~69%.  │\n"
            "│                                                             │\n"
            "│  Fix:  pip install scipy                                    │\n"
            "└─────────────────────────────────────────────────────────────┘\n",
            file=sys.stderr,
        )
        return {s.slot_code: None for s in specs}, [
            {"slot_code": s.slot_code, "reason": "scipy not available — LAP disabled"}
            for s in specs
        ]

    # ── 1. Build candidate pool (only TMs not already placed) ──────────
    # yest_iso used by BTB guard.
    try:
        yest_iso = (date.fromisoformat(day_iso) - timedelta(days=1)).isoformat()
    except (ValueError, TypeError):
        yest_iso = None

    pool = [rk for rk in pool_list
            if roster[rk]["display_name"] not in placed_today]

    if not pool:
        return {s.slot_code: None for s in specs}, [
            {"slot_code": s.slot_code, "reason": "empty pool after pre-pass"} for s in specs
        ]

    n_pool  = len(pool)
    n_slots = len(specs)
    dim     = max(n_pool, n_slots)

    # ── 2. Classify each (rk, slot_spec) cell cost ─────────────────────
    import numpy as np

    cost = np.full((dim, dim), 0.0, dtype=float)

    # Dummy pool rows (real pool exhausted) → HARD cost for real slot cols
    for i in range(n_pool, dim):
        cost[i, :n_slots] = HARD_BLOCK_COST

    # Dummy slot cols (real slots exhausted) → 0.0 cost (any pool member fine)
    # already 0.0 by default.

    for ci, rk in enumerate(pool):
        dn = roster[rk]["display_name"]
        for si, spec in enumerate(specs):
            # Slot not present today → HARD
            if spec.slot_code not in cell_map_day:
                cost[ci, si] = HARD_BLOCK_COST
                continue
            # Trainee exclusion
            if spec.skip_trainees and dn in trainee_display:
                cost[ci, si] = HARD_BLOCK_COST
                continue
            # Global avoid_names (AVOID_PHYSICAL etc.)
            if spec.avoid_names and dn in spec.avoid_names:
                cost[ci, si] = HARD_BLOCK_COST
                continue
            # Per-TM slot avoidance
            if spec.slot_code in slot_avoid_by_tm.get(dn, ()):
                cost[ci, si] = HARD_BLOCK_COST
                continue
            # Eligibility
            if not elig_fn(rk, spec.elig_col):
                cost[ci, si] = HARD_BLOCK_COST
                continue
            # Hard preference block (avoid:hard in profile)
            if has_hard_block_fn(dn, spec.slot_code):
                cost[ci, si] = SOFT_BLOCK_COST
                continue
            # Back-to-back guard
            if (yest_iso
                    and spec.slot_code in backtoback_slots
                    and spec.slot_code in tm_slots_by_date.get(yest_iso, {}).get(dn, ())):
                cost[ci, si] = SOFT_BLOCK_COST
                continue
            # Normal path: use scorecard total (lower = better)
            try:
                sc = score_fn(rk, spec.slot_code,
                              skill_priority=spec.skill_priority,
                              soft_prefer_set=spec.soft_prefer_set or None,
                              day_name=day_name)
                cost[ci, si] = float(sc["total"])
            except Exception:
                cost[ci, si] = SOFT_BLOCK_COST  # degrade gracefully

    # ── 3. Run LAP ───────────────────────────────────────────────────────
    row_ind, col_ind = linear_sum_assignment(cost)

    # ── 4. Build assignment dict ─────────────────────────────────────────
    slot_to_rk: dict[str, str | None] = {s.slot_code: None for s in specs}
    fallback_detail: list[dict] = []

    # Map col indices back to slot specs
    col_to_spec: dict[int, SlotSpec] = {si: spec for si, spec in enumerate(specs)}

    for ri, ci in zip(row_ind, col_ind):
        if ci >= n_slots:
            # Real pool member matched to a dummy slot — they stay unplaced.
            continue
        if ri >= n_pool:
            # Dummy pool matched to a real slot — slot unfilled.
            spec = col_to_spec[ci]
            fallback_detail.append({
                "slot_code": spec.slot_code,
                "reason": "no eligible pool member — dummy matched (pool exhausted)",
            })
            continue
        spec = col_to_spec[ci]
        rk   = pool[ri]
        dn   = roster[rk]["display_name"]
        c    = cost[ri, ci]

        if c >= HARD_BLOCK_COST:
            # All pool members blocked — leave slot None.
            fallback_detail.append({
                "slot_code": spec.slot_code,
                "reason": f"LAP assigned {dn} but cost={c:.0e} (HARD_BLOCK) — slot left unresolved",
            })
            continue

        if c >= SOFT_BLOCK_COST:
            # Soft-block match (BTB or hard-prefer override) — accept but audit it.
            fallback_detail.append({
                "slot_code": spec.slot_code,
                "reason": f"LAP assigned {dn} with SOFT_BLOCK override (BTB or hard-pref) cost={c:.0e}",
            })

        # Apply prefer_names hard preference: if the LAP picked someone other
        # than a prefer_names member but a prefer_names member IS available,
        # swap to the preferred TM.  This respects specialist hard-preference
        # (e.g. Z9SR weekend) without encoding it redundantly in the cost matrix.
        if spec.prefer_names:
            pref_match = next(
                (prk for prk in pool
                 if roster[prk]["display_name"] in spec.prefer_names
                    and roster[prk]["display_name"] not in placed_today
                    and roster[prk]["display_name"] not in
                        {slot_to_rk.get(s2.slot_code) for s2 in specs}
                    and elig_fn(prk, spec.elig_col)
                    and c < HARD_BLOCK_COST),
                None,
            )
            if pref_match:
                rk = pref_match
                dn = roster[rk]["display_name"]

        slot_to_rk[spec.slot_code] = dn

    return slot_to_rk, fallback_detail
