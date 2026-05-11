"""Fatigue index calculator for the live Shift Dash.

Mirrors `apps/zds/engine/glcr_engine/scorecard.fatigue_index` so the
number a supervisor sees in the HUD matches the number the placement
engine penalizes during planning.

Engine formula:
    fatigue_index(tm) = Σ slot_load[slot] for each slot the TM worked
                        within the trailing `fatigue_window_days`
                        (counting only the most recent date per slot).

Why a separate, query-shaped implementation:
    The engine module is global-stateful — it expects `scorecard.init(...)`
    to populate process-level dicts. A long-lived FastAPI worker can't
    safely reinit that on every request. This service rebuilds the same
    math from Supabase reads with no shared mutable state.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from supabase import Client

log = logging.getLogger(__name__)


class FatigueService:
    """Query-only fatigue scorer keyed on (tm_id, anchor_date)."""

    DEFAULT_WINDOW_DAYS = 7

    def __init__(self, supabase: Client):
        self.supabase = supabase

    # ── Config + load scores ───────────────────────────────────────

    def _load_window_days(self) -> int:
        """Read fatigue window from `scorecard_config`; fall back to 7.

        Engine reads the same column in fill_engine.py:589, so a single
        config row drives both planner and live HUD.
        """
        try:
            res = (
                self.supabase.table("scorecard_config")
                .select("fatigue_index_window_days")
                .eq("id", 1)
                .limit(1)
                .execute()
            )
            row = (res.data or [{}])[0]
            return int(row.get("fatigue_index_window_days") or self.DEFAULT_WINDOW_DAYS)
        except Exception as exc:
            log.debug("scorecard_config read failed (%s); defaulting window=%d",
                      exc, self.DEFAULT_WINDOW_DAYS)
            return self.DEFAULT_WINDOW_DAYS

    def _load_slot_loads(self) -> dict[str, int]:
        try:
            res = self.supabase.table("slot_load_scores").select("slot_id, load").execute()
            return {r["slot_id"]: int(r["load"]) for r in (res.data or [])}
        except Exception as exc:
            log.debug("slot_load_scores read failed (%s); using empty map", exc)
            return {}

    # ── Public API ─────────────────────────────────────────────────

    def compute(
        self,
        tm_ids: list[str],
        anchor_date: date,
        *,
        window_days: Optional[int] = None,
        slot_loads: Optional[dict[str, int]] = None,
    ) -> tuple[dict[str, float], int]:
        """Return (`{tm_id: fatigue_index}`, `window_days`).

        Only the most recent date per (tm, slot) inside the window
        contributes — same as the engine. Missing slot loads default to
        a load of 2 (the engine's `slot_loads.get(slot, 2)` fallback).
        """
        wd = int(window_days) if window_days is not None else self._load_window_days()
        loads = dict(slot_loads) if slot_loads is not None else self._load_slot_loads()
        if not tm_ids:
            return {}, wd

        cutoff = anchor_date - timedelta(days=wd)
        scores: dict[str, float] = {tm_id: 0.0 for tm_id in tm_ids}

        try:
            res = (
                self.supabase.table("zone_assignments")
                .select("tm_id, slot_key, slot_type, rr_side, nights(night_date)")
                .in_("tm_id", tm_ids)
                .execute()
            )
        except Exception as exc:
            log.warning("zone_assignments lookup for fatigue failed: %s", exc)
            return scores, wd

        latest_per_pair: dict[tuple[str, str], date] = {}
        for row in (res.data or []):
            tm_id = row.get("tm_id")
            slot_key = self._canonical_slot(row)
            night = row.get("nights") or {}
            nd_raw = night.get("night_date")
            if not tm_id or not slot_key or not nd_raw:
                continue
            nd = _parse_iso_date(nd_raw)
            if nd is None:
                continue
            if nd < cutoff or nd > anchor_date:
                continue
            prev = latest_per_pair.get((tm_id, slot_key))
            if prev is None or nd > prev:
                latest_per_pair[(tm_id, slot_key)] = nd

        for (tm_id, slot_key), _last_d in latest_per_pair.items():
            if tm_id not in scores:
                continue
            scores[tm_id] += float(loads.get(slot_key, 2))

        return scores, wd

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _canonical_slot(row: dict) -> str:
        """Match the engine's slot vocabulary so `slot_loads` lookups hit.

        zone_assignments stores slot_key like 'zone_3' + rr_side='mens'.
        The engine keys slot_loads on the same strings, but RR rows in
        the legacy archive use the combined form 'rr_3_M' / 'rr_3_W' —
        defensively normalize so loads still resolve.
        """
        sk = (row.get("slot_key") or "").strip()
        if not sk:
            return ""
        if row.get("slot_type") == "rr" or sk.startswith("rr_"):
            side = (row.get("rr_side") or "").strip().lower()
            tag = "M" if side.startswith("m") else ("W" if side.startswith("w") else "")
            if tag and not sk.endswith(f"_{tag}"):
                return f"{sk}_{tag}"
        return sk


def _parse_iso_date(value: object) -> Optional[date]:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None
