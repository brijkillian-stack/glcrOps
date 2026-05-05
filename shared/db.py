"""
db.py — Supabase client for GLCR Memory Dashboard.

Replaces the direct SQLite layer. All queries go through supabase-py
using the service_role key (server-side only — never exposed to browser).

Schema (Supabase / Postgres):
  notes:    id, content, content_type, sentiment, original_date, author,
            captured_at, captured_via, source_ref, metadata (jsonb), archived,
            embedding (vector(1536))
  tasks:    id, title, description, category, status, priority, due_at,
            source, related_entity_id, owner, created_at, updated_at, completed_at
  events:   id, event_type, title, description, created_at, metadata (jsonb),
            event_date, shift, summary, source_ref, captured_at
  entities: id, name, entity_type, metadata (jsonb), created_at, display_name,
            status, updated_at, embedding (vector(1536))
  note_entities: note_id, entity_id, role, created_at (link table)
  event_notes:   event_id, note_id, created_at (link table)
  threads:   id, title, topic, metadata (jsonb), created_at, updated_at
  thread_notes: thread_id, note_id, created_at (link table)
  files:    id, name, path, size, created_at, metadata (jsonb)
  search_log: id, query, hit_count, user_id, created_at
  _schema:  key, value (metadata table for schema version)
"""

import os
import time
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the reflex/ directory
load_dotenv(Path(__file__).parent.parent / ".env")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# ── Client singleton ──────────────────────────────────────────────────────────

_client = None


def get_client():
    global _client
    if _client is None:
        from supabase import create_client
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print(f"[db] Supabase client initialised → {SUPABASE_URL[:40]}…")
    return _client


# ── Icon map (same as before) ─────────────────────────────────────────────────

_ICON_MAP = {
    "kudos":       ("★", "feed-icon-gold"),
    "flag":        ("⚑", "feed-icon-flag"),
    "incident":    ("⚠", "feed-icon-flag"),
    "observation": ("◐", "feed-icon"),
    "huddle":      ("⊕", "feed-icon-blue"),
    "beo":         ("⊟", "feed-icon-flag"),
    "callout":     ("⚑", "feed-icon-flag"),
    "floor_walk":  ("◫", "feed-icon-blue"),
    "shift_recap": ("≡", "feed-icon"),
    "dispatch":    ("",  ""),
    "reference":   ("✉", "feed-icon"),
    "request":     ("→", "feed-icon"),
    "feedback":    ("◈", "feed-icon"),
}


def _format_ts(ts_str: str | None) -> str:
    if not ts_str:
        return "—"
    try:
        ts = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts) if "T" in ts else datetime.strptime(ts[:10], "%Y-%m-%d")
        today = date.today()
        yesterday = today - timedelta(days=1)
        if dt.date() == today:
            return dt.strftime("%-I:%M%p").lower().replace("am", "a").replace("pm", "p")
        elif dt.date() == yesterday:
            return "Yest"
        else:
            return dt.strftime("%-m/%-d")
    except Exception:
        return ts_str[:5] if ts_str else "—"


# ── Tonight tasks ─────────────────────────────────────────────────────────────

def get_tonight_tasks(limit: int = 8) -> list[dict]:
    try:
        today_str = date.today().isoformat()
        res = (
            get_client()
            .table("tasks")
            .select("id, title, status, priority, due_at, category")
            .in_("status", ["open", "in_progress"])
            .execute()
        )
        tasks = res.data or []

        priority_order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
        for t in tasks:
            due = t.get("due_at")
            due_date_str = due[:10] if due else ""
            # Overdue: either due_at is in the past, or title contains OVERDUE marker
            t["due_date"]  = due_date_str
            t["is_overdue"] = bool(
                (due_date_str and due_date_str < today_str)
                or "OVERDUE" in (t.get("title") or "")
            )
            t["category"] = t.get("category") or ""
            t["priority"] = t.get("priority") or "normal"

        tasks.sort(key=lambda t: (
            0 if t["is_overdue"] else 1,
            priority_order.get(t["priority"], 2),
            t.get("due_at") or "9999-12-31",
        ))
        return tasks[:limit]
    except Exception:
        print(f"[db] get_tonight_tasks error:\n{traceback.format_exc()}")
        return []


# ── Activity feed ─────────────────────────────────────────────────────────────

