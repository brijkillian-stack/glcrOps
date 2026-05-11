"""Route smoke test for POST /v1/planning/simulate.

Stubs the supabase + redis dependencies and patches SimulationService
so the request goes through the FastAPI surface without ever touching
a real database. Verifies request validation, the response shape, and
that scope errors come back as 400s.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from apps.zds.api.core import dependencies as deps  # noqa: E402
from apps.zds.api.routers import planning as planning_router  # noqa: E402

# Import the FastAPI app — `lifespan` would call get_supabase_client() on
# startup and crash without env vars, so we override the deps before any
# request fires (TestClient triggers the lifespan on first context-enter).


@pytest.fixture
def client(monkeypatch):
    # Skip the supabase / redis startup checks: the deps are overridden
    # below, but the lifespan in main.py still calls get_supabase_client
    # directly. Patch the module-level singleton resolvers to no-ops.
    monkeypatch.setattr(deps, "_supabase_singleton", lambda: object())
    monkeypatch.setattr(deps, "_redis_singleton", lambda: None)

    from apps.zds.api.main import app  # local import → after monkeypatch

    app.dependency_overrides[deps.get_supabase_client] = lambda: object()
    app.dependency_overrides[deps.get_redis_client] = lambda: None

    # Replace SimulationService with a stub whose `simulate` returns a
    # predictable payload. The router does not care what the service does
    # internally — it just shapes the result through SimulateResponse.
    class _StubService:
        def __init__(self, *a, **kw):
            pass

        async def simulate(self, **kw):
            return _stub_payload(kw)

    monkeypatch.setattr(planning_router, "SimulationService", _StubService)

    with TestClient(app) as tc:
        yield tc

    app.dependency_overrides.clear()


def _stub_payload(kwargs):
    return {
        "scope": "week" if kwargs.get("week_id") else "night",
        "target_id": kwargs.get("week_id") or kwargs.get("night_id"),
        "applied_changes": len(kwargs.get("staffing_changes") or []),
        "elapsed_ms": 1,
        "baseline": {
            "coverage": {
                "total_slots": 10, "filled_slots": 9, "unfilled_slots": 1,
                "fill_rate": 0.9, "by_type": {}, "by_night": {},
            },
            "overlap": None,
            "fatigue": None,
            "violations": [],
        },
        "scenario": {
            "coverage": {
                "total_slots": 10, "filled_slots": 8, "unfilled_slots": 2,
                "fill_rate": 0.8, "by_type": {}, "by_night": {},
            },
            "overlap": None,
            "fatigue": None,
            "violations": [],
        },
        "delta": {
            "filled_delta": -1, "unfilled_delta": 1,
            "fill_rate_delta": -0.1, "violations_delta": 0,
        },
    }


def test_simulate_happy_path(client):
    response = client.post(
        "/v1/planning/simulate",
        json={
            "week_id": "wk-1",
            "staffing_changes": [
                {"kind": "mark_unavailable", "tm_id": "tm-a"},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "week"
    assert body["target_id"] == "wk-1"
    assert body["applied_changes"] == 1
    assert body["delta"]["filled_delta"] == -1


def test_simulate_rejects_no_scope(client):
    response = client.post("/v1/planning/simulate", json={})
    assert response.status_code == 422  # pydantic validator


def test_simulate_rejects_both_scopes(client):
    response = client.post(
        "/v1/planning/simulate",
        json={"week_id": "wk-1", "night_id": "n-mon"},
    )
    assert response.status_code == 422


def test_simulate_invalid_change_kind(client):
    response = client.post(
        "/v1/planning/simulate",
        json={
            "week_id": "wk-1",
            "staffing_changes": [{"kind": "delete_universe"}],
        },
    )
    # Literal validator on StaffingChange.kind catches this.
    assert response.status_code == 422


def test_simulate_returns_400_on_service_error(client, monkeypatch):
    from apps.zds.api.services.simulation_service import SimulationError

    class _RaisingService:
        def __init__(self, *a, **kw):
            pass

        async def simulate(self, **kw):
            raise SimulationError("week_id 'missing' not found")

    monkeypatch.setattr(planning_router, "SimulationService", _RaisingService)

    response = client.post(
        "/v1/planning/simulate",
        json={"week_id": "missing"},
    )
    assert response.status_code == 400
    assert "missing" in response.json()["detail"]


def test_kinds_endpoint(client):
    response = client.get("/v1/planning/simulate/kinds")
    assert response.status_code == 200
    body = response.json()
    assert "mark_unavailable" in body["staffing_changes"]
    assert "min_coverage" in body["constraints"]
