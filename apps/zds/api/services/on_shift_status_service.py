"""Live On-Shift Status — read + write service for the Shift Dash.

Read side (`get_status`) reconciles three sources into a single
snapshot:

  * `zone_assignments` — primary + any secondary zone responsibilities
  * `overlap_assignments` — PM/AM overlap shifts
  * `call_offs` — drives the `warn` heat tier on filled slots

Write side (`patch_assignment`) targets one row at a time. Supervisors
edit live by dragging a TM onto a new slot — that's a single PATCH;
the heatmap re-renders from a fresh GET. Redis keys for the affected
night are invalidated on every write so cached GETs don't stale.
"""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Optional
from zoneinfo import ZoneInfo

from supabase import Client

from ..models.shift_status import (
    AssignmentPatchResponse,
    AssignmentReason,
    CoverageHeatmapCell,
    CoverageStats,
    HeatLevel,
    MultiAreaAssignment,
    MultiAreaAssignmentPatch,
    OnShiftStatusResponse,
    TmCoverage,
)
from .cache_service import CacheService
from .fatigue_service import FatigueService

log = logging.getLogger(__name__)

_ET = ZoneInfo("America/Detroit")

# Mirrors apps/zds/state stat conventions: a stretched TM is one whose
# fatigue index is at or above this score. Tuned to match the engine's
# soft-penalty knee in scorecard.fatigue_penalty (fi/8 weighting).
FATIGUE_STRETCHED_THRESHOLD = 8.0


