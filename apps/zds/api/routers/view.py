"""View router — Published Schedule Viewer (public, no auth in v1).

Public surface
──────────────
    GET  /v1/view/night/{date}   → ViewNightMeta
    GET  /v1/view/archive        → list[ViewArchiveEntry]
    POST /v1/view/audit          → 204

The viewer resolves a shift date (YYYY-MM-DD) to a published night,
returns editability based on the 90-minute buffer rule, and provides the
archive listing for the date picker.

Edit permissions (enforced client-side; v1 has no server-side auth):
    current shift + future published nights  → is_editable = True
    past published nights                    → is_editable = False

The 90-minute buffer:
    The grave shift ends at 7 AM.  We stay on the same shift date until
    8:30 AM (7:00 + 90 min).  Before 8:30 AM the current shift date is
    yesterday.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..core.dependencies import get_supabase_client

log = logging.getLogger("zds.api.view")

router = APIRouter(prefix="/v1/view", tags=["View"])

_SHIFT_CUTOVER_HOUR   = 8
_SHIFT_CUTOVER_MINUTE = 30


# ── Shift date helpers ────────────────────────────────────────────────────────

def _current_shift_date() -> date:
    """Return today's shift date, respecting the 90-minute post-shift buffer."""
    now     = datetime.now()
    cutover = now.replace(hour=_SHIFT_CUTOVER_HOUR, minute=_SHIFT_CUTOVER_MINUTE,
                          second=0, microsecond=0)
    if now < cutover:
        return (now - timedelta(days=1)).date()
    return now.date()


def _is_editable(shift_date: date) -> bool:
    """Editable if the shift date is the current shift or in the future."""
    return shift_date >= _current_shift_date()


# ── Pydantic models ───────────────────────────────────────────────────────────

class ViewNightMeta(BaseModel):
    night_id:    str
    shift_date:  str            # "YYYY-MM-DD"
    day_name:    str
    week_id:     str
    week_label:  Optional[str]
    week_status: str            # "published" | "archived"
    is_editable: bool


class ViewArchiveEntry(BaseModel):
    night_id:    str
    shift_date:  str
    day_name:    str
    week_id:     str
    week_label:  Optional[str]
    week_status: str
    is_editable: bool


class ViewAuditPayload(BaseModel):
    night_id:     str
    shift_date:   str
    action_type:  str            # "assign_tm" | "clear_tm" | "patch_tasks"
    slot_id:      Optional[str] = None
    slot_key:     Optional[str] = None
    value_before: Optional[str] = None
    value_after:  Optional[str] = None
    editor_label: str = "supervisor"


# ── Error helpers ─────────────────────────────────────────────────────────────

def _bad_date(date_str: str) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"error": "invalid_date", "detail": f"Not a valid ISO date: {date_str!r}"},
    )

def _not_found(date_str: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": "not_found",
                "detail": f"No published schedule found for {date_str}"},
    )

def _unavailable(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"error": "unavailable", "detail": str(exc)},
    )


# ═════════════════════════════════════════════════════════════════════════════
# GET /v1/view/night/{date}
# ═════════════════════════════════════════════════════════════════════════════

@router.get(
    "/night/{date_str}",
    response_model=ViewNightMeta,
    summary="Resolve a shift date to its published night",
    responses={
        200: {"description": "Published night meta for this shift date"},
        400: {"description": "Invalid date format"},
        404: {"description": "No published night for this date"},
        503: {"description": "Database unavailable"},
    },
)
async def get_view_night(date_str: str):
    """Return published night metadata for a given YYYY-MM-DD shift date.

    Looks for a ``nights`` row whose ``night_date`` matches and whose parent
    week has status ``published`` or ``archived``.  Returns 404 if no such
    night exists (e.g. date is in a draft week).
    """
    try:
        shift_date = date.fromisoformat(date_str)
    except ValueError:
        raise _bad_date(date_str)

    supabase = get_supabase_client()
    try:
        res = (
            supabase.table("nights")
            .select("id, night_date, day_name, week_id, weeks!inner(id, label, status)")
            .eq("night_date", date_str)
            .in_("weeks.status", ["published", "archived"])
            .execute()
        )
    except Exception as exc:
        log.exception("get_view_night(%s) DB query failed", date_str)
        raise _unavailable(exc)

    rows = res.data or []
    row  = next(
        (r for r in rows
         if r.get("weeks") and r["weeks"].get("status") in ("published", "archived")),
        None,
    )

    if not row:
        raise _not_found(date_str)

    week = row["weeks"]
    return ViewNightMeta(
        night_id    = row["id"],
        shift_date  = str(row["night_date"]),
        day_name    = row["day_name"],
        week_id     = week["id"],
        week_label  = week.get("label"),
        week_status = week["status"],
        is_editable = _is_editable(shift_date),
    )


# ═════════════════════════════════════════════════════════════════════════════
# GET /v1/view/archive
# ═════════════════════════════════════════════════════════════════════════════

@router.get(
    "/archive",
    response_model=list[ViewArchiveEntry],
    summary="All published nights for the archive date picker",
    responses={
        200: {"description": "Published nights sorted newest-first"},
        503: {"description": "Database unavailable"},
    },
)
async def get_view_archive():
    """Return all nights in published/archived weeks, newest-first.

    Capped at 120 rows (~4 months of nightly data).  The frontend uses
    this to populate the calendar date picker and the recent-shifts list.
    """
    supabase = get_supabase_client()
    try:
        res = (
            supabase.table("nights")
            .select("id, night_date, day_name, week_id, weeks(id, label, status)")
            .order("night_date", desc=True)
            .limit(120)
            .execute()
        )
    except Exception as exc:
        log.exception("get_view_archive DB query failed")
        raise _unavailable(exc)

    current = _current_shift_date()
    entries: list[ViewArchiveEntry] = []

    for r in (res.data or []):
        week = r.get("weeks") or {}
        if week.get("status") not in ("published", "archived"):
            continue
        d = date.fromisoformat(str(r["night_date"]))
        entries.append(ViewArchiveEntry(
            night_id    = r["id"],
            shift_date  = str(r["night_date"]),
            day_name    = r["day_name"],
            week_id     = week.get("id", ""),
            week_label  = week.get("label"),
            week_status = week["status"],
            is_editable = d >= current,
        ))

    return entries


# ═════════════════════════════════════════════════════════════════════════════
# POST /v1/view/audit
# ═════════════════════════════════════════════════════════════════════════════

@router.post(
    "/audit",
    status_code=204,
    summary="Log a viewer edit for audit trail",
    responses={
        204: {"description": "Logged (no body)"},
        503: {"description": "Log insert failed"},
    },
)
async def post_view_audit(payload: ViewAuditPayload, request: Request):
    """Append one row to ``view_edit_log``.

    Called by the viewer frontend after every successful PATCH so every edit
    to a published schedule is auditable.  Failures are non-fatal — the
    caller's PATCH already succeeded, so a 503 here is logged but swallowed.
    """
    ip = request.client.host if request.client else None
    supabase = get_supabase_client()
    try:
        supabase.table("view_edit_log").insert({
            "night_id":     payload.night_id,
            "shift_date":   payload.shift_date,
            "action_type":  payload.action_type,
            "slot_id":      payload.slot_id,
            "slot_key":     payload.slot_key,
            "value_before": payload.value_before,
            "value_after":  payload.value_after,
            "editor_label": payload.editor_label,
            "ip_address":   ip,
        }).execute()
    except Exception as exc:
        log.warning("view_edit_log insert failed: %s", exc)
        # Non-fatal — don't 503 the caller
