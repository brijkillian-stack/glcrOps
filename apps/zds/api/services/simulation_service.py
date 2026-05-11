"""Simulation service — non-destructive what-if planning.

Loads a baseline week (or single night) via the read-only
`PlacementService`, applies in-memory scenario mutations, then computes
coverage / fatigue / overlap metrics on both the baseline and scenario
snapshots so the caller can see the delta. Nothing is ever written to
the database — this is the foundation for the interactive pre-shift
planning UI ("what happens if I pull two TMs from Friday?").

Speed: all work is dict transforms over already-cached reads, so an
already-warm week answers in tens of milliseconds.
"""

from __future__ import annotations

import copy
import logging
import time
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Optional

from supabase import Client

from .cache_service import CacheService
from .placement_service import PlacementService

log = logging.getLogger(__name__)


# ── Scenario mutation kinds ─────────────────────────────────────────
#
# Kept as plain string constants rather than an Enum so the router can
# accept them as strings without an extra Pydantic enum-coercion hop.

CHANGE_MARK_UNAVAILABLE   = "mark_unavailable"
CHANGE_REMOVE_ASSIGNMENT  = "remove_assignment"
CHANGE_ADD_ASSIGNMENT     = "add_assignment"
CHANGE_REASSIGN           = "reassign"

VALID_CHANGE_KINDS = {
    CHANGE_MARK_UNAVAILABLE,
    CHANGE_REMOVE_ASSIGNMENT,
    CHANGE_ADD_ASSIGNMENT,
    CHANGE_REASSIGN,
}

CONSTRAINT_MAX_CONSECUTIVE = "max_consecutive_nights"
CONSTRAINT_MAX_NIGHTS      = "max_nights_per_week"
CONSTRAINT_MIN_COVERAGE    = "min_coverage"
CONSTRAINT_EXCLUDE_ZONE    = "exclude_zone"
CONSTRAINT_REQUIRE_SKILL   = "require_skill_min"

VALID_CONSTRAINT_KINDS = {
    CONSTRAINT_MAX_CONSECUTIVE,
    CONSTRAINT_MAX_NIGHTS,
    CONSTRAINT_MIN_COVERAGE,
    CONSTRAINT_EXCLUDE_ZONE,
    CONSTRAINT_REQUIRE_SKILL,
}


class SimulationError(ValueError):
    """Raised when scenario input is malformed or refers to missing rows."""