def get_activity_feed(since_days: int = 2, limit: int = 12) -> list[dict]:
    try:
        cutoff_date = (date.today() - timedelta(days=since_days)).isoformat()
        cutoff_ts   = cutoff_date + "T00:00:00"
        sb = get_client()

        note_res = (
            sb.table("notes")
            .select("id, content, content_type, sentiment, original_date, captured_at, metadata")
            .eq("archived", False)
            .in_("content_type", list(_OPERATIONAL_TYPES))   # ← filter: no reference/dispatch
            .gte("original_date", cutoff_date)
            .order("original_date", desc=True)
            .limit(limit)
            .execute()
        )
        event_res = (
            sb.table("events")
            .select("id, event_type, title, created_at, metadata")
            .gte("created_at", cutoff_ts)
            .neq("event_type", "dispatch")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        notes = [
            {
                "kind":         "note",
                "id":           r["id"],
                "text":         r.get("content") or "",
                "content_type": r.get("content_type") or "observation",
                "ts":           r.get("original_date") or r.get("captured_at") or "",
                "metadata":     r.get("metadata") or {},
            }
            for r in (note_res.data or [])
        ]
        events = [
            {
                "kind":         "event",
                "id":           r["id"],
                "text":         r.get("title") or "",
                "content_type": r.get("event_type") or "event",
                "ts":           r.get("created_at") or "",
                "metadata":     r.get("metadata") or {},
            }
            for r in (event_res.data or [])
        ]

        combined = sorted(notes + events, key=lambda x: x.get("ts", ""), reverse=True)[:limit]

        for item in combined:
            ct = item.get("content_type", "observation")
            icon, _ = _ICON_MAP.get(ct, ("·", "feed-icon"))
            item["icon"]              = icon
            item["note_type"]         = ct
            item["timestamp_display"] = _format_ts(item.get("ts"))

        return combined
    except Exception:
        print(f"[db] get_activity_feed error:\n{traceback.format_exc()}")
        return []


# ── KPIs ──────────────────────────────────────────────────────────────────────

def get_kpis() -> dict:
    result = {
        "captures_today":     0,
        "captures_yesterday": 0,
        "captures_delta":     "+0 vs yest",
        "captures_direction": "flat",
        "open_tasks":         0,
        "overdue_tasks":      0,
        "active_flags":       0,
        "flags_last_week":    0,
        "backend_ok":         False,
        "backend_latency_ms": 0,
    }
    try:
        t0       = time.monotonic()
        today    = date.today().isoformat()
        yest     = (date.today() - timedelta(days=1)).isoformat()
        week_ago = (date.today() - timedelta(days=7)).isoformat()
        fortnight = (date.today() - timedelta(days=14)).isoformat()
        sb = get_client()

        cap_today = (
            sb.table("notes").select("id", count="exact")
            .eq("original_date", today).eq("archived", False).execute().count or 0
        )
        cap_yest = (
            sb.table("notes").select("id", count="exact")
            .eq("original_date", yest).eq("archived", False).execute().count or 0
        )
        open_t = (
            sb.table("tasks").select("id", count="exact")
            .in_("status", ["open", "in_progress"]).execute().count or 0
        )
        # Overdue = due_at is set and in the past (excludes null due_at)
        overdue_t = (
            sb.table("tasks").select("id", count="exact")
            .in_("status", ["open", "in_progress"])
            .lt("due_at", today + "T00:00:00")
            .not_.is_("due_at", "null")
            .execute().count or 0
        )
        flags_now = (
            sb.table("notes").select("id", count="exact")
            .in_("content_type", ["flag", "incident"])
            .gte("original_date", week_ago)
            .eq("archived", False).execute().count or 0
        )
        flags_prev = (
            sb.table("notes").select("id", count="exact")
            .in_("content_type", ["flag", "incident"])
            .gte("original_date", fortnight)
            .lt("original_date", week_ago)
            .eq("archived", False).execute().count or 0
        )

        latency_ms = int((time.monotonic() - t0) * 1000)
        delta = cap_today - cap_yest
        result.update({
            "captures_today":     cap_today,
            "captures_yesterday": cap_yest,
            "captures_delta":     f"{'▲ +' if delta >= 0 else '▼ '}{abs(delta)} vs yest",
            "captures_direction": "up" if delta >= 0 else "down",
            "open_tasks":         open_t,
            "overdue_tasks":      overdue_t,
            "active_flags":       flags_now,
            "flags_last_week":    flags_prev,
            "backend_ok":         True,
            "backend_latency_ms": latency_ms,
        })
    except Exception:
        print(f"[db] get_kpis error:\n{traceback.format_exc()}")
    return result


# ── Brewing items ─────────────────────────────────────────────────────────────

def get_brewing_items(window_days: int = 14, min_count: int = 2, limit: int = 5) -> list[dict]:
    """
    Return high-priority entities with recent flag/incident activity.

    Reads from brewing_items_v view (pre-filtered to 14-day window, >= 2 flags).
    The view already handles flag/incident detection and priority scoring;
    we simply apply client-side limit filtering and map to the expected contract:
      - title: "{entity_display_name} — {flag_count} {'flags'|'flag'} in 14 days"
      - excerpt: sample_excerpt
      - priority: the view's priority column (already 'urgent'/'high'/'normal')

    Note: window_days and min_count params are preserved for backward compat but
    the view is hard-coded to 14 days. To filter by a different window, you'd need
    to apply client-side post-filtering or update the view definition.
    """
    try:
        res = (
            get_client()
            .table("brewing_items_v")
            .select("entity_display_name, flag_count, sample_excerpt, priority")
            .limit(limit)
            .execute()
        )
        rows = res.data or []

        brewing = [
            {
                "title":    f"{r['entity_display_name']} — {r['flag_count']} {'flags' if r['flag_count'] != 1 else 'flag'} in 14 days",
                "excerpt":  r.get("sample_excerpt", ""),
                "priority": r.get("priority", "normal"),
            }
            for r in rows
        ]
        return brewing
    except Exception:
        print(f"[db] get_brewing_items error:\n{traceback.format_exc()}")
        return []


# ── Page summary ──────────────────────────────────────────────────────────────

def get_today_summary() -> str:
    try:
        kpis    = get_kpis()
        open_t  = kpis["open_tasks"]
        overdue = kpis["overdue_tasks"]
        flags   = kpis["active_flags"]
        overdue_str = f", {overdue} overdue" if overdue > 0 else ""
        flags_str   = f", {flags} active flag{'s' if flags != 1 else ''}" if flags > 0 else ""
        return f"{open_t} open task{'s' if open_t != 1 else ''}{overdue_str}{flags_str}."
    except Exception:
        return "Loading…"


# ── Writes ────────────────────────────────────────────────────────────────────

def save_floor_walk(
    ok_areas: list[str],
    flags: list[dict],
    duration_min: int,
    skipped_count: int = 0,
) -> bool:
    """
    Save a completed floor walk to the notes table.
    ok_areas: list of area names that were checked OK.
    flags:    list of {name, note} dicts for flagged areas.
    duration_min: duration in minutes.
    skipped_count: number of areas skipped.
    Returns True on success.
    """
    try:
        import uuid
        total   = len(ok_areas) + len(flags) + skipped_count
        checked = len(ok_areas)

        flag_lines = [f"  ⚑ {f['name']}: {f['note']}" for f in flags] if flags else ["  None"]
        ok_sample  = ", ".join(ok_areas[:6]) + ("…" if len(ok_areas) > 6 else "")

        summary_parts = [
            f"Floor Walk — {checked}/{total} areas checked, "
            f"{len(flags)} flag{'s' if len(flags) != 1 else ''}",
        ]
        if skipped_count > 0:
            summary_parts.append(f", {skipped_count} skipped")
        summary_parts.append(f". Duration: ~{duration_min} min.")

        content_parts = ["".join(summary_parts)]
        if flags:
            content_parts.append("Flags:")
            content_parts.extend(flag_lines)
        if ok_areas:
            content_parts.append(f"OK: {ok_sample}")

        note = {
            "id":           f"note_{uuid.uuid4().hex[:12]}",
            "content":      "\n".join(content_parts),
            "content_type": "floor_walk",
            "sentiment":    "flag" if flags else "positive",
            "original_date": date.today().isoformat(),
            "author":       "brian",
            "captured_via": "dashboard",
            "metadata": {
                "checked": checked,
                "total":   total,
                "flags":   flags,
                "skipped": skipped_count,
                "duration_min": duration_min,
            },
        }
        get_client().table("notes").insert(note).execute()

        # Also save individual flag entries so they appear in the feed
        for f in flags:
            get_client().table("notes").insert({
                "id":           f"note_{uuid.uuid4().hex[:12]}",
                "content":      f"{f['name']}: {f['note']}",
                "content_type": "flag",
                "sentiment":    "flag",
                "original_date": date.today().isoformat(),
                "author":       "brian",
                "captured_via": "dashboard",
            }).execute()

        return True
    except Exception:
        print(f"[db] save_floor_walk error:\n{traceback.format_exc()}")
        return False


def save_note(note: dict) -> bool:
    """Insert a new note. Returns True on success."""
    try:
        get_client().table("notes").insert(note).execute()
        return True
    except Exception:
        print(f"[db] save_note error:\n{traceback.format_exc()}")
        return False


def get_people() -> list[dict]:
    """
    Return all active TMs sorted by skill_score desc, then name.
    Extracts badge flags, score tier, and last observation reason
    from entity metadata for display on the People page.
    """
    try:
        res = (
            get_client()
            .table("entities")
            .select("id, name, metadata")
            .eq("entity_type", "tm")
            .neq("id", "tm_grave_shift")
            .execute()
        )
        rows = res.data or []

        seen_ids: set = set()
        people = []

        for r in rows:
            tm_id = r.get("id", "")
            if not tm_id or tm_id in seen_ids:
                continue
            seen_ids.add(tm_id)

            full_name = (r.get("name") or "").strip()
            meta = r.get("metadata") or {}
            if not isinstance(meta, dict):
                meta = {}

            # display_name is stored in metadata; fall back to first word of full name
            name = (meta.get("display_name") or full_name.split()[0] if full_name else "").strip()
            if not name:
                continue

            raw_score = meta.get("skill_score") or 5
            skill_score = float(raw_score)
            score_label = f"{skill_score:g}"   # 7.0 → "7", 7.5 → "7.5"

            if skill_score >= 8:
                score_tier = "top"
            elif skill_score >= 6:
                score_tier = "solid"
            elif skill_score >= 5:
                score_tier = "standard"
            else:
                score_tier = "developing"

            # Most recent score-change note
            history = meta.get("score_history") or []
            last_reason = ""
            if history and isinstance(history, list):
                reason = (history[-1].get("reason") or "").replace("Brian: ", "").strip()
                last_reason = reason[:90]

            # Accommodation flags
            accommodations = meta.get("accommodations") or []
            has_no_sweeper = (
                meta.get("legacy_slot_preference") == "no_sweeper"
                or any(
                    a.get("type") == "physical" and "sweeper" in (a.get("target") or "")
                    for a in accommodations
                )
            )
            has_am_only = any(
                a.get("type") == "am_overlap_only"
                for a in accommodations
            )

            # Restroom preference
            prefs = meta.get("preferences") or []
            has_rr_pref = (
                meta.get("legacy_slot_preference") == "restroom"
                or any(
                    "restroom" in (p.get("target") or "").lower()
                    or "restroom" in (p.get("note") or "").lower()
                    for p in prefs
                )
            )

            # Trainer flag from any score-history reason mentioning "trainer"
            is_trainer = any(
                "trainer" in (h.get("reason") or "").lower()
                for h in history
            )

            status = (meta.get("status") or "active").strip()
            active = status not in ("separated", "inactive")
            rank   = int(meta.get("tie_break_rank") or 99)

            people.append({
                "id":             tm_id,
                "name":           name,        # display name ("Abby")
                "first_name":     name,        # alias — card uses first_name key
                "full_name":      full_name,   # legal name ("Abagail Slovak Banks")
                "skill_score":    skill_score,
                "score_label":    score_label,
                "score_tier":     score_tier,
                "last_reason":    last_reason,
                "has_no_sweeper": has_no_sweeper,
                "has_am_only":    has_am_only,
                "has_rr_pref":    has_rr_pref,
                "is_trainer":     is_trainer,
                "status":         status,
                "active":         active,
                "rank":           rank,
                # Phase O — surface shift assignment for the People page filter.
                # grave_pool is the canonical metadata field — "Grave" / "PM" / "AM" / "Other".
                "grave_pool":     (meta.get("grave_pool") or "").strip(),
            })

        people.sort(key=lambda p: (-p["skill_score"], p["name"]))
        return people

    except Exception:
        print(f"[db] get_people error:\n{traceback.format_exc()}")
        return []


# Content types that belong in operational shift views (recap, floor walk, today).
# Reference / dispatch entries are surfaced on the Logs page instead.
_OPERATIONAL_TYPES = frozenset([
    "observation", "kudos", "flag", "incident",
    "callout", "beo", "floor_walk", "huddle", "shift_recap",
])

# Mapping used by the Logs page type-filter tabs
_LOG_TYPE_GROUPS: dict[str, list[str]] = {
    "observations": ["observation", "floor_walk", "huddle", "callout", "beo", "shift_recap"],
    "flags":        ["flag", "incident"],
    "kudos":        ["kudos"],
    "reference":    ["reference", "dispatch", "request", "feedback"],
}


def get_logs(
    type_filter: str = "all",
    days_back: int = 7,
    search: str = "",
    limit: int = 80,
) -> list[dict]:
    """
    Return notes for the Logs page.
    type_filter: "all" | "observations" | "flags" | "kudos" | "reference"
    days_back:   0 = all time, otherwise only notes >= today - days_back
    search:      case-insensitive substring match on content
    """
    try:
        sb = get_client()
        q = sb.table("notes").select(
            "id, content, content_type, sentiment, original_date, captured_at"
        ).eq("archived", False)

        if type_filter != "all" and type_filter in _LOG_TYPE_GROUPS:
            q = q.in_("content_type", _LOG_TYPE_GROUPS[type_filter])

        if days_back > 0:
            cutoff = (date.today() - timedelta(days=days_back)).isoformat()
            q = q.gte("original_date", cutoff)

        # Simple search: Supabase ilike on content column
        if search.strip():
            q = q.ilike("content", f"%{search.strip()}%")

        res = q.order("original_date", desc=True).order("captured_at", desc=True).limit(limit).execute()

        items = []
        for r in (res.data or []):
            ct = r.get("content_type", "observation")
            icon, _ = _ICON_MAP.get(ct, ("·", ""))
            full_text = (r.get("content") or "").strip()
            # Truncate long entries — reference/dispatch can be enormous
            display_text = full_text[:300] + ("…" if len(full_text) > 300 else "")
            items.append({
                "id":            r["id"],
                "text":          display_text,
                "note_type":     ct,
                "icon":          icon,
                "ts":            r.get("original_date") or r.get("captured_at") or "",
                "timestamp_display": _format_ts(
                    r.get("captured_at") or r.get("original_date")
                ),
            })
        return items
    except Exception:
        print(f"[db] get_logs error:\n{traceback.format_exc()}")
        return []


def get_shift_timeline(shift_date: str) -> list[dict]:
    """
    Return OPERATIONAL notes logged on shift_date (sorted chronologically).
    Reference, dispatch, and other non-operational types are excluded —
    those belong on the Logs page.
    """
    try:
        res = (
            get_client()
            .table("notes")
            .select("id, content, content_type, sentiment, original_date, captured_at")
            .eq("original_date", shift_date)
            .eq("archived", False)
            .in_("content_type", list(_OPERATIONAL_TYPES))
            .order("captured_at", desc=False)
            .execute()
        )
        items = []
        for r in (res.data or []):
            ct = r.get("content_type", "observation")
            icon, _ = _ICON_MAP.get(ct, ("·", ""))
            items.append({
                "id":          r["id"],
                "text":        r.get("content") or "",
                "note_type":   ct,
                "icon":        icon,
                "ts":          r.get("captured_at") or r.get("original_date") or "",
                "timestamp_display": _format_ts(
                    r.get("captured_at") or r.get("original_date")
                ),
            })
        return sorted(items, key=lambda x: x.get("ts", ""))
    except Exception:
        print(f"[db] get_shift_timeline error:\n{traceback.format_exc()}")
        return []


# ── AREA CHECKS (Phase M) ─────────────────────────────────────────────────────
# Quick spot-check ratings the supervisor logs while walking the floor.
# Each row scores an area (zone/RR/aux) 1-10 and links to the TM assigned
# at check time. Powers the Areas + People history views and feeds Grok.

# Canonical area list — used by the Quick Area Check overlay's picker.
AREA_CHECK_AREAS: list[dict] = [
    # Zones
    {"key": "zone_1",  "label": "Zone 1",  "side": ""},
    {"key": "zone_2",  "label": "Zone 2",  "side": ""},
    {"key": "zone_3",  "label": "Zone 3",  "side": ""},
    {"key": "zone_4",  "label": "Zone 4",  "side": ""},
    {"key": "zone_5",  "label": "Zone 5",  "side": ""},
    {"key": "zone_6",  "label": "Zone 6",  "side": ""},
    {"key": "zone_7",  "label": "Zone 7",  "side": ""},
    {"key": "zone_8",  "label": "Zone 8",  "side": ""},
    {"key": "zone_9",  "label": "Zone 9",  "side": ""},
    {"key": "zone_10", "label": "Zone 10", "side": ""},
    # Restrooms — separate row per side
    {"key": "rr_1_2",  "label": "RR 1+2 Mens",   "side": "mens"},
    {"key": "rr_1_2",  "label": "RR 1+2 Women's","side": "womens"},
    {"key": "rr_6",    "label": "RR 6 Mens",     "side": "mens"},
    {"key": "rr_6",    "label": "RR 6 Women's",  "side": "womens"},
    {"key": "rr_7",    "label": "RR 7 Mens",     "side": "mens"},
    {"key": "rr_7",    "label": "RR 7 Women's",  "side": "womens"},
    {"key": "rr_8",    "label": "RR 8 Mens",     "side": "mens"},
    {"key": "rr_8",    "label": "RR 8 Women's",  "side": "womens"},
    {"key": "rr_10",   "label": "RR 10 Mens",    "side": "mens"},
    {"key": "rr_10",   "label": "RR 10 Women's", "side": "womens"},
    # Auxiliary
    {"key": "z9_sr",     "label": "Z9 SR",     "side": ""},
    {"key": "admin",     "label": "Admin",     "side": ""},
    {"key": "trash_1",   "label": "Trash 1",   "side": ""},
    {"key": "trash_2",   "label": "Trash 2",   "side": ""},
    {"key": "support_1", "label": "MP 1",      "side": ""},
    {"key": "support_2", "label": "MP 2",      "side": ""},
    {"key": "support_3", "label": "Support 3", "side": ""},
]


def fetch_assigned_tm_for_area(area_key: str, rr_side: str, night_date: str) -> dict:
    """Look up the TM currently assigned to an area on a given night date.

    Walks: nights(night_date=X) → zone_assignments(area_key, rr_side) → entities.
    Returns {tm_id, display_name, slot_id} or empty dict if unfilled / no night.
    """
    try:
        sb = get_client()
        n_res = sb.table("nights").select("id").eq("night_date", night_date).limit(1).execute()
        nights = n_res.data or []
        if not nights:
            return {}
        night_id = nights[0]["id"]

        # zone_assignments query — filter by slot_key always; rr_side only if provided
        q = (
            sb.table("zone_assignments")
            .select("id, tm_id, entities(display_name)")
            .eq("night_id", night_id)
            .eq("slot_key", area_key)
        )
        if rr_side:
            q = q.eq("rr_side", rr_side)
        else:
            q = q.is_("rr_side", "null")
        za_res = q.limit(1).execute()
        rows = za_res.data or []
        if not rows:
            return {}
        row = rows[0]
        tm_id = row.get("tm_id") or ""
        ent = row.get("entities") or {}
        return {
            "tm_id":        tm_id,
            "display_name": ent.get("display_name", "") if tm_id else "",
            "slot_id":      row.get("id", ""),
        }
    except Exception as e:
        print(f"[fetch_assigned_tm_for_area] {e}")
        return {}


def insert_area_check(
    area_key: str,
    rr_side: str,
    score: int,
    tm_id: str = "",
    note: str = "",
    night_date: str = "",
) -> bool:
    """Insert a single area check row. Returns True on success."""
    if not area_key or not (1 <= int(score) <= 10):
        return False
    try:
        from datetime import date as _date
        sb = get_client()
        payload = {
            "area_key":   area_key,
            "rr_side":    rr_side or None,
            "score":      int(score),
            "tm_id":      tm_id or None,
            "note":       (note or "").strip() or None,
            "night_date": night_date or _date.today().isoformat(),
        }
        sb.table("area_checks").insert(payload).execute()
        return True
    except Exception as e:
        print(f"[insert_area_check] {e}")
        return False


def fetch_recent_area_checks(limit: int = 20) -> list[dict]:
    """Return recent area checks across all areas/TMs, newest first.
    Each row joined with entities for display_name."""
    try:
        sb = get_client()
        res = (
            sb.table("area_checks")
            .select("area_key, rr_side, score, night_date, note, created_at, entities(display_name)")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        out = []
        for r in (res.data or []):
            ent = r.get("entities") or {}
            out.append({
                "area_key":     r.get("area_key", ""),
                "rr_side":      r.get("rr_side") or "",
                "score":        int(r.get("score", 0)),
                "night_date":   r.get("night_date", ""),
                "note":         r.get("note") or "",
                "created_at":   r.get("created_at", ""),
                "tm_name":      ent.get("display_name", ""),
            })
        return out
    except Exception as e:
        print(f"[fetch_recent_area_checks] {e}")
        return []


def _join_names(names: list[str]) -> str:
    """English-style list join: ['A','B','C'] → 'A, B, and C'.

    Used by the recap auto-populate to build readable lines like
    'Barbie, Mary, and Sue on PTO.'
    """
    cleaned = [n for n in (s.strip() for s in names or []) if n]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"


def get_recap_auto_populate(shift_date: str) -> dict:
    """Phase L.2 — Pull all the Supabase-backed data we can use to pre-fill
    sections of the morning shift recap.

    Returns a dict of section -> pre-formatted multi-line string. Empty
    strings mean "no data" and the caller should leave the section as-is.

        {
          "team_graves":     "...",  # call_offs joined to entities
          "team_beos":       "...",  # captures with content_type 'beo'
          "overlap_graves":  "...",  # overlap_assignments joined to entities + tasks
          "floor_walk_notes":"...",  # captures with content_type 'observation'/'floor_walk'
        }
    """
    out = {
        "team_days":        "",
        "team_swings":      "",
        "team_graves":      "",
        "team_beos":        "",
        "overlap_graves":   "",
        "floor_walk_notes": "",
    }
    try:
        sb = get_client()

        # ── Call-offs (any shift) on this date ───────────────────────────────
        co_res = (
            sb.table("call_offs")
            .select("reason, entities(display_name)")
            .eq("night_date", shift_date)
            .execute()
        )
        call_off_names: list[tuple[str, str]] = []
        for row in (co_res.data or []):
            ent = row.get("entities") or {}
            name = ent.get("display_name", "")
            reason = (row.get("reason") or "").strip()
            if name:
                call_off_names.append((name, reason))

        # ── Per-shift PTO/MDL from the linked weekly schedule xlsx ───────────
        # Pulls the latest schedule from local Inputs (or Storage), parses
        # all three sheets, returns who's PTO/MDL on this exact date.
        # Returns empty buckets if no schedule is loaded — that's fine,
        # the recap still gets the call-off info merged below.
        rosters: dict = {
            "days":   {"working": [], "pto": [], "mdl": [], "other": []},
            "swings": {"working": [], "pto": [], "mdl": [], "other": []},
            "graves": {"working": [], "pto": [], "mdl": [], "other": []},
        }
        try:
            from apps.zds import schedule_parser, database as zds_db
            path = schedule_parser.get_latest_schedule_path()
            if path:
                # Pull entities so the resolver can map xlsx legal names
                # (Stephen, Christopher, …) to entity nicknames (Steve, Chris)
                # via metadata.aliases.
                try:
                    ents = zds_db.fetch_all_tms()
                except Exception:
                    ents = []
                rosters = schedule_parser.peek_shift_rosters_for_date(
                    path, shift_date, entities=ents,
                ) or rosters
        except Exception as exc:
            print(f"[recap.shift_rosters] {exc}")

        # Merge call-offs (which we don't tag by shift yet) with PTO/MDL.
        # Heuristic: a TM's call-off applies to whichever shift they're
        # SCHEDULED on for this date. If they appear on multiple shift's
        # rosters (rare), they get listed under each.
        co_by_shift: dict[str, list[str]] = {"days": [], "swings": [], "graves": []}
        unmatched_callouts: list[str] = []
        for name, reason in call_off_names:
            placed = False
            for shift in ("days", "swings", "graves"):
                # Match by display_name appearing in any roster bucket
                bucket_names = (
                    rosters[shift]["working"]
                    + rosters[shift]["pto"]
                    + rosters[shift]["mdl"]
                )
                if any(name.startswith(bn.split()[0]) or bn.startswith(name.split()[0])
                       for bn in bucket_names):
                    suffix = f" ({reason})" if reason else ""
                    co_by_shift[shift].append(f"{name} called off{suffix}.")
                    placed = True
                    break
            if not placed:
                suffix = f" ({reason})" if reason else ""
                unmatched_callouts.append(f"{name} called off{suffix}.")

        # Assemble per-shift summary string. Format mirrors Brian's email:
        #   "Auggie called off."
        #   "Michelle B is off, Barbie and Mary on PTO"
        def _fmt_shift(shift: str) -> str:
            lines: list[str] = []
            lines.extend(co_by_shift[shift])
            pto = rosters[shift]["pto"]
            mdl = rosters[shift]["mdl"]
            other = rosters[shift]["other"]
            if pto:
                lines.append(_join_names(pto) + " on PTO.")
            if mdl:
                lines.append(_join_names(mdl) + " on MDL.")
            if other:
                lines.append(_join_names(other) + " unscheduled.")
            return " ".join(lines)

        out["team_days"]   = _fmt_shift("days")
        out["team_swings"] = _fmt_shift("swings")
        out["team_graves"] = _fmt_shift("graves")
        # If any call-off didn't match a roster, fall back into team_graves
        # (most common case for grave shift supervisor).
        if unmatched_callouts:
            tail = " ".join(unmatched_callouts)
            out["team_graves"] = (out["team_graves"] + " " + tail).strip()

        # ── Captures by content_type ─────────────────────────────────────────
        notes_res = (
            sb.table("notes")
            .select("content, content_type")
            .eq("original_date", shift_date)
            .eq("archived", False)
            .order("captured_at", desc=False)
            .execute()
        )
        beo_lines = []
        narrative_lines = []
        for n in (notes_res.data or []):
            ct = (n.get("content_type") or "").lower()
            text = (n.get("content") or "").strip()
            if not text:
                continue
            if ct == "beo":
                beo_lines.append(text)
            elif ct in ("observation", "floor_walk"):
                narrative_lines.append(text)
        if beo_lines:
            out["team_beos"] = ", ".join(beo_lines) + "."
        if narrative_lines:
            # Concatenate observations as a starting paragraph; Brian will polish.
            out["floor_walk_notes"] = "\n\n".join(narrative_lines)

        # ── Overlap assignments for the night with this date ─────────────────
        # Find the night row(s) for this shift_date, then pull their overlap_assignments.
        night_res = (
            sb.table("nights")
            .select("id")
            .eq("night_date", shift_date)
            .execute()
        )
        night_ids = [r["id"] for r in (night_res.data or [])]
        if night_ids:
            ov_res = (
                sb.table("overlap_assignments")
                .select("overlap_window, task, entities(display_name)")
                .in_("night_id", night_ids)
                .eq("is_filled", True)
                .order("position")
                .execute()
            )
            grave_overlap_rows = []
            for r in (ov_res.data or []):
                ent = r.get("entities") or {}
                name = ent.get("display_name", "")
                task = (r.get("task") or "").strip()
                if name and task:
                    grave_overlap_rows.append(f"  • {name} – {task}")
                elif name:
                    grave_overlap_rows.append(f"  • {name}")
            if grave_overlap_rows:
                out["overlap_graves"] = "\n".join(grave_overlap_rows)
    except Exception:
        print(f"[db] get_recap_auto_populate error:\n{traceback.format_exc()}")
    return out


def generate_shift_recap(shift_date: str) -> str:
    """
    Build a plain-text morning recap draft suitable for pasting into
    an email to Group - Operations Department.
    """
    try:
        from collections import defaultdict

        sb = get_client()

        # ── Notes ──────────────────────────────────────────────────────────────
        note_res = (
            sb.table("notes")
            .select("content, content_type")
            .eq("original_date", shift_date)
            .eq("archived", False)
            .order("captured_at", desc=False)
            .execute()
        )
        buckets: dict = defaultdict(list)
        for n in (note_res.data or []):
            ct = n.get("content_type", "observation")
            text = (n.get("content") or "").strip()
            if text:
                buckets[ct].append(text)

        # ── Completed tasks ────────────────────────────────────────────────────
        done_res = (
            sb.table("tasks")
            .select("title")
            .eq("status", "completed")
            .gte("completed_at", shift_date + "T00:00:00")
            .execute()
        )
        completed = [t.get("title", "") for t in (done_res.data or []) if t.get("title")]

        # ── Open tasks ─────────────────────────────────────────────────────────
        open_res = (
            sb.table("tasks")
            .select("title, priority, due_at")
            .in_("status", ["open", "in_progress"])
            .order("priority")
            .limit(10)
            .execute()
        )
        open_tasks = open_res.data or []

        # ── Format date ────────────────────────────────────────────────────────
        try:
            dt = datetime.strptime(shift_date, "%Y-%m-%d")
            date_str = dt.strftime("%A, %B %-d, %Y")
        except Exception:
            date_str = shift_date

        # ── Build text ─────────────────────────────────────────────────────────
        def section(title: str, items: list, empty_msg: str = "None.") -> list:
            out = [title, "-" * len(title)]
            if items:
                for item in items:
                    out.append(f"  • {item}")
            else:
                out.append(f"  {empty_msg}")
            out.append("")
            return out

        lines: list = [
            f"GRAVE SHIFT RECAP  —  {date_str}",
            f"Supervisor: Brian Killian  |  Internal Maintenance",
            "=" * 52,
            "",
        ]

        lines += section(
            "CALL-OUTS / COVERAGE CHANGES",
            buckets.get("callout", []),
            "No call-outs reported.",
        )
        lines += section(
            "BEOs / SPECIAL EVENTS",
            buckets.get("beo", []),
            "None.",
        )
        lines += section(
            "FLOOR OBSERVATIONS",
            buckets.get("floor_walk", []) + buckets.get("observation", []),
            "No observations logged this shift.",
        )
        kudos = buckets.get("kudos", [])
        if kudos:
            lines += section("RECOGNITION", kudos)
        flags = buckets.get("flag", []) + buckets.get("incident", [])
        if flags:
            lines += section("FLAGS / INCIDENTS", flags)
        lines += section(
            "TASKS COMPLETED THIS SHIFT",
            completed,
            "None marked complete.",
        )

        if open_tasks:
            lines.append("TASKS CARRYING FORWARD")
            lines.append("-" * 25)
            for t in open_tasks:
                due = t.get("due_at")
                due_str = f"  (due {due[:10]})" if due else ""
                lines.append(f"  • {t['title']}{due_str}")
            lines.append("")

        lines += ["─" * 52, "End of shift recap."]

        return "\n".join(lines)

    except Exception:
        print(f"[db] generate_shift_recap error:\n{traceback.format_exc()}")
        return f"[Error generating recap for {shift_date}]"


def get_tasks_flat(status_filter: str = "open") -> list[dict]:
    """
    Return tasks as a flat list interleaved with group-header sentinel rows.
    Every item (header or task) shares the same key set so rx.foreach can
    access any key without a KeyError.

    Header sentinel:  {"_type": "header", "name": <cat>, "count": "N", …nulls}
    Task row:         {"_type": "task", "id": …, "title": …, "name": "", …}
    """
    try:
        today_str = date.today().isoformat()
        sb = get_client()
        q = sb.table("tasks").select(
            "id, title, description, status, priority, due_at, "
            "category, created_at, completed_at"
        )

        if status_filter == "open":
            q = q.in_("status", ["open", "in_progress"])
        elif status_filter == "completed":
            q = q.eq("status", "completed")
        # "all" → no status filter

        res = q.execute()
        tasks = res.data or []

        priority_order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
        CAT_ORDER = {
            c: i for i, c in enumerate(
                ["HR", "Scheduling", "Parts", "Awareness", "Tasks", "Reminders"]
            )
        }

        for t in tasks:
            due = t.get("due_at")
            due_str = due[:10] if due else ""
            t["due_date"]    = due_str
            t["is_overdue"]  = bool(
                due_str and due_str < today_str
                and t.get("status") != "completed"
            )
            t["category"]    = t.get("category") or "Tasks"
            t["priority"]    = t.get("priority") or "normal"
            t["description"] = t.get("description") or ""
            t["status"]      = t.get("status") or "open"
            t["_type"]       = "task"
            t["name"]        = ""   # header-only field — blank on task rows
            t["count"]       = "0"  # header-only field — blank on task rows

        # Sort
        if status_filter == "completed":
            tasks.sort(key=lambda t: t.get("completed_at") or "", reverse=True)
        else:
            tasks.sort(key=lambda t: (
                CAT_ORDER.get(t["category"], 99),
                0 if t["is_overdue"] else 1,
                priority_order.get(t["priority"], 2),
                t.get("due_at") or "9999-12-31",
            ))

        # Group (dict insertion order preserved in Python 3.7+)
        groups: dict[str, list] = {}
        for t in tasks:
            cat = t["category"]
            groups.setdefault(cat, []).append(t)

        # Build flat list with header sentinels
        _EMPTY_TASK_FIELDS = dict(
            id="", title="", category="", priority="",
            due_date="", is_overdue=False, description="", status="",
            due_at=None, created_at=None, completed_at=None,
            is_collapsed=False,
        )
        flat: list[dict] = []
        for cat, cat_tasks in groups.items():
            flat.append({
                "_type": "header",
                "name":  cat,
                "count": str(len(cat_tasks)),
                **_EMPTY_TASK_FIELDS,
            })
            flat.extend(cat_tasks)

        return flat
    except Exception:
        print(f"[db] get_tasks_flat error:\n{traceback.format_exc()}")
        return []


def complete_task(task_id: str) -> bool:
    """Mark a task as completed."""
    try:
        from datetime import timezone
        now = datetime.now(timezone.utc).isoformat()
        get_client().table("tasks").update({
            "status":       "completed",
            "completed_at": now,
            "updated_at":   now,
        }).eq("id", task_id).execute()
        return True
    except Exception:
        print(f"[db] complete_task error:\n{traceback.format_exc()}")
        return False


def create_task(
    title:       str,
    category:    str = "Tasks",
    priority:    str = "normal",
    due_date:    str = "",      # ISO date string "YYYY-MM-DD", or ""
    description: str = "",
) -> bool:
    """Insert a new task row.  Returns True on success."""
    try:
        import uuid
        from datetime import timezone
        now      = datetime.now(timezone.utc).isoformat()
        task_id  = f"task_{uuid.uuid4().hex[:12]}"
        due_at   = (due_date + "T23:59:00") if due_date else None
        row: dict = {
            "id":          task_id,
            "title":       title.strip(),
            "description": description.strip(),
            "category":    category,
            "priority":    priority,
            "status":      "open",
            "source":      "dashboard",
            "created_at":  now,
            "updated_at":  now,
        }
        if due_at:
            row["due_at"] = due_at
        get_client().table("tasks").insert(row).execute()
        return True
    except Exception:
        print(f"[db] create_task error:\n{traceback.format_exc()}")
        return False


def update_task_priority(task_id: str, priority: str) -> bool:
    """Update the priority of a single task."""
    try:
        from datetime import timezone
        now = datetime.now(timezone.utc).isoformat()
        get_client().table("tasks").update({
            "priority":   priority,
            "updated_at": now,
        }).eq("id", task_id).execute()
        return True
    except Exception:
        print(f"[db] update_task_priority error:\n{traceback.format_exc()}")
        return False


def get_tm_notes(tm_name: str, limit: int = 30) -> list[dict]:
    """
    Return the most recent notes that mention a TM by name.
    Used by the TM profile drawer.
    """
    try:
        pat = f"%{tm_name.strip()}%"
        res = (
            get_client()
            .table("notes")
            .select("id, content, content_type, sentiment, original_date, captured_at")
            .eq("archived", False)
            .ilike("content", pat)
            .order("original_date", desc=True)
            .order("captured_at", desc=True)
            .limit(limit)
            .execute()
        )
        items = []
        for r in (res.data or []):
            ct      = r.get("content_type", "observation")
            icon, _ = _ICON_MAP.get(ct, ("·", ""))
            ts      = r.get("original_date") or r.get("captured_at") or ""
            text    = (r.get("content") or "").strip()
            items.append({
                "id":                r["id"],
                "text":              text,
                "note_type":         ct,
                "icon":              icon,
                "ts":                ts,
                "timestamp_display": _format_ts(ts),
            })
        return items
    except Exception:
        print(f"[db] get_tm_notes error:\n{traceback.format_exc()}")
        return []


# ── Search ────────────────────────────────────────────────────────────────────



def search_all(
    query: str,
    kind_filter: str = "all",   # "all" | "notes" | "tasks" | "people"
    limit: int = 40,
) -> list[dict]:
    """
    Full-text search across notes, tasks, and entities (TMs).
    Uses the hybrid search RPC which combines FTS + vector similarity.

    Returns a unified list of result dicts (kind, id, title, excerpt,
    type_label, ts, timestamp_display, icon, score).
    """
    q = query.strip()
    if len(q) < 2:
        return []

    # Map UI kind_filter to RPC kind values
    # RPC expects: null (all), "note", "task", "entity"
    kind_map = {
        "all":    None,
        "notes":  "note",
        "tasks":  "task",
        "people": "entity",
    }
    rpc_kind = kind_map.get(kind_filter, None)

    try:
        sb = get_client()
        # Call the RPC: search_hybrid_text(q, k, filter_kind, filter_content_type, use_vec, log_query)
        rpc_res = sb.rpc(
            "search_hybrid_text",
            {
                "q": q,
                "k": limit,
                "filter_kind": rpc_kind,
                "filter_content_type": None,
                "use_vec": True,
                "log_query": True,
            },
        ).execute()

        rpc_rows = rpc_res.data or []
        results: list[dict] = []

        for r in rpc_rows:
            kind = r.get("kind", "note")  # note | entity | event | task | file
            result_id = r.get("id", "")
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            score = r.get("score", 0.0)
            source_ref = r.get("source_ref")
            metadata = r.get("metadata") or {}

            # Derive type_label from kind + metadata.content_type
            if kind == "note":
                content_type = metadata.get("content_type", "observation")
                type_label = content_type.replace("_", " ")
                icon, _ = _ICON_MAP.get(content_type, ("·", ""))
            elif kind == "entity":
                # For entity (TM), pull skill score from metadata
                skill_score = float(metadata.get("skill_score") or 5)
                type_label = f"score {skill_score:g}"
                icon = "◍"
            elif kind == "task":
                status = metadata.get("status", "open")
                priority = metadata.get("priority", "normal")
                type_label = f"{status}  ·  {priority}"
                icon = "☐"
            elif kind == "event":
                event_type = metadata.get("event_type", "event")
                type_label = event_type.replace("_", " ")
                icon, _ = _ICON_MAP.get(event_type, ("·", ""))
            else:
                type_label = kind
                icon = "·"

            # Extract timestamp from metadata.captured_at, metadata.original_date, or metadata.created_at
            ts = (
                metadata.get("captured_at")
                or metadata.get("original_date")
                or metadata.get("created_at")
                or ""
            )

            # Build timestamp display
            timestamp_display = _format_ts(ts)

            # For entities (people), use the skill score as timestamp display
            if kind == "entity":
                skill_score = float(metadata.get("skill_score") or 5)
                timestamp_display = f"{skill_score:g}"

            results.append({
                "kind": kind if kind != "entity" else "person",  # Normalize "entity" → "person"
                "id": result_id,
                "title": title,
                "excerpt": snippet,
                "type_label": type_label,
                "ts": ts,
                "timestamp_display": timestamp_display,
                "icon": icon,
                "score": score,
            })

        return results[:limit]

    except Exception:
        print(f"[db] search_all error:\n{traceback.format_exc()}")
        return []


# ── Eligibility / TM Profile ──────────────────────────────────────────────────

# Canonical slot order (matches Eligibility Roster.xlsx column order)
ELIGIBILITY_SLOTS: list[str] = [
    "Zone 1", "Zone 2", "Zone 3", "Zone 4", "Zone 5",
    "Zone 6", "Zone 7", "Zone 8", "Zone 9", "Zone 10", "Zone 9 SR",
    "Mens 1 + 2", "Mens 6", "Mens 7", "Mens 8", "Mens 10",
    "Womens 1 + 2", "Womens 6", "Womens 7", "Womens 8", "Womens 10",
    "Trash 1", "Trash 2", "Admin", "MP 1", "MP 2", "PM OL", "AM OL",
]

SLOT_GROUPS: dict[str, list[str]] = {
    "Zones":         ["Zone 1","Zone 2","Zone 3","Zone 4","Zone 5",
                      "Zone 6","Zone 7","Zone 8","Zone 9","Zone 10","Zone 9 SR"],
    "Men's RR":      ["Mens 1 + 2","Mens 6","Mens 7","Mens 8","Mens 10"],
    "Women's RR":    ["Womens 1 + 2","Womens 6","Womens 7","Womens 8","Womens 10"],
    "Support":       ["Admin","MP 1","MP 2","Trash 1","Trash 2","PM OL","AM OL"],
}

_ELIGIBILITY_CACHE: dict = {}   # {display_name: {slot: bool, ...}}  in-process cache


def _roster_path() -> str:
    # db.py lives at: .../GLCR/glcr_memory/dashboard/reflex/glcr_dashboard/db.py
    # 5 parents up = GLCR/  →  Rules/Eligibility Roster.xlsx
    return str(Path(__file__).parent.parent.parent.parent.parent /
               "Rules" / "Eligibility Roster.xlsx")


def get_eligibility_roster(force_reload: bool = False) -> dict:
    """
    Returns {display_name: {slot: bool, active: bool, tie_break_rank: int,
                            full_name: str, grave_pool: str}}
    Reads the Excel file once and caches the result in-process.
    """
    global _ELIGIBILITY_CACHE
    if _ELIGIBILITY_CACHE and not force_reload:
        return _ELIGIBILITY_CACHE
    try:
        import openpyxl
        wb  = openpyxl.load_workbook(_roster_path(), read_only=True, data_only=True)
        ws  = wb.active
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        # Row 1 (index 0 of rows) is the actual header row
        headers = [c for c in rows[0]]
        result: dict = {}
        for row in rows[1:]:
            if not row or not row[0]:
                continue
            r = dict(zip(headers, row))
            display = (r.get("Display Name") or "").strip()
            if not display:
                continue
            elig: dict = {
                "full_name":      (r.get("Employee Name") or "").strip(),
                "active":         r.get("Active", "N") == "Y",
                "grave_pool":     r.get("Grave Pool", ""),
                "tie_break_rank": int(r.get("Tie Break Rank") or 99),
            }
            for slot in ELIGIBILITY_SLOTS:
                elig[slot] = r.get(slot, "N") == "Y"
            result[display] = elig
        wb.close()
        _ELIGIBILITY_CACHE = result
        return result
    except Exception:
        print(f"[db] get_eligibility_roster error:\n{traceback.format_exc()}")
        return {}


def find_tm_id_by_name(name: str) -> str:
    """
    Returns the entity id for a TM whose name (case-insensitive) fuzzy matches.

    Uses pg_trgm (trigram similarity) via the % operator for fast pre-filter,
    then similarity() to rank results. Falls back to 3-pass ilike if RPC unavailable.

    Returns just the id (str) on success, empty string on miss.
    """
    if not name or not name.strip():
        return ""
    name_clean = name.strip()
    try:
        sb = get_client()
        # Try RPC call to pg_trgm-based search (if Workhorse created it)
        try:
            res = sb.rpc(
                "find_tm_by_trgm",
                {"search_name": name_clean}
            ).execute()
            if res.data and len(res.data) > 0:
                return res.data[0].get("id", "")
        except Exception:
            pass  # Fall through to ilike approach

        # Fallback: 3-pass ilike (exact, prefix, contains) — simple and reliable
        for pattern in [name_clean, f"{name_clean}%", f"%{name_clean}%"]:
            res = (
                sb.table("entities")
                .select("id")
                .eq("entity_type", "tm")
                .ilike("name", pattern)
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]["id"]

    except Exception:
        print(f"[db] find_tm_id_by_name error:\n{traceback.format_exc()}")

    return ""


def get_tm_full_profile(tm_id: str) -> dict:
    """
    Returns the complete TM profile dict, merging:
      - Supabase entity metadata (source of truth for score, accommodations, etc.)
      - Eligibility Roster.xlsx as the baseline for zone eligibility
      - Supabase metadata.eligibility overrides (if any)
    """
    try:
        res = (
            get_client()
            .table("entities")
            .select("id, name, metadata")
            .eq("id", tm_id)
            .single()
            .execute()
        )
        entity   = res.data or {}
        meta     = entity.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}

        full_name    = entity.get("name", "").strip()
        # display_name lives in metadata (e.g. "Abby"); fall back to first word of full name
        display_name = (meta.get("display_name") or full_name.split()[0] if full_name else "").strip()
        status       = meta.get("status", "active")
        skill_score  = float(meta.get("skill_score") or 5)

        # Eligibility: start with Excel baseline (keyed by display_name), apply Supabase overrides
        roster        = get_eligibility_roster()
        roster_entry  = roster.get(display_name, {})
        base_elig     = {s: roster_entry.get(s, False) for s in ELIGIBILITY_SLOTS}
        supa_elig     = meta.get("eligibility") or {}
        # Supabase overrides take precedence (only keys that are present)
        merged_elig   = {**base_elig, **{k: bool(v) for k, v in supa_elig.items()}}

        return {
            "id":              tm_id,
            "name":            display_name,
            "full_name":       full_name,
            "skill_score":     skill_score,
            "status":          status,
            "loa_note":        meta.get("loa_note", ""),
            "score_history":   meta.get("score_history") or [],
            "accommodations":  meta.get("accommodations") or [],
            "preferences":     meta.get("preferences") or [],
            "pair_affinities": meta.get("pair_affinities") or [],
            "eligibility":     merged_elig,
            "active_roster":   roster_entry.get("active", True),
            "tie_break_rank":  roster_entry.get("tie_break_rank", 99),
            "grave_pool":      roster_entry.get("grave_pool", "Grave"),
            # Phase O — first-name aliases used by the schedule parser to map
            # xlsx legal names to this entity's display_name.
            "aliases":         list(meta.get("aliases") or []),
        }
    except Exception:
        print(f"[db] get_tm_full_profile error:\n{traceback.format_exc()}")
        return {}


def update_tm_metadata(tm_id: str, updates: dict) -> bool:
    """
    Fetch current metadata for tm_id, shallow-merge updates, write back.
    Thread-safe for single-user; for concurrent use, use Postgres jsonb_set.
    """
    try:
        res     = get_client().table("entities").select("metadata").eq("id", tm_id).single().execute()
        current = (res.data or {}).get("metadata") or {}
        if not isinstance(current, dict):
            current = {}
        merged  = {**current, **updates}
        get_client().table("entities").update({"metadata": merged}).eq("id", tm_id).execute()
        return True
    except Exception:
        print(f"[db] update_tm_metadata error:\n{traceback.format_exc()}")
        return False


def update_tm_eligibility(tm_id: str, eligibility: dict) -> bool:
    """Save the full eligibility dict to metadata.eligibility in Supabase."""
    return update_tm_metadata(tm_id, {"eligibility": eligibility})


# ── Deployment Roster ─────────────────────────────────────────────────────────

def get_patterns_data(window_days: int = 30) -> dict:
    """
    Trend data for the Patterns page, pulled from Postgres views + direct queries.

    The Patterns page expects these top-level sections:
      - tm_trending_positive, tm_trending_negative, unresolved_topics, equipment_recurring
      - tm_no_recent_notes, capture_gaps, zero_result_searches
      - callouts, zone_flags, score_movers (legacy, still supported)

    Pulls from:
      - pattern_insights_v (multi-category view)
      - tm_recent_activity_v (for tm_no_recent_notes)
      - search_log table (for zero_result_searches)

    Any missing category from pattern_insights_v returns an empty list.
    """
    result: dict = {
        "callouts": [], "zone_flags": [], "score_movers": [],
        "tm_trending_positive": [], "tm_trending_negative": [],
        "unresolved_topics": [], "equipment_recurring": [],
        "tm_no_recent_notes": [], "capture_gaps": [], "zero_result_searches": [],
    }

    try:
        sb = get_client()

        # ── pattern_insights_v: Pull all categories ────────────────────────────
        insights_res = (
            sb.table("pattern_insights_v")
            .select("category, id, label, metric, metadata")
            .execute()
        )
        insights_rows = insights_res.data or []

        # Group by category
        by_category: dict = {}
        for r in insights_rows:
            cat = r.get("category", "")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(r)

        # Map each category to result; graceful fallback for missing categories
        category_map = {
            "tm_trending_positive":   "tm_trending_positive",
            "tm_trending_negative":   "tm_trending_negative",
            "unresolved_topics":      "unresolved_topics",
            "equipment_recurring":    "equipment_recurring",
            "callouts":               "callouts",
            "zone_flags":             "zone_flags",
            "score_movers":           "score_movers",
        }

        for src_cat, result_key in category_map.items():
            if src_cat in by_category:
                result[result_key] = by_category[src_cat]

        # ── tm_no_recent_notes: from tm_recent_activity_v ────────────────────
        activity_res = (
            sb.table("tm_recent_activity_v")
            .select("tm_id, display_name, note_count_30d")
            .eq("note_count_30d", 0)
            .limit(20)
            .execute()
        )
        result["tm_no_recent_notes"] = [
            {
                "id": r.get("tm_id", ""),
                "name": r.get("display_name", ""),
                "note_count": 0,
            }
            for r in (activity_res.data or [])
        ]

        # ── zero_result_searches: from search_log table directly ──────────────
        search_res = sb.rpc(
            "get_zero_hit_searches",
            {"limit_val": 10}
        ).execute()
        result["zero_result_searches"] = search_res.data or []

    except Exception as e:
        print(f"[db] get_patterns_data error:\n{traceback.format_exc()}")

    return result


def get_deployment_roster() -> list[dict]:
    """
    Return all TMs with their eligibility for every slot, formatted for the
    deployment grid.  Excel Roster.xlsx provides the baseline; Supabase
    metadata.eligibility overrides take precedence (same logic as
    get_tm_full_profile).

    Each row:
      id, name, rank, active, score, score_tier,
      cells: [{slot, group, eligible, tm_id}]   # fixed order = ELIGIBILITY_SLOTS
    """
    try:
        roster_data = get_eligibility_roster()   # {display_name: {...}}

        res = (
            get_client()
            .table("entities")
            .select("id, name, metadata")
            .eq("entity_type", "tm")
            .neq("id", "tm_grave_shift")
            .execute()
        )
        rows = res.data or []

        # slot → group lookup (built once)
        slot_group_map: dict[str, str] = {
            slot: group
            for group, slots in SLOT_GROUPS.items()
            for slot in slots
        }

        result: list[dict] = []
        seen: set = set()

        for r in rows:
            full_name = (r.get("name") or "").strip()
            tm_id     = r.get("id", "")
            if not tm_id or tm_id in seen:
                continue
            seen.add(tm_id)

            meta = r.get("metadata") or {}
            if not isinstance(meta, dict):
                meta = {}

            # display_name lives in metadata — this is the roster lookup key
            display_name = (meta.get("display_name") or full_name.split()[0] if full_name else "").strip()

            raw_score  = meta.get("skill_score") or 5
            skill_score = float(raw_score)
            if skill_score >= 8:
                tier = "top"
            elif skill_score >= 6:
                tier = "solid"
            elif skill_score >= 5:
                tier = "standard"
            else:
                tier = "developing"

            # Eligibility: Excel baseline (keyed by display_name) + Supabase overrides
            roster_entry = roster_data.get(display_name, {})
            base_elig    = {s: roster_entry.get(s, False) for s in ELIGIBILITY_SLOTS}
            meta_elig    = meta.get("eligibility") or {}
            if isinstance(meta_elig, dict):
                for slot, val in meta_elig.items():
                    if slot in base_elig:
                        base_elig[slot] = bool(val)

            active = bool(roster_entry.get("active", True))
            rank   = int(roster_entry.get("tie_break_rank") or 99)
            status = str(meta.get("status") or "active")

            # Flatten eligibility into top-level keys to avoid nested foreach in UI
            flat_elig = {f"elig_{slot}": base_elig.get(slot, False) for slot in ELIGIBILITY_SLOTS}

            row: dict = {
                "id":         tm_id,
                "name":       display_name,   # show name, e.g. "Abby"
                "rank":       rank,
                "rank_label": str(rank) if rank < 99 else "—",
                "active":     active,
                "status":     status,
                "score":      skill_score,
                "score_label": str(int(skill_score)) if skill_score == int(skill_score) else str(skill_score),
                "score_tier": tier,
            }
            row.update(flat_elig)
            result.append(row)

        result.sort(key=lambda x: (x["rank"], x["name"]))
        return result

    except Exception:
        print(f"[db] get_deployment_roster error:\n{traceback.format_exc()}")
        return []


# ── Health metrics ────────────────────────────────────────────────────────────

def get_health_metrics() -> dict:
    """
    Reads the singleton health_metrics_v view.
    Returns a dict with all health KPI columns or an empty dict on error.
    """
    try:
        res = get_client().table("health_metrics_v").select("*").single().execute()
        return res.data or {}
    except Exception:
        print(f"[db] get_health_metrics error:\n{traceback.format_exc()}")
        return {}


# ── Threads ───────────────────────────────────────────────────────────────────

def list_threads(limit: int = 50) -> list[dict]:
    """
    Return all threads (auto-grouped topics) sorted by last_active descending.
    """
    try:
        res = (
            get_client()
            .table("threads")
            .select("id, title, status, note_count, last_active, created_at")
            .order("last_active", desc=True)
            .limit(limit)
            .execute()
        )
        threads = res.data or []

        for t in threads:
            ts = t.get("last_active") or t.get("created_at") or ""
            t["last_active_relative"] = _format_ts(ts)
            t["note_count"] = t.get("note_count", 0)
            t["status"] = t.get("status", "active")

        return threads
    except Exception:
        print(f"[db] list_threads error:\n{traceback.format_exc()}")
        return []


def get_thread_notes(thread_id: str, limit: int = 20) -> list[dict]:
    """
    Return the notes linked to a thread via the thread_notes join table.
    """
    try:
        # Join through thread_notes to get the note details
        res = (
            get_client()
            .table("thread_notes")
            .select("note_id, created_at")
            .eq("thread_id", thread_id)
            .execute()
        )
        links = res.data or []

        # Fetch the actual note content for each linked note
        notes = []
        for link in links[:limit]:
            note_id = link.get("note_id", "")
            if not note_id:
                continue
            note_res = (
                get_client()
                .table("notes")
                .select("id, content, captured_at, content_type")
                .eq("id", note_id)
                .single()
                .execute()
            )
            if note_res.data:
                notes.append(note_res.data)

        return notes
    except Exception:
        print(f"[db] get_thread_notes error:\n{traceback.format_exc()}")
        return []


# ── Write-Ups (Progressive Discipline) ────────────────────────────────────────

def list_writeups(level_filter: str = "all") -> list[dict]:
    """
    Return write-up records (notes flagged as write_up with discipline_level metadata)
    sorted by original_date descending.

    level_filter: "all" | "verbal" | "written" | "final"
    """
    try:
        sb = get_client()
        # Notes with content_type write_up or sentiment flag (approximate match)
        res = (
            sb.table("notes")
            .select("id, content, original_date, metadata, captured_at")
            .eq("archived", False)
            .or_("content_type.eq.write_up,sentiment.eq.flag")
            .order("original_date", desc=True)
            .limit(100)
            .execute()
        )
        rows = res.data or []

        writeups = []
        for r in rows:
            meta = r.get("metadata") or {}
            if not isinstance(meta, dict):
                meta = {}

            # Filter by discipline_level if specified
            level = meta.get("discipline_level", "")
            if level_filter != "all" and level != level_filter:
                continue

            # Resolve TM name via note_entities join
            tm_name = "—"
            note_id = r.get("id", "")
            if note_id:
                try:
                    ne_res = (
                        sb.table("note_entities")
                        .select("entity_id")
                        .eq("note_id", note_id)
                        .limit(1)
                        .execute()
                    )
                    ne_rows = ne_res.data or []
                    if ne_rows:
                        entity_id = ne_rows[0].get("entity_id", "")
                        if entity_id:
                            ent_res = (
                                sb.table("entities")
                                .select("metadata")
                                .eq("id", entity_id)
                                .single()
                                .execute()
                            )
                            if ent_res.data:
                                ent_meta = ent_res.data.get("metadata") or {}
                                tm_name = ent_meta.get("display_name", "—")
                except Exception:
                    pass

            writeups.append({
                "id": note_id,
                "tm_display_name": tm_name,
                "original_date": r.get("original_date", ""),
                "content": r.get("content", ""),
                "discipline_level": level,
                "captured_at": r.get("captured_at", ""),
            })

        return writeups

    except Exception:
        print(f"[db] list_writeups error:\n{traceback.format_exc()}")
        return []


# ── Grok Conversations (Phase 5.2) ───────────────────────────────────────────

def list_recent_conversations(limit: int = 10) -> list[dict]:
    """
    Return recent Grok conversations from ai_messages table.
    Used by the conversation dropdown in the Grok panel.
    Returns [{id, last_message, ts}] ordered by recency.
    """
    try:
        sb = get_client()
        # Get unique conversation_ids with the most recent timestamp
        res = (
            sb.table("ai_messages")
            .select("conversation_id, content, created_at")
            .eq("role", "user")  # Only user messages have the query text
            .order("created_at", desc=True)
            .limit(limit * 2)  # Fetch extra to account for duplicates
            .execute()
        )
        rows = res.data or []

        # Group by conversation_id, keeping only the most recent
        seen: dict[str, dict] = {}
        for r in rows:
            conv_id = r.get("conversation_id", "")
            if conv_id and conv_id not in seen:
                content = r.get("content", "")
                # Truncate for display
                last_msg = content[:50] + ("…" if len(content) > 50 else "")
                ts = r.get("created_at", "")
                seen[conv_id] = {
                    "id": conv_id,
                    "last_message": last_msg,
                    "ts": ts,
                }

        return list(seen.values())[:limit]

    except Exception:
        print(f"[db] list_recent_conversations error:\n{traceback.format_exc()}")
        return []


def get_conversation_messages(conversation_id: str) -> list[dict]:
    """
    Fetch all messages for a conversation from ai_messages table.
    Returns [{role, content, tool_call?, tool_result?}] in order.
    """
    try:
        sb = get_client()
        res = (
            sb.table("ai_messages")
            .select("role, content, tool_call, tool_result, created_at")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)
            .execute()
        )
        rows = res.data or []

        messages = []
        for r in rows:
            msg = {
                "role": r.get("role", "user"),
            }
            if r.get("content"):
                msg["content"] = r["content"]
            if r.get("tool_call"):
                msg["tool_call"] = r["tool_call"]
            if r.get("tool_result"):
                msg["tool_result"] = r["tool_result"]
                # For tool messages, extract a summary
                result = r["tool_result"]
                if isinstance(result, dict):
                    msg["result_summary"] = result.get("count", result.get("summary", "ok"))
            messages.append(msg)

        return messages

    except Exception:
        print(f"[db] get_conversation_messages error:\n{traceback.format_exc()}")
        return []


