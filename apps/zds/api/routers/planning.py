"""Planning router — weekly pre-shift planning overview (GLC-12).

Public surface
──────────────
    GET /v1/planning/weekly/{week_id}
            → WeeklyPlanningOverviewResponse (application/json)

The response aggregates:
  • Week metadata (id, dates, status)
  • Night-by-night coverage snapshots (filled/unfilled slots, overrides)
  • Aggregated metrics (fatigue index, gaps, multi-area overlaps)
  • Synthetic planning notes generated from coverage analysis
  • Active slot_assignment overrides across all nights
  • Quick-action links (print HTML/PDF, reoptimize)

Cache strategy
──────────────
PlanningService caches the computed overview for 15 s keyed by week_id.
This is intentionally short — supervisors edit placements actively in the
hour before shift; stale coverage counts are worse than extra DB round-trips.

The endpoint itself adds ``Cache-Control: private, max-age=15`` so the
browser won't replay the response beyond that window.

Error envelopes
───────────────
    404 → {"error": "not_found", "detail": "..."}
    503 → {"error": "planning_unavailable", "detail": "..."}
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from ..core.dependencies import get_planning_service, get_placement_service
from ..models.planning import WeeklyPlanningOverviewResponse
from ..models.tm import TMRow
from ..models.week import WeekRow
from ..services.placement_service import PlacementService
from ..services.planning_service import PlanningService

log = logging.getLogger("zds.api.planning")

router = APIRouter(prefix="/v1/planning", tags=["Planning"])

_CACHE_CONTROL = "private, max-age=15"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _not_found(detail: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": "not_found", "detail": detail},
    )


def _planning_unavailable(detail: str) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"error": "planning_unavailable", "detail": detail},
    )


# ═════════════════════════════════════════════════════════════════════════════
# Endpoints
# ═════════════════════════════════════════════════════════════════════════════

# ── Settings ──────────────────────────────────────────────────────────────────

_DEFAULT_TAB_CONFIG = [
    {"id": "zone",  "label": "Zone",  "cats": ["zone", "rr", "aux"]},
    {"id": "sweep", "label": "Sweep", "cats": ["sweep"]},
    {"id": "am",    "label": "AM",    "cats": ["overlap_am"]},
    {"id": "pm",    "label": "PM",    "cats": ["overlap_pm"]},
]


@router.get(
    "/settings/tab_config",
    summary="Get task picker tab configuration",
)
async def get_tab_config(
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Return the ordered list of task picker tabs and which categories each tab shows.
    Falls back to the default config if the DB row is missing.
    """
    try:
        res = placement_service.supabase.table("zds_settings") \
            .select("value") \
            .eq("key", "task_tab_config") \
            .single() \
            .execute()
        return (res.data or {}).get("value", _DEFAULT_TAB_CONFIG)
    except Exception:
        return _DEFAULT_TAB_CONFIG


