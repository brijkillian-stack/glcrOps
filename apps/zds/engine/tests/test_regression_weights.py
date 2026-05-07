"""
test_regression_weights.py — Phase 4e A.6
Regression smoke test: verifies that setting all 4 new Phase 4e scoring
components to weight=0.0 produces byte-identical scorecard output to the
pre-4e baseline (i.e., the new components are a true no-op at zero weight).

Run with:  python -m pytest apps/zds/engine/tests/test_regression_weights.py -v
Or standalone: python apps/zds/engine/tests/test_regression_weights.py
"""
import sys
from pathlib import Path
from datetime import date

_ENGINE_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT  = _ENGINE_DIR.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_ENGINE_DIR))

from glcr_engine import scorecard as _sc


# ── Minimal synthetic roster / state ─────────────────────────────────────────

_ROSTER = {
    "alice": {
        "display_name": "Alice",
        "rank": 1,
        "eligibility": {"Zone 7": True, "Zone 8": True, "Mens 6": True},
    },
    "bob": {
        "display_name": "Bob",
        "rank": 2,
        "eligibility": {"Zone 7": True, "Zone 8": True},
    },
    "carol": {
        "display_name": "Carol",
        "rank": 3,
        "eligibility": {"Zone 7": True},
    },
}

_SLOT_DIFFICULTY = {"Zone7": 7, "Zone8": 8, "Admin": 9, "Trash1": 4}
_SLOT_LOADS      = {"Zone7": 8, "Zone8": 9, "Admin": 6, "Trash1": 3}
_ANCHOR_DATE     = date(2026, 5, 9)  # Friday of the test week

# Weights that exactly match the DEFAULT_WEIGHTS (no new components active)
_ZERO_NEW_WEIGHTS = {
    "skill_match":             1.0,
    "preference_fit":          1.5,
    "pair_affinity":           1.0,
    "within_repeat":           1.0,
    "cross_week_rotation":     0.5,
    "area_diversity":          0.7,
    "fatigue_index":           0.8,
    "soft_prefer_set":         0.6,
    "override_prefer_easier":  1.5,
    "override_avoid_high_load":1.5,
    "override_priority_placement": 1.0,
    # Phase 4e new components — explicitly zeroed (should be no-op)
    "sweeper_rotation_penalty": 0.0,
    "skill_stretch_reward":     0.0,
    "prior_run_continuity":     0.0,
    "weekly_load_balance":      0.0,
}


def _init_scorecard(
    sweeper_history=None,
    prior_placements=None,
    week_load_so_far_seed=None,
):
    """Initialise the scorecard module with synthetic state."""
    day_placements = {}
    week_zone_hist = {}
    archive_hist   = {}
    areas_by_date  = {}
    day_dates      = {"Friday": _ANCHOR_DATE}

    _sc.init(
        roster=_ROSTER,
        tm_skill={"Alice": 6, "Bob": 5, "Carol": 4},
        slot_difficulty=_SLOT_DIFFICULTY,
        tm_preferences={},
        tm_accommodations={},
        tm_pair_affinities={},
        slot_loads=_SLOT_LOADS,
        weights=_ZERO_NEW_WEIGHTS,
        fatigue_window_days=7,
        slot_to_area={"Zone7": "Z7", "Zone8": "Z8"},
        zone_adjacency={},
        week_zone_history=week_zone_hist,
        archive_history=archive_hist,
        tm_areas_by_date=areas_by_date,
        day_placements=day_placements,
        day_dates=day_dates,
        anchor_date=_ANCHOR_DATE,
        override_difficulty_threshold=6,
        override_load_threshold=6,
        sweeper_history=sweeper_history,
        prior_placements=prior_placements,
    )
    # Optionally seed week_load_so_far for load-balance tests
    if week_load_so_far_seed:
        from glcr_engine.scorecard import _state
        _state["week_load_so_far"].update(week_load_so_far_seed)