class SimulationService:
    """Pure read-only simulator over PlacementService data."""

    def __init__(self, supabase: Client, cache: Optional[CacheService] = None):
        self.supabase = supabase
        self.cache = cache or CacheService(None)
        self.placement = PlacementService(supabase, cache=self.cache)

    # ── Public entry point ───────────────────────────────────────

    async def simulate(
        self,
        *,
        week_id: Optional[str] = None,
        night_id: Optional[str] = None,
        staffing_changes: Optional[list[dict]] = None,
        constraints: Optional[list[dict]] = None,
        include_overlaps: bool = True,
        include_fatigue: bool = True,
    ) -> dict:
        if not week_id and not night_id:
            raise SimulationError("simulate requires week_id or night_id")
        if week_id and night_id:
            raise SimulationError("simulate accepts week_id or night_id, not both")

        started = time.perf_counter()

        baseline = await self._load_snapshot(week_id=week_id, night_id=night_id)
        scenario = self._apply_changes(
            copy.deepcopy(baseline), staffing_changes or []
        )

        baseline_metrics = self._compute_metrics(
            baseline,
            constraints or [],
            include_overlaps=include_overlaps,
            include_fatigue=include_fatigue,
        )
        scenario_metrics = self._compute_metrics(
            scenario,
            constraints or [],
            include_overlaps=include_overlaps,
            include_fatigue=include_fatigue,
        )

        elapsed_ms = int((time.perf_counter() - started) * 1000)

        return {
            "scope": "week" if week_id else "night",
            "target_id": week_id or night_id,
            "baseline": baseline_metrics,
            "scenario": scenario_metrics,
            "delta": _coverage_delta(baseline_metrics, scenario_metrics),
            "applied_changes": len(staffing_changes or []),
            "elapsed_ms": elapsed_ms,
        }

    # ── Snapshot loading ─────────────────────────────────────────

    async def _load_snapshot(
        self,
        *,
        week_id: Optional[str],
        night_id: Optional[str],
    ) -> dict:
        """Build {night_id: {meta, assignments, overlaps}} from cached reads."""
        nights: list[dict] = []
        if week_id:
            week = await self.placement.get_week(week_id)
            if not week:
                raise SimulationError(f"week_id {week_id!r} not found")
            nights = await self.placement.get_week_nights(week_id)
        else:
            # PlacementService doesn't have a single-night meta fetcher
            # (the printer path always loads via the parent week). For the
            # night-scoped simulation we only need the night_id itself —
            # the assignment fetch carries everything we evaluate.
            nights = [{"id": night_id, "night_date": "", "day_name": ""}]

        snapshot: dict[str, dict] = {}
        for night in nights:
            nid = night.get("id")
            if not nid:
                continue
            assignments = await self.placement.get_night_assignments(nid)
            overlaps = await self.placement.get_night_overlaps(nid)
            snapshot[nid] = {
                "meta": {
                    "id": nid,
                    "night_date": night.get("night_date", ""),
                    "day_name": night.get("day_name", ""),
                },
                # Deep copy so a buggy mutation can't poison the cached row.
                "assignments": copy.deepcopy(assignments),
                "overlaps": copy.deepcopy(overlaps),
            }
        return snapshot

    # ── Mutation engine ──────────────────────────────────────────

    def _apply_changes(self, snapshot: dict, changes: list[dict]) -> dict:
        for idx, change in enumerate(changes):
            kind = change.get("kind")
            if kind not in VALID_CHANGE_KINDS:
                raise SimulationError(
                    f"staffing_changes[{idx}].kind {kind!r} is not one of "
                    f"{sorted(VALID_CHANGE_KINDS)}"
                )
            if kind == CHANGE_MARK_UNAVAILABLE:
                self._apply_mark_unavailable(snapshot, change, idx)
            elif kind == CHANGE_REMOVE_ASSIGNMENT:
                self._apply_remove_assignment(snapshot, change, idx)
            elif kind == CHANGE_ADD_ASSIGNMENT:
                self._apply_add_assignment(snapshot, change, idx)
            elif kind == CHANGE_REASSIGN:
                self._apply_reassign(snapshot, change, idx)
        return snapshot

    @staticmethod
    def _nights_for_change(snapshot: dict, change: dict, idx: int) -> list[str]:
        """Resolve which nights a change applies to.

        Defaults to all nights in the snapshot. A `night_id` narrows it
        down; `night_ids` (plural) limits to a subset. Unknown ids raise.
        """
        explicit = change.get("night_id")
        plural = change.get("night_ids")
        if explicit and plural:
            raise SimulationError(
                f"staffing_changes[{idx}] sets both night_id and night_ids"
            )
        if explicit:
            target = [explicit]
        elif plural:
            target = list(plural)
        else:
            return list(snapshot.keys())
        for nid in target:
            if nid not in snapshot:
                raise SimulationError(
                    f"staffing_changes[{idx}] references night {nid!r} "
                    "which is not in the simulated scope"
                )
        return target

    def _apply_mark_unavailable(self, snapshot: dict, change: dict, idx: int) -> None:
        tm_id = change.get("tm_id")
        if not tm_id:
            raise SimulationError(
                f"staffing_changes[{idx}] (mark_unavailable) requires tm_id"
            )
        for nid in self._nights_for_change(snapshot, change, idx):
            for row in snapshot[nid]["assignments"]:
                if row.get("tm_id") == tm_id:
                    _clear_zone_assignment(row)
            for row in snapshot[nid]["overlaps"]:
                if row.get("tm_id") == tm_id:
                    _clear_overlap_assignment(row)

    def _apply_remove_assignment(self, snapshot: dict, change: dict, idx: int) -> None:
        assignment_id = change.get("assignment_id")
        if not assignment_id:
            raise SimulationError(
                f"staffing_changes[{idx}] (remove_assignment) requires assignment_id"
            )
        if not _mutate_assignment_by_id(snapshot, assignment_id, _clear_zone_assignment):
            raise SimulationError(
                f"staffing_changes[{idx}] assignment {assignment_id!r} not found"
            )

    def _apply_add_assignment(self, snapshot: dict, change: dict, idx: int) -> None:
        """Place a TM into an existing slot (assignment_id) or fail loudly.

        Slot creation isn't supported here — every night row is already
        seeded with the full slot set, so "add" really means "fill the
        currently-empty slot with this TM".
        """
        tm_id = change.get("tm_id")
        if not tm_id:
            raise SimulationError(
                f"staffing_changes[{idx}] (add_assignment) requires tm_id"
            )
        assignment_id = change.get("assignment_id")
        if not assignment_id:
            raise SimulationError(
                f"staffing_changes[{idx}] (add_assignment) requires assignment_id"
            )
        tm_name = change.get("tm_name") or ""
        tm_skill = change.get("tm_skill")

        def _fill(row: dict) -> None:
            row["tm_id"] = tm_id
            row["tm_name"] = tm_name or row.get("tm_name") or ""
            if tm_skill is not None:
                row["tm_skill"] = tm_skill
            row["is_filled"] = True
            row["is_empty"] = False
            row["display_name"] = tm_name or row.get("tm_name") or "Unfilled"

        if not _mutate_assignment_by_id(snapshot, assignment_id, _fill):
            raise SimulationError(
                f"staffing_changes[{idx}] assignment {assignment_id!r} not found"
            )

    def _apply_reassign(self, snapshot: dict, change: dict, idx: int) -> None:
        """Move the current TM at `assignment_id` to a different slot.

        If `target_assignment_id` is supplied the TM lands there; otherwise
        the source slot is just cleared.
        """
        source_id = change.get("assignment_id")
        if not source_id:
            raise SimulationError(
                f"staffing_changes[{idx}] (reassign) requires assignment_id"
            )
        target_id = change.get("target_assignment_id")

        carried: dict = {}

        def _take(row: dict) -> None:
            carried.update(
                tm_id=row.get("tm_id"),
                tm_name=row.get("tm_name"),
                tm_skill=row.get("tm_skill"),
            )
            _clear_zone_assignment(row)

        if not _mutate_assignment_by_id(snapshot, source_id, _take):
            raise SimulationError(
                f"staffing_changes[{idx}] source {source_id!r} not found"
            )
        if not target_id:
            return
        if not carried.get("tm_id"):
            raise SimulationError(
                f"staffing_changes[{idx}] source {source_id!r} had no TM to reassign"
            )

        def _drop(row: dict) -> None:
            row["tm_id"] = carried["tm_id"]
            row["tm_name"] = carried.get("tm_name") or row.get("tm_name") or ""
            if carried.get("tm_skill") is not None:
                row["tm_skill"] = carried["tm_skill"]
            row["is_filled"] = True
            row["is_empty"] = False
            row["display_name"] = carried.get("tm_name") or "Unfilled"

        if not _mutate_assignment_by_id(snapshot, target_id, _drop):
            raise SimulationError(
                f"staffing_changes[{idx}] target {target_id!r} not found"
            )

    # ── Metrics ──────────────────────────────────────────────────

    def _compute_metrics(
        self,
        snapshot: dict,
        constraints: list[dict],
        *,
        include_overlaps: bool,
        include_fatigue: bool,
    ) -> dict:
        coverage = _compute_coverage(snapshot)
        overlap = _compute_overlap(snapshot) if include_overlaps else None
        fatigue = _compute_fatigue(snapshot) if include_fatigue else None
        violations = _evaluate_constraints(snapshot, constraints, coverage, fatigue)
        return {
            "coverage": coverage,
            "overlap": overlap,
            "fatigue": fatigue,
            "violations": violations,
        }


