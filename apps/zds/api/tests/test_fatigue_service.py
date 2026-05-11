"""Fatigue parity tests.

Pin behavior against the engine's `scorecard.fatigue_index` formula:

    fi(tm) = Σ slot_load[slot] over the most-recent date per slot
             in the trailing fatigue_window_days window.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.zds.api.services.fatigue_service import FatigueService


def _make_supabase(fake_supabase_factory, *, zone_assignments, slot_loads, window=7):
    return fake_supabase_factory({
        "zone_assignments": zone_assignments,
        "slot_load_scores": [{"slot_id": k, "load": v} for k, v in slot_loads.items()],
        "scorecard_config":  [{"id": 1, "fatigue_index_window_days": window}],
        "nights": [
            {"id": "n1", "night_date": "2026-05-10"},
            {"id": "n2", "night_date": "2026-05-08"},
            {"id": "n3", "night_date": "2026-05-04"},
            {"id": "n_old", "night_date": "2026-04-20"},
        ],
        "entities": [],
    })


def test_fatigue_sums_recent_loads_only(fake_supabase_factory):
    sb = _make_supabase(
        fake_supabase_factory,
        zone_assignments=[
            {"id": "a1", "tm_id": "tm_a", "slot_key": "zone_3", "slot_type": "zone",
             "rr_side": "", "night_id": "n1"},
            {"id": "a2", "tm_id": "tm_a", "slot_key": "zone_9", "slot_type": "zone",
             "rr_side": "", "night_id": "n2"},
            # outside window — must not contribute
            {"id": "a3", "tm_id": "tm_a", "slot_key": "zone_1", "slot_type": "zone",
             "rr_side": "", "night_id": "n_old"},
        ],
        slot_loads={"zone_3": 4, "zone_9": 5, "zone_1": 3},
    )

    svc = FatigueService(sb)
    scores, window = svc.compute(["tm_a"], anchor_date=date(2026, 5, 11))

    assert window == 7
    assert scores["tm_a"] == pytest.approx(4 + 5)


def test_fatigue_dedupes_same_slot_multiple_days(fake_supabase_factory):
    """Same slot worked twice in window counts once (most recent wins)."""
    sb = _make_supabase(
        fake_supabase_factory,
        zone_assignments=[
            {"id": "a1", "tm_id": "tm_b", "slot_key": "zone_5", "slot_type": "zone",
             "rr_side": "", "night_id": "n1"},
            {"id": "a2", "tm_id": "tm_b", "slot_key": "zone_5", "slot_type": "zone",
             "rr_side": "", "night_id": "n2"},
        ],
        slot_loads={"zone_5": 6},
    )

    scores, _ = FatigueService(sb).compute(["tm_b"], anchor_date=date(2026, 5, 11))

    assert scores["tm_b"] == pytest.approx(6)


def test_fatigue_missing_load_defaults_to_two(fake_supabase_factory):
    """Slots without a load row contribute the engine's fallback of 2."""
    sb = _make_supabase(
        fake_supabase_factory,
        zone_assignments=[
            {"id": "a1", "tm_id": "tm_c", "slot_key": "support", "slot_type": "aux",
             "rr_side": "", "night_id": "n1"},
        ],
        slot_loads={},  # nothing for "support"
    )
    scores, _ = FatigueService(sb).compute(["tm_c"], anchor_date=date(2026, 5, 11))
    assert scores["tm_c"] == pytest.approx(2)


def test_fatigue_returns_zero_for_inactive_tm(fake_supabase_factory):
    sb = _make_supabase(
        fake_supabase_factory,
        zone_assignments=[
            {"id": "a1", "tm_id": "tm_other", "slot_key": "zone_3",
             "slot_type": "zone", "rr_side": "", "night_id": "n1"},
        ],
        slot_loads={"zone_3": 4},
    )
    scores, _ = FatigueService(sb).compute(["tm_quiet"], anchor_date=date(2026, 5, 11))
    assert scores["tm_quiet"] == 0.0


def test_rr_slot_key_canonicalized_with_side(fake_supabase_factory):
    """RR slots stored as (slot_key='rr_3', rr_side='mens') must look up 'rr_3_M'."""
    sb = _make_supabase(
        fake_supabase_factory,
        zone_assignments=[
            {"id": "a1", "tm_id": "tm_d", "slot_key": "rr_3", "slot_type": "rr",
             "rr_side": "mens", "night_id": "n1"},
        ],
        slot_loads={"rr_3_M": 3, "rr_3": 99},  # 'rr_3' must NOT be picked
    )
    scores, _ = FatigueService(sb).compute(["tm_d"], anchor_date=date(2026, 5, 11))
    assert scores["tm_d"] == pytest.approx(3)