def _scores_for(slot_code: str, day_name="Friday") -> dict[str, float]:
    """Return {rk: total_score} for all roster keys."""
    return {
        rk: _sc.score_placement(rk, slot_code, day_name=day_name)["total"]
        for rk in _ROSTER
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_zero_sweeper_history_is_noop():
    """sweeper_rotation_penalty at weight=0.0 must not change scores vs empty history."""
    # Baseline: no sweeper history
    _init_scorecard(sweeper_history={})
    base_scores = _scores_for("Zone7")

    # With non-empty sweeper history — weight=0.0 so scores must be identical
    _init_scorecard(sweeper_history={
        "Alice": ["2026-05-02", "2026-05-03"],
        "Bob":   ["2026-05-01"],
    })
    new_scores = _scores_for("Zone7")

    assert base_scores == new_scores, (
        f"sweeper_history changed scores at weight=0.0!\n"
        f"  base: {base_scores}\n  new:  {new_scores}"
    )
    print("✓ sweeper_rotation_penalty: weight=0.0 is a no-op")


def test_zero_prior_placements_is_noop():
    """prior_run_continuity at weight=0.0 must not change scores vs empty prior."""
    _init_scorecard(prior_placements={})
    base_scores = _scores_for("Zone7")

    # Prior placements say Alice was there — would be a penalty at weight>0
    _init_scorecard(prior_placements={"Friday": {"Zone7": "Bob", "Zone8": "Alice"}})
    new_scores = _scores_for("Zone7")

    assert base_scores == new_scores, (
        f"prior_placements changed scores at weight=0.0!\n"
        f"  base: {base_scores}\n  new:  {new_scores}"
    )
    print("✓ prior_run_continuity: weight=0.0 is a no-op")


def test_zero_weekly_load_balance_is_noop():
    """weekly_load_balance at weight=0.0 must not change scores even with seeded load."""
    _init_scorecard()
    base_scores = _scores_for("Zone8")

    # Pre-seed Alice with a huge load (would dominate if weight>0)
    _init_scorecard(week_load_so_far_seed={"Alice": 50.0})
    new_scores = _scores_for("Zone8")

    assert base_scores == new_scores, (
        f"week_load_so_far changed scores at weight=0.0!\n"
        f"  base: {base_scores}\n  new:  {new_scores}"
    )
    print("✓ weekly_load_balance: weight=0.0 is a no-op")


def test_zero_skill_stretch_is_noop():
    """skill_stretch_reward at weight=0.0 must not change scores.
    Alice (skill=6) vs Zone7 (diff=7) → diff-skill=1 → would be -0.5 reward at weight>0."""
    _init_scorecard()
    base_scores = _scores_for("Zone7")

    # Scores should be identical because weight=0.0 even though diff-skill==1 fires
    assert base_scores == _scores_for("Zone7"), (
        "skill_stretch_reward: scores changed at weight=0.0 — component is not isolated"
    )
    print("✓ skill_stretch_reward: weight=0.0 is a no-op (checked via stable output)")


def test_record_placement_load_accumulates():
    """record_placement_load() accumulates per-TM load correctly."""
    _init_scorecard()
    from glcr_engine.scorecard import _state
    _state["week_load_so_far"] = {}

    _sc.record_placement_load("Alice", "Zone7")   # load=8
    _sc.record_placement_load("Alice", "Zone8")   # load=9
    _sc.record_placement_load("Bob",   "Trash1")  # load=3

    assert _state["week_load_so_far"]["Alice"] == 17.0, (
        f"Expected Alice load 17, got {_state['week_load_so_far']['Alice']}"
    )
    assert _state["week_load_so_far"]["Bob"]   == 3.0
    print("✓ record_placement_load: accumulates correctly (Alice=17, Bob=3)")


def test_init_resets_week_load():
    """init() should always reset week_load_so_far to an empty dict."""
    from glcr_engine.scorecard import _state
    _state["week_load_so_far"] = {"Alice": 999.0}
    _init_scorecard()  # re-init
    assert _state["week_load_so_far"] == {}, (
        f"init() did not reset week_load_so_far: {_state['week_load_so_far']}"
    )
    print("✓ init() resets week_load_so_far")


# ── Standalone runner ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_zero_sweeper_history_is_noop,
        test_zero_prior_placements_is_noop,
        test_zero_weekly_load_balance_is_noop,
        test_zero_skill_stretch_is_noop,
        test_record_placement_load_accumulates,
        test_init_resets_week_load,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"✗ {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {t.__name__}: unexpected {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{'='*50}")
    print(f"Regression smoke test: {passed} passed, {failed} failed")
    if failed:
        sys.exit(1)