@router.patch(
    "/settings/tab_config",
    summary="Update task picker tab configuration",
)
async def patch_tab_config(
    body: dict,
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Upsert the task_tab_config setting.  Body: { tabs: [...] }"""
    tabs = body.get("tabs")
    if not isinstance(tabs, list):
        raise HTTPException(status_code=400, detail={"error": "invalid_body", "detail": "Expected { tabs: [...] }"})

    VALID_CATS = {"zone", "rr", "aux", "sweep", "overlap_am", "overlap_pm"}
    for tab in tabs:
        if not isinstance(tab, dict) or not tab.get("id") or not tab.get("label"):
            raise HTTPException(status_code=400, detail={"error": "invalid_tab", "detail": "Each tab needs id and label"})
        for cat in tab.get("cats", []):
            if cat not in VALID_CATS:
                raise HTTPException(
                    status_code=400,
                    detail={"error": "invalid_category", "detail": f"Unknown category: {cat!r}"},
                )

    try:
        placement_service.supabase.table("zds_settings").upsert(
            {"key": "task_tab_config", "value": tabs},
            on_conflict="key",
        ).execute()
    except Exception as exc:
        log.exception("patch_tab_config failed")
        raise HTTPException(status_code=503, detail={"error": "db_error", "detail": str(exc)})

    return {"updated": True, "tabs": tabs}


_DEFAULT_BREAK_SCHEDULE = {
    "wave_labels": {"1": "First Break", "2": "Main Break", "3": "Last Break"},
    "times": {
        "1": {"1": ["00:45", "01:00", 15], "2": ["02:30", "03:00", 30], "3": ["05:00", "05:15", 15]},
        "2": {"1": ["01:00", "01:15", 15], "2": ["03:00", "03:30", 30], "3": ["05:00", "05:15", 15]},
        "3": {"1": ["01:15", "01:30", 15], "2": ["03:30", "04:00", 30], "3": ["05:15", "05:30", 15]},
    },
}


@router.get(
    "/settings/break_schedule",
    summary="Get break schedule configuration",
)
async def get_break_schedule(
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Return the 3×3 break schedule (group × wave → start/end/duration).
    Falls back to hardcoded defaults if the DB row is missing.
    """
    try:
        res = placement_service.supabase.table("zds_settings") \
            .select("value") \
            .eq("key", "break_schedule") \
            .single() \
            .execute()
        return (res.data or {}).get("value", _DEFAULT_BREAK_SCHEDULE)
    except Exception:
        return _DEFAULT_BREAK_SCHEDULE


@router.patch(
    "/settings/break_schedule",
    summary="Update break schedule configuration",
)
async def patch_break_schedule(
    body: dict,
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Upsert the break_schedule setting.
    Body: { wave_labels: {1:..., 2:..., 3:...}, times: {grp: {wave: [start, end, dur]}} }
    """
    import re as _re
    _TIME_RE = _re.compile(r"^\d{2}:\d{2}$")

    wave_labels = body.get("wave_labels")
    times       = body.get("times")

    if not isinstance(wave_labels, dict) or not isinstance(times, dict):
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_body", "detail": "Expected { wave_labels: {...}, times: {...} }"},
        )

    for grp, waves in times.items():
        if not isinstance(waves, dict):
            raise HTTPException(status_code=400, detail={"error": "invalid_times"})
        for wave, slot in waves.items():
            if not isinstance(slot, list) or len(slot) != 3:
                raise HTTPException(status_code=400, detail={"error": "invalid_slot", "detail": f"group {grp} wave {wave}"})
            start, end, dur = slot
            if not _TIME_RE.match(str(start)) or not _TIME_RE.match(str(end)):
                raise HTTPException(
                    status_code=400,
                    detail={"error": "invalid_time_format", "detail": f"Times must be HH:MM, got {start!r}/{end!r}"},
                )
            if not isinstance(dur, int) or dur <= 0:
                raise HTTPException(status_code=400, detail={"error": "invalid_duration", "detail": f"duration must be a positive int, got {dur!r}"})

    value = {"wave_labels": wave_labels, "times": times}
    try:
        placement_service.supabase.table("zds_settings").upsert(
            {"key": "break_schedule", "value": value},
            on_conflict="key",
        ).execute()
    except Exception as exc:
        log.exception("patch_break_schedule failed")
        raise HTTPException(status_code=503, detail={"error": "db_error", "detail": str(exc)})

    return {"updated": True, **value}


# ── Zone Tasks ─────────────────────────────────────────────────────────────────

@router.get(
    "/tasks",
    summary="Zone task catalogue",
    responses={200: {"description": "Active zone tasks, optionally filtered by slot type / key"}},
)
async def list_zone_tasks(
    slot_type: str | None = Query(None, description="zone | restroom | auxiliary"),
    include_inactive: bool = Query(False, description="Include archived/inactive tasks"),
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Return active zone_tasks, optionally filtered for a specific slot.

    Used by the Daily Planner task picker sheet.  Pass slot_type + slot_key
    to get only the tasks relevant to that slot (plus AM/PM overlap tasks).
    Omit both to get the full catalogue.  Pass include_inactive=true to
    return all tasks regardless of active status (for the Control Panel).
    """
    try:
        return await placement_service.list_zone_tasks(
            slot_type=slot_type,
            include_inactive=include_inactive,
        )
    except Exception as exc:
        log.exception("list_zone_tasks raised")
        raise HTTPException(status_code=503, detail={"error": "unavailable", "detail": str(exc)})


@router.post(
    "/tasks",
    summary="Create a zone task",
    status_code=201,
)
async def create_zone_task(
    body: dict,
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Create a new zone_tasks row.  Body fields: name (required), category,
    code, description, display_order, target_codes, labor_category,
    is_compliance_required, frequency, shift_phase, estimated_duration_min,
    days_active, notes.
    """
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail={"error": "missing_name", "detail": "name is required"})

    VALID_CATS       = {"zone", "rr", "aux", "sweep", "overlap_am", "overlap_pm"}
    VALID_LABOR      = {"cleaning", "inspection", "coverage", "compliance", "security", "other", None}
    VALID_FREQUENCY  = {"once_per_shift", "ongoing", "as_needed"}
    VALID_PHASE      = {"all", "opening", "mid_shift", "closing"}

    category = body.get("category", "zone")
    if category not in VALID_CATS:
        raise HTTPException(status_code=400, detail={"error": "invalid_category"})

    row = {
        "name":                    name,
        "category":                category,
        "code":                    body.get("code") or None,
        "description":             body.get("description") or None,
        "display_order":           body.get("display_order") if body.get("display_order") is not None else 100,
        "target_codes":            body.get("target_codes") or [],
        "active":                  True,
        "labor_category":          body.get("labor_category") or None,
        "is_compliance_required":  bool(body.get("is_compliance_required", False)),
        "frequency":               body.get("frequency") or "once_per_shift",
        "shift_phase":             body.get("shift_phase") or "all",
        "estimated_duration_min":  body.get("estimated_duration_min") or None,
        "days_active":             body.get("days_active") or ["fri","sat","sun","mon","tue","wed","thu"],
        "notes":                   body.get("notes") or None,
    }

    try:
        res = placement_service.supabase.table("zone_tasks").insert(row).execute()
        created = (res.data or [{}])[0]
    except Exception as exc:
        log.exception("create_zone_task failed")
        raise HTTPException(status_code=503, detail={"error": "db_error", "detail": str(exc)})

    return created


@router.patch(
    "/tasks/{task_id}",
    summary="Update a zone task",
)
async def patch_zone_task(
    task_id: str,
    body: dict,
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Partial update for a zone_tasks row.  Any combination of:
    name, category, code, description, display_order, target_codes, active.
    """
    VALID_CATS = {"zone", "rr", "aux", "sweep", "overlap_am", "overlap_pm"}
    allowed = {
        "name", "category", "code", "description", "display_order", "target_codes", "active",
        "labor_category", "is_compliance_required", "frequency", "shift_phase",
        "estimated_duration_min", "days_active", "notes",
    }
    patch = {k: v for k, v in body.items() if k in allowed}

    if not patch:
        raise HTTPException(status_code=400, detail={"error": "empty_patch", "detail": "No patchable fields provided"})

    if "category" in patch and patch["category"] not in VALID_CATS:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_category", "detail": f"category must be one of {sorted(VALID_CATS)}"},
        )

    try:
        res = placement_service.supabase.table("zone_tasks").update(patch).eq("id", task_id).execute()
        rows = res.data or []
    except Exception as exc:
        log.exception("patch_zone_task(%s) failed", task_id)
        raise HTTPException(status_code=503, detail={"error": "db_error", "detail": str(exc)})

    if not rows:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": f"Task {task_id!r} not found"})

    return rows[0]


@router.delete(
    "/tasks/{task_id}",
    summary="Soft-delete (deactivate) a zone task",
)
async def delete_zone_task(
    task_id: str,
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Soft-delete by setting active=False and archived_at=now().
    Tasks are never hard-deleted so historical assignments remain readable.
    """
    import datetime
    patch = {"active": False, "archived_at": datetime.datetime.utcnow().isoformat()}
    try:
        res = placement_service.supabase.table("zone_tasks").update(patch).eq("id", task_id).execute()
        rows = res.data or []
    except Exception as exc:
        log.exception("delete_zone_task(%s) failed", task_id)
        raise HTTPException(status_code=503, detail={"error": "db_error", "detail": str(exc)})

    if not rows:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": f"Task {task_id!r} not found"})

    return {"task_id": task_id, "deleted": True}


@router.post(
    "/tasks/reorder",
    summary="Bulk-update display_order for a list of tasks",
)
async def reorder_zone_tasks(
    body: dict,
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Accept an ordered list of task IDs and assign display_order = index * 10.

    Body: { ids: ["uuid1", "uuid2", ...] }
    The caller sends the full ordered list; we assign display_order in sequence.
    """
    ids = body.get("ids")
    if not isinstance(ids, list) or not ids:
        raise HTTPException(status_code=400, detail={"error": "invalid_body", "detail": "Expected { ids: [...] }"})

    try:
        for idx, task_id in enumerate(ids):
            placement_service.supabase.table("zone_tasks") \
                .update({"display_order": idx * 10}) \
                .eq("id", task_id) \
                .execute()
    except Exception as exc:
        log.exception("reorder_zone_tasks failed")
        raise HTTPException(status_code=503, detail={"error": "db_error", "detail": str(exc)})

    return {"reordered": len(ids)}


@router.get(
    "/tms",
    response_model=list[TMRow],
    summary="Active TM roster",
    responses={200: {"description": "All active TMs ordered by display name"}},
)
async def list_tms(
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Return all active TMs from the entities table.

    Used by the Daily Planner TM picker sheet — cached for 10 min in
    PlacementService (TM_TTL = 600 s).  Not paginated — the roster is
    small enough to load in full and filter client-side.
    """
    try:
        return await placement_service.list_active_tms()
    except Exception as exc:
        log.exception("list_active_tms raised")
        raise HTTPException(status_code=503, detail={"error": "unavailable", "detail": str(exc)})


@router.get(
    "/weeks",
    response_model=list[WeekRow],
    summary="List recent weeks",
    responses={200: {"description": "Most recent weeks ordered by week_ending desc"}},
)
async def list_weeks(
    limit: int = 12,
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Return the most recent *limit* weeks from Supabase, ordered newest first.

    Used by the Launchpad page to populate the Recent Weeks list.
    Not cached — list view needs freshness so newly-created weeks appear immediately.
    """
    try:
        weeks = await placement_service.list_recent_weeks(limit=limit)
        return weeks
    except Exception as exc:
        log.exception("list_recent_weeks raised")
        raise HTTPException(status_code=503, detail={"error": "unavailable", "detail": str(exc)})


@router.patch(
    "/weeks/{week_id}/status",
    summary="Publish or unpublish a week",
    responses={
        200: {"description": "Status updated"},
        400: {"description": "Invalid status value"},
        404: {"description": "Week not found"},
        503: {"description": "Update failed"},
    },
)
async def patch_week_status(
    week_id: str,
    body: dict,
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Set a week's status to 'published' or 'draft'.

    Used by the Publish/Unpublish button in the Week Overview and
    Daily Planner.  Also invalidates the planning cache so the
    next overview fetch reflects the new status.
    """
    new_status = (body.get("status") or "").strip().lower()
    if new_status not in ("published", "draft", "archived"):
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_status",
                    "detail": f"status must be 'published', 'draft', or 'archived'; got {new_status!r}"},
        )

    try:
        week = await placement_service.get_week(week_id)
    except Exception as exc:
        log.exception("get_week(%s) raised in patch_week_status", week_id)
        raise HTTPException(status_code=503, detail={"error": "unavailable", "detail": str(exc)})

    if week is None:
        raise _not_found(f"Week not found: {week_id!r}")

    # Write directly via the supabase client — PlacementService exposes it.
    try:
        placement_service.supabase.table("weeks").update(
            {"status": new_status}
        ).eq("id", week_id).execute()
    except Exception as exc:
        log.exception("weeks status update failed for %s", week_id)
        raise HTTPException(status_code=503, detail={"error": "unavailable", "detail": str(exc)})

    # Bust the planning cache so the next overview fetch is fresh.
    try:
        await placement_service.invalidate_week(week_id)
    except Exception:
        pass  # Non-fatal

    return {"week_id": week_id, "status": new_status, "updated": True}


@router.get(
    "/weekly/{week_id}",
    response_model=WeeklyPlanningOverviewResponse,
    summary="Weekly planning overview",
    responses={
        200: {"description": "Full planning overview for the week"},
        404: {"description": "Week not found"},
        503: {"description": "Planning data temporarily unavailable"},
    },
)
async def get_weekly_planning_overview(
    week_id: str,
    planning_service: PlanningService = Depends(get_planning_service),
):
    """Return a comprehensive pre-shift planning overview for the week.

    Aggregates coverage health, gap counts, active overrides, multi-area
    overlaps, and quick-action links into a single response.  Suitable for
    powering a planning dashboard without client-side data stitching.

    The response is cached for 15 seconds in PlanningService.  Callers that
    need guaranteed fresh data should call the invalidation endpoint first
    (or simply wait for the TTL to expire).

    Night snapshots include ``reoptimize_recommended=true`` for any night
    with unfilled slots, making it easy for clients to surface actionable
    gaps.
    """
    try:
        overview = await planning_service.get_weekly_overview(week_id)
    except Exception as exc:
        log.exception("PlanningService.get_weekly_overview(%s) raised", week_id)
        raise _planning_unavailable(str(exc))

    if overview is None:
        raise _not_found(f"Week not found: {week_id!r}")

    from fastapi.responses import JSONResponse

    return JSONResponse(
        content=overview.model_dump(),
        headers={"Cache-Control": _CACHE_CONTROL},
    )


# ── Schedule upload ───────────────────────────────────────────────────────────

@router.post(
    "/weeks/upload",
    summary="Upload an ADP/Kronos schedule xlsx and link it to the matching week",
    status_code=200,
)
async def upload_schedule(
    payload: dict = Body(...),
    week_id: str | None = Query(None, description="Pin upload to a specific week ID (skips filename parsing)"),
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Accept a .xlsx schedule upload as base64-encoded JSON body.

    Body shape: { "filename": "...", "data": "<base64>" }

    If week_id is provided the file is always linked to that week (used for
    re-uploads from the Week Overview).  Otherwise the week is matched by
    parsing the week_ending date from the filename, or created if missing.

    Using JSON/base64 instead of multipart avoids the python-multipart
    dependency check that FastAPI performs at route registration time.
    """
    import base64
    import re
    from shared import storage as _storage

    filename = payload.get("filename") or "schedule.xlsx"
    raw_b64  = payload.get("data") or ""
    try:
        data = base64.b64decode(raw_b64)
    except Exception:
        raise HTTPException(status_code=400, detail={"error": "bad_payload", "detail": "data must be valid base64"})

    # Upload to Supabase Storage
    try:
        _storage.upload_schedule(filename, data)
    except Exception as exc:
        log.exception("Storage upload failed for %s", filename)
        raise HTTPException(status_code=503, detail={"error": "upload_failed", "detail": str(exc)})

    # ── Fast path: week_id explicitly provided (re-upload from Week Overview) ──
    if week_id:
        try:
            placement_service.supabase.table("weeks") \
                .update({"schedule_path": filename}) \
                .eq("id", week_id) \
                .execute()
        except Exception as exc:
            log.exception("schedule_path update failed for week %s", week_id)
            raise HTTPException(status_code=503, detail={"error": "db_error", "detail": str(exc)})
        try:
            await placement_service.invalidate_week(week_id)
        except Exception:
            pass
        return {"uploaded": True, "filename": filename, "week_id": week_id, "week_ending": None}

    # ── Slow path: parse week_ending from filename ────────────────────────────
    # Matches patterns like "5-28-26", "05-28-2026", "2026-05-28"
    week_ending: str | None = None
    # ISO format YYYY-MM-DD
    m = re.search(r"(20\d\d)-(\d{2})-(\d{2})", filename)
    if m:
        week_ending = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    else:
        # Short US format M-D-YY or MM-DD-YY
        m2 = re.search(r"(\d{1,2})-(\d{1,2})-(\d{2,4})", filename)
        if m2:
            month, day, year = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
            if year < 100:
                year += 2000
            week_ending = f"{year:04d}-{month:02d}-{day:02d}"

    if not week_ending:
        # File uploaded successfully but no week could be matched — return info only
        return {"uploaded": True, "filename": filename, "week_id": None, "week_ending": None,
                "message": "File uploaded but could not parse week_ending from filename."}

    # Find or create the week row
    try:
        res = placement_service.supabase.table("weeks") \
            .select("id, schedule_path") \
            .eq("week_ending", week_ending) \
            .execute()
        rows = res.data or []
    except Exception as exc:
        log.exception("weeks lookup failed for %s", week_ending)
        raise HTTPException(status_code=503, detail={"error": "db_error", "detail": str(exc)})

    if rows:
        resolved_week_id = rows[0]["id"]
        placement_service.supabase.table("weeks") \
            .update({"schedule_path": filename}) \
            .eq("id", resolved_week_id) \
            .execute()
    else:
        # Create the week
        import datetime
        we = datetime.date.fromisoformat(week_ending)
        new_row = placement_service.supabase.table("weeks").insert({
            "week_ending":    week_ending,
            "label":          f"Week ending {week_ending}",
            "status":         "draft",
            "schedule_path":  filename,
        }).execute()
        resolved_week_id = (new_row.data or [{}])[0].get("id")

    # Bust cache
    try:
        await placement_service.invalidate_week(resolved_week_id)
    except Exception:
        pass

    return {"uploaded": True, "filename": filename, "week_id": resolved_week_id, "week_ending": week_ending}


# ── Delete schedule link ──────────────────────────────────────────────────────

@router.delete(
    "/weeks/{week_id}/schedule",
    summary="Unlink (and optionally delete from Storage) the schedule for a week",
)
async def delete_week_schedule(
    week_id: str,
    remove_from_storage: bool = False,
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Clear schedule_path on the week row. Optionally remove from Supabase Storage."""
    try:
        # Get current schedule_path first
        res = placement_service.supabase.table("weeks") \
            .select("schedule_path") \
            .eq("id", week_id) \
            .single() \
            .execute()
        current_path = (res.data or {}).get("schedule_path")
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"error": "db_error", "detail": str(exc)})

    if remove_from_storage and current_path:
        try:
            from shared import storage as _storage
            _storage.delete_schedule(current_path)
        except Exception as exc:
            log.warning("Storage delete failed for %s: %s", current_path, exc)

    try:
        placement_service.supabase.table("weeks") \
            .update({"schedule_path": None}) \
            .eq("id", week_id) \
            .execute()
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"error": "db_error", "detail": str(exc)})

    try:
        await placement_service.invalidate_week(week_id)
    except Exception:
        pass

    return {"week_id": week_id, "schedule_path": None, "removed_from_storage": remove_from_storage and bool(current_path)}


# ── Delete week ───────────────────────────────────────────────────────────────

@router.delete(
    "/weeks/{week_id}",
    summary="Permanently delete a week and all associated data",
)
async def delete_week(
    week_id: str,
    confirm: str = "",
    placement_service: PlacementService = Depends(get_placement_service),
):
    """Hard-delete a week row. Cascades to nights, zone_assignments, overlaps, etc.
    Requires confirm='DELETE' query param to prevent accidents.
    """
    if confirm != "DELETE":
        raise HTTPException(
            status_code=400,
            detail={"error": "confirmation_required",
                    "detail": "Pass ?confirm=DELETE to permanently delete this week."},
        )

    try:
        placement_service.supabase.table("weeks").delete().eq("id", week_id).execute()
    except Exception as exc:
        log.exception("delete_week(%s) failed", week_id)
        raise HTTPException(status_code=503, detail={"error": "db_error", "detail": str(exc)})

    try:
        await placement_service.invalidate_week(week_id)
    except Exception:
        pass

    return {"week_id": week_id, "deleted": True}
