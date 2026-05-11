"""Behavior tests for OnShiftStatusService.

Covers the read-side reconciliation (primary + secondary + overlap,
called-off handling, heatmap, stats) and the PATCH semantics.
"""

from __future__ import annotations

import pytest

from apps.zds.api.models.shift_status import (
    AssignmentReason,
    HeatLevel,
    MultiAreaAssignmentPatch,
)
from apps.zds.api.services.on_shift_status_service import (
    FATIGUE_STRETCHED_THRESHOLD,
    OnShiftStatusService,
)


# Use a fixed night that lines up with the fatigue test fixtures.
NIGHT = {"id": "n1", "week_id": "w1", "night_date": "2026-05-11",
        "day_name": "Mon", "is_locked": False}
PRIOR_NIGHT = {"id": "n2", "week_id": "w1", "night_date": "2026-05-08",
               "day_name": "Fri", "is_locked": False}


def _entities():
    return [
        {"id": "tm_alice",  "display_name": "Alice"},
        {"id": "tm_bob",    "display_name": "Bob"},
        {"id": "tm_carol",  "display_name": "Carol"},
    ]


def _base_tables(zone_rows: list[dict], overlap_rows: list[dict],
                 call_offs: list[dict] | None = None,
                 prior_zone_rows: list[dict] | None = None,
                 slot_loads: dict[str, int] | None = None) -> dict[str, list[dict]]:
    return {
        "nights": [NIGHT, PRIOR_NIGHT],
        "entities": _entities(),
        "zone_assignments": zone_rows + (prior_zone_rows or []),
        "overlap_assignments": overlap_rows,
        "call_offs": call_offs or [],
        "slot_load_scores": [{"slot_id": k, "load": v}
                              for k, v in (slot_loads or {}).items()],
        "scorecard_config": [{"id": 1, "fatigue_index_window_days": 7}],
    }


@pytest.mark.asyncio
async def test_primary_and_additional_zones_are_split(fake_supabase_factory):
    """A TM in two zone slots should produce primary + secondary_zone."""
    sb = fake_supabase_factory(_base_tables(
        zone_rows=[
            {"id": "z_pri",  "night_id": "n1", "slot_type": "zone", "slot_key": "zone_3",
             "rr_side": "", "is_filled": True, "is_locked": False, "sort_order": 30,
             "group_num": 1, "tm_id": "tm_alice"},
            {"id": "z_sec",  "night_id": "n1", "slot_type": "zone", "slot_key": "zone_9",
             "rr_side": "", "is_filled": True, "is_locked": True, "sort_order": 90,
             "group_num": 2, "tm_id": "tm_alice"},
        ],
        overlap_rows=[],
    ))

    resp = await OnShiftStatusService(sb).get_status(night_id="n1")

    alice = next(t for t in resp.tm_coverage if t.tm_id == "tm_alice")
    assert alice.primary_zone is not None
    assert alice.primary_zone.slot_key == "zone_3"
    assert alice.primary_zone.reason is AssignmentReason.primary
    assert len(alice.additional_zones) == 1
    extra = alice.additional_zones[0]
    assert extra.slot_key == "zone_9"
    assert extra.reason is AssignmentReason.secondary_zone
    assert extra.is_locked is True
    assert alice.is_multi_area is True
    assert resp.stats.multi_area_tms == 1


@pytest.mark.asyncio
async def test_overlap_assignment_uses_overlap_reason(fake_supabase_factory):
    sb = fake_supabase_factory(_base_tables(
        zone_rows=[
            {"id": "z_b",  "night_id": "n1", "slot_type": "zone", "slot_key": "zone_4",
             "rr_side": "", "is_filled": True, "is_locked": False, "sort_order": 40,
             "group_num": 1, "tm_id": "tm_bob"},
        ],
        overlap_rows=[
            {"id": "o_b", "night_id": "n1", "overlap_window": "pm", "position": 2,
             "is_filled": True, "task": "Trash 1 sweep", "tm_id": "tm_bob"},
        ],
    ))

    resp = await OnShiftStatusService(sb).get_status(night_id="n1")

    bob = next(t for t in resp.tm_coverage if t.tm_id == "tm_bob")
    assert bob.primary_zone is not None
    assert bob.primary_zone.reason is AssignmentReason.primary
    assert len(bob.additional_zones) == 1
    ov = bob.additional_zones[0]
    assert ov.source_table == "overlap_assignments"
    assert ov.reason is AssignmentReason.overlap_pm
    assert ov.slot_key.startswith("PMOL")