# ── Areas page ────────────────────────────────────────────────────────────────

def list_areas_with_counts() -> list[dict]:
    """
    List all area entities with a count of notes linked in the last 30 days.
    Organizes by section for grid display.
    """
    try:
        sb = get_client()
        res = (
            sb.table("entities")
            .select("id, display_name, metadata")
            .eq("entity_type", "area")
            .eq("status", "active")
            .order("id")
            .execute()
        )
        rows = res.data or []

        # Fetch all note_entities for these area IDs in one query
        area_ids = [r["id"] for r in rows]
        cutoff = (date.today() - timedelta(days=30)).isoformat()

        note_link_res = (
            sb.table("note_entities")
            .select("entity_id")
            .in_("entity_id", area_ids)
            .execute()
        )
        note_links = note_link_res.data or []

        # Count notes per area
        counts_by_area = {}
        for link in note_links:
            eid = link.get("entity_id")
            counts_by_area[eid] = counts_by_area.get(eid, 0) + 1

        result = []
        for r in rows:
            area_id = r["id"]
            meta = r.get("metadata") or {}
            section = meta.get("section", "other")

            result.append({
                "id": area_id,
                "name": r.get("display_name", area_id),
                "section": section,
                "recent_count": counts_by_area.get(area_id, 0),
            })

        return result
    except Exception:
        print(f"[db] list_areas_with_counts error:\n{traceback.format_exc()}")
        return []