# ── Pure helpers ────────────────────────────────────────────────────


def _clear_zone_assignment(row: dict) -> None:
    row["tm_id"] = ""
    row["tm_name"] = ""
    row["tm_skill"] = 0
    row["is_filled"] = False
    row["is_empty"] = True
    row["display_name"] = "Unfilled"


def _clear_overlap_assignment(row: dict) -> None:
    row["tm_id"] = ""
    row["tm_name"] = ""
    row["is_filled"] = False


def _mutate_assignment_by_id(snapshot: dict, assignment_id: str, fn) -> bool:
    """Walk every night until we find the assignment with this id."""
    for night in snapshot.values():
        for row in night["assignments"]:
            if row.get("id") == assignment_id:
                fn(row)
                return True
    return False


def _compute_coverage(snapshot: dict) -> dict:
    total = filled = 0
    by_type: dict[str, dict[str, int]] = defaultdict(lambda: {"filled": 0, "total": 0})
    by_night: dict[str, dict[str, Any]] = {}

    for nid, night in snapshot.items():
        n_total = n_filled = 0
        for row in night["assignments"]:
            slot_type = row.get("slot_type") or "unknown"
            by_type[slot_type]["total"] += 1
            n_total += 1
            if row.get("is_filled"):
                by_type[slot_type]["filled"] += 1
                n_filled += 1
        total += n_total
        filled += n_filled
        by_night[nid] = {
            "night_date": night["meta"]["night_date"],
            "day_name": night["meta"]["day_name"],
            "filled": n_filled,
            "total": n_total,
            "unfilled": n_total - n_filled,
            "fill_rate": _safe_rate(n_filled, n_total),
        }

    return {
        "total_slots": total,
        "filled_slots": filled,
        "unfilled_slots": total - filled,
        "fill_rate": _safe_rate(filled, total),
        "by_type": {k: {**v, "fill_rate": _safe_rate(v["filled"], v["total"])}
                    for k, v in by_type.items()},
        "by_night": by_night,
    }


