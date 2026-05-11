"""Unit tests for SimulationService.

The service is exercised through a fake PlacementService that returns
hard-coded week + assignment data, so the tests don't need Supabase or
Redis. The route smoke test (test_planning_router.py) covers the
integration path with the FastAPI dep-override hook.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

# Repo root needs to be on sys.path for `apps.zds...` package imports.
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from apps.zds.api.services.simulation_service import (  # noqa: E402
    SimulationError,
    SimulationService,
    _max_consecutive_streak,
    _safe_rate,
)


# ── Fixture data ────────────────────────────────────────────────────


def _zone_row(*, id_, slot_type, slot_key, tm_id="", tm_name="",
              tm_skill=0, label=None):
    """Match the dict shape produced by database.fetch_zone_assignments."""
    return {
        "id": id_,
        "slot_type": slot_type,
        "slot_key": slot_key,
        "rr_side": "",
        "tm_id": tm_id,
        "tm_name": tm_name,
        "tm_skill": tm_skill,
        "is_filled": bool(tm_id),
        "is_empty": not bool(tm_id),
        "label": label or slot_key,
        "display_name": tm_name or "Unfilled",
    }


def _overlap(*, id_, window, position, tm_id="", tm_name=""):
    return {
        "id": id_,
        "overlap_window": window,
        "position": position,
        "is_filled": bool(tm_id),
        "task": "",
        "tm_id": tm_id,
        "tm_name": tm_name,
    }


WEEK = {"id": "wk-1", "week_ending": "2026-05-15", "label": "Week 1",
        "status": "draft"}

NIGHTS = [
    {"id": "n-mon", "night_date": "2026-05-11", "day_name": "Mon"},
    {"id": "n-tue", "night_date": "2026-05-12", "day_name": "Tue"},
    {"id": "n-wed", "night_date": "2026-05-13", "day_name": "Wed"},
]

ASSIGNMENTS = {
    "n-mon": [
        _zone_row(id_="a1", slot_type="zone", slot_key="zone_1",
                  tm_id="tm-a", tm_name="Alice", tm_skill=8),
        _zone_row(id_="a2", slot_type="zone", slot_key="zone_2",
                  tm_id="tm-b", tm_name="Bob", tm_skill=6),
        _zone_row(id_="a3", slot_type="aux", slot_key="trash_1"),
    ],
    "n-tue": [
        _zone_row(id_="b1", slot_type="zone", slot_key="zone_1",
                  tm_id="tm-a", tm_name="Alice", tm_skill=8),
        _zone_row(id_="b2", slot_type="zone", slot_key="zone_2",
                  tm_id="tm-c", tm_name="Carol", tm_skill=4),
    ],
    "n-wed": [
        _zone_row(id_="c1", slot_type="zone", slot_key="zone_1",
                  tm_id="tm-a", tm_name="Alice", tm_skill=8),
        _zone_row(id_="c2", slot_type="zone", slot_key="zone_2",
                  tm_id="tm-b", tm_name="Bob", tm_skill=6),
    ],
}

OVERLAPS = {
    "n-mon": [
        _overlap(id_="o1", window="pm", position=1, tm_id="tm-x", tm_name="X"),
        _overlap(id_="o2", window="am", position=1),
    ],
    "n-tue": [
        _overlap(id_="o3", window="pm", position=1, tm_id="tm-y", tm_name="Y"),
        _overlap(id_="o4", window="am", position=1, tm_id="tm-z", tm_name="Z"),
    ],
    "n-wed": [
        _overlap(id_="o5", window="pm", position=1),
        _overlap(id_="o6", window="am", position=1),
    ],
}


class FakePlacement:
    """Stand-in for PlacementService that serves the fixtures above."""

    def __init__(self, week=WEEK, nights=NIGHTS,
                 assignments=ASSIGNMENTS, overlaps=OVERLAPS):
        self._week = week
        self._nights = nights
        self._assignments = assignments
        self._overlaps = overlaps

    async def get_week(self, week_id):
        return self._week if self._week and self._week["id"] == week_id else None

    async def get_week_nights(self, week_id):
        return list(self._nights)

    async def get_night_assignments(self, night_id):
        return list(self._assignments.get(night_id, []))

    async def get_night_overlaps(self, night_id):
        return list(self._overlaps.get(night_id, []))


def _make_service():
    svc = SimulationService.__new__(SimulationService)  # bypass __init__
    svc.supabase = None
    svc.cache = None
    svc.placement = FakePlacement()
    return svc


def _run(coro):
    return asyncio.run(coro)


# ── Helpers ─────────────────────────────────────────────────────────


def test_safe_rate_zero_denominator():
    assert _safe_rate(0, 0) == 0.0
    assert _safe_rate(5, 10) == 0.5


def test_max_consecutive_streak():
    assert _max_consecutive_streak(set()) == 0
    assert _max_consecutive_streak({"2026-05-11"}) == 1
    assert _max_consecutive_streak({
        "2026-05-11", "2026-05-12", "2026-05-13"
    }) == 3
    assert _max_consecutive_streak({
        "2026-05-11", "2026-05-13", "2026-05-14"
    }) == 2


# ── Service: scope validation ───────────────────────────────────────


def test_simulate_rejects_no_scope():
    svc = _make_service()
    with pytest.raises(SimulationError):
        _run(svc.simulate())


def test_simulate_rejects_both_scopes():
    svc = _make_service()
    with pytest.raises(SimulationError):
        _run(svc.simulate(week_id="wk-1", night_id="n-mon"))


def test_simulate_rejects_unknown_week():
    svc = _make_service()
    with pytest.raises(SimulationError):
        _run(svc.simulate(week_id="missing"))


# ── Service: baseline metrics ───────────────────────────────────────


def test_baseline_coverage_matches_fixture():
    svc = _make_service()
    result = _run(svc.simulate(week_id="wk-1"))
    cov = result["baseline"]["coverage"]
    assert cov["total_slots"] == 7  # 3 + 2 + 2
    assert cov["filled_slots"] == 6  # only Mon's aux is empty
    assert cov["unfilled_slots"] == 1
    assert cov["fill_rate"] == round(6 / 7, 4)
    assert cov["by_type"]["aux"] == {
        "filled": 0, "total": 1, "fill_rate": 0.0,
    }


def test_baseline_overlap_metrics():
    svc = _make_service()
    result = _run(svc.simulate(week_id="wk-1"))
    overlap = result["baseline"]["overlap"]
    assert overlap["pm_total"] == 3 and overlap["pm_filled"] == 2
    assert overlap["am_total"] == 3 and overlap["am_filled"] == 1


def test_baseline_fatigue_streaks():
    svc = _make_service()
    result = _run(svc.simulate(week_id="wk-1"))
    fatigue = result["baseline"]["fatigue"]
    alice = next(e for e in fatigue["per_tm"] if e["tm_id"] == "tm-a")
    assert alice["nights_worked"] == 3
    assert alice["consecutive_nights"] == 3
    bob = next(e for e in fatigue["per_tm"] if e["tm_id"] == "tm-b")
    assert bob["nights_worked"] == 2  # Mon + Wed (not consecutive)
    assert bob["consecutive_nights"] == 1


# ── Service: scenario mutations ─────────────────────────────────────


def test_mark_unavailable_clears_assignments_and_overlaps():
    svc = _make_service()
    result = _run(svc.simulate(
        week_id="wk-1",
        staffing_changes=[{"kind": "mark_unavailable", "tm_id": "tm-a"}],
    ))
    s_cov = result["scenario"]["coverage"]
    assert s_cov["filled_slots"] == 3  # Alice removed from all three nights
    assert result["delta"]["filled_delta"] == -3
    assert result["delta"]["unfilled_delta"] == 3


def test_remove_assignment_targets_one_slot():
    svc = _make_service()
    result = _run(svc.simulate(
        week_id="wk-1",
        staffing_changes=[
            {"kind": "remove_assignment", "assignment_id": "a1"},
        ],
    ))
    assert result["scenario"]["coverage"]["filled_slots"] == 5
    assert result["delta"]["filled_delta"] == -1


def test_add_assignment_fills_empty_slot():
    svc = _make_service()
    result = _run(svc.simulate(
        week_id="wk-1",
        staffing_changes=[{
            "kind": "add_assignment",
            "assignment_id": "a3",
            "tm_id": "tm-new",
            "tm_name": "Newbie",
            "tm_skill": 5,
        }],
    ))
    assert result["scenario"]["coverage"]["filled_slots"] == 7
    assert result["delta"]["filled_delta"] == 1


def test_reassign_moves_tm_between_slots():
    svc = _make_service()
    result = _run(svc.simulate(
        week_id="wk-1",
        staffing_changes=[{
            "kind": "reassign",
            "assignment_id": "a1",          # Alice on Mon Z1
            "target_assignment_id": "a3",   # → Mon trash_1 (was empty)
        }],
    ))
    s_cov = result["scenario"]["coverage"]
    # Total filled is unchanged: cleared one, filled one.
    assert s_cov["filled_slots"] == 6
    assert result["delta"]["filled_delta"] == 0


def test_unknown_change_kind_raises():
    svc = _make_service()
    with pytest.raises(SimulationError):
        _run(svc.simulate(
            week_id="wk-1",
            staffing_changes=[{"kind": "delete_universe"}],
        ))


def test_unknown_assignment_id_raises():
    svc = _make_service()
    with pytest.raises(SimulationError):
        _run(svc.simulate(
            week_id="wk-1",
            staffing_changes=[
                {"kind": "remove_assignment", "assignment_id": "nope"},
            ],
        ))


def test_unknown_night_id_in_change_raises():
    svc = _make_service()
    with pytest.raises(SimulationError):
        _run(svc.simulate(
            week_id="wk-1",
            staffing_changes=[{
                "kind": "mark_unavailable",
                "tm_id": "tm-a",
                "night_id": "n-fri",
            }],
        ))


# ── Service: constraints ────────────────────────────────────────────


def test_max_consecutive_constraint_flags_alice():
    svc = _make_service()
    result = _run(svc.simulate(
        week_id="wk-1",
        constraints=[{"kind": "max_consecutive_nights", "value": 2}],
    ))
    violations = result["baseline"]["violations"]
    assert any(v["kind"] == "max_consecutive_nights" for v in violations)
    flagged = next(v for v in violations
                   if v["kind"] == "max_consecutive_nights")
    assert any(a["tm_id"] == "tm-a" for a in flagged["affected"])


def test_min_coverage_constraint_flags_low_night():
    svc = _make_service()
    result = _run(svc.simulate(
        week_id="wk-1",
        constraints=[{"kind": "min_coverage", "value": 0.9}],
    ))
    flagged = [v for v in result["baseline"]["violations"]
               if v["kind"] == "min_coverage"]
    assert flagged
    affected_nights = {a["night_id"] for a in flagged[0]["affected"]}
    assert "n-mon" in affected_nights  # only Mon has the empty trash_1


def test_require_skill_constraint_flags_low_skill():
    svc = _make_service()
    result = _run(svc.simulate(
        week_id="wk-1",
        constraints=[{"kind": "require_skill_min", "value": 5}],
    ))
    flagged = [v for v in result["baseline"]["violations"]
               if v["kind"] == "require_skill_min"]
    assert flagged
    # Carol (skill 4) is the only TM below 5.
    affected_tms = {a["tm_id"] for a in flagged[0]["affected"]}
    assert affected_tms == {"tm-c"}


def test_exclude_zone_constraint_flags_matches():
    svc = _make_service()
    result = _run(svc.simulate(
        week_id="wk-1",
        constraints=[{"kind": "exclude_zone", "target": "zone_1"}],
    ))
    flagged = [v for v in result["baseline"]["violations"]
               if v["kind"] == "exclude_zone"]
    assert flagged
    # All three nights have a filled zone_1.
    assert len(flagged[0]["affected"]) == 3


# ── Service: non-destructive ───────────────────────────────────────


def test_simulation_does_not_mutate_baseline_fixtures():
    svc = _make_service()
    _run(svc.simulate(
        week_id="wk-1",
        staffing_changes=[{"kind": "mark_unavailable", "tm_id": "tm-a"}],
    ))
    # The module-level ASSIGNMENTS dict must still show Alice in slot a1.
    assert ASSIGNMENTS["n-mon"][0]["tm_id"] == "tm-a"
    assert ASSIGNMENTS["n-mon"][0]["is_filled"] is True


def test_elapsed_ms_present_and_reasonable():
    svc = _make_service()
    result = _run(svc.simulate(week_id="wk-1"))
    assert isinstance(result["elapsed_ms"], int)
    assert result["elapsed_ms"] >= 0
