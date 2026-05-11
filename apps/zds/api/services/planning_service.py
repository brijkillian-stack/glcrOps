"""Weekly planning overview — pre-shift dashboard aggregator.

Composes a single response payload from `PlacementService` for the
Next.js weekly view. Each night summary carries staffing counts,
coverage gaps, notes, call-offs, overlap fill, and night-lock status;
the week wrapper carries the schedule-override list and rolled-up
totals so the dashboard can render without follow-up requests.

This module is read-only. Mutations (notes, overrides, locks) are
handled by their own services and invalidate the relevant cache
entries through `PlacementService.invalidate_*`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from pydantic import BaseModel, Field
from supabase import Client

from .cache_service import CacheService
from .placement_service import PlacementService

log = logging.getLogger(__name__)


# ── Response models ─────────────────────────────────────────────────


class WeekInfo(BaseModel):
    id: str
    week_ending: str = ""
    label: str = ""
    status: str = ""
    schedule_path: str = ""
    date_range: str = ""


class StaffingStats(BaseModel):
    filled: int = 0
    total: int = 0
    unfilled: int = 0
    locked: int = 0
    called_off: int = 0


class CoverageGap(BaseModel):
    slot_id: str
    slot_type: str
    slot_key: str
    label: str
    rr_side: str = ""
    sort_order: int = 0


class NightNote(BaseModel):
    id: str
    type: str = ""
    text: str = ""
    created_by: str = ""
    created_at: str = ""


class CallOffEntry(BaseModel):
    tm_id: str
    display_name: str = ""
    reason: str = ""
    created_at: str = ""


class OverlapSummary(BaseModel):
    pm_filled: int = 0
    pm_total: int = 0
    am_filled: int = 0
    am_total: int = 0


class NightSummary(BaseModel):
    id: str
    week_id: str
    night_date: str = ""
    day_name: str = ""
    day_num: int = 0
    page_num: int = 0
    in_rotation: int = 0
    breaks_5: int = 0
    breaks_9: int = 0
    breaks_4: int = 0
    is_locked: bool = False
    locked_by: str = ""
    locked_at: str = ""
    staffing: StaffingStats = Field(default_factory=StaffingStats)
    coverage_gaps: list[CoverageGap] = Field(default_factory=list)
    notes: list[NightNote] = Field(default_factory=list)
    call_offs: list[CallOffEntry] = Field(default_factory=list)
    overlaps: OverlapSummary = Field(default_factory=OverlapSummary)


class ScheduleOverrideEntry(BaseModel):
    schedule_path: str
    tm_id: str
    shift: str = ""
    cell_date: str = ""
    override_value: str = ""
    note: str = ""


class WeeklyTotals(BaseModel):
    filled: int = 0
    total: int = 0
    unfilled: int = 0
    locked: int = 0
    called_off: int = 0
    coverage_gaps: int = 0
    nights_locked: int = 0
    notes: int = 0
    overrides: int = 0


class WeeklyPlanningOverview(BaseModel):
    week: WeekInfo
    nights: list[NightSummary] = Field(default_factory=list)
    overrides: list[ScheduleOverrideEntry] = Field(default_factory=list)
    totals: WeeklyTotals = Field(default_factory=WeeklyTotals)


# ── Service ────────────────────────────────────────────────────────


class PlanningService:
    """Builds the weekly planning overview by aggregating PlacementService reads."""

    def __init__(self, supabase: Client, cache: Optional[CacheService] = None):
        self.cache = cache or CacheService(None)
        self.placement = PlacementService(supabase, cache=self.cache)

    async def get_weekly_overview(self, week_id: str) -> Optional[WeeklyPlanningOverview]:
        week_row = await self.placement.get_week(week_id)
        if not week_row:
            return None

        nights_raw = await self.placement.get_week_nights(week_id)
        stats_by_id = await self.placement.get_week_night_stats(week_id)

        # Fan out per-night reads concurrently — each night needs four
        # independent queries (assignments, overlaps, notices, call_offs).
        night_summaries = await asyncio.gather(
            *(self._build_night_summary(n, stats_by_id) for n in nights_raw)
        )

        overrides_raw = await self.placement.get_schedule_overrides(
            week_row.get("schedule_path") or ""
        )
        overrides = [
            ScheduleOverrideEntry(
                schedule_path=row.get("schedule_path") or "",
                tm_id=row.get("tm_id") or "",
                shift=row.get("shift") or "",
                cell_date=row.get("cell_date") or "",
                override_value=row.get("override_value") or "",
                note=row.get("note") or "",
            )
            for row in overrides_raw
        ]

        totals = self._roll_up_totals(night_summaries, overrides)

        return WeeklyPlanningOverview(
            week=WeekInfo(
                id=week_row.get("id") or week_id,
                week_ending=week_row.get("week_ending") or "",
                label=week_row.get("label") or "",
                status=week_row.get("status") or "",
                schedule_path=week_row.get("schedule_path") or "",
                date_range=week_row.get("date_range") or "",
            ),
            nights=night_summaries,
            overrides=overrides,
            totals=totals,
        )

    # ── internals ─────────────────────────────────────────────────

    async def _build_night_summary(
        self, night: dict, stats_by_id: dict[str, dict]
    ) -> NightSummary:
        night_id = night.get("id") or ""
        night_date = night.get("night_date") or ""

        assignments, overlaps, notices, call_offs = await asyncio.gather(
            self.placement.get_night_assignments(night_id),
            self.placement.get_night_overlaps(night_id),
            self.placement.get_night_notices(night_id),
            self.placement.get_night_call_offs(night_date),
        )

        stats = stats_by_id.get(night_id, {}) if stats_by_id else {}
        staffing = StaffingStats(
            filled=int(stats.get("filled", 0)),
            total=int(stats.get("total", 0)),
            unfilled=int(stats.get("unfilled", 0)),
            locked=int(stats.get("locked", 0)),
            called_off=int(stats.get("called_off", 0)),
        )

        coverage_gaps = [
            CoverageGap(
                slot_id=row.get("id") or "",
                slot_type=row.get("slot_type") or "",
                slot_key=row.get("slot_key") or "",
                label=row.get("label") or row.get("slot_key") or "",
                rr_side=row.get("rr_side") or "",
                sort_order=int(row.get("sort_order") or 0),
            )
            for row in assignments
            if not row.get("is_filled") and not row.get("is_empty")
        ]
        coverage_gaps.sort(key=lambda g: g.sort_order)

        return NightSummary(
            id=night_id,
            week_id=night.get("week_id") or "",
            night_date=night_date,
            day_name=night.get("day_name") or "",
            day_num=int(night.get("day_num") or 0),
            page_num=int(night.get("page_num") or 0),
            in_rotation=int(night.get("in_rotation") or 0),
            breaks_5=int(night.get("breaks_5") or 0),
            breaks_9=int(night.get("breaks_9") or 0),
            breaks_4=int(night.get("breaks_4") or 0),
            is_locked=bool(night.get("is_locked")),
            locked_by=night.get("locked_by") or "",
            locked_at=night.get("locked_at") or "",
            staffing=staffing,
            coverage_gaps=coverage_gaps,
            notes=[
                NightNote(
                    id=row.get("id") or "",
                    type=row.get("type") or "",
                    text=row.get("text") or "",
                    created_by=row.get("created_by") or "",
                    created_at=row.get("created_at") or "",
                )
                for row in notices
            ],
            call_offs=[
                CallOffEntry(
                    tm_id=row.get("tm_id") or "",
                    display_name=row.get("display_name") or "",
                    reason=row.get("reason") or "",
                    created_at=row.get("created_at") or "",
                )
                for row in call_offs
            ],
            overlaps=self._summarize_overlaps(overlaps),
        )

    @staticmethod
    def _summarize_overlaps(rows: list[dict]) -> OverlapSummary:
        summary = OverlapSummary()
        for row in rows:
            window = (row.get("overlap_window") or "").lower()
            filled = bool(row.get("is_filled"))
            if window == "pm":
                summary.pm_total += 1
                if filled:
                    summary.pm_filled += 1
            elif window == "am":
                summary.am_total += 1
                if filled:
                    summary.am_filled += 1
        return summary

    @staticmethod
    def _roll_up_totals(
        nights: list[NightSummary],
        overrides: list[ScheduleOverrideEntry],
    ) -> WeeklyTotals:
        totals = WeeklyTotals(overrides=len(overrides))
        for n in nights:
            totals.filled += n.staffing.filled
            totals.total += n.staffing.total
            totals.unfilled += n.staffing.unfilled
            totals.locked += n.staffing.locked
            totals.called_off += n.staffing.called_off
            totals.coverage_gaps += len(n.coverage_gaps)
            totals.notes += len(n.notes)
            if n.is_locked:
                totals.nights_locked += 1
        return totals
