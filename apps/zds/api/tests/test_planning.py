"""Tests for GLC-12: Weekly Planning Overview endpoint.

Structure
─────────
  TestPlanningEndpointStructure   — Tier 1 structural tests with FakePlanningService
                                    (no DB, no cache; always runs).
  TestPlanningServiceUnit         — Unit tests for PlanningService with a fake
                                    PlacementService (no DB, no Redis).

Running
───────
  pytest apps/zds/api/tests/test_planning.py -v
  pytest apps/zds/api/tests/test_planning.py -v -k endpoint
  pytest apps/zds/api/tests/test_planning.py -v -k service
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from apps.zds.api.models.planning import (
    NightPlanningSnapshot,
    OverrideSummary,
    PlanningLinks,
    PlanningNote,
    WeeklyPlanningOverviewResponse,
    WeekMeta,
    WeekMetrics,
)


# ══════════════════════════════════════════════════════════════════════════════
# Shared test fixtures / fakes
# ══════════════════════════════════════════════════════════════════════════════

# ── Canned data ───────────────────────────────────────────────────────────────

WEEK_ID   = "week-abc-123"
NIGHT_ID  = "night-fri-001"
NIGHT_ID2 = "night-sat-002"

WEEK_DICT = {
    "id":          WEEK_ID,
    "week_ending": "2026-05-14",
    "label":       "Week of May 8–14, 2026",
    "status":      "published",
}

NIGHTS_LIST = [
    {
        "id":          NIGHT_ID,
        "week_id":     WEEK_ID,
        "night_date":  "2026-05-08",
        "day_name":    "Friday",
        "day_num":     1,
        "in_rotation": 1,
    },
    {
        "id":          NIGHT_ID2,
        "week_id":     WEEK_ID,
        "night_date":  "2026-05-09",
        "day_name":    "Saturday",
        "day_num":     2,
        "in_rotation": 1,
    },
]

# Friday: 3 assignments — 2 filled, 1 gap
ASSIGNMENTS_FRI = [
    {"id": "a1", "night_id": NIGHT_ID, "slot_key": "Z1", "tm_id": "tm-001"},
    {"id": "a2", "night_id": NIGHT_ID, "slot_key": "Z2", "tm_id": "tm-002"},
    {"id": "a3", "night_id": NIGHT_ID, "slot_key": "Z3", "tm_id": None},    # gap
]

# Saturday: 2 assignments — both filled
ASSIGNMENTS_SAT = [
    {"id": "a4", "night_id": NIGHT_ID2, "slot_key": "Z1", "tm_id": "tm-001"},
    {"id": "a5", "night_id": NIGHT_ID2, "slot_key": "Z2", "tm_id": "tm-003"},
]

CANNED_OVERVIEW = WeeklyPlanningOverviewResponse(
    week=WeekMeta(
        id="week-abc-123",
        label="Week of May 8–14, 2026",
        week_start="2026-05-08",
        week_ending="2026-05-14",
        status="published",
    ),
    nights=[
        NightPlanningSnapshot(
            night_id="night-fri-001",
            night_date="2026-05-08",
            day_name="Friday",
            in_rotation=True,
            total_slots=3,
            filled_slots=2,
            gap_count=1,
            coverage_pct=66.7,
            multi_area_overlap_count=0,
            override_count=0,
            reoptimize_recommended=True,
        ),
    ],
    metrics=WeekMetrics(
        total_assignments=2,
        total_gaps=1,
        nights_with_gaps=1,
        multi_area_overlap_count=0,
        active_override_count=0,
        fatigue_index=1.0,
        reoptimize_opportunities=1,
    ),
    planning_notes=[
        PlanningNote(
            night_id="night-fri-001",
            day_name="Friday",
            note_kind="gap",
            note_text="1 unfilled slot — run Reoptimize or assign manually.",
        ),
    ],
    active_overrides=[],
    links=PlanningLinks(
        print_week_html="/v1/print/week/week-abc-123.html",
        print_week_pdf="/v1/print/week/week-abc-123.pdf",
        reoptimize="/v1/engine/week/week-abc-123/reoptimize",
    ),
    cached_at=datetime.now(timezone.utc).isoformat(),
)


# ── FakePlanningService (for endpoint tests) ──────────────────────────────────

class FakePlanningService:
    """Returns canned data. Lets us test the router without any DB."""

    def __init__(self, overview: Optional[WeeklyPlanningOverviewResponse] = CANNED_OVERVIEW):
        self._overview = overview
        self.call_count = 0

    async def get_weekly_overview(
        self, week_id: str
    ) -> Optional[WeeklyPlanningOverviewResponse]:
        self.call_count += 1
        if week_id == "nonexistent":
            return None
        if week_id == "exploding":
            raise RuntimeError("DB is on fire")
        return self._overview


# ── FakePlacementService (for PlanningService unit tests) ─────────────────────

class FakeCache:
    """Minimal in-memory cache."""

    def __init__(self):
        self._store: dict = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: Any, ttl: int = 60):
        self._store[key] = value

    async def delete(self, key: str):
        self._store.pop(key, None)


class FakePlacementService:
    """PlacementService stand-in for PlanningService unit tests."""

    def __init__(
        self,
        week:                   Optional[dict]       = None,
        nights:                 Optional[list]       = None,
        assignments_by_night:   Optional[dict]       = None,
        overlaps_by_night:      Optional[dict]       = None,
        overrides_by_night:     Optional[dict]       = None,
    ):
        self._week      = week
        self._nights    = nights or []
        self._assigns   = assignments_by_night or {}
        self._overlaps  = overlaps_by_night or {}
        self._overrides = overrides_by_night or {}
        self.cache      = FakeCache()
        self.get_week_call_count = 0

    async def get_week(self, week_id: str):
        self.get_week_call_count += 1
        return self._week

    async def get_week_nights(self, week_id: str):
        return self._nights

    async def get_night_assignments(self, night_id: str):
        return self._assigns.get(night_id, [])

    async def get_night_overlaps(self, night_id: str):
        return self._overlaps.get(night_id, [])

    async def list_overrides(self, night_id: str):
        return self._overrides.get(night_id, [])


# ── httpx AsyncClient factory for endpoint tests ──────────────────────────────

def _make_client(planning_svc=None):
    try:
        from httpx import AsyncClient, ASGITransport
    except ImportError:
        pytest.skip("httpx not installed — pip install httpx")

    from apps.zds.api.main import app
    from apps.zds.api.core.dependencies import get_planning_service

    svc = planning_svc or FakePlanningService()
    app.dependency_overrides[get_planning_service] = lambda: svc

    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test"), app, svc


# ══════════════════════════════════════════════════════════════════════════════
# Endpoint structural tests
# ══════════════════════════════════════════════════════════════════════════════

class TestPlanningEndpointStructure:
    """Router-level tests using FakePlanningService — no DB or Redis required."""

    @pytest.mark.asyncio
    async def test_200_for_existing_week(self):
        """Happy path: existing week → 200 JSON."""
        client, app, _ = _make_client()
        async with client as c:
            r = await c.get(f"/v1/planning/weekly/{WEEK_ID}")
        app.dependency_overrides.clear()

        assert r.status_code == 200
        assert "application/json" in r.headers["content-type"]

    @pytest.mark.asyncio
    async def test_404_for_missing_week(self):
        """Non-existent week → 404 with structured error envelope."""
        client, app, _ = _make_client()
        async with client as c:
            r = await c.get("/v1/planning/weekly/nonexistent")
        app.dependency_overrides.clear()

        assert r.status_code == 404
        body = r.json()
        assert body["detail"]["error"] == "not_found"
        assert "nonexistent" in body["detail"]["detail"]

    @pytest.mark.asyncio
    async def test_503_when_service_raises(self):
        """Unexpected PlanningService exception → 503 structured error."""
        client, app, _ = _make_client()
        async with client as c:
            r = await c.get("/v1/planning/weekly/exploding")
        app.dependency_overrides.clear()

        assert r.status_code == 503
        body = r.json()
        assert body["detail"]["error"] == "planning_unavailable"

    @pytest.mark.asyncio
    async def test_response_has_cache_control_header(self):
        """Response must carry Cache-Control: private, max-age=15."""
        client, app, _ = _make_client()
        async with client as c:
            r = await c.get(f"/v1/planning/weekly/{WEEK_ID}")
        app.dependency_overrides.clear()

        cc = r.headers.get("cache-control", "")
        assert "private" in cc
        assert "max-age=15" in cc

    @pytest.mark.asyncio
    async def test_response_week_meta_fields(self):
        """week object must have id, label, week_start, week_ending, status."""
        client, app, _ = _make_client()
        async with client as c:
            r = await c.get(f"/v1/planning/weekly/{WEEK_ID}")
        app.dependency_overrides.clear()

        week = r.json()["week"]
        assert week["id"]          == WEEK_ID
        assert week["week_ending"] == "2026-05-14"
        assert week["week_start"]  == "2026-05-08"
        assert week["status"]      == "published"
        assert "label" in week

    @pytest.mark.asyncio
    async def test_response_has_nights_list(self):
        """nights field must be a list."""
        client, app, _ = _make_client()
        async with client as c:
            r = await c.get(f"/v1/planning/weekly/{WEEK_ID}")
        app.dependency_overrides.clear()

        assert isinstance(r.json()["nights"], list)

    @pytest.mark.asyncio
    async def test_response_metrics_fields(self):
        """metrics object must expose all expected top-level keys."""
        client, app, _ = _make_client()
        async with client as c:
            r = await c.get(f"/v1/planning/weekly/{WEEK_ID}")
        app.dependency_overrides.clear()

        m = r.json()["metrics"]
        for key in (
            "total_assignments",
            "total_gaps",
            "nights_with_gaps",
            "multi_area_overlap_count",
            "active_override_count",
            "fatigue_index",
            "reoptimize_opportunities",
        ):
            assert key in m, f"metrics missing key: {key!r}"

    @pytest.mark.asyncio
    async def test_response_has_planning_notes(self):
        """planning_notes must be a list (may be empty)."""
        client, app, _ = _make_client()
        async with client as c:
            r = await c.get(f"/v1/planning/weekly/{WEEK_ID}")
        app.dependency_overrides.clear()

        assert isinstance(r.json()["planning_notes"], list)

    @pytest.mark.asyncio
    async def test_response_has_active_overrides(self):
        """active_overrides must be a list (may be empty)."""
        client, app, _ = _make_client()
        async with client as c:
            r = await c.get(f"/v1/planning/weekly/{WEEK_ID}")
        app.dependency_overrides.clear()

        assert isinstance(r.json()["active_overrides"], list)

    @pytest.mark.asyncio
    async def test_response_links_contain_print_and_reoptimize(self):
        """links must include print_week_html, print_week_pdf, reoptimize."""
        client, app, _ = _make_client()
        async with client as c:
            r = await c.get(f"/v1/planning/weekly/{WEEK_ID}")
        app.dependency_overrides.clear()

        links = r.json()["links"]
        assert ".html" in links["print_week_html"]
        assert ".pdf"  in links["print_week_pdf"]
        assert "reoptimize" in links["reoptimize"]
        assert WEEK_ID in links["print_week_html"]

    @pytest.mark.asyncio
    async def test_openapi_schema_includes_planning_route(self):
        """OpenAPI schema must expose the /v1/planning/weekly/{week_id} GET."""
        from apps.zds.api.main import app
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/openapi.json")
        assert r.status_code == 200
        paths = r.json()["paths"]
        assert "/v1/planning/weekly/{week_id}" in paths
        assert "get" in paths["/v1/planning/weekly/{week_id}"]


# ══════════════════════════════════════════════════════════════════════════════
# PlanningService unit tests
# ══════════════════════════════════════════════════════════════════════════════

class TestPlanningServiceUnit:
    """Unit tests for PlanningService against FakePlacementService.

    No DB, no Redis, no FastAPI — tests the computation logic in isolation.
    """

    def _make_service(self, **kwargs):
        from apps.zds.api.services.planning_service import PlanningService
        placement = FakePlacementService(**kwargs)
        return PlanningService(placement=placement), placement

    @pytest.mark.asyncio
    async def test_week_not_found_returns_none(self):
        """When get_week returns None, get_weekly_overview must return None."""
        svc, _ = self._make_service(week=None, nights=[])
        result = await svc.get_weekly_overview("no-such-week")
        assert result is None

    @pytest.mark.asyncio
    async def test_happy_path_returns_response_model(self):
        """Full data path returns a WeeklyPlanningOverviewResponse."""
        svc, _ = self._make_service(
            week=WEEK_DICT,
            nights=NIGHTS_LIST,
            assignments_by_night={
                NIGHT_ID:  ASSIGNMENTS_FRI,
                NIGHT_ID2: ASSIGNMENTS_SAT,
            },
        )
        result = await svc.get_weekly_overview(WEEK_ID)
        assert result is not None
        assert isinstance(result, WeeklyPlanningOverviewResponse)

    @pytest.mark.asyncio
    async def test_coverage_pct_fully_filled(self):
        """Night with all slots filled → coverage_pct == 100.0, gap_count == 0."""
        svc, _ = self._make_service(
            week=WEEK_DICT,
            nights=[NIGHTS_LIST[1]],   # Saturday only
            assignments_by_night={NIGHT_ID2: ASSIGNMENTS_SAT},
        )
        result = await svc.get_weekly_overview(WEEK_ID)
        snapshot = result.nights[0]
        assert snapshot.filled_slots == 2
        assert snapshot.gap_count    == 0
        assert snapshot.coverage_pct == 100.0
        assert snapshot.reoptimize_recommended is False

    @pytest.mark.asyncio
    async def test_coverage_pct_with_gaps(self):
        """Night with one unfilled slot → coverage_pct ~66.7, gap_count == 1."""
        svc, _ = self._make_service(
            week=WEEK_DICT,
            nights=[NIGHTS_LIST[0]],   # Friday only
            assignments_by_night={NIGHT_ID: ASSIGNMENTS_FRI},
        )
        result = await svc.get_weekly_overview(WEEK_ID)
        snap = result.nights[0]
        assert snap.total_slots  == 3
        assert snap.filled_slots == 2
        assert snap.gap_count    == 1
        assert snap.coverage_pct == pytest.approx(66.7, abs=0.1)
        assert snap.reoptimize_recommended is True

    @pytest.mark.asyncio
    async def test_metrics_total_assignments(self):
        """total_assignments sums filled slots across all in-rotation nights."""
        svc, _ = self._make_service(
            week=WEEK_DICT,
            nights=NIGHTS_LIST,
            assignments_by_night={
                NIGHT_ID:  ASSIGNMENTS_FRI,  # 2 filled
                NIGHT_ID2: ASSIGNMENTS_SAT,  # 2 filled
            },
        )
        result = await svc.get_weekly_overview(WEEK_ID)
        assert result.metrics.total_assignments == 4

    @pytest.mark.asyncio
    async def test_metrics_total_gaps(self):
        """total_gaps sums gap_count across all in-rotation nights."""
        svc, _ = self._make_service(
            week=WEEK_DICT,
            nights=NIGHTS_LIST,
            assignments_by_night={
                NIGHT_ID:  ASSIGNMENTS_FRI,  # 1 gap
                NIGHT_ID2: ASSIGNMENTS_SAT,  # 0 gaps
            },
        )
        result = await svc.get_weekly_overview(WEEK_ID)
        assert result.metrics.total_gaps             == 1
        assert result.metrics.nights_with_gaps       == 1
        assert result.metrics.reoptimize_opportunities == 1

    @pytest.mark.asyncio
    async def test_planning_note_generated_for_gap(self):
        """A gap night must generate a 'gap' planning note."""
        svc, _ = self._make_service(
            week=WEEK_DICT,
            nights=[NIGHTS_LIST[0]],
            assignments_by_night={NIGHT_ID: ASSIGNMENTS_FRI},
        )
        result = await svc.get_weekly_overview(WEEK_ID)
        gap_notes = [n for n in result.planning_notes if n.note_kind == "gap"]
        assert len(gap_notes) == 1
        assert gap_notes[0].night_id == NIGHT_ID
        assert "unfilled" in gap_notes[0].note_text

    @pytest.mark.asyncio
    async def test_no_planning_note_when_fully_staffed(self):
        """Fully-staffed nights must produce no gap notes."""
        svc, _ = self._make_service(
            week=WEEK_DICT,
            nights=[NIGHTS_LIST[1]],
            assignments_by_night={NIGHT_ID2: ASSIGNMENTS_SAT},
        )
        result = await svc.get_weekly_overview(WEEK_ID)
        gap_notes = [n for n in result.planning_notes if n.note_kind == "gap"]
        assert gap_notes == []

    @pytest.mark.asyncio
    async def test_links_contain_correct_week_id(self):
        """Links must embed the actual week_id, not a placeholder."""
        svc, _ = self._make_service(week=WEEK_DICT, nights=[])
        result = await svc.get_weekly_overview(WEEK_ID)
        assert WEEK_ID in result.links.print_week_html
        assert WEEK_ID in result.links.print_week_pdf
        assert WEEK_ID in result.links.reoptimize

    @pytest.mark.asyncio
    async def test_week_start_derived_correctly(self):
        """week_start must be exactly 6 days before week_ending."""
        svc, _ = self._make_service(week=WEEK_DICT, nights=[])
        result = await svc.get_weekly_overview(WEEK_ID)
        assert result.week.week_start  == "2026-05-08"
        assert result.week.week_ending == "2026-05-14"

    @pytest.mark.asyncio
    async def test_cache_hit_skips_placement_calls(self):
        """Second call with warm cache must not call get_week again."""
        svc, placement = self._make_service(
            week=WEEK_DICT,
            nights=NIGHTS_LIST,
            assignments_by_night={
                NIGHT_ID:  ASSIGNMENTS_FRI,
                NIGHT_ID2: ASSIGNMENTS_SAT,
            },
        )
        # First call — cold cache.
        await svc.get_weekly_overview(WEEK_ID)
        calls_after_first = placement.get_week_call_count

        # Second call — cache should be warm.
        await svc.get_weekly_overview(WEEK_ID)
        calls_after_second = placement.get_week_call_count

        assert calls_after_first == 1
        assert calls_after_second == 1, (
            "get_week was called again on the second request — cache miss when a hit was expected"
        )

    @pytest.mark.asyncio
    async def test_empty_nights_list(self):
        """A week with no nights produces empty lists and zero metrics."""
        svc, _ = self._make_service(week=WEEK_DICT, nights=[])
        result = await svc.get_weekly_overview(WEEK_ID)
        assert result.nights          == []
        assert result.planning_notes  == []
        assert result.active_overrides == []
        assert result.metrics.total_assignments == 0
        assert result.metrics.total_gaps        == 0
        assert result.metrics.fatigue_index     == 0.0

    @pytest.mark.asyncio
    async def test_zero_slot_night_coverage_is_zero(self):
        """A night with no assignment rows must show coverage_pct == 0, not divide-by-zero."""
        svc, _ = self._make_service(
            week=WEEK_DICT,
            nights=[NIGHTS_LIST[0]],
            assignments_by_night={NIGHT_ID: []},  # empty
        )
        result = await svc.get_weekly_overview(WEEK_ID)
        snap = result.nights[0]
        assert snap.total_slots  == 0
        assert snap.coverage_pct == 0.0

    @pytest.mark.asyncio
    async def test_override_note_generated(self):
        """A night with active overrides must generate an 'override' planning note."""
        fake_override = {
            "id":        "ov-001",
            "slot_key":  "Z1",
            "tm_id":     "tm-001",
            "note":      "Brian pinned this",
            "created_at": "2026-05-08T22:00:00Z",
        }
        svc, _ = self._make_service(
            week=WEEK_DICT,
            nights=[NIGHTS_LIST[0]],
            assignments_by_night={NIGHT_ID: ASSIGNMENTS_FRI},
            overrides_by_night={NIGHT_ID: [fake_override]},
        )
        result = await svc.get_weekly_overview(WEEK_ID)
        ov_notes = [n for n in result.planning_notes if n.note_kind == "override"]
        assert len(ov_notes) == 1
        assert "override" in ov_notes[0].note_text.lower()
        # The override should also appear in active_overrides.
        assert len(result.active_overrides) == 1
        assert result.active_overrides[0].slot_key == "Z1"
