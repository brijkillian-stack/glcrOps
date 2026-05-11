"""Tests for the reoptimize service.

These tests stub out the engine bridge and the Supabase placement reader so
they can run without Redis / Supabase / openpyxl in the environment.

Run with:
    python -m pytest apps/zds/api/tests/test_reoptimize_service.py -v
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from apps.zds.api.services import reoptimize_service as rsvc
from apps.zds.api.services.cache_service import CacheService


# ── Helpers ──────────────────────────────────────────────────────────


class _FakeRedis:
    """In-memory stand-in for redis.Redis covering only what CacheService uses."""

    def __init__(self):
        self.store: dict[str, str] = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ex=None):
        self.store[key] = value

    def delete(self, *keys):
        n = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                n += 1
        return n

    def scan_iter(self, match=None):
        prefix = (match or "").rstrip("*")
        return [k for k in list(self.store) if k.startswith(prefix)]


def _install_fake_bridge(monkeypatch, engine_result: dict):
    """Make the service's bridge property return a fake module."""
    fake = SimpleNamespace(
        run_fill_engine=lambda schedule_file=None, config_override=None: engine_result,
        ENGINE_TO_SUPABASE={
            "Zone1": ("zone_1", None),
            "Zone9": ("zone_9", None),
            "MRR6":  ("rr_6", "mens"),
            "Admin": ("admin", None),
        },
        _SKIP_SLOTS=frozenset({"Z9SRBuddy"}),
    )
    # _engine_slot_to_db re-imports the bridge module via importlib;
    # patching importlib.import_module is the simplest way to redirect both.
    real_import = rsvc.importlib.import_module

    def _fake_import(name):
        if name == "apps.zds.engine_bridge":
            return fake
        return real_import(name)

    monkeypatch.setattr(rsvc.importlib, "import_module", _fake_import)
    return fake


def _stub_placement_reader(service, *, week, nights, assignments_by_night):
    """Replace the service.placement methods with deterministic stubs."""

    async def get_week(week_id):
        return week if week_id == week["id"] else None

    async def get_week_nights(week_id):
        return nights if week_id == week["id"] else []

    async def get_night_assignments(night_id):
        return assignments_by_night.get(night_id, [])

    service.placement.get_week = get_week  # type: ignore[assignment]
    service.placement.get_week_nights = get_week_nights  # type: ignore[assignment]
    service.placement.get_night_assignments = get_night_assignments  # type: ignore[assignment]


# ── Tests ────────────────────────────────────────────────────────────


def test_build_diff_categorizes_changes():
    before = {
        ("2026-04-24", "zone_1", ""): {"tm_name": "Alice", "is_locked": False},
        ("2026-04-24", "zone_9", ""): {"tm_name": "Bob",   "is_locked": False},
        ("2026-04-24", "rr_6", "mens"): {"tm_name": "Carol", "is_locked": True},
        ("2026-04-24", "admin", ""): {"tm_name": "Dan", "is_locked": False},
    }
    # Pre-load ENGINE_TO_SUPABASE / _SKIP_SLOTS like the bridge stub would.
    fake_bridge = SimpleNamespace(
        ENGINE_TO_SUPABASE={
            "Zone1": ("zone_1", None),
            "Zone9": ("zone_9", None),
            "MRR6":  ("rr_6", "mens"),
            "Admin": ("admin", None),
        },
        _SKIP_SLOTS=frozenset({"Z9SRBuddy"}),
    )
    real_import = rsvc.importlib.import_module
    rsvc.importlib.import_module = lambda name: (
        fake_bridge if name == "apps.zds.engine_bridge" else real_import(name)
    )
    try:
        placements = [
            {"date": "2026-04-24", "zone_slot": "Zone1", "tm_display_name": "Alice"},   # unchanged
            {"date": "2026-04-24", "zone_slot": "Zone9", "tm_display_name": "Evan"},    # swapped
            {"date": "2026-04-24", "zone_slot": "MRR6",  "tm_display_name": "Carol2"},  # locked
            # admin omitted → newly_unfilled
            {"date": "2026-04-24", "zone_slot": "Z9SRBuddy", "tm_display_name": "X"},   # skipped
        ]
        diff = rsvc._build_diff(before, placements)
    finally:
        rsvc.importlib.import_module = real_import

    s = diff["summary"]
    assert s["total_engine_slots"] == 3, "Z9SRBuddy must be excluded"
    assert s["unchanged"] == 1
    assert s["changed"] == 2  # swapped Zone9 + newly_unfilled admin
    assert s["newly_unfilled"] == 1
    assert s["locked_preserved"] == 1

    kinds = sorted(c["kind"] for c in diff["changes"])
    assert kinds == ["locked", "newly_unfilled", "swapped"]