# ── Engine Data (ZDS fill engine) ────────────────────────────────────────────
#
# These helpers replace the Rules/*.json + Eligibility Roster.xlsx file reads
# that fill_engine.py previously did at startup. They return data shaped to
# exactly match what the old file reads produced so call-site changes in
# fill_engine.py are minimal.
#
# Slot-id vocabulary: the DB stores eligibility by engine slot codes (Zone1,
# MRR1, MP1, PMOL1…). fill_engine.py looks up eligibility by "roster column
# name" (Zone 1, Mens 1 + 2, MP 1, PM OL…). The mapping below bridges them.

_SLOT_ID_TO_ELIG_COL: dict[str, str] = {
    "Zone1":   "Zone 1",    "Zone2":  "Zone 2",   "Zone3":  "Zone 3",
    "Zone4":   "Zone 4",    "Zone5":  "Zone 5",   "Zone6":  "Zone 6",
    "Zone7":   "Zone 7",    "Zone8":  "Zone 8",   "Zone9":  "Zone 9",
    "Zone10":  "Zone 10",   "Zone9SR":"Zone 9 SR",
    "MRR1":    "Mens 1 + 2","MRR6":  "Mens 6",   "MRR7":   "Mens 7",
    "MRR8":    "Mens 8",    "MRR10": "Mens 10",
    "WRR1":    "Womens 1 + 2","WRR6":"Womens 6", "WRR7":   "Womens 7",
    "WRR8":    "Womens 8",  "WRR10": "Womens 10",
    "Trash1":  "Trash 1",   "Trash2":"Trash 2",
    "Admin":   "Admin",
    "MP1":     "MP 1",      "MP2":   "MP 2",
}
# PMOL/AMOL each have per-slot rows; the engine checks eligibility via the
# single "PM OL" / "AM OL" column names. Collapse: if ANY PMOL slot = eligible
# then "PM OL" = True (and same for AMOL).
_PMOL_SLOTS: frozenset = frozenset({"PMOL1","PMOL2","PMOL3","PMOL4","PMOL5","PMOL6"})
_AMOL_SLOTS: frozenset = frozenset({"AMOL1","AMOL2","AMOL3","AMOL4","AMOL5","AMOL6"})