def _compute_overlap(snapshot: dict) -> dict:
    windows = {"pm": {"filled": 0, "total": 0},
               "am": {"filled": 0, "total": 0}}
    for night in snapshot.values():
        for row in night["overlaps"]:
            window = (row.get("overlap_window") or "").lower()
            bucket = windows.get(window)
            if bucket is None:
                continue
            bucket["total"] += 1
            if row.get("is_filled"):
                bucket["filled"] += 1
    return {
        "pm_filled": windows["pm"]["filled"],
        "pm_total": windows["pm"]["total"],
        "pm_fill_rate": _safe_rate(windows["pm"]["filled"], windows["pm"]["total"]),
        "am_filled": windows["am"]["filled"],
        "am_total": windows["am"]["total"],
        "am_fill_rate": _safe_rate(windows["am"]["filled"], windows["am"]["total"]),
    }


def _compute_fatigue(snapshot: dict) -> dict:
    """Per-TM workload + max consecutive-night streak across the snapshot."""
    # Group by TM → ordered list of night_dates worked.
    per_tm: dict[str, dict[str, Any]] = {}
    for night in snapshot.values():
        date_str = night["meta"]["night_date"]
        seen_this_night: set[str] = set()
        for row in night["assignments"]:
            tm_id = row.get("tm_id")
            if not tm_id or not row.get("is_filled"):
                continue
            entry = per_tm.setdefault(tm_id, {
                "tm_id": tm_id,
                "tm_name": row.get("tm_name") or "",
                "nights_worked": 0,
                "slot_count": 0,
                "skill_sum": 0,
                "skill_n": 0,
                "_dates": set(),
            })
            entry["slot_count"] += 1
            skill = row.get("tm_skill") or 0
            if skill:
                entry["skill_sum"] += skill
                entry["skill_n"] += 1
            if tm_id not in seen_this_night:
                entry["_dates"].add(date_str)
                entry["nights_worked"] += 1
                seen_this_night.add(tm_id)

    per_tm_list: list[dict] = []
    max_streak_global = 0
    for entry in per_tm.values():
        streak = _max_consecutive_streak(entry.pop("_dates"))
        avg_skill = (
            round(entry["skill_sum"] / entry["skill_n"], 2)
            if entry["skill_n"] else 0
        )
        per_tm_list.append({
            "tm_id": entry["tm_id"],
            "tm_name": entry["tm_name"],
            "nights_worked": entry["nights_worked"],
            "slot_count": entry["slot_count"],
            "consecutive_nights": streak,
            "avg_skill": avg_skill,
        })
        if streak > max_streak_global:
            max_streak_global = streak

    per_tm_list.sort(key=lambda r: (-r["nights_worked"], r["tm_name"]))

    nights = [e["nights_worked"] for e in per_tm_list]
    return {
        "tm_count": len(per_tm_list),
        "avg_nights_per_tm": round(sum(nights) / len(nights), 2) if nights else 0,
        "max_nights_per_tm": max(nights) if nights else 0,
        "max_consecutive_nights": max_streak_global,
        "per_tm": per_tm_list,
    }


