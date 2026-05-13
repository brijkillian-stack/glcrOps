"""PlanningService — pre-shift planning data aggregator (GLC-12).

Single responsibility: compose PlacementService calls into the
WeeklyPlanningOverviewResponse shape, apply a short TTL cache, and expose
a clean invalidation hook.

Architecture
────────────
PlanningService wraps PlacementService — it never touches Supabase directly.
All data flows: PlanningService → PlacementService → CacheService / Supabase.

Cache key:  ``zds:planning:week:{week_id}``
TTL:        15 seconds (short — planning supervisors need fresh data during
            active pre-shift editing; CacheService no-ops gracefully when
            Redis is absent).

Sacred renderer rule
────────────────────
PlanningService never imports or calls render_deployment_book.py.
Print links in PlanningLinks are URL strings only — the print endpoints
handle rendering.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from datetime import date as _date
from datetime import timedelta
from typing import Optional

from ..models.planning import (
    NightPlanningSnapshot,
    OverrideSummary,
    PlanningLinks,
    PlanningNote,
    WeeklyPlanningOverviewResponse,
    WeekMetrics,
    WeekMeta,
)

log = logging.getLogger(__name__)

PLANNING_TTL = 15   # seconds; intentionally short for a live planning tool
PLANNING_CACHE_VER = "v2"  # bump when WeekMeta/NightPlanningSnapshot shape changes

# ── Per-day target capacity (Brian's spec 5/12/26) ────────────────────────────
# "100% fill rate" is defined against these targets, not against the raw slot
# count in the DB.  This lets the rings and metrics reflect operational targets
# rather than the total number of seats that *could* be filled.
#
#   Friday / Saturday  → 25 staffed = 100%
#   Sunday             → 20 staffed = 100%
#   Monday–Thursday    → 18 staffed = 100%
#
# coverage_pct is capped at 100 so over-staffed nights don't exceed the ring.
_TARGET_CAPACITY: dict[str, int] = {
    "Friday":    25,
    "Saturday":  25,
    "Sunday":    20,
    "Monday":    18,
    "Tuesday":   18,
    "Wednesday": 18,
    "Thursday":  18,
}
_DEFAULT_TARGET = 18  # fallback for any unexpected day_name


class PlanningService:
    """Aggregate planning data for a week from PlacementService."""

    def __init__(self, placement) -> None:
        self.placement = placement

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_weekly_overview(
        self, week_id: str
    ) -> Optional[WeeklyPlanningOverviewResponse]:
        """Fetch and compute the weekly planning overview.

        Returns None when the week doesn't exist (caller raises 404).
        Result is cached for PLANNING_TTL seconds.
        """
        cache_key = f"zds:planning:week:{week_id}:{PLANNING_CACHE_VER}"
        cached = await self.placement.cache.get(cache_key)
        if cached is not None:
            try:
                return WeeklyPlanningOverviewResponse.model_validate(cached)
            except Exception as exc:
                log.warning("planning cache deserialise failed: %s", exc)
                # Fall through to a fresh compute.

        # ── Fetch raw data ────────────────────────────────────────────────
        week_dict = await self.placement.get_week(week_id)
        if not week_dict:
            return None

        nights_dicts = await self.placement.get_week_nights(week_id) or []

        # ── Process each night ────────────────────────────────────────────
        night_snapshots: list[NightPlanningSnapshot] = []
        all_overrides:   list[OverrideSummary]        = []
        planning_notes:  list[PlanningNote]           = []

        total_assignments       = 0
        total_gaps              = 0
        total_multi_area        = 0
        total_overrides         = 0
        nights_with_gaps        = 0
        all_tm_ids: set[str]    = set()

        for night in nights_dicts:
            nid       = night.get("id", "")
            day_name  = night.get("day_name", "")
            in_rot    = bool(night.get("in_rotation", 1))

            # Only count in-rotation nights in aggregate metrics.
            assignments = await self.placement.get_night_assignments(nid)
            overlaps    = await self.placement.get_night_overlaps(nid)

            total_slots  = len(assignments)
            filled_slots = sum(
                1 for a in assignments
                if a.get("tm_id") not in (None, "", "null")
            )
            gap_count    = total_slots - filled_slots
            # coverage_pct uses the per-day *target* capacity as the denominator
            # so the fill ring reflects operational targets, not raw slot counts.
            # Capped at 100 so over-staffed nights don't exceed the ring.
            target       = _TARGET_CAPACITY.get(day_name, _DEFAULT_TARGET)
            coverage_pct = min((filled_slots / target * 100.0) if target else 0.0, 100.0)

            # ── Zone / RR breakdown ───────────────────────────────────
            zone_total  = sum(1 for a in assignments if a.get("slot_type") == "zone")
            zone_filled = sum(1 for a in assignments if a.get("slot_type") == "zone" and a.get("tm_id") not in (None, "", "null"))
            rr_total    = sum(1 for a in assignments if a.get("slot_type") == "rr")
            rr_filled   = sum(1 for a in assignments if a.get("slot_type") == "rr"   and a.get("tm_id") not in (None, "", "null"))

            # ── Sweeper status ─────────────────────────────────────────
            sweeper_main_filled = False
            sweeper_sr_filled   = False

            # Primary: scan zone_assignments (zone / rr / aux cards) for
            # rows where is_sweeper=True — these are the actual sweeper
            # positions in the deployment grid.  sweeper_route "sr" maps
            # to Sweeper 9/10/SR; anything else (including "main" or null)
            # maps to Sweeper 5/8/HL (main route).
            for a in assignments:
                if not a.get("is_sweeper"):
                    continue
                if a.get("tm_id") in (None, "", "null"):
                    continue
                route = (a.get("sweeper_route") or "").lower()
                if route == "sr":
                    sweeper_sr_filled = True
                else:
                    sweeper_main_filled = True

            # Fallback 1: dedicated night_sweepers table
            # (populated by the manual Sweeper panel in the Daily Planner).
            if not (sweeper_main_filled and sweeper_sr_filled):
                try:
                    sw_res = self.placement.supabase.table("night_sweepers") \
                        .select("slot,tm_id") \
                        .eq("night_id", nid) \
                        .execute()
                    for sw in (sw_res.data or []):
                        if sw.get("tm_id"):
                            if sw["slot"] == "main":
                                sweeper_main_filled = True
                            elif sw["slot"] == "sr":
                                sweeper_sr_filled = True
                except Exception as exc:
                    log.warning("sweeper fetch(%s) failed: %s", nid, exc)

            # Fallback 2: scan custom_tasks arrays on filled zone assignments.
            # Covers the common case where a TM was given a sweeper task via
            # the task picker rather than through the dedicated Sweeper panel.
            # SR sweeper: task name contains "sr" or "9/10" or "9 / 10".
            # Main sweeper: any other task name containing "sweep".
            if not (sweeper_main_filled and sweeper_sr_filled):
                for a in assignments:
                    if a.get("tm_id") in (None, "", "null"):
                        continue
                    for task in (a.get("custom_tasks") or []):
                        t = task.lower().strip()
                        if "sweep" not in t:
                            continue
                        is_sr = "sr" in t or "9/10" in t or "9 / 10" in t
                        if is_sr:
                            sweeper_sr_filled = True
                        else:
                            sweeper_main_filled = True
                        if sweeper_main_filled and sweeper_sr_filled:
                            break
                    if sweeper_main_filled and sweeper_sr_filled:
                        break

            # ── Night note ─────────────────────────────────────────────
            night_note = night.get("notes")

            # Gather TM ids for fatigue index.
            for a in assignments:
                tid = a.get("tm_id")
                if tid and tid not in (None, "", "null"):
                    all_tm_ids.add(tid)

            # Overrides for this night.
            override_rows = []
            try:
                override_rows = await self.placement.list_overrides(nid)
            except Exception as exc:
                log.warning("list_overrides(%s) failed: %s", nid, exc)

            override_count = len(override_rows)

            # Build OverrideSummary entries.
            for ov in override_rows:
                ov_dict = ov if isinstance(ov, dict) else ov.model_dump()
                all_overrides.append(OverrideSummary(
                    night_id   = nid,
                    day_name   = day_name,
                    slot_key   = ov_dict.get("slot_key", ""),
                    tm_id      = ov_dict.get("tm_id"),
                    note       = ov_dict.get("note"),
                    created_at = ov_dict.get("created_at"),
                ))

            # Generate synthetic planning notes.
            if in_rot and gap_count > 0:
                slot_word = "slot" if gap_count == 1 else "slots"
                planning_notes.append(PlanningNote(
                    night_id  = nid,
                    day_name  = day_name,
                    note_kind = "gap",
                    note_text = f"{gap_count} unfilled {slot_word} — run Reoptimize or assign manually.",
                ))
            if in_rot and override_count > 0:
                ov_word = "override" if override_count == 1 else "overrides"
                planning_notes.append(PlanningNote(
                    night_id  = nid,
                    day_name  = day_name,
                    note_kind = "override",
                    note_text = f"{override_count} active {ov_word} — verify assignments before printing.",
                ))
            if in_rot and len(overlaps) > 0:
                planning_notes.append(PlanningNote(
                    night_id  = nid,
                    day_name  = day_name,
                    note_kind = "overlap",
                    note_text = f"{len(overlaps)} multi-area overlap(s) recorded.",
                ))

            # Accumulate totals (in-rotation nights only).
            if in_rot:
                total_assignments += filled_slots
                total_gaps        += gap_count
                total_multi_area  += len(overlaps)
                total_overrides   += override_count
                if gap_count > 0:
                    nights_with_gaps += 1

            night_snapshots.append(NightPlanningSnapshot(
                night_id                 = nid,
                night_date               = night.get("night_date", ""),
                day_name                 = day_name,
                in_rotation              = in_rot,
                total_slots              = total_slots,
                filled_slots             = filled_slots,
                gap_count                = gap_count,
                coverage_pct             = round(coverage_pct, 1),
                target_capacity          = target,
                zone_total               = zone_total,
                zone_filled              = zone_filled,
                rr_total                 = rr_total,
                rr_filled                = rr_filled,
                sweeper_main_filled      = sweeper_main_filled,
                sweeper_sr_filled        = sweeper_sr_filled,
                multi_area_overlap_count = len(overlaps),
                override_count           = override_count,
                reoptimize_recommended   = in_rot and gap_count > 0,
                note                     = night_note,
            ))

        # ── Week metadata ─────────────────────────────────────────────────
        week_ending = week_dict.get("week_ending", "")
        try:
            we_date    = _date.fromisoformat(week_ending)
            week_start = (we_date - timedelta(days=6)).isoformat()
        except (ValueError, TypeError):
            week_start = ""

        week_meta = WeekMeta(
            id            = week_dict.get("id", week_id),
            label         = week_dict.get("label", ""),
            week_start    = week_start,
            week_ending   = week_ending,
            status        = week_dict.get("status", "draft"),
            schedule_path = week_dict.get("schedule_path") or None,
        )

        # ── Fatigue index ─────────────────────────────────────────────────
        fatigue_index = (
            round(total_assignments / len(all_tm_ids), 2)
            if all_tm_ids else 0.0
        )

        metrics = WeekMetrics(
            total_assignments        = total_assignments,
            total_gaps               = total_gaps,
            nights_with_gaps         = nights_with_gaps,
            multi_area_overlap_count = total_multi_area,
            active_override_count    = total_overrides,
            fatigue_index            = fatigue_index,
            reoptimize_opportunities = nights_with_gaps,
        )

        links = PlanningLinks(
            print_week_html = f"/v1/print/week/{week_id}.html",
            print_week_pdf  = f"/v1/print/week/{week_id}.pdf",
            reoptimize      = f"/v1/engine/week/{week_id}/reoptimize",
        )

        response = WeeklyPlanningOverviewResponse(
            week             = week_meta,
            nights           = night_snapshots,
            metrics          = metrics,
            planning_notes   = planning_notes,
            active_overrides = all_overrides,
            links            = links,
            cached_at        = datetime.now(timezone.utc).isoformat(),
        )

        # ── Cache the result ──────────────────────────────────────────────
        try:
            await self.placement.cache.set(
                cache_key, response.model_dump(), ttl=PLANNING_TTL
            )
        except Exception as exc:
            log.warning("planning cache set failed: %s", exc)

        return response

    async def invalidate_week_planning(self, week_id: str) -> None:
        """Invalidate the planning overview cache for a week.

        Call this whenever assignments, overrides, or the week row change.
        PlacementService.invalidate_week() does NOT clear the planning cache
        because PlanningService sits above it and owns its own namespace.
        """
        await self.placement.cache.delete(f"zds:planning:week:{week_id}:{PLANNING_CACHE_VER}")