def get_engine_roster_from_db() -> "tuple[dict, dict]":
    """
    Replace the openpyxl Eligibility Roster.xlsx read in fill_engine.py.

    Returns (roster, fn_lookup):
      roster:    {employee_name.lower(): {emp_name, display_name, pool, rank, eligibility}}
                 eligibility keys are roster column names ("Zone 1", "Mens 1 + 2", etc.)
      fn_lookup: {first_name.lower(): [roster_key, ...]}
    """
    try:
        sb = get_client()
        profiles_res = sb.table("tm_profiles").select(
            "tm_id, employee_name, display_name, active, grave_pool, tie_break_rank"
        ).eq("active", True).execute()
        profiles = profiles_res.data or []
        tm_ids = [p["tm_id"] for p in profiles]

        # Fetch eligibility for all active TMs in one query
        elig_res = (
            sb.table("tm_eligibility")
            .select("tm_id, slot_id, eligible")
            .in_("tm_id", tm_ids)
            .execute()
        )

        # Pivot eligibility into {tm_id: {elig_col_name: bool}}
        elig_by_tm: dict[str, dict] = {p["tm_id"]: {} for p in profiles}
        for row in (elig_res.data or []):
            tid = row["tm_id"]
            sid = row["slot_id"]
            val = bool(row["eligible"])
            if tid not in elig_by_tm:
                continue
            if sid in _PMOL_SLOTS:
                # Any PMOL eligible → TM is PM OL eligible
                if val:
                    elig_by_tm[tid]["PM OL"] = True
            elif sid in _AMOL_SLOTS:
                if val:
                    elig_by_tm[tid]["AM OL"] = True
            elif sid in _SLOT_ID_TO_ELIG_COL:
                elig_by_tm[tid][_SLOT_ID_TO_ELIG_COL[sid]] = val

        # Default ALL expected eligibility columns to False for any TM missing rows.
        # Some TMs may have sparse rows in tm_eligibility (new TMs, partial ingests).
        # The engine's elig() always returns False for missing keys anyway, but
        # explicit False is better than a silent miss for drift detection.
        _ALL_ELIG_COLS = (
            set(_SLOT_ID_TO_ELIG_COL.values())   # 26 slot columns
            | {"PM OL", "AM OL"}                  # overlap columns
        )
        for tid_map in elig_by_tm.values():
            for col in _ALL_ELIG_COLS:
                tid_map.setdefault(col, False)

        roster: dict = {}
        fn_lookup: dict = {}
        for p in profiles:
            emp  = (p.get("employee_name") or "").strip()
            disp = (p.get("display_name") or (emp.split()[0] if emp else "")).strip()
            pool = (p.get("grave_pool") or "Grave").strip()
            try:
                rank = int(p.get("tie_break_rank") or 999)
            except (TypeError, ValueError):
                rank = 999
            key = emp.lower()
            roster[key] = {
                "emp_name":    emp,
                "display_name": disp,
                "pool":        pool,
                "rank":        rank,
                "eligibility": elig_by_tm.get(p["tm_id"], {}),
            }
            fn_key = key.split()[0] if key else ""
            if fn_key:
                fn_lookup.setdefault(fn_key, []).append(key)

        return roster, fn_lookup
    except Exception:
        print(f"[db] get_engine_roster_from_db error:\n{traceback.format_exc()}")
        return {}, {}