def _max_consecutive_streak(date_strs: set[str]) -> int:
    """Longest run of consecutive YYYY-MM-DD dates in the set.

    Bad / blank dates fall back to a "no streak info" return of just the
    count of distinct entries (1 or 0) so we never lie with a zero when
    a TM clearly worked. Real data should always parse cleanly.
    """
    if not date_strs:
        return 0
    parsed: list[date] = []
    for s in date_strs:
        try:
            parsed.append(datetime.strptime(s, "%Y-%m-%d").date())
        except (ValueError, TypeError):
            continue
    if not parsed:
        return 1
    parsed.sort()
    longest = current = 1
    for prev, cur in zip(parsed, parsed[1:]):
        if (cur - prev).days == 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def _evaluate_constraints(
    snapshot: dict,
    constraints: list[dict],
    coverage: dict,
    fatigue: Optional[dict],
) -> list[dict]:
    out: list[dict] = []
    for idx, c in enumerate(constraints):
        kind = c.get("kind")
        if kind not in VALID_CONSTRAINT_KINDS:
            raise SimulationError(
                f"constraints[{idx}].kind {kind!r} is not one of "
                f"{sorted(VALID_CONSTRAINT_KINDS)}"
            )
        if kind == CONSTRAINT_MAX_CONSECUTIVE:
            if fatigue is None:
                continue
            limit = int(c.get("value") or 0)
            offenders = [
                {"tm_id": e["tm_id"], "tm_name": e["tm_name"],
                 "consecutive_nights": e["consecutive_nights"]}
                for e in fatigue["per_tm"]
                if limit and e["consecutive_nights"] > limit
            ]
            if offenders:
                out.append({
                    "kind": kind, "value": limit,
                    "severity": "warning",
                    "detail": f"{len(offenders)} TM(s) exceed {limit} consecutive nights",
                    "affected": offenders,
                })
        elif kind == CONSTRAINT_MAX_NIGHTS:
            if fatigue is None:
                continue
            limit = int(c.get("value") or 0)
            offenders = [
                {"tm_id": e["tm_id"], "tm_name": e["tm_name"],
                 "nights_worked": e["nights_worked"]}
                for e in fatigue["per_tm"]
                if limit and e["nights_worked"] > limit
            ]
            if offenders:
                out.append({
                    "kind": kind, "value": limit,
                    "severity": "warning",
                    "detail": f"{len(offenders)} TM(s) exceed {limit} nights/week",
                    "affected": offenders,
                })
        elif kind == CONSTRAINT_MIN_COVERAGE:
            threshold = float(c.get("value") or 0)
            offenders = [
                {"night_id": nid, **stats}
                for nid, stats in coverage["by_night"].items()
                if stats["fill_rate"] < threshold
            ]
            if offenders:
                out.append({
                    "kind": kind, "value": threshold,
                    "severity": "error",
                    "detail": f"{len(offenders)} night(s) below {threshold:.0%} coverage",
                    "affected": offenders,
                })
        elif kind == CONSTRAINT_EXCLUDE_ZONE:
            target = (c.get("target") or "").strip()
            if not target:
                continue
            target_lower = target.lower()
            offenders = []
            for nid, night in snapshot.items():
                for row in night["assignments"]:
                    if not row.get("is_filled"):
                        continue
                    label = (row.get("label") or "").lower()
                    slot_key = (row.get("slot_key") or "").lower()
                    if target_lower in (label, slot_key):
                        offenders.append({
                            "night_id": nid,
                            "assignment_id": row.get("id"),
                            "slot_key": row.get("slot_key"),
                            "tm_id": row.get("tm_id"),
                            "tm_name": row.get("tm_name"),
                        })
            if offenders:
                out.append({
                    "kind": kind, "target": target,
                    "severity": "warning",
                    "detail": f"{len(offenders)} placement(s) on excluded slot {target!r}",
                    "affected": offenders,
                })
        elif kind == CONSTRAINT_REQUIRE_SKILL:
            min_skill = int(c.get("value") or 0)
            offenders = []
            for nid, night in snapshot.items():
                for row in night["assignments"]:
                    if not row.get("is_filled"):
                        continue
                    skill = row.get("tm_skill") or 0
                    if skill < min_skill:
                        offenders.append({
                            "night_id": nid,
                            "assignment_id": row.get("id"),
                            "slot_key": row.get("slot_key"),
                            "tm_id": row.get("tm_id"),
                            "tm_name": row.get("tm_name"),
                            "tm_skill": skill,
                        })
            if offenders:
                out.append({
                    "kind": kind, "value": min_skill,
                    "severity": "info",
                    "detail": f"{len(offenders)} placement(s) below skill {min_skill}",
                    "affected": offenders,
                })
    return out


def _coverage_delta(baseline: dict, scenario: dict) -> dict:
    b = baseline["coverage"]
    s = scenario["coverage"]
    return {
        "filled_delta":   s["filled_slots"]   - b["filled_slots"],
        "unfilled_delta": s["unfilled_slots"] - b["unfilled_slots"],
        "fill_rate_delta": round(s["fill_rate"] - b["fill_rate"], 4),
        "violations_delta":
            len(scenario["violations"]) - len(baseline["violations"]),
    }


def _safe_rate(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return round(numerator / denominator, 4)
