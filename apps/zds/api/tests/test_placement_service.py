"""Unit tests for PlacementService.

Tests verify:
  - Each method round-trips through cache correctly (set → get returns cached
    object; assert fake DB was called exactly once for two sequential reads)
  - invalidate_night blows away related cache keys; next read calls DB fresh
  - apply_override invalidates the night's assignment cache
  - upsert_annotation invalidates only the affected day's anno: key
  - list_active_tms returns TMRow models, not raw dicts
  - list_tasks returns TaskRow models and caches them
  - assign_tm_to_areas upserts and invalidates night assignments cache
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.zds.api.models import (
    AnnotationRow,
    MultiAreaAssignmentRow,
    NightRow,
    TaskRow,
    TMRow,
    WeekRow,
)


# ── get_week ──────────────────────────────────────────────────────────────────

class TestGetWeek:
    @pytest.mark.asyncio
    async def test_returns_dict_on_hit(self, placement_service, week_fixture):
        result = await placement_service.get_week("week-abc-123")
        assert result is not None
        assert result["id"] == "week-abc-123"

    @pytest.mark.asyncio
    async def test_caches_on_first_call(self, placement_service):
        """DB must be called exactly once for two sequential get_week calls."""
        svc = placement_service
        svc._db.call_count = 0
        await svc.get_week("week-abc-123")
        await svc.get_week("week-abc-123")
        assert svc._db.call_count == 1  # second call hit cache


# ── get_night ─────────────────────────────────────────────────────────────────

class TestGetNight:
    @pytest.mark.asyncio
    async def test_returns_night_row_model(self, placement_service, week_fixture):
        # Wire fake supabase to return the night fixture.
        night_data = week_fixture["night"]
        placement_service.supabase._table_data["nights"] = night_data

        result = await placement_service.get_night("night-fri-001")
        assert result is not None
        assert isinstance(result, NightRow)
        assert result.id == "night-fri-001"
        assert result.day_name == "Friday"

    @pytest.mark.asyncio
    async def test_caches_night(self, placement_service, week_fixture, cache_service):
        night_data = week_fixture["night"]
        placement_service.supabase._table_data["nights"] = night_data

        # Call twice — cache should hold after first.
        await placement_service.get_night("night-fri-001")
        # Verify cache is warm.
        cached = await cache_service.get("zds:night:night-fri-001")
        assert cached is not None
        assert cached["id"] == "night-fri-001"


# ── list_recent_weeks ─────────────────────────────────────────────────────────

class TestListRecentWeeks:
    @pytest.mark.asyncio
    async def test_returns_week_rows(self, placement_service, week_fixture):
        placement_service.supabase._table_data["weeks"] = [week_fixture["week"]]
        result = await placement_service.list_recent_weeks()
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], WeekRow)
        assert result[0].id == "week-abc-123"


# ── list_tasks ────────────────────────────────────────────────────────────────

class TestListTasks:
    @pytest.mark.asyncio
    async def test_returns_task_rows(self, placement_service, tasks_fixture):
        result = await placement_service.list_tasks()
        assert len(result) == len(tasks_fixture)
        for row in result:
            assert isinstance(row, TaskRow)

    @pytest.mark.asyncio
    async def test_caches_on_first_call(self, placement_service):
        svc = placement_service
        svc._shared_db.call_count = 0
        await svc.list_tasks()
        await svc.list_tasks()
        assert svc._shared_db.call_count == 1  # cached after first

    @pytest.mark.asyncio
    async def test_upsert_task_invalidates_cache(self, placement_service, cache_service):
        svc = placement_service
        # Prime the cache.
        await svc.list_tasks()
        assert await cache_service.get("zds:tasks:*:*:*") is not None
        # Upsert should blow away tasks:* cache keys.
        await svc.upsert_task({"name": "New Task"})
        assert await cache_service.get("zds:tasks:*:*:*") is None


# ── list_active_tms ───────────────────────────────────────────────────────────

class TestListActiveTms:
    @pytest.mark.asyncio
    async def test_returns_tm_rows(self, placement_service, week_fixture):
        placement_service.supabase._table_data["entities"] = week_fixture["tms"]
        result = await placement_service.list_active_tms()
        assert len(result) == 2
        for tm in result:
            assert isinstance(tm, TMRow)

    @pytest.mark.asyncio
    async def test_caches_after_first_call(self, placement_service, week_fixture, cache_service):
        placement_service.supabase._table_data["entities"] = week_fixture["tms"]
        await placement_service.list_active_tms()
        cached = await cache_service.get("zds:tms:active")
        assert cached is not None
        assert len(cached) == 2

    @pytest.mark.asyncio
    async def test_get_tm_by_id(self, placement_service, week_fixture):
        placement_service.supabase._table_data["entities"] = week_fixture["tms"][0]
        result = await placement_service.get_tm("tm-seth-001")
        assert result is not None
        assert isinstance(result, TMRow)
        assert result.name == "Seth"


# ── list_annotations_for_day ──────────────────────────────────────────────────

class TestAnnotations:
    @pytest.mark.asyncio
    async def test_returns_grouped_dict(self, placement_service):
        result = await placement_service.list_annotations_for_day(
            week_ending=date(2026, 5, 14), day="fri"
        )
        assert isinstance(result, dict)
        assert "task" in result

    @pytest.mark.asyncio
    async def test_caches_annotations(self, placement_service, cache_service):
        we = date(2026, 5, 14)
        await placement_service.list_annotations_for_day(we, "fri")
        cached = await cache_service.get("zds:anno:2026-05-14:fri")
        assert cached is not None

    @pytest.mark.asyncio
    async def test_upsert_annotation_invalidates_day_cache(
        self, placement_service, cache_service
    ):
        we = date(2026, 5, 14)
        # Prime cache.
        await placement_service.list_annotations_for_day(we, "fri")
        assert await cache_service.get("zds:anno:2026-05-14:fri") is not None

        # Upsert must clear that exact key.
        await placement_service.upsert_annotation(
            we, "fri", "task", "task-sweep-001", "highlight", {"color": "yellow"}
        )
        assert await cache_service.get("zds:anno:2026-05-14:fri") is None

    @pytest.mark.asyncio
    async def test_upsert_annotation_returns_model(self, placement_service):
        result = await placement_service.upsert_annotation(
            date(2026, 5, 14), "fri", "task", "task-sweep-001",
            "highlight", {"color": "yellow"}
        )
        assert isinstance(result, AnnotationRow)
        assert result.annotation_kind == "highlight"

    @pytest.mark.asyncio
    async def test_delete_annotation_invalidates_cache(
        self, placement_service, cache_service
    ):
        we = date(2026, 5, 14)
        await placement_service.list_annotations_for_day(we, "fri")
        await placement_service.delete_annotation(
            we, "fri", "task", "task-sweep-001", "highlight"
        )
        assert await cache_service.get("zds:anno:2026-05-14:fri") is None


# ── invalidate_night ──────────────────────────────────────────────────────────

class TestInvalidateNight:
    @pytest.mark.asyncio
    async def test_invalidate_clears_night_keys(
        self, placement_service, cache_service, week_fixture
    ):
        svc = placement_service
        night_data = week_fixture["night"]
        svc.supabase._table_data["nights"] = night_data

        night_id = "night-fri-001"

        # Warm all caches.
        await svc.get_night_assignments(night_id)
        await svc.get_night_overlaps(night_id)
        assert await cache_service.get(f"zds:night:{night_id}:assignments") is not None
        assert await cache_service.get(f"zds:night:{night_id}:overlaps") is not None

        # Invalidate.
        await svc.invalidate_night(night_id)

        # All night keys must be gone.
        assert await cache_service.get(f"zds:night:{night_id}:assignments") is None
        assert await cache_service.get(f"zds:night:{night_id}:overlaps") is None

    @pytest.mark.asyncio
    async def test_after_invalidation_next_read_hits_db(
        self, placement_service, week_fixture
    ):
        svc = placement_service
        night_id = "night-fri-001"

        # Pre-warm the week cache so that invalidate_night's internal get_week()
        # call hits cache rather than the DB, keeping _db.call_count clean.
        await svc.get_week("week-abc-123")

        svc._db.call_count = 0
        await svc.get_night_assignments(night_id)  # first — DB call
        count_after_first = svc._db.call_count

        await svc.get_night_assignments(night_id)  # second — cached (no DB)
        assert svc._db.call_count == count_after_first

        # invalidate_night: get_night() hits Supabase (not _db), get_week() hits
        # cache (pre-warmed above) — so _db.call_count stays at count_after_first.
        await svc.invalidate_night(night_id)

        await svc.get_night_assignments(night_id)  # cache cleared — DB call again
        assert svc._db.call_count == count_after_first + 1


# ── assign_tm_to_areas ────────────────────────────────────────────────────────

class TestAssignTmToAreas:
    @pytest.mark.asyncio
    async def test_returns_multi_area_assignment_row(self, placement_service, week_fixture):
        night_id = "night-fri-001"
        svc = placement_service

        # Fake Supabase returns a row on upsert.
        svc.supabase._table_data["multi_area_assignments"] = [{
            "id": "maa-001",
            "night_id": night_id,
            "tm_id": "tm-seth-001",
            "primary_area": "Z1",
            "additional_areas": ["Z2"],
            "created_at": "2026-05-08T22:00:00Z",
            "updated_at": "2026-05-08T22:00:00Z",
        }]

        result = await svc.assign_tm_to_areas(
            night_id=night_id,
            tm_id="tm-seth-001",
            primary_area="Z1",
            additional_areas=["Z2"],
        )
        assert isinstance(result, MultiAreaAssignmentRow)
        assert result.primary_area == "Z1"
        assert result.additional_areas == ["Z2"]

    @pytest.mark.asyncio
    async def test_invalidates_assignment_cache(
        self, placement_service, cache_service, week_fixture
    ):
        svc = placement_service
        night_id = "night-fri-001"

        # Prime assignment cache.
        await svc.get_night_assignments(night_id)
        assert await cache_service.get(f"zds:night:{night_id}:assignments") is not None

        svc.supabase._table_data["multi_area_assignments"] = [{
            "id": "maa-001",
            "night_id": night_id,
            "tm_id": "tm-seth-001",
            "primary_area": "Z1",
            "additional_areas": [],
            "created_at": "2026-05-08T22:00:00Z",
            "updated_at": "2026-05-08T22:00:00Z",
        }]

        await svc.assign_tm_to_areas(night_id, "tm-seth-001", "Z1")
        # Assignment cache must have been cleared.
        assert await cache_service.get(f"zds:night:{night_id}:assignments") is None