@pytest.mark.asyncio
async def test_overlap_only_tm_has_overlap_as_primary(fake_supabase_factory):
    """PMOL-only TMs (no zone) should surface their overlap as primary."""
    sb = fake_supabase_factory(_base_tables(
        zone_rows=[],
        overlap_rows=[
            {"id": "o_c", "night_id": "n1", "overlap_window": "am", "position": 1,
             "is_filled": True, "task": "Trash 1", "tm_id": "tm_carol"},
        ],
    ))

    resp = await OnShiftStatusService(sb).get_status(night_id="n1")

    carol = next(t for t in resp.tm_coverage if t.tm_id == "tm_carol")
    assert carol.primary_zone is not None
    assert carol.primary_zone.reason is AssignmentReason.overlap_am
    assert carol.additional_zones == []
    assert carol.is_multi_area is False


@pytest.mark.asyncio
async def test_called_off_marks_warn_and_lowers_filled_count(fake_supabase_factory):
    """A called-off occupant should leave is_filled=True but heat=warn."""
    sb = fake_supabase_factory(_base_tables(
        zone_rows=[
            {"id": "z_a",  "night_id": "n1", "slot_type": "zone", "slot_key": "zone_3",
             "rr_side": "", "is_filled": True, "is_locked": False, "sort_order": 30,
             "group_num": 1, "tm_id": "tm_alice"},
            {"id": "z_b",  "night_id": "n1", "slot_type": "zone", "slot_key": "zone_5",
             "rr_side": "", "is_filled": False, "is_locked": False, "sort_order": 50,
             "group_num": 1, "tm_id": None},
        ],
        overlap_rows=[],
        call_offs=[{"tm_id": "tm_alice", "night_date": "2026-05-11", "reason": "Sick"}],
    ))

    resp = await OnShiftStatusService(sb).get_status(night_id="n1")

    alice = next(t for t in resp.tm_coverage if t.tm_id == "tm_alice")
    assert alice.is_called_off is True

    by_slot = {c.slot_key: c for c in resp.heatmap}
    assert by_slot["zone_3"].heat_level is HeatLevel.warn
    assert by_slot["zone_5"].heat_level is HeatLevel.open
    assert resp.stats.called_off == 1
    assert resp.stats.open == 1
    assert resp.stats.filled == 0


@pytest.mark.asyncio
async def test_fatigue_index_drives_stretched_heat(fake_supabase_factory):
    """A TM with fatigue ≥ threshold lands on the stretched heat tier."""
    heavy_load = int(FATIGUE_STRETCHED_THRESHOLD) + 1
    sb = fake_supabase_factory(_base_tables(
        zone_rows=[
            {"id": "z_cur",  "night_id": "n1", "slot_type": "zone", "slot_key": "zone_3",
             "rr_side": "", "is_filled": True, "is_locked": False, "sort_order": 30,
             "group_num": 1, "tm_id": "tm_alice"},
        ],
        prior_zone_rows=[
            {"id": "z_prev",  "night_id": "n2", "slot_type": "zone", "slot_key": "zone_7",
             "rr_side": "", "is_filled": True, "is_locked": False, "sort_order": 70,
             "group_num": 1, "tm_id": "tm_alice"},
        ],
        overlap_rows=[],
        slot_loads={"zone_7": heavy_load},
    ))

    resp = await OnShiftStatusService(sb).get_status(night_id="n1")

    alice = next(t for t in resp.tm_coverage if t.tm_id == "tm_alice")
    assert alice.fatigue_index >= FATIGUE_STRETCHED_THRESHOLD

    cell = next(c for c in resp.heatmap if c.slot_key == "zone_3")
    assert cell.heat_level is HeatLevel.stretched