def get_engine_profiles_from_db() -> dict:
    """
    Replace TM Profiles.json read(s) in fill_engine.py.

    Returns a dict shaped like the JSON file:
      {"profiles": {display_name: {skill_score, slot_preference, status,
                                   preferences, accommodations, pair_affinities}},
       "_meta": {...}}

    Fetches ALL TMs (not filtered by active) so the profile-drift check
    can detect separated/transferred TMs that still appear on the roster.
    """
    try:
        sb = get_client()
        profiles_res = sb.table("tm_profiles").select(
            "tm_id, display_name, skill_score, slot_preference, status"
        ).execute()
        profiles = profiles_res.data or []

        # Fetch detail tables in parallel (supabase-py is synchronous, so sequentially)
        prefs_res = sb.table("tm_preferences").select(
            "tm_id, stance, strength, target, note, added_date"
        ).execute()
        accs_res = sb.table("tm_accommodations").select(
            "tm_id, type, severity, target, note, added_date, status"
        ).execute()
        pairs_res = sb.table("tm_pair_affinities").select(
            "tm_id, with_tm_id, with_label, stance, strength, note, added_date"
        ).execute()

        # Index by tm_id
        prefs_by_tm: dict = {}
        for r in (prefs_res.data or []):
            prefs_by_tm.setdefault(r["tm_id"], []).append({
                "stance":      r.get("stance"),
                "strength":    r.get("strength"),
                "target":      r.get("target"),
                "note":        r.get("note"),
                "added_date":  str(r.get("added_date", "") or ""),
            })

        accs_by_tm: dict = {}
        for r in (accs_res.data or []):
            accs_by_tm.setdefault(r["tm_id"], []).append({
                "type":        r.get("type"),
                "severity":    r.get("severity"),
                "target":      r.get("target"),
                "note":        r.get("note"),
                "added_date":  str(r.get("added_date", "") or ""),
                "status":      r.get("status", "active"),
            })

        pairs_by_tm: dict = {}
        for r in (pairs_res.data or []):
            # "with" key matches the TM Profiles JSON structure the engine reads
            pairs_by_tm.setdefault(r["tm_id"], []).append({
                "with":       r.get("with_label") or r.get("with_tm_id") or "",
                "with_tm_id": r.get("with_tm_id"),
                "stance":     r.get("stance"),
                "strength":   r.get("strength"),
                "note":       r.get("note"),
                "added_date": str(r.get("added_date", "") or ""),
            })

        result_profiles: dict = {}
        for p in profiles:
            dn = (p.get("display_name") or "").strip()
            if not dn:
                continue
            tid = p["tm_id"]
            result_profiles[dn] = {
                "skill_score":     float(p.get("skill_score") or 5),
                "slot_preference": p.get("slot_preference"),
                "status":          p.get("status") or "active",
                "preferences":     prefs_by_tm.get(tid, []),
                "accommodations":  accs_by_tm.get(tid, []),
                "pair_affinities": pairs_by_tm.get(tid, []),
                # score_history / comments not needed by the engine
            }

        return {
            "profiles": result_profiles,
            "_meta": {"source": "supabase", "last_updated": date.today().isoformat()},
        }
    except Exception:
        print(f"[db] get_engine_profiles_from_db error:\n{traceback.format_exc()}")
        return {"profiles": {}, "_meta": {}}