class OnShiftStatusService:
    """Read + write for `/v1/shift/on-shift-status`."""

    STATUS_TTL = 15  # seconds — short enough that PATCH invalidation is rarely visible
    _ALLOWED_TABLES = {"zone_assignments", "overlap_assignments"}

    def __init__(self, supabase: Client, cache: Optional[CacheService] = None):
        self.supabase = supabase
        self.cache = cache or CacheService(None)
        self.fatigue = FatigueService(supabase)

    # ── Read ──────────────────────────────────────────────────────

    def _status_cache_key(self, night_id: str) -> str:
        return f"shift:on-shift-status:{night_id}"

    async def get_status(self, night_id: Optional[str] = None) -> OnShiftStatusResponse:
        """Return the live snapshot.

        If `night_id` is None, resolve tonight via shift-start-anchored
        Eastern Time (same convention as apps/shift/state.py — mid-shift
        before 7am pulls last night's deployment).
        """
        resolved_night = night_id or self._resolve_tonight_night_id()
        if not resolved_night:
            raise LookupError("No active night found for the current shift.")

        cache_key = self._status_cache_key(resolved_night)
        cached = await self.cache.get(cache_key)
        if cached is not None:
            try:
                return OnShiftStatusResponse.model_validate(cached)
            except Exception:
                # Stale shape (post-deploy schema change). Fall through and rebuild.
                pass

        night = self._fetch_night(resolved_night)
        zone_rows = self._fetch_zone_assignments(resolved_night)
        overlap_rows = self._fetch_overlap_assignments(resolved_night)
        called_off = self._fetch_called_off_ids(night.get("night_date") or "")

        # Compute fatigue per TM occupied tonight.
        tm_ids = sorted({r["tm_id"] for r in zone_rows + overlap_rows if r.get("tm_id")})
        anchor_iso = night.get("night_date") or _dt.date.today().isoformat()
        anchor_d = _parse_iso_date(anchor_iso) or _dt.date.today()
        fatigue_scores, fatigue_window = self.fatigue.compute(tm_ids, anchor_d)

        # Build per-TM coverage.
        tm_coverage = self._build_tm_coverage(
            zone_rows=zone_rows,
            overlap_rows=overlap_rows,
            fatigue_scores=fatigue_scores,
            fatigue_window=fatigue_window,
            called_off_ids=called_off,
        )

        # Build heatmap cells from every slot row (zone + overlap).
        heatmap = self._build_heatmap(
            zone_rows=zone_rows,
            overlap_rows=overlap_rows,
            fatigue_scores=fatigue_scores,
            called_off_ids=called_off,
        )

        stats = self._build_stats(heatmap, tm_coverage)

        resp = OnShiftStatusResponse(
            night_id=resolved_night,
            night_date=anchor_iso,
            day_name=night.get("day_name") or "",
            shift_label="Grave",
            generated_at=_dt.datetime.now(tz=_ET).isoformat(timespec="seconds"),
            stats=stats,
            tm_coverage=tm_coverage,
            heatmap=heatmap,
        )

        await self.cache.set(cache_key, resp.model_dump(mode="json"), ttl=self.STATUS_TTL)
        return resp

    # ── Write ─────────────────────────────────────────────────────

    async def patch_assignment(
        self,
        assignment_id: str,
        patch: MultiAreaAssignmentPatch,
    ) -> AssignmentPatchResponse:
        """Update one assignment row. Returns the row's post-write state."""
        if patch.source_table not in self._ALLOWED_TABLES:
            raise ValueError(f"Unsupported source_table: {patch.source_table!r}")

        # Build the update payload from only-the-fields-the-caller-set.
        update: dict[str, object] = {}
        if "tm_id" in patch.model_fields_set:
            update["tm_id"] = patch.tm_id
            update["is_filled"] = patch.tm_id is not None
        if "is_locked" in patch.model_fields_set and patch.is_locked is not None:
            update["is_locked"] = bool(patch.is_locked)

        if not update:
            # Idempotent: fetch and return current state.
            current = self._fetch_row(patch.source_table, assignment_id)
            return self._patch_response(assignment_id, patch.source_table, current)

        try:
            res = (
                self.supabase.table(patch.source_table)
                .update(update)
                .eq("id", assignment_id)
                .execute()
            )
        except Exception as exc:
            log.warning("PATCH %s/%s failed: %s", patch.source_table, assignment_id, exc)
            raise

        rows = res.data or []
        if not rows:
            raise LookupError(f"No {patch.source_table} row with id={assignment_id}")
        row = rows[0]

        night_id = row.get("night_id") or ""
        if night_id:
            await self.cache.delete(self._status_cache_key(night_id))

        return self._patch_response(assignment_id, patch.source_table, row)

    # ── Internals ─────────────────────────────────────────────────

    def _build_tm_coverage(
        self,
        *,
        zone_rows: list[dict],
        overlap_rows: list[dict],
        fatigue_scores: dict[str, float],
        fatigue_window: int,
        called_off_ids: set[str],
    ) -> list[TmCoverage]:
        by_tm: dict[str, dict] = {}

        # Stable sort: lower sort_order wins primary on ties.
        zone_sorted = sorted(zone_rows, key=lambda r: (r.get("sort_order") or 0, r.get("slot_key") or ""))
        for row in zone_sorted:
            tm_id = row.get("tm_id")
            if not tm_id:
                continue
            bucket = by_tm.setdefault(tm_id, {
                "display_name": row.get("tm_name") or "",
                "primary": None,
                "additional": [],
            })
            assignment = MultiAreaAssignment(
                assignment_id=row.get("id") or "",
                source_table="zone_assignments",
                slot_key=row.get("slot_key") or "",
                slot_label=row.get("label") or _slot_short_label(row),
                area=row.get("area") or "",
                reason=AssignmentReason.primary if bucket["primary"] is None
                       else AssignmentReason.secondary_zone,
                is_filled=bool(row.get("is_filled")),
                is_locked=bool(row.get("is_locked")),
            )
            if bucket["primary"] is None:
                bucket["primary"] = assignment
            else:
                bucket["additional"].append(assignment)

        for row in overlap_rows:
            tm_id = row.get("tm_id")
            if not tm_id:
                continue
            bucket = by_tm.setdefault(tm_id, {
                "display_name": row.get("tm_name") or "",
                "primary": None,
                "additional": [],
            })
            window = (row.get("overlap_window") or "").lower()
            reason = (
                AssignmentReason.overlap_pm if window == "pm"
                else AssignmentReason.overlap_am if window == "am"
                else AssignmentReason.other
            )
            assignment = MultiAreaAssignment(
                assignment_id=row.get("id") or "",
                source_table="overlap_assignments",
                slot_key=f"{window.upper()}OL{row.get('position') or ''}",
                slot_label=f"{window.upper()} Overlap {row.get('position') or ''}".strip(),
                area="Overlap",
                reason=reason,
                is_filled=bool(row.get("is_filled")),
                is_locked=False,
            )
            # Overlap can be the only assignment a TM has (PMOL-only TMs).
            if bucket["primary"] is None and not bucket["additional"]:
                bucket["primary"] = assignment
            else:
                bucket["additional"].append(assignment)

        out: list[TmCoverage] = []
        for tm_id, bucket in by_tm.items():
            out.append(TmCoverage(
                tm_id=tm_id,
                display_name=bucket["display_name"],
                primary_zone=bucket["primary"],
                additional_zones=bucket["additional"],
                fatigue_index=float(fatigue_scores.get(tm_id, 0.0)),
                fatigue_window_days=fatigue_window,
                is_called_off=tm_id in called_off_ids,
            ))
        out.sort(key=lambda t: t.display_name.lower())
        return out

    def _build_heatmap(
        self,
        *,
        zone_rows: list[dict],
        overlap_rows: list[dict],
        fatigue_scores: dict[str, float],
        called_off_ids: set[str],
    ) -> list[CoverageHeatmapCell]:
        cells: list[CoverageHeatmapCell] = []
        for row in zone_rows:
            tm_id = row.get("tm_id") or ""
            is_filled = bool(row.get("is_filled"))
            is_locked = bool(row.get("is_locked"))
            is_warn = bool(tm_id and tm_id in called_off_ids)
            fatigue = float(fatigue_scores.get(tm_id, 0.0)) if tm_id else 0.0
            cells.append(CoverageHeatmapCell(
                slot_key=row.get("slot_key") or "",
                slot_label=row.get("label") or _slot_short_label(row),
                area=row.get("area") or "",
                is_filled=is_filled,
                is_locked=is_locked,
                is_warn=is_warn,
                tm_id=tm_id,
                tm_name=row.get("tm_name") or "",
                tm_fatigue=fatigue,
                heat_level=_derive_heat_level(is_filled=is_filled, is_warn=is_warn,
                                              is_locked=is_locked, fatigue=fatigue),
                assignment_id=row.get("id") or "",
                source_table="zone_assignments",
            ))
        for row in overlap_rows:
            tm_id = row.get("tm_id") or ""
            is_filled = bool(row.get("is_filled"))
            is_warn = bool(tm_id and tm_id in called_off_ids)
            fatigue = float(fatigue_scores.get(tm_id, 0.0)) if tm_id else 0.0
            window = (row.get("overlap_window") or "").upper()
            slot_key = f"{window}OL{row.get('position') or ''}"
            cells.append(CoverageHeatmapCell(
                slot_key=slot_key,
                slot_label=f"{window} Overlap {row.get('position') or ''}".strip(),
                area="Overlap",
                is_filled=is_filled,
                is_locked=False,
                is_warn=is_warn,
                tm_id=tm_id,
                tm_name=row.get("tm_name") or "",
                tm_fatigue=fatigue,
                heat_level=_derive_heat_level(is_filled=is_filled, is_warn=is_warn,
                                              is_locked=False, fatigue=fatigue),
                assignment_id=row.get("id") or "",
                source_table="overlap_assignments",
            ))
        return cells

    def _build_stats(
        self,
        heatmap: list[CoverageHeatmapCell],
        tm_coverage: list[TmCoverage],
    ) -> CoverageStats:
        total = len(heatmap)
        filled = sum(1 for c in heatmap if c.is_filled and not c.is_warn)
        opened = sum(1 for c in heatmap if not c.is_filled)
        locked = sum(1 for c in heatmap if c.is_locked)
        warned = sum(1 for c in heatmap if c.is_warn)
        multi_area = sum(1 for tm in tm_coverage if tm.is_multi_area)
        fatigues = [tm.fatigue_index for tm in tm_coverage]
        return CoverageStats(
            total_slots=total,
            filled=filled,
            open=opened,
            locked=locked,
            called_off=warned,
            multi_area_tms=multi_area,
            fatigue_avg=round(sum(fatigues) / len(fatigues), 2) if fatigues else 0.0,
            fatigue_max=round(max(fatigues), 2) if fatigues else 0.0,
        )

    # ── DB readers ────────────────────────────────────────────────

    def _fetch_night(self, night_id: str) -> dict:
        try:
            res = (
                self.supabase.table("nights")
                .select("id, week_id, night_date, day_name, is_locked")
                .eq("id", night_id)
                .limit(1)
                .execute()
            )
            return (res.data or [{}])[0]
        except Exception as exc:
            log.warning("fetch night %s failed: %s", night_id, exc)
            return {}

    def _fetch_zone_assignments(self, night_id: str) -> list[dict]:
        try:
            res = (
                self.supabase.table("zone_assignments")
                .select(
                    "id, slot_type, slot_key, rr_side, is_filled, is_locked,"
                    "sort_order, group_num, entities(id, display_name)"
                )
                .eq("night_id", night_id)
                .order("sort_order")
                .execute()
            )
        except Exception as exc:
            log.warning("zone_assignments read failed (night=%s): %s", night_id, exc)
            return []
        rows = res.data or []
        for row in rows:
            ent = row.pop("entities", None) or {}
            row["tm_id"] = ent.get("id") or ""
            row["tm_name"] = ent.get("display_name") or ""
        return rows

    def _fetch_overlap_assignments(self, night_id: str) -> list[dict]:
        try:
            res = (
                self.supabase.table("overlap_assignments")
                .select(
                    "id, overlap_window, position, is_filled, task,"
                    "entities(id, display_name)"
                )
                .eq("night_id", night_id)
                .order("overlap_window")
                .order("position")
                .execute()
            )
        except Exception as exc:
            log.warning("overlap_assignments read failed (night=%s): %s", night_id, exc)
            return []
        rows = res.data or []
        for row in rows:
            ent = row.pop("entities", None) or {}
            row["tm_id"] = ent.get("id") or ""
            row["tm_name"] = ent.get("display_name") or ""
        return rows

    def _fetch_called_off_ids(self, night_date: str) -> set[str]:
        if not night_date:
            return set()
        try:
            res = (
                self.supabase.table("call_offs")
                .select("tm_id")
                .eq("night_date", night_date)
                .execute()
            )
        except Exception as exc:
            log.debug("call_offs read failed for %s: %s", night_date, exc)
            return set()
        return {r["tm_id"] for r in (res.data or []) if r.get("tm_id")}

    def _fetch_row(self, table: str, row_id: str) -> dict:
        try:
            res = (
                self.supabase.table(table)
                .select("id, tm_id, is_filled, is_locked, night_id")
                .eq("id", row_id)
                .limit(1)
                .execute()
            )
            return (res.data or [{}])[0]
        except Exception as exc:
            log.warning("fetch %s/%s failed: %s", table, row_id, exc)
            return {}

    def _patch_response(self, assignment_id: str, table: str, row: dict) -> AssignmentPatchResponse:
        return AssignmentPatchResponse(
            assignment_id=assignment_id,
            source_table=table,  # type: ignore[arg-type]
            tm_id=row.get("tm_id"),
            is_filled=bool(row.get("is_filled")),
            is_locked=bool(row.get("is_locked")),
        )

    def _resolve_tonight_night_id(self) -> str:
        """Find the night row whose date matches the current grave shift.

        Mid-shift before 7am ET, the shift started yesterday — the same
        anchor convention used by apps/shift/state._build_from_zds.
        """
        now = _dt.datetime.now(tz=_ET)
        anchor = now.date() if now.hour >= 7 else now.date() - _dt.timedelta(days=1)
        for candidate in (anchor, anchor + _dt.timedelta(days=1),
                          anchor - _dt.timedelta(days=1)):
            try:
                res = (
                    self.supabase.table("nights")
                    .select("id")
                    .eq("night_date", candidate.isoformat())
                    .limit(1)
                    .execute()
                )
                if res.data:
                    return res.data[0]["id"]
            except Exception as exc:
                log.debug("nights lookup for %s failed: %s", candidate, exc)
        return ""