@pytest.mark.asyncio
async def test_stats_count_unique_multi_area_tms(fake_supabase_factory):
    sb = fake_supabase_factory(_base_tables(
        zone_rows=[
            {"id": "z1",  "night_id": "n1", "slot_type": "zone", "slot_key": "zone_1",
             "rr_side": "", "is_filled": True, "is_locked": False, "sort_order": 10,
             "group_num": 1, "tm_id": "tm_alice"},
            {"id": "z2",  "night_id": "n1", "slot_type": "zone", "slot_key": "zone_2",
             "rr_side": "", "is_filled": True, "is_locked": False, "sort_order": 20,
             "group_num": 1, "tm_id": "tm_alice"},
            {"id": "z3",  "night_id": "n1", "slot_type": "zone", "slot_key": "zone_3",
             "rr_side": "", "is_filled": True, "is_locked": False, "sort_order": 30,
             "group_num": 1, "tm_id": "tm_bob"},
        ],
        overlap_rows=[],
    ))
    resp = await OnShiftStatusService(sb).get_status(night_id="n1")
    assert resp.stats.multi_area_tms == 1


# ── PATCH ───────────────────────────────────────────────────────────


def _capturing_supabase(fake_supabase_factory, tables, captured):
    sb = fake_supabase_factory(tables)

    def mutator(mode, ctx, _):
        captured["mode"] = mode
        captured["ctx"] = ctx
        target_id = ctx.get("id")
        table = ctx["table"]
        payload = ctx.get("payload") or {}
        # Mutate the in-memory table so subsequent reads reflect the write
        rows = sb._tables.get(table, [])  # type: ignore[attr-defined]
        for r in rows:
            if r.get("id") == target_id:
                r.update(payload)
                return [dict(r)]
        return []

    sb._mutator = mutator  # type: ignore[attr-defined]
    return sb


@pytest.mark.asyncio
async def test_patch_assigns_tm_and_marks_filled(fake_supabase_factory):
    tables = _base_tables(
        zone_rows=[
            {"id": "z_open", "night_id": "n1", "slot_type": "zone", "slot_key": "zone_5",
             "rr_side": "", "is_filled": False, "is_locked": False, "sort_order": 50,
             "group_num": 1, "tm_id": None},
        ],
        overlap_rows=[],
    )
    captured: dict = {}
    sb = _capturing_supabase(fake_supabase_factory, tables, captured)

    svc = OnShiftStatusService(sb)
    result = await svc.patch_assignment(
        "z_open",
        MultiAreaAssignmentPatch(source_table="zone_assignments", tm_id="tm_carol"),
    )

    assert captured["mode"] == "update"
    assert captured["ctx"]["payload"] == {"tm_id": "tm_carol", "is_filled": True}
    assert result.tm_id == "tm_carol"
    assert result.is_filled is True


@pytest.mark.asyncio
async def test_patch_clearing_unsets_is_filled(fake_supabase_factory):
    tables = _base_tables(
        zone_rows=[
            {"id": "z_f", "night_id": "n1", "slot_type": "zone", "slot_key": "zone_3",
             "rr_side": "", "is_filled": True, "is_locked": False, "sort_order": 30,
             "group_num": 1, "tm_id": "tm_alice"},
        ],
        overlap_rows=[],
    )
    captured: dict = {}
    sb = _capturing_supabase(fake_supabase_factory, tables, captured)

    result = await OnShiftStatusService(sb).patch_assignment(
        "z_f",
        MultiAreaAssignmentPatch(source_table="zone_assignments", tm_id=None),
    )

    assert captured["ctx"]["payload"] == {"tm_id": None, "is_filled": False}
    assert result.tm_id is None
    assert result.is_filled is False


@pytest.mark.asyncio
async def test_patch_rejects_unknown_table(fake_supabase_factory):
    sb = fake_supabase_factory(_base_tables(zone_rows=[], overlap_rows=[]))
    svc = OnShiftStatusService(sb)
    # Pydantic blocks the literal at construction time — assert the model itself
    # rejects an invalid source_table value.
    with pytest.raises(Exception):
        MultiAreaAssignmentPatch(source_table="some_other_table", tm_id="tm_x")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_patch_missing_row_raises_lookuperror(fake_supabase_factory):
    captured: dict = {}
    sb = _capturing_supabase(fake_supabase_factory,
                              _base_tables(zone_rows=[], overlap_rows=[]),
                              captured)
    svc = OnShiftStatusService(sb)
    with pytest.raises(LookupError):
        await svc.patch_assignment(
            "no-such-id",
            MultiAreaAssignmentPatch(source_table="zone_assignments", tm_id="tm_x"),
        )