def get_slot_difficulty() -> dict:
    """
    Replace Slot Difficulty.json read in fill_engine.py.
    Returns {"slots": {slot_id: {"difficulty": int, "notes": str}}}
    slot_id keys are engine codes (Zone1, MRR1, Admin, …).
    """
    try:
        res = (
            get_client()
            .table("slot_difficulty")
            .select("slot_id, difficulty, notes")
            .execute()
        )
        slots = {
            r["slot_id"]: {"difficulty": int(r["difficulty"]), "notes": r.get("notes") or ""}
            for r in (res.data or [])
        }
        return {"slots": slots}
    except Exception:
        print(f"[db] get_slot_difficulty error:\n{traceback.format_exc()}")
        return {"slots": {}}


def get_slot_load_scores() -> dict:
    """
    Replace Slot Load Scores.json read in fill_engine.py.
    Returns {"loads": {slot_id: int}, "sweeper_tag_bonus": int, "training_role_bonus": dict}
    """
    try:
        sb = get_client()
        loads_res = sb.table("slot_load_scores").select("slot_id, load").execute()
        config_res = (
            sb.table("slot_load_config")
            .select("sweeper_tag_bonus, training_role_bonus")
            .limit(1)
            .execute()
        )
        loads = {r["slot_id"]: int(r["load"]) for r in (loads_res.data or [])}
        cfg = (config_res.data or [{}])[0]
        return {
            "loads": loads,
            "sweeper_tag_bonus":   int(cfg.get("sweeper_tag_bonus") or 2),
            "training_role_bonus": cfg.get("training_role_bonus") or {"trainer": 1, "trainee": 1},
        }
    except Exception:
        print(f"[db] get_slot_load_scores error:\n{traceback.format_exc()}")
        return {"loads": {}, "sweeper_tag_bonus": 2, "training_role_bonus": {"trainer": 1, "trainee": 1}}