# ── Module-level helpers ────────────────────────────────────────────


def _derive_heat_level(
    *, is_filled: bool, is_warn: bool, is_locked: bool, fatigue: float
) -> HeatLevel:
    if is_warn:
        return HeatLevel.warn
    if not is_filled:
        return HeatLevel.open
    if fatigue >= FATIGUE_STRETCHED_THRESHOLD:
        return HeatLevel.stretched
    if is_locked or fatigue >= FATIGUE_STRETCHED_THRESHOLD / 2:
        return HeatLevel.ok
    return HeatLevel.ok_light


def _slot_short_label(row: dict) -> str:
    """Fallback display label when the DB row doesn't carry one."""
    sk = (row.get("slot_key") or "").strip()
    if not sk:
        return ""
    if sk.startswith("zone_"):
        n = sk.rsplit("_", 1)[-1]
        return f"Z{n}"
    if sk.startswith("rr_"):
        side = (row.get("rr_side") or "").strip().lower()
        n = sk.rsplit("_", 1)[-1] if sk != "rr_1_2" else "1"
        tag = "M" if side.startswith("m") else "W" if side.startswith("w") else ""
        return f"RR {n} {tag}".strip()
    return sk.replace("_", " ").title()


def _parse_iso_date(value: object) -> Optional[_dt.date]:
    if isinstance(value, _dt.date) and not isinstance(value, _dt.datetime):
        return value
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return _dt.date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None