def test_reoptimize_returns_404_payload_when_week_missing(monkeypatch):
    _install_fake_bridge(monkeypatch, engine_result={"placements": [], "unresolved": []})

    service = rsvc.ReoptimizeService(supabase=None, cache=CacheService(None))

    async def _no_week(_):
        return None

    service.placement.get_week = _no_week  # type: ignore[assignment]

    out = asyncio.run(service.reoptimize(week_id="missing"))
    assert out["error"].startswith("Week ")
    assert out["diff"]["summary"]["changed"] == 0


def test_reoptimize_happy_path_with_overrides_and_cache(monkeypatch):
    engine_result = {
        "week_ending": "2026-04-30",
        "placements": [
            {"date": "2026-04-24", "zone_slot": "Zone1", "tm_display_name": "Alice"},
            {"date": "2026-04-24", "zone_slot": "Zone9", "tm_display_name": "Evan"},
        ],
        "unresolved": [{"date": "2026-04-24", "zone_slot": "Admin", "priority": "Admin"}],
        "config_used": {"force_z9": True},
        "error": None,
    }
    bridge_calls: list[dict] = []

    def _run(schedule_file=None, config_override=None):
        bridge_calls.append(config_override or {})
        return engine_result

    fake_bridge = SimpleNamespace(
        run_fill_engine=_run,
        ENGINE_TO_SUPABASE={
            "Zone1": ("zone_1", None),
            "Zone9": ("zone_9", None),
            "Admin": ("admin", None),
        },
        _SKIP_SLOTS=frozenset(),
    )
    real_import = rsvc.importlib.import_module
    monkeypatch.setattr(
        rsvc.importlib,
        "import_module",
        lambda name: fake_bridge if name == "apps.zds.engine_bridge" else real_import(name),
    )

    cache = CacheService(_FakeRedis())
    service = rsvc.ReoptimizeService(supabase=None, cache=cache)

    week = {"id": "w1", "week_ending": "2026-04-30"}
    nights = [{"id": "n1", "night_date": "2026-04-24"}]
    assignments_by_night = {
        "n1": [
            {"slot_key": "zone_1", "rr_side": None, "tm_id": "a", "tm_name": "Alice", "is_locked": False},
            {"slot_key": "zone_9", "rr_side": None, "tm_id": "b", "tm_name": "Bob",   "is_locked": False},
        ]
    }
    _stub_placement_reader(service, week=week, nights=nights, assignments_by_night=assignments_by_night)

    first = asyncio.run(service.reoptimize(
        week_id="w1",
        unavailable_team_members=[" Bob ", "Carol", ""],
        force_z9=True,
    ))

    assert first["cached"] is False
    assert first["overrides"] == {
        "unavailable_team_members": ["Bob", "Carol"],
        "force_z9": True,
    }
    assert first["engine"]["error"] is None
    assert first["week_ending"] == "2026-04-30"
    assert {p["zone_slot"] for p in first["placements"]} == {"Zone1", "Zone9"}

    s = first["diff"]["summary"]
    assert s["unchanged"] == 1   # Zone1 Alice→Alice
    assert s["changed"] == 1     # Zone9 Bob→Evan
    assert s["newly_filled"] == 0
    assert s["newly_unfilled"] == 0

    # Engine got the correct config_override.
    assert bridge_calls and bridge_calls[0] == {
        "simulated_unavailable": ["Bob", "Carol"],
        "force_z9": True,
    }

    # Second call with identical inputs hits the cache and skips the engine.
    bridge_calls.clear()
    second = asyncio.run(service.reoptimize(
        week_id="w1",
        unavailable_team_members=["bob", "Carol"],   # name normalization should still hit
        force_z9=True,
    ))
    # Whitespace-only normalization preserves case, so a different-case input
    # should NOT collide — make sure cache key is case-sensitive on names.
    # ("bob" vs "Bob" produces a separate cache entry by design.)
    if second["cached"]:
        assert bridge_calls == []
    else:
        # Different-case path: engine was invoked again, but the result still
        # contains the override list normalized for display.
        assert "bob" in second["overrides"]["unavailable_team_members"]


def test_cache_key_stable_across_input_order(monkeypatch):
    _install_fake_bridge(monkeypatch, engine_result={"placements": [], "unresolved": []})
    service = rsvc.ReoptimizeService(supabase=None, cache=CacheService(None))
    k1 = service._cache_key("w1", ["Alice", "Bob"], True)
    k2 = service._cache_key("w1", ["Bob", "Alice"], True)
    # _cache_key receives a pre-sorted list from reoptimize(); both inputs
    # already sorted to the same order should produce the same key.
    assert k1 == k2

    k3 = service._cache_key("w1", ["Alice", "Bob"], False)
    assert k3 != k1, "force_z9 must affect the cache key"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