def get_scorecard_config() -> dict:
    """
    Replace Scorecard Weights.json read in fill_engine.py.
    Returns {"weights": {...}, "fatigue_index_window_days": int}
    """
    try:
        res = (
            get_client()
            .table("scorecard_config")
            .select("weights, fatigue_index_window_days")
            .eq("id", 1)
            .limit(1)
            .execute()
        )
        cfg = (res.data or [{}])[0]
        return {
            "weights":                  cfg.get("weights") or {},
            "fatigue_index_window_days": int(cfg.get("fatigue_index_window_days") or 7),
        }
    except Exception:
        print(f"[db] get_scorecard_config error:\n{traceback.format_exc()}")
        return {"weights": {}, "fatigue_index_window_days": 7}


def get_overlap_tasks_for_engine(target_date: "date | None" = None) -> dict:
    """
    Replace Overlap Tasks.json read in fill_engine.py.
    Returns {"PM": {slot_id: task_str}, "AM": {slot_id: task_str}}
    Merges canonical tasks with per-date overrides (overrides win on same slot).
    target_date: if provided, applies overlap_task_overrides for that date.
    """
    try:
        sb = get_client()
        canon_res = sb.table("overlap_tasks").select("period, slot_id, task").execute()
        result: dict = {"PM": {}, "AM": {}}
        for r in (canon_res.data or []):
            p = r.get("period")
            if p in result:
                result[p][r["slot_id"]] = r["task"]

        if target_date is not None:
            date_str = target_date.isoformat() if hasattr(target_date, "isoformat") else str(target_date)
            ov_res = (
                sb.table("overlap_task_overrides")
                .select("period, slot_id, task")
                .eq("override_date", date_str)
                .execute()
            )
            for r in (ov_res.data or []):
                p = r.get("period")
                if p in result:
                    result[p][r["slot_id"]] = r["task"]

        return result
    except Exception:
        print(f"[db] get_overlap_tasks_for_engine error:\n{traceback.format_exc()}")
        return {"PM": {}, "AM": {}}


def get_training_schedule_from_db() -> dict:
    """
    Replace Training Config.json read in fill_engine.py.
    Returns {"schedule": {date_iso: {"trainee": display_name, "trainer": display_name, "day": int}}}
    Only returns rows with status in (scheduled, active) or null status.
    """
    try:
        sb = get_client()
        sched_res = (
            sb.table("training_schedule")
            .select("training_date, trainee_id, trainer_id, day_number, status")
            .execute()
        )
        rows = sched_res.data or []
        # Filter: include only scheduled/active/null-status entries
        rows = [r for r in rows
                if not r.get("status") or r["status"] in ("scheduled", "active")]

        if not rows:
            return {"schedule": {}}

        # Look up display names
        all_tm_ids = list({tid for r in rows for tid in [r.get("trainee_id"), r.get("trainer_id")] if tid})
        dn_res = (
            sb.table("tm_profiles")
            .select("tm_id, display_name")
            .in_("tm_id", all_tm_ids)
            .execute()
        )
        dn_map = {r["tm_id"]: r["display_name"] for r in (dn_res.data or [])}

        schedule: dict = {}
        for r in rows:
            d = r.get("training_date")
            if not d or not r.get("trainee_id") or not r.get("trainer_id"):
                continue
            schedule[str(d)] = {
                "trainee": dn_map.get(r["trainee_id"], r["trainee_id"]),
                "trainer": dn_map.get(r["trainer_id"], r["trainer_id"]),
                "day":     int(r.get("day_number") or 1),
            }

        return {"schedule": schedule}
    except Exception:
        print(f"[db] get_training_schedule_from_db error:\n{traceback.format_exc()}")
        return {"schedule": {}}


def create_new_tm_stub_in_db(full_name: str, display_name: str, week_ending: str) -> bool:
    """
    DB replacement for the new-TM auto-detection file write in fill_engine.py.

    Creates minimal entity + tm_profiles rows for an unrecognised grave-pool TM
    found on the schedule. Returns True if inserted, False if TM already exists
    (no-op) or on error.
    """
    import uuid as _uuid
    try:
        sb = get_client()
        # Idempotency check: bail if display_name already in tm_profiles
        existing = (
            sb.table("tm_profiles")
            .select("tm_id")
            .eq("display_name", display_name)
            .limit(1)
            .execute()
        )
        if existing.data:
            return False

        tm_id = f"tm_{display_name.lower().replace(' ', '_')}_{_uuid.uuid4().hex[:4]}"

        # Insert entity row
        sb.table("entities").insert({
            "id":           tm_id,
            "name":         full_name,
            "display_name": display_name,
            "entity_type":  "tm",
            "status":       "active",
            "metadata": {
                "display_name": display_name,
                "skill_score":  5,
                "status":       "active",
                "comments": [{
                    "date":       str(date.today()),
                    "week_ending": week_ending,
                    "category":   "Administrative",
                    "sentiment":  "Flag",
                    "note":       (
                        f"Auto-detected: {full_name} on grave schedule "
                        f"but not in Eligibility Roster. Needs roster entry."
                    ),
                }],
            },
        }).execute()

        # Insert tm_profiles stub
        sb.table("tm_profiles").insert({
            "tm_id":         tm_id,
            "full_name":     full_name,
            "employee_name": full_name,
            "display_name":  display_name,
            "active":        True,
            "grave_pool":    "Grave",
            "skill_score":   5,
            "status":        "active",
        }).execute()

        return True
    except Exception:
        print(f"[db] create_new_tm_stub_in_db error:\n{traceback.format_exc()}")
        return False


def save_area_note(area_id: str, content: str, sentiment: str = "neutral") -> bool:
    """
    Save a quick area note; auto-link to the area entity via note_entities.
    Returns True on success.
    """
    if not content.strip():
        return False

    try:
        import uuid
        note_id = f"note_{uuid.uuid4().hex[:12]}"
        sb = get_client()

        sb.table("notes").insert({
            "id": note_id,
            "content": content.strip(),
            "content_type": "observation",
            "sentiment": sentiment,
            "author": "brian",
            "original_date": date.today().isoformat(),
            "captured_via": "areas_quick_note",
            "metadata": {"area_id": area_id},
        }).execute()

        sb.table("note_entities").insert({
            "note_id": note_id,
            "entity_id": area_id,
            "role": "subject",
        }).execute()

        return True
    except Exception:
        print(f"[db] save_area_note error:\n{traceback.format_exc()}")
        return False
