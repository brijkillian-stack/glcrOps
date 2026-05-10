"""
GLCR Zone Deployment Book — Supabase print renderer.

Dynamically imports the existing render_deployment_book.py engine (which owns
all CSS, card renderers, HTML shell, and SVG sprites), then feeds it Supabase
data instead of an xlsx file.

Exports:
    render_week_html(week_id: str) -> str   — full 14-page book
    render_night_html(night_id: str) -> str — 2-page single night
"""

from __future__ import annotations
import importlib.util
import datetime as dt
from pathlib import Path
from typing import Optional

from . import database
from shared.db import list_annotations_grouped as _list_annotations_grouped
from .components.glcr_icons import glcr_icon as _glcr_icon

# ── Dynamic import of the rendering engine ───────────────────────────────────
# Vendored to apps/zds/engine/render_deployment_book.py during Phase G.1.
# Same path locally and on Render — no OneDrive dependency.
_RDB_PATH = Path(__file__).resolve().parent / "engine" / "render_deployment_book.py"
_spec = importlib.util.spec_from_file_location("_rdb", _RDB_PATH)
_rdb  = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_rdb)

# Pull in constants + card-level render functions
DAY_COLOR          = _rdb.DAY_COLOR
ZONE_COLOR         = _rdb.ZONE_COLOR
RR_COLOR           = _rdb.RR_COLOR
TASKS_ZONE         = _rdb.TASKS_ZONE
TASKS_RR           = _rdb.TASKS_RR
TASKS_AUX          = _rdb.TASKS_AUX
TASKS_PM_OL        = _rdb.TASKS_PM_OL
TASKS_AM_OL        = _rdb.TASKS_AM_OL
BG_ZONE            = _rdb.BG_ZONE
BG_RR_M            = _rdb.BG_RR_M
BG_RR_W            = _rdb.BG_RR_W
BG_AUX             = _rdb.BG_AUX
esc                = _rdb.esc
render_zone_card   = _rdb.render_zone_card
render_rr_card     = _rdb.render_rr_card
render_aux_card    = _rdb.render_aux_card
render_overlap_mini = _rdb.render_overlap_mini
render_break_col   = _rdb.render_break_col
join_assigns       = _rdb.join_assigns
abbrev_task        = _rdb.abbrev_task
CSS                = _rdb.CSS
SVG_SPRITE         = _rdb.SVG_SPRITE
HTML_SHELL         = _rdb.HTML_SHELL


# ── Phase 4k.4 — TM annotation print CSS ─────────────────────────────────────
# Appended to the engine's CSS block at render time so we don't touch the engine.

_TM_ANNOTATION_CSS = """
/* Phase 4k.4 — TM pre-shift annotation markers */
.tm-preshift-note {
  display: block;
  margin-left: 14px;
  font-size: 0.85em;
  font-style: italic;
  color: #4b5563;
  line-height: 1.2;
}
.tm-log-marker {
  vertical-align: -1px;
  margin-left: 4px;
  opacity: 0.7;
}
"""

# ── Phase 4k.5 — Card annotation print CSS ───────────────────────────────────

_CARD_ANNOTATION_CSS = """
/* Phase 4k.5 — card-level annotation markers in print output */
.card-priority-stripe {
  border-left: 3px solid #d97706;
  padding-left: 3px;
}
.card-note {
  display: block;
  font-size: 0.8em;
  font-style: italic;
  color: #4b5563;
  margin-top: 2px;
  margin-left: 2px;
}
.card-adhoc-task {
  display: block;
  font-size: 0.78em;
  color: #374151;
  margin-top: 1px;
  margin-left: 2px;
}
.card-adhoc-task::before {
  content: "→ ";
  color: #9ca3af;
}
"""

# ── Phase 4k.6 — Task highlight print CSS ────────────────────────────────────
# _inject_task_highlights() walks the card HTML and adds class="task-hl-{color}"
# to <li> elements that have a highlight annotation. The classes are styled in
# the live app via assets/ops_tokens.css, but the print HTML is self-contained
# and never loads that file — so we inline the rules here. Hardcoded RGB tints
# (no color-mix) for B&W-printer-safe rendering and to avoid CSS-var lookup
# failures when the print HTML is rendered standalone by Chrome.

_TASK_ANNOTATION_CSS = """
/* Phase 4k.6 — task highlight tints (printed) */
/* print-color-adjust forces Chrome to render background colors in print/PDF */
.task-hl-yellow { background: rgba(245, 200,  60, 0.30); border-radius: 3px; padding: 0 3px; print-color-adjust: exact; -webkit-print-color-adjust: exact; }
.task-hl-red    { background: rgba(228,  78,  78, 0.22); border-radius: 3px; padding: 0 3px; print-color-adjust: exact; -webkit-print-color-adjust: exact; }
.task-hl-green  { background: rgba( 80, 180, 110, 0.26); border-radius: 3px; padding: 0 3px; print-color-adjust: exact; -webkit-print-color-adjust: exact; }
.task-hl-blue   { background: rgba( 55, 145, 245, 0.26); border-radius: 3px; padding: 0 3px; print-color-adjust: exact; -webkit-print-color-adjust: exact; }
.task-hl-purple { background: rgba(155, 110, 215, 0.26); border-radius: 3px; padding: 0 3px; print-color-adjust: exact; -webkit-print-color-adjust: exact; }
.task-hl-orange { background: rgba(245, 145,  60, 0.26); border-radius: 3px; padding: 0 3px; print-color-adjust: exact; -webkit-print-color-adjust: exact; }
"""

# ── Print layout overrides — no footer, tighter top/bottom ───────────────────
# Hides the footer bar (GLCR · Grave + page numbers) and recovers the ~14px
# it occupied by trimming the masthead top padding by ~6px. The remaining
# space flows into the card body rows, which is where it's useful.
_PRINT_LAYOUT_CSS = """
.page-foot { display: none !important; }
.mast      { padding-top: 8px !important; }
"""

# ── Phase 4g.x — Week-dots strip (Brian wants it in upper-right of masthead) ──
# day_idx is 1-based (Friday=1, Thursday=7). The 7-letter array maps directly:
# [F]riday, [S]aturday, [S]unday, [M]onday, [T]uesday, [W]ednesday, [T]hursday.
_WEEK_LETTERS = ['F', 'S', 'S', 'M', 'T', 'W', 'T']

def _week_dots_html(day_idx: int) -> str:
    """Build the F-S-S-M-T-W-T strip with the current day highlighted."""
    cur_i = (day_idx - 1) if 1 <= day_idx <= 7 else -1
    return '<div class="week-dots">' + ''.join(
        f'<div class="week-dot{ "  cur" if i == cur_i else "" }">{d}</div>'
        for i, d in enumerate(_WEEK_LETTERS)
    ) + '</div>'

# ── Slot-key mappings ─────────────────────────────────────────────────────────
# DB slot_key → index in rr_mens / rr_womens arrays
_RR_IDX  = {"rr_1_2": 0, "rr_6": 1, "rr_7": 2, "rr_8": 3, "rr_10": 4}
# index → canonical RR number
_RR_NUM  = {0: 1, 1: 6, 2: 7, 3: 8, 4: 10}
# DB aux slot_key → render_deployment_book.py key
_AUX_KEY = {
    "z9_sr":    "z9_sr",
    "admin":    "admin",
    "trash_1":  "trash_1_5",
    "trash_2":  "trash_6_10",
    "support_1": "support_1",
    "support_2": "support_2",
    "support_3": "support_3",
}


# ── Data helpers ──────────────────────────────────────────────────────────────

def _fetch_night_data(night_id: str) -> tuple:
    """Return (night_record, day_dict, slot_map, overlaps).

    slot_map keys:
        zone_1 .. zone_10            — zone slot rows
        rr_1_2_mens / rr_1_2_womens — RR slot rows (by side)
        z9_sr / admin / trash_1 ..   — aux slot rows
        tm:<name>                    — fast lookup by TM name
    """
    res   = (database._client().table("nights").select("*")
             .eq("id", night_id).single().execute())
    night = res.data

    assignments = database.fetch_zone_assignments(night_id)
    overlaps    = database.fetch_overlap_assignments(night_id)
    notices     = database.fetch_notices(night_id)  # Phase E

    slot_map: dict[str, dict] = {}
    zones   = [""] * 10
    rr_m    = [""] * 5
    rr_w    = [""] * 5
    aux_d   = {k: "" for k in
               ("z9_sr", "z9_sr_buddy", "admin",
                "trash_1_5", "trash_6_10",
                "support_1", "support_2", "support_3")}
    pm_ol   = [""] * 6
    am_ol   = [""] * 6

    for s in assignments:
        tm  = s.get("tm_name") or ""
        sk  = s["slot_key"]
        st  = s["slot_type"]
        rrs = s.get("rr_side", "")

        if st == "zone":
            n = int(sk.rsplit("_", 1)[-1]) - 1   # "zone_7" → 6
            if 0 <= n < 10:
                zones[n] = tm
                slot_map[sk] = s
        elif st == "rr":
            idx = _RR_IDX.get(sk, -1)
            if idx >= 0:
                (rr_m if rrs == "mens" else rr_w)[idx] = tm
                slot_map[f"{sk}_{rrs}"] = s
        elif st == "aux":
            dk = _AUX_KEY.get(sk)
            if dk:
                aux_d[dk] = tm
            slot_map[sk] = s

        if tm:
            slot_map[f"tm:{tm}"] = s

    for ol in overlaps:
        pos  = (ol.get("position") or 1) - 1
        name = ol.get("tm_name") or ""
        if ol.get("overlap_window") == "pm" and 0 <= pos < 6:
            pm_ol[pos] = name
        elif ol.get("overlap_window") == "am" and 0 <= pos < 6:
            am_ol[pos] = name

    ndate   = dt.date.fromisoformat(night["night_date"])
    # Use the actual calendar weekday of night_date (the morning the shift ends)
    # so labels match dates — same convention as the web UI.
    weekday = ndate.strftime("%A")
    # Phase E — build slot_key → list[notice] map for print badges
    notices_by_slot: dict[str, list] = {}
    for n_row in notices:
        notices_by_slot.setdefault(n_row["slot_key"], []).append(n_row)

    day   = {
        "date":           ndate,
        "label":          ndate.strftime("%A, %B %-d, %Y"),
        "weekday":        weekday,
        "date_short":     ndate.strftime("%B %-d, %Y"),
        "day_num":        ndate.day,
        "zones":          zones,
        "rr_mens":        rr_m,
        "rr_womens":      rr_w,
        "pm_ol":          pm_ol,
        "am_ol":          am_ol,
        "aux":            aux_d,
        # Phase D + E additions
        "is_locked":      bool(night.get("is_locked", False)),
        "locked_by":      night.get("locked_by") or "",
        "notices_by_slot": notices_by_slot,
    }
    return night, day, slot_map, overlaps


def _sweeper_add(slot_map: dict) -> dict:
    """Build sweeper_add dict  {slot_key: [label, ...]} from DB is_sweeper flags."""
    out: dict[str, list] = {}
    for key, s in slot_map.items():
        if key.startswith("tm:") or not s.get("is_sweeper") or not s.get("sweeper_route"):
            continue
        label = f"Sweeper {s['sweeper_route']}"
        st    = s["slot_type"]
        sk    = s["slot_key"]
        if st == "zone":
            out.setdefault(sk, []).append(label)
        elif st == "rr":
            n = _RR_NUM.get(_RR_IDX.get(sk, -1), -1)
            if n > 0:
                out.setdefault(f"rr_{n}", []).append(label)
        elif st == "aux":
            rdb_k = _AUX_KEY.get(sk, sk)
            out.setdefault(f"aux_{rdb_k}", []).append(label)
    return out


def _alert(sk: str, slot_map: dict) -> str:
    s = slot_map.get(sk, {})
    return s.get("alert_target", "") if s.get("has_alert") else ""


def _grp(sk: str, slot_map: dict) -> Optional[int]:
    return slot_map.get(sk, {}).get("group_num") or None


# ── Deployment page renderer ───────────────────────────────────────────────────

# ── Phase 4k.3: annotation helpers ───────────────────────────────────────────

_DAY_KEY_MAP = {
    "Friday": "fri", "Saturday": "sat", "Sunday": "sun",
    "Monday": "mon", "Tuesday": "tue", "Wednesday": "wed", "Thursday": "thu",
}


def _day_key_from_weekday(weekday: str) -> str:
    """Map full weekday name → 3-letter day slug used in zds_annotations."""
    return _DAY_KEY_MAP.get(weekday, weekday[:3].lower() if weekday else "fri")


def _apply_task_annotations(items: list, annots: dict) -> list[str]:
    """Apply skip / symbol / note annotations; return final display strings.

    items:  list of {id, name} dicts  (custom/hardcoded tasks carry id="")
    annots: {task_uuid: {annotation_kind: value_dict}} — the "task" sub-dict
            from list_annotations_grouped(); pass {} to skip the annotation pass.

    Returns a list of plain-text name strings:
      • Symbol annotations are prepended  (e.g. "★ Mop entrance")
      • Note annotations are appended     (e.g. "Mop entrance (check near door)")
      • Tasks with a skip annotation are omitted entirely
      • Custom / hardcoded tasks (id="") pass through unchanged
    """
    result: list[str] = []
    for item in items:
        if isinstance(item, dict):
            # Phase 4k.7: use annot_id as the stable annotation key.
            # Fall back to id for any pre-4k.7 dicts that lack the field.
            annot_id = item.get("annot_id") or item.get("id", "")
            name     = item.get("name", "")
        else:
            annot_id = ""
            name     = str(item)

        if annot_id and annot_id in annots:
            task_ann = annots[annot_id]
            # Skip — omit from print output entirely
            if task_ann.get("skip"):
                continue
            sym_ann  = task_ann.get("symbol") or {}
            sym_sec  = sym_ann.get("section", "")
            sym_slug = sym_ann.get("slug", "")
            sym_char = sym_ann.get("char", "")   # legacy fallback (pre-4k.3.1 rows)
            note_val = (task_ann.get("note") or {}).get("text", "")
            if sym_sec and sym_slug:
                try:
                    prefix = _glcr_icon(sym_sec, sym_slug, size=11,
                                        css_class="task-symbol") + " "
                except Exception:
                    prefix = ""
            elif sym_char:
                prefix = f"{sym_char} "
            else:
                prefix = ""
            suffix = f" ({note_val})" if note_val else ""
            result.append(f"{prefix}{name}{suffix}")
        else:
            result.append(name)

    return result


def _inject_task_highlights(card_html: str, task_items: list, annots: dict) -> str:
    """Post-process a rendered card HTML string to add highlight CSS classes to task <li>s.

    The engine's _render_task_li escapes task strings, so we cannot inject HTML
    before the render call. Instead we walk the rendered HTML and find each task's
    <li> by matching the end-anchor ``{esc(name)}</li>``, then inject a
    ``class="task-hl-{color}"`` attribute.

    Phase 4k.7: uses annot_id (stable for both canonical and custom tasks).
    Falls back to id for pre-4k.7 dicts missing the annot_id field.

    Phase 4k.6 hotfix: adds highlight rendering to PDF output.
    """
    if not annots:
        return card_html
    for item in task_items:
        if not isinstance(item, dict):
            continue
        annot_id = item.get("annot_id") or item.get("id", "")
        if not annot_id:
            continue
        ann = annots.get(annot_id) or {}
        hl_color = (ann.get("highlight") or {}).get("color", "")
        if not hl_color:
            continue
        esc_name = esc(item.get("name", ""))
        end_anchor = f"{esc_name}</li>"
        idx = card_html.find(end_anchor)
        if idx == -1:
            continue
        # Walk back from idx to find the opening <li>
        li_start = card_html.rfind("<li>", 0, idx)
        if li_start == -1:
            continue
        old_li = card_html[li_start : idx + len(end_anchor)]
        inner   = old_li[4 : -5]  # strip <li> (4) and </li> (5)
        new_li  = f'<li class="task-hl-{hl_color}">{inner}</li>'
        card_html = card_html[:li_start] + new_li + card_html[li_start + len(old_li):]
    return card_html


def _apply_tm_annotations(card_html: str, tm_id: str, tm_name: str,
                          tm_annots: dict) -> str:
    """Post-process a rendered card HTML string to inject TM annotation markup.

    Finds the escaped TM name inside any *-name div
    (zone-name / name / aux-name) and appends:
      • pin-bookmark SVG inline next to name if profile_log annotation exists
      • italic pre-shift note block below name if note annotation exists

    Phase 4k.4. Called after render_zone_card / render_rr_card / render_aux_card
    because those engine functions HTML-escape `name_str`, so we cannot inject
    HTML before the call.

    Args:
        card_html:  Full HTML string returned by a render_*_card function.
        tm_id:      The TM's UUID (also the entities.id).
        tm_name:    The TM's plain display name (used to locate the text in HTML).
        tm_annots:  The "tm" sub-dict of list_annotations_grouped() —
                    {tm_id: {annotation_kind: value_dict}}.

    Returns the card_html unchanged if tm_id / tm_name are empty or no annotations exist.
    """
    from html import escape as _html_escape
    if not tm_id or not tm_name:
        return card_html
    tm_anns = tm_annots.get(tm_id, {})
    if not tm_anns:
        return card_html

    note = tm_anns.get("note")
    log  = tm_anns.get("profile_log")

    extras = ""
    if log:
        try:
            extras += _glcr_icon("ui", "pin-bookmark", size=10,
                                 css_class="tm-log-marker")
        except Exception:
            pass
    if note and note.get("text"):
        extras += (f'<span class="tm-preshift-note">'
                   f'{_html_escape(note["text"])}</span>')

    if not extras:
        return card_html

    # All three card types escape the TM name then insert a closing "</div>".
    # We find ">escaped_name<" and append the extras before the "<".
    escaped_name = esc(tm_name)
    needle = f">{escaped_name}<"
    replacement = f">{escaped_name}{extras}<"
    return card_html.replace(needle, replacement, 1)


def _apply_card_annotations(card_html: str, card_code: str,
                            card_annots: dict) -> str:
    """Post-process a rendered card HTML string to inject card annotation markup.

    Uses the collapsed card_annotation_data format produced by
    _collapse_card_annotations():
      {card_code: {note?, priority?, adhoc_tasks: [{ref, name}, ...]}}

    Injections:
      • priority stripe: adds card-priority-stripe class to the outer card div
      • note + adhoc blocks: injects after the card's header meta div
        (engine class names: zone-meta, rr-head, aux-meta)

    Phase 4k.5. Called after render_zone_card / render_rr_card / render_aux_card.
    """
    from html import escape as _html_escape
    if not card_code:
        return card_html
    anns = card_annots.get(card_code, {})
    if not anns:
        return card_html

    # Priority stripe — inject class onto any top-level card wrapper.
    # Engine uses zone-card, rr-card, aux-card — match any.
    priority = anns.get("priority")
    if priority:
        for card_cls in ("zone-card", "rr-card", "aux-card"):
            marker = f'class="{card_cls} '
            if marker in card_html:
                card_html = card_html.replace(marker,
                    f'class="{card_cls} card-priority-stripe ', 1)
                break
            # Card with no extra classes: class="zone-card"
            marker2 = f'class="{card_cls}"'
            if marker2 in card_html:
                card_html = card_html.replace(marker2,
                    f'class="{card_cls} card-priority-stripe"', 1)
                break

    # Note + adhoc tasks — build a block then inject after the header meta div.
    extras = ""
    note = anns.get("note")
    if note and note.get("text"):
        extras += f'<div class="card-note">{_html_escape(note["text"])}</div>'
    for task in (anns.get("adhoc_tasks") or []):
        name = task.get("name", "")
        if name:
            extras += f'<div class="card-adhoc-task">{_html_escape(name)}</div>'

    if extras:
        # Try each engine meta-div class in order
        for meta_cls in ("zone-meta", "rr-head", "aux-meta"):
            open_tag = f'<div class="{meta_cls}'
            if open_tag not in card_html:
                continue
            # Find the closing </div> of this section and inject after it
            start = card_html.find(open_tag)
            # Walk forward to find the matching </div>
            depth = 0
            i = start
            while i < len(card_html):
                if card_html[i:i+4] == "<div":
                    depth += 1
                    i += 4
                elif card_html[i:i+6] == "</div>":
                    depth -= 1
                    if depth == 0:
                        inject_at = i + 6
                        card_html = (card_html[:inject_at]
                                     + f'<div class="card-annots">{extras}</div>'
                                     + card_html[inject_at:])
                        break
                    i += 6
                else:
                    i += 1
            break

    return card_html


def _notice_badges_html(slot_key: str, notices_by_slot: dict) -> str:
    """Phase E — render inline notice badges for print output.

    Darker colors used for print contrast per handoff spec.
    """
    rows = notices_by_slot.get(slot_key, [])
    if not rows:
        return ""
    parts = []
    for n in rows:
        t = n.get("type", "info")
        parts.append(f'<span class="print-notice print-notice-{t}">{t.upper()}</span>')
    return "".join(parts)


def _render_deployment_page(night: dict, day: dict, slot_map: dict,
                              overlaps: list,
                              page_num: int, page_total: int,
                              day_idx: int, total_days: int) -> str:
    weekday         = day["weekday"]
    day_color       = DAY_COLOR.get(weekday, "#444444")
    sw_add          = _sweeper_add(slot_map)
    notices_by_slot = day.get("notices_by_slot", {})
    is_locked       = day.get("is_locked", False)

    # ── Phase 4k.3: load task annotations for this night ─────────────────────
    # Derive week_ending (the Thursday) from the night's calendar date.
    # GLCR week runs Fri–Thu; weekday() gives 0=Mon…3=Thu…6=Sun.
    _ndate    = day["date"]                                    # dt.date object
    _delta    = (3 - _ndate.weekday()) % 7                    # days to Thursday
    _week_end = _ndate + dt.timedelta(days=_delta)
    _day_slug = _day_key_from_weekday(weekday)
    try:
        _all_annots = _list_annotations_grouped(_week_end, _day_slug)
        task_annots = _all_annots.get("task", {})
        tm_annots   = _all_annots.get("tm",   {})
        # Phase 4k.5 — collapsed card annotations keyed by card code
        from .state import _collapse_card_annotations
        card_annots = _collapse_card_annotations(_all_annots.get("card", {}))
    except Exception:
        _all_annots = {}
        task_annots = {}
        tm_annots   = {}
        card_annots = {}
    # ─────────────────────────────────────────────────────────────────────────

    def zone_tasks(n: int) -> list[str]:
        """Use DB display_tasks (respects custom overrides + sweeper); fallback to defaults.

        Phase 4k.3: display_tasks is now list[{id, name}]. Skip/symbol/note
        annotations are applied via _apply_task_annotations; skipped tasks are
        omitted from print output.
        """
        sk    = f"zone_{n}"
        s     = slot_map.get(sk, {})
        items = (
            list(s["display_tasks"])
            if s.get("display_tasks") is not None
            else [{"id": "", "name": t} for t in TASKS_ZONE.get(n, [])]
        )
        # Append sweeper labels (plain strings → no UUID → id="")
        existing_names = {(i["name"] if isinstance(i, dict) else i) for i in items}
        for t in sw_add.get(f"zone_{n}", []):
            if t not in existing_names:
                items.append({"id": "", "name": t})
        return _apply_task_annotations(items, task_annots)

    def rr_extra_tasks(rr_sk: str) -> list[str] | None:
        """Collect custom-added tasks for an RR bank (sweeper + any user additions).

        Phase 4k.3: display_tasks items are now {id, name} dicts; dedup by name.
        """
        sm   = slot_map.get(f"{rr_sk}_mens",   {})
        sw   = slot_map.get(f"{rr_sk}_womens", {})
        n    = _RR_NUM.get(_RR_IDX.get(rr_sk, -1), -1)
        base          = set(TASKS_RR.get(n, []))
        extras_items: list = []
        extras_names: set  = set()
        for s in (sm, sw):
            for item in (s.get("display_tasks") or []):
                name = item["name"] if isinstance(item, dict) else item
                if name not in base and name not in extras_names:
                    extras_items.append(
                        item if isinstance(item, dict) else {"id": "", "name": item}
                    )
                    extras_names.add(name)
        for t in sw_add.get(f"rr_{n}", []):
            if t not in extras_names:
                extras_items.append({"id": "", "name": t})
                extras_names.add(t)
        if not extras_items:
            return None
        result = _apply_task_annotations(extras_items, task_annots)
        return result or None

    def aux_extra_tasks(db_key: str, rdb_key: str) -> list[str] | None:
        """Collect custom-added tasks for an aux slot beyond its defaults.

        Phase 4k.3: display_tasks items are now {id, name} dicts; dedup by name.
        """
        s      = slot_map.get(db_key, {})
        _, sub = TASKS_AUX.get(rdb_key, ("", ""))
        base          = {sub} if sub else set()
        extras_items: list = []
        extras_names: set  = set()
        for item in (s.get("display_tasks") or []):
            name = item["name"] if isinstance(item, dict) else item
            if name not in base and name not in extras_names:
                extras_items.append(
                    item if isinstance(item, dict) else {"id": "", "name": item}
                )
                extras_names.add(name)
        for t in sw_add.get(f"aux_{rdb_key}", []):
            if t not in extras_names:
                extras_items.append({"id": "", "name": t})
                extras_names.add(t)
        if not extras_items:
            return None
        result = _apply_task_annotations(extras_items, task_annots)
        return result or None

    # Zone cards
    zone_cards = []
    for n in range(1, 11):
        sk      = f"zone_{n}"
        s       = slot_map.get(sk, {})
        tm_nm   = s.get("tm_name") or ""
        tm_id_z = s.get("tm_id") or ""
        # Capture raw items (with UUIDs) for the highlight post-processor, then
        # build the processed task list (skip applied, sweeper appended).
        raw_items = (
            list(s["display_tasks"]) if s.get("display_tasks") is not None
            else [{"id": "", "name": t} for t in TASKS_ZONE.get(n, [])]
        )
        card = render_zone_card(
            n, tm_nm, ZONE_COLOR[n],
            zone_tasks(n),
            alert=_alert(sk, slot_map),
            group=_grp(sk, slot_map),
        )
        card = _inject_task_highlights(card, raw_items, task_annots)
        card = _apply_tm_annotations(card, tm_id_z, tm_nm, tm_annots)
        # card code matches ZONE_LABELS["zone_N"] = "Zone N" = slot["label"] in UI
        card = _apply_card_annotations(card, f"Zone {n}", card_annots)
        zone_cards.append(card)

    # RR cards
    rr_nums = [1, 6, 7, 8, 10]
    rr_cards = []
    for idx, n in enumerate(rr_nums):
        rr_sk   = "rr_1_2" if n == 1 else f"rr_{n}"
        sm      = slot_map.get(f"{rr_sk}_mens",   {})
        sw      = slot_map.get(f"{rr_sk}_womens",  {})
        alert   = _alert(f"{rr_sk}_mens", slot_map) or _alert(f"{rr_sk}_womens", slot_map)
        m_name  = sm.get("tm_name") or ""
        w_name  = sw.get("tm_name") or ""
        m_id    = sm.get("tm_id") or ""
        w_id    = sw.get("tm_id") or ""
        card = render_rr_card(
            n, m_name, w_name, RR_COLOR[n],
            extra_tasks=rr_extra_tasks(rr_sk),
            alert=alert,
            mens_group=sm.get("group_num") or None,
            womens_group=sw.get("group_num") or None,
        )
        card = _apply_tm_annotations(card, m_id, m_name, tm_annots)
        card = _apply_tm_annotations(card, w_id, w_name, tm_annots)
        # card code: ZONE_LABELS["rr_N"] = "RR N" or "RR 1 + 2" — matches slot["label"] in UI
        rr_label = "RR 1 + 2" if n == 1 else f"RR {n}"
        card = _apply_card_annotations(card, rr_label, card_annots)
        rr_cards.append(card)

    # Aux cards
    aux_order = [
        ("z9_sr",    "z9_sr",     "red"),
        ("admin",    "admin",     "purple"),
        ("trash_1",  "trash_1_5", "orange"),
        ("trash_2",  "trash_6_10","orange"),
        ("support_1","support_1", "grey"),
        ("support_2","support_2", "grey"),
    ]
    aux_cards = []
    for db_key, rdb_key, color in aux_order:
        s      = slot_map.get(db_key, {})
        a_name = s.get("tm_name") or ""
        a_id   = s.get("tm_id") or ""
        card = render_aux_card(
            rdb_key, a_name, color,
            extra_tasks=aux_extra_tasks(db_key, rdb_key),
            alert=_alert(db_key, slot_map),
            group=_grp(db_key, slot_map),
        )
        # card code: ZONE_LABELS[db_key] — matches slot["label"] in UI
        aux_label = database.ZONE_LABELS.get(db_key, db_key)
        card = _apply_tm_annotations(card, a_id, a_name, tm_annots)
        card = _apply_card_annotations(card, aux_label, card_annots)
        aux_cards.append(card)
    s3 = slot_map.get("support_3", {})
    if s3.get("tm_name"):
        s3_name = s3["tm_name"]
        s3_id   = s3.get("tm_id") or ""
        card = render_aux_card(
            "support_3", s3_name, "teal",
            alert=_alert("support_3", slot_map),
            group=_grp("support_3", slot_map),
            conditional=True,
        )
        card = _apply_tm_annotations(card, s3_id, s3_name, tm_annots)
        card = _apply_card_annotations(
            card, database.ZONE_LABELS.get("support_3", "Support 3"), card_annots
        )
        aux_cards.append(card)
    has_s3      = bool(s3.get("tm_name"))
    aux_strip_cls = "aux-strip" + (" has-support-3" if has_s3 else "")

    # Counts
    zones_f = sum(1 for n in day["zones"] if n)
    rr_f    = sum(1 for n in day["rr_mens"] + day["rr_womens"] if n)
    base_aux = ("trash_1_5","trash_6_10","admin","z9_sr","support_1","support_2")
    aux_f   = sum(1 for k in base_aux if day["aux"].get(k))
    aux_t   = len(base_aux)
    if day["aux"].get("support_3"): aux_f += 1; aux_t += 1
    ol_f    = sum(1 for n in day["pm_ol"] + day["am_ol"] if n)

    # Break counts
    g = [0, 0, 0]
    for i, nm in enumerate(day["zones"]):
        if nm:
            bg = BG_ZONE.get(i + 1)
            if bg in (1, 2, 3): g[bg - 1] += 1
    for i, nm in enumerate(day["rr_mens"]):
        if nm:
            bg = BG_RR_M.get(_RR_NUM[i])
            if bg in (1, 2, 3): g[bg - 1] += 1
    for i, nm in enumerate(day["rr_womens"]):
        if nm:
            bg = BG_RR_W.get(_RR_NUM[i])
            if bg in (1, 2, 3): g[bg - 1] += 1
    for k, nm in day["aux"].items():
        if nm:
            bg = BG_AUX.get(k)
            if bg in (1, 2, 3): g[bg - 1] += 1
    g1, g2, g3 = g

    zones_html = "\n".join(zone_cards)
    rr_html    = "\n".join(rr_cards)
    aux_html   = "\n".join(aux_cards)
    month_name = day["date"].strftime("%B %Y")

    return f"""<article class="page" data-screen-label="{weekday} {esc(day['date_short'])}" style="--day-color:{day_color};">
  <header class="mast">
    <div class="mast-day-num">{day['day_num']}</div>
    <div class="mast-meta">
      <div class="day-name">{weekday}</div>
      <div class="month">{month_name} · Day {day_idx} of {total_days}</div>
      <div class="status">
        <span class="break-bar">
          <span class="lbl">Breaks</span>
          <span class="dot" data-group="1" title="Break 1">{g1}</span>
          <span class="dot" data-group="2" title="Break 2">{g2}</span>
          <span class="dot" data-group="3" title="Break 3">{g3}</span>
        </span>
      </div>
    </div>
    <div class="mast-context">
      <div class="shift">Grave · 11pm – 7am</div>
      {_week_dots_html(day_idx)}
      <div class="group-key">
        Group <span class="gp" data-group="1">1</span>
        <span class="gp" data-group="2">2</span>
        <span class="gp" data-group="3">3</span>
      </div>
    </div>
  </header>
  <div class="body">
    <section>
      <h2 class="section-label is-primary">
        <svg class="glyph"><use href="#g-zones"/></svg>
        Zones <span class="meta">{zones_f} / 10 filled</span>
      </h2>
      <div class="zones-grid">
{zones_html}
      </div>
    </section>
    <section>
      <h2 class="section-label">
        <svg class="glyph"><use href="#g-restroom"/></svg>
        Restrooms <span class="meta">{rr_f} / 10 filled</span>
      </h2>
      <div class="rr-grid">
{rr_html}
      </div>
    </section>
    <section>
      <h2 class="section-label">
        <svg class="glyph"><use href="#g-aux"/></svg>
        Auxiliary <span class="meta">{aux_f} / {aux_t} filled</span>
      </h2>
      <div class="{aux_strip_cls}">
{aux_html}
      </div>
    </section>
  </div>
  <footer class="page-foot">
    <span class="slug-mark">
      <span class="swatch"></span>GLCR · Grave
      {"&nbsp;&nbsp;<span class='foot-lock-stamp'>🔒 LOCKED</span>" if is_locked else ""}
    </span>
    <span class="slug-path"><span class="now">{weekday}</span> {esc(day['date_short'])}<span class="sep">·</span>Zone Deployment</span>
    <span class="slug-pn"><span class="pn-cur">{page_num}</span> / {page_total}</span>
  </footer>
</article>"""


# ── Break sheet renderer ──────────────────────────────────────────────────────

def _wave_for_slot_ref(slot_ref: str) -> int:
    """Derive break wave (1/2/3) from a slot_ref string using BG_ZONE/BG_RR_M/BG_RR_W/BG_AUX.

    Phase 4g fix: the DB `break_wave` column is unreliable (Phase 4d set all=1).
    This replicates the same lookup logic render_deployment_book.py uses.
    Returns 1 if the slot cannot be mapped (safe fallback, same as before).
    """
    r  = slot_ref.strip()
    rl = r.lower()

    # Zone: compact "Z1"–"Z10" or long "Zone 1"
    if r.startswith("Z") and " " not in r and r[1:].isdigit():
        return BG_ZONE.get(int(r[1:]), 1)
    if rl.startswith("zone "):
        try: return BG_ZONE.get(int(r.split()[-1]), 1)
        except ValueError: pass

    # Restroom: compact "RR7 M", "RR1+2 W", or long "RR 7 Men's"
    if r.upper().startswith("RR") and " " in r:
        parts = r[2:].strip().split()
        num_str = parts[0]; side_str = parts[-1].upper() if len(parts) >= 2 else ""
        n = 1 if num_str == "1+2" else (int(num_str) if num_str.isdigit() else None)
        if n is not None:
            if side_str in ("M", "MEN'S"): return BG_RR_M.get(n, 1)
            if side_str in ("W", "WOMEN'S"): return BG_RR_W.get(n, 1)
    if rl.startswith("rr "):
        parts = r.split()
        nstr = parts[1] if len(parts) > 1 else ""
        n = 1 if nstr == "1+2" else (int(nstr) if nstr.isdigit() else None)
        # Can't tell M/W from slot_ref alone in long format → default Men's table
        if n is not None: return BG_RR_M.get(n, 1)

    # Auxiliary: map to _AUX_COLOR keys used in BG_AUX
    _aux_key_map = {
        "z9 sr": "z9_sr", "z9sr": "z9_sr", "z9 sr buddy": "z9_sr_buddy",
        "admin":   "admin",
        "trash 1": "trash_1_5", "trash 2": "trash_6_10",
        "supp 1":  "support_1", "supp 2": "support_2", "supp 3": "support_3",
        "support 1": "support_1", "support 2": "support_2", "support 3": "support_3",
    }
    for key, rdb_key in _aux_key_map.items():
        if rl == key or rl.startswith(key):
            return BG_AUX.get(rdb_key, 1)

    return 1  # safe fallback


def _break_row_meta(slot_ref: str, tm_name: str, slot_map: dict) -> dict:
    """Derive {section, badge, color, assign} for a break-sheet row.

    Handles two slot_ref formats:
      • Legacy long form: "Zone 1", "RR 7 Men's", "Trash 1", "Z9 SR"
      • New compact form (written by the engine): "Z1", "RR7 M", "RR1+2 W",
        "Z9 SR", "Admin", "Trash 1", "Trash 2", "Supp 1"
    """
    r  = slot_ref.strip()
    rl = r.lower()
    tm_slot       = slot_map.get(f"tm:{tm_name}", {})
    is_sweeper    = tm_slot.get("is_sweeper") and tm_slot.get("sweeper_route")
    sweeper_label = f"Sweeper – {tm_slot['sweeper_route']}" if is_sweeper else ""

    # ── Helper: try to identify zone number ──────────────────────────────────
    def _zone_n() -> int | None:
        # New compact: "Z1"–"Z10"  (no space, only digits after Z)
        if r.startswith("Z") and " " not in r and r[1:].isdigit():
            return int(r[1:])
        # Old long: "Zone 1"
        if rl.startswith("zone "):
            try: return int(r.split()[-1])
            except ValueError: pass
        return None

    # ── Helper: try to identify RR bank + side ────────────────────────────────
    def _rr_info() -> tuple | None:
        """Return (n, side_label) or None."""
        # New compact: "RR1+2 M", "RR6 M", "RR7 W", …
        if r.upper().startswith("RR") and " " in r:
            parts = r[2:].strip().split()
            num_str = parts[0]
            side_str = parts[-1].upper() if len(parts) >= 2 else ""
            n = 1 if num_str in ("1+2", "1+2") else (int(num_str) if num_str.isdigit() else None)
            if n is None: return None
            side_label = "Men's" if side_str == "M" else "Women's" if side_str == "W" else ""
            return n, side_label
        # Old long: "RR 7 Men's", "RR 1+2", "rr 1+2"
        if rl.startswith("rr ") or rl == "rr 1+2":
            parts = r.split()
            nstr = parts[-1] if parts[-1] not in ("Men's", "Women's") else parts[1]
            n = 1 if nstr in ("1+2",) else (int(nstr) if nstr.isdigit() else None)
            if n is None: return None
            raw_side = tm_slot.get("rr_side", "")
            side_label = "Men's" if raw_side == "mens" else "Women's" if raw_side == "womens" else ""
            return n, side_label
        return None

    # ── Zone ─────────────────────────────────────────────────────────────────
    zone_n = _zone_n()
    if zone_n is not None:
        dt = tm_slot.get("display_tasks")
        if dt is not None:
            # Use live display_tasks so pool-added / custom tasks appear on break sheet
            tasks = [item["name"] if isinstance(item, dict) else item for item in dt]
        else:
            tasks = list(TASKS_ZONE.get(zone_n, []))
        if sweeper_label and sweeper_label not in tasks:
            tasks.append(sweeper_label)
        badge = r if not r.startswith("Z") or " " in r else f"Zone {zone_n}"
        return {
            "section": "Zones",
            "badge":   badge,
            "color":   ZONE_COLOR.get(zone_n, "grey"),
            "assign":  join_assigns(tasks),
        }

    # ── Restroom ─────────────────────────────────────────────────────────────
    rr_info = _rr_info()
    if rr_info is not None:
        n, side_label = rr_info
        dt = tm_slot.get("display_tasks")
        if dt is not None:
            rr_tasks = [item["name"] if isinstance(item, dict) else item for item in dt]
        else:
            rr_tasks = list(TASKS_RR.get(n, []))
        tasks = ([side_label] if side_label else []) + rr_tasks
        if sweeper_label and sweeper_label not in tasks:
            tasks.append(sweeper_label)
        badge = "RR 1+2" if n == 1 else f"RR {n}"
        return {
            "section": "Restrooms",
            "badge":   badge,
            "color":   RR_COLOR.get(n, "grey"),
            "assign":  join_assigns(tasks),
        }

    # ── Auxiliary ────────────────────────────────────────────────────────────
    _aux_color_map = {
        "z9 sr":    "red",    "z9sr":    "red",
        "admin":    "purple", # Admin is purple per Brian (matches render_deployment_book)
        "trash 1":  "orange", "trash 2": "orange",
        "supp 1":   "grey",   "supp 2":  "grey",   "supp 3": "teal",
        "support 1":"grey",   "support 2":"grey",  "support 3":"teal",
        "z9 sr buddy": "red",
    }
    _aux_rdb_map = {
        "z9 sr":   "z9_sr", "z9sr": "z9_sr",
        "trash 1": "trash_1_5", "trash 2": "trash_6_10",
        "admin":   "admin",
        "supp 1":  "support_1", "supp 2": "support_2", "supp 3": "support_3",
        "support 1":"support_1","support 2":"support_2","support 3":"support_3",
    }
    color   = "grey"
    rdb_key = None
    for key, c in _aux_color_map.items():
        if rl == key or rl.startswith(key):
            color   = c
            rdb_key = _aux_rdb_map.get(key)
            break
    tasks = []
    dt = tm_slot.get("display_tasks")
    if dt is not None:
        tasks = [item["name"] if isinstance(item, dict) else item for item in dt]
    elif rdb_key:
        _, sub = TASKS_AUX.get(rdb_key, ("", ""))
        if sub: tasks.append(sub)
    if sweeper_label and sweeper_label not in tasks:
        tasks.append(sweeper_label)
    return {
        "section": "Auxiliary",
        "badge":   r,
        "color":   color,
        "assign":  join_assigns(tasks),
    }


def _render_break_page(night: dict, day: dict, slot_map: dict,
                        overlaps: list,
                        page_num: int, page_total: int,
                        day_idx: int) -> str:
    weekday   = day["weekday"]
    day_color = DAY_COLOR.get(weekday, "#444444")

    # Fetch break_assignments for this night
    break_rows_raw = database.fetch_break_assignments(night["id"])

    # Group into waves, derive metadata for each row.
    # Phase 4g: derive wave from slot_ref via _wave_for_slot_ref() instead of the DB
    # break_wave column, which is unreliable (all rows set to 1 since Phase 4d).
    groups: dict[int, list] = {1: [], 2: [], 3: []}
    _seen_section: dict[int, str] = {1: "", 2: "", 3: ""}
    for br in sorted(break_rows_raw, key=lambda x: x.get("sort_order", 0)):
        sref = br.get("slot_ref") or ""
        wave = _wave_for_slot_ref(sref)  # Phase 4g: ignore DB break_wave; derive from slot_ref
        tm   = br.get("tm_name") or ""
        meta = _break_row_meta(sref, tm, slot_map)
        groups[wave].append({
            "section": meta["section"],
            "name":    tm,
            "badge":   meta["badge"],
            "color":   meta["color"],
            "assign":  meta["assign"],
        })

    cols_html = "\n".join(render_break_col(g, groups[g]) for g in (1, 2, 3))

    # Overlap section (matches HTML file layout — on break sheet, not deploy page)
    pm_tasks = list(TASKS_PM_OL)
    am_tasks = list(TASKS_AM_OL)
    # Use stored task text from overlap_assignments if available
    for ol in overlaps:
        pos  = (ol.get("position") or 1) - 1
        task = ol.get("task") or ""
        if ol.get("overlap_window") == "pm" and 0 <= pos < 6 and task:
            pm_tasks[pos] = task
        elif ol.get("overlap_window") == "am" and 0 <= pos < 6 and task:
            am_tasks[pos] = task

    pm_minis = "".join(render_overlap_mini(day["pm_ol"][i], pm_tasks[i]) for i in range(6))
    am_minis = "".join(render_overlap_mini(day["am_ol"][i], am_tasks[i]) for i in range(6))
    ol_filled = sum(1 for n in day["pm_ol"] + day["am_ol"] if n)

    in_rotation = sum(1 for n in day["zones"] if n)
    in_rotation += sum(1 for n in day["rr_mens"] + day["rr_womens"] if n)
    in_rotation += sum(1 for n in day["aux"].values() if n)

    g = [0, 0, 0]
    for wave_rows in groups.values():
        pass  # already counted above
    g1 = len(groups[1]); g2 = len(groups[2]); g3 = len(groups[3])

    month_name = day["date"].strftime("%B %Y")

    return f"""<article class="page break-page" data-screen-label="{weekday} {esc(day['date_short'])} — Break Sheet" style="--day-color:{day_color};">
  <header class="mast">
    <div class="mast-day-num is-outline">{day['day_num']}</div>
    <div class="mast-meta">
      <div class="day-name">Break Sheet</div>
      <div class="month">{weekday} · {month_name}</div>
      <div class="status">
        <span class="stat"><span class="num">{in_rotation}</span><span class="lbl">In Rotation</span></span>
        <span class="break-bar">
          <span class="lbl">Breaks</span>
          <span class="dot" data-group="1">{g1}</span>
          <span class="dot" data-group="2">{g2}</span>
          <span class="dot" data-group="3">{g3}</span>
        </span>
      </div>
    </div>
    <div class="mast-context">
      <div class="shift">By Break Wave</div>
      {_week_dots_html(day_idx)}
    </div>
  </header>
  <div class="body">
    <div class="break-cols">
{cols_html}
    </div>
    <section class="overlaps-section">
      <h2 class="section-label">
        <svg class="glyph"><use href="#g-overlap"/></svg>
        Overlaps <span class="meta">{ol_filled} / 12 filled</span>
      </h2>
      <div class="overlap-row">
        <div class="overlap-window">11p – 1a<span class="kind">Late evening</span></div>
        <div class="overlap-mini-grid">{pm_minis}</div>
      </div>
      <div class="overlap-row">
        <div class="overlap-window">5a – 7a<span class="kind">Early AM</span></div>
        <div class="overlap-mini-grid">{am_minis}</div>
      </div>
    </section>
  </div>
  <footer class="page-foot">
    <span class="slug-mark"><span class="swatch"></span>GLCR · Grave</span>
    <span class="slug-path"><span class="now">{weekday}</span> {esc(day['date_short'])}<span class="sep">·</span>Break Sheet</span>
    <span class="slug-pn">{page_num} / <span class="pn-cur">{page_total}</span></span>
  </footer>
</article>"""


# ── Public API ────────────────────────────────────────────────────────────────

def _build_page_pair(night_id: str, day_idx: int, total_days: int,
                     page_base: int, page_total: int) -> str:
    """Render the 2 pages (deployment + break sheet) for a single night."""
    night, day, slot_map, overlaps = _fetch_night_data(night_id)
    deploy = _render_deployment_page(
        night, day, slot_map, overlaps,
        page_num=page_base, page_total=page_total,
        day_idx=day_idx, total_days=total_days,
    )
    brk = _render_break_page(
        night, day, slot_map, overlaps,
        page_num=page_base + 1, page_total=page_total,
        day_idx=day_idx,
    )
    return deploy + "\n" + brk


def render_night_html(night_id: str) -> str:
    """Return complete HTML for a single night (2 pages)."""
    res   = (database._client().table("nights").select("night_date, day_name")
             .eq("id", night_id).single().execute())
    night = res.data
    ndate = dt.date.fromisoformat(night["night_date"])
    title = f"{night['day_name']} {ndate.strftime('%B %-d, %Y')}"

    pages = _build_page_pair(night_id,
                              day_idx=1, total_days=1,
                              page_base=1, page_total=2)
    return HTML_SHELL.format(
        week_end_short=title,
        css=CSS + _TM_ANNOTATION_CSS + _CARD_ANNOTATION_CSS + _TASK_ANNOTATION_CSS + _PRINT_LAYOUT_CSS,
        sprite=SVG_SPRITE,
        pages=pages,
    )


def render_week_html(week_id: str) -> str:
    """Return complete HTML for a full week (14 pages)."""
    res  = (database._client().table("weeks").select("*")
            .eq("id", week_id).single().execute())
    week = res.data

    nights = database.fetch_nights(week_id)
    total  = len(nights)
    pages  = []
    for idx, n in enumerate(nights):
        pages.append(_build_page_pair(
            n["id"],
            day_idx=idx + 1,
            total_days=total,
            page_base=2 * idx + 1,
            page_total=2 * total,
        ))

    title = week.get("label") or f"Week ending {week.get('week_ending', '')}"
    return HTML_SHELL.format(
        week_end_short=title,
        css=CSS + _TM_ANNOTATION_CSS + _CARD_ANNOTATION_CSS + _TASK_ANNOTATION_CSS + _PRINT_LAYOUT_CSS,
        sprite=SVG_SPRITE,
        pages="\n".join(pages),
    )


def render_single_card_html(night_id: str, card_code: str) -> str:
    """Return a self-contained portrait HTML page with a single rendered card.

    Intended for the "Print this card" action in the Phase 4k.5 card annotation
    menu. Renders the card at full size on a letter-portrait page with the GLCR
    masthead, a recipient line, and auto-launches print dialog on load.

    card_code: the slot["label"] value from the live UI — e.g. "Zone 1",
    "RR 1 + 2", "Z9 SR", "Admin", "Trash 1", "Support 1", etc.
    """
    night, day, slot_map, _overlaps = _fetch_night_data(night_id)
    # Use the actual calendar weekday from night_date (same convention as _render_deployment_page)
    day_name   = day.get("weekday") or night.get("day_name", "")
    week_id    = night.get("week_id", "")

    week = {}
    if week_id:
        week_res = (database._client().table("weeks")
                    .select("week_ending, label")
                    .eq("id", week_id).single().execute())
        week = week_res.data or {}
    # Derive week_ending (Thursday) from night date — same logic as _render_deployment_page
    _ndate    = day["date"]
    _delta    = (3 - _ndate.weekday()) % 7
    week_ending = str(_ndate + dt.timedelta(days=_delta))
    day_slug = _day_key_from_weekday(day_name) if day_name else "fri"

    # Load annotations
    try:
        _all_annots = _list_annotations_grouped(week_ending, day_slug)
        task_annots = _all_annots.get("task", {})
        tm_annots   = _all_annots.get("tm",   {})
        from .state import _collapse_card_annotations
        card_annots = _collapse_card_annotations(_all_annots.get("card", {}))
    except Exception:
        task_annots = tm_annots = card_annots = {}

    # Build the card HTML for this specific code
    card_html = ""

    # Normalise card_code lookup helpers
    from .database import ZONE_LABELS as _ZL
    # Reverse ZONE_LABELS: display label → slot_key
    _label_to_sk = {v: k for k, v in _ZL.items()}
    sk = _label_to_sk.get(card_code, "")

    if sk and sk.startswith("zone_"):
        try:
            n = int(sk.split("_")[1])
        except (IndexError, ValueError):
            n = 0
        if n:
            s  = slot_map.get(sk, {})
            tm = s.get("tm_name") or ""
            tm_id = s.get("tm_id") or ""
            raw_tasks = (list(s["display_tasks"])
                         if s.get("display_tasks") is not None
                         else [{"id": "", "name": t} for t in TASKS_ZONE.get(n, [])])
            z_tasks = _apply_task_annotations(raw_tasks, task_annots)
            card_html = render_zone_card(
                n, tm, ZONE_COLOR[n],
                z_tasks,
                alert=_alert(sk, slot_map),
                group=_grp(sk, slot_map),
            )
            card_html = _inject_task_highlights(card_html, raw_tasks, task_annots)
            card_html = _apply_tm_annotations(card_html, tm_id, tm, tm_annots)
            card_html = _apply_card_annotations(card_html, card_code, card_annots)

    elif sk and sk.startswith("rr_"):
        rr_num = 1 if sk == "rr_1_2" else int(sk.split("_")[1])
        sm = slot_map.get(f"{sk}_mens",   {})
        sw = slot_map.get(f"{sk}_womens", {})
        alert = (_alert(f"{sk}_mens", slot_map)
                 or _alert(f"{sk}_womens", slot_map))
        card_html = render_rr_card(
            rr_num,
            sm.get("tm_name") or "",
            sw.get("tm_name") or "",
            RR_COLOR[rr_num],
            extra_tasks=None,  # standard tasks from engine; custom tasks omitted in single-card view
            alert=alert,
            mens_group=sm.get("group_num") or None,
            womens_group=sw.get("group_num") or None,
        )
        card_html = _apply_tm_annotations(card_html, sm.get("tm_id", ""),
                                          sm.get("tm_name", ""), tm_annots)
        card_html = _apply_tm_annotations(card_html, sw.get("tm_id", ""),
                                          sw.get("tm_name", ""), tm_annots)
        card_html = _apply_card_annotations(card_html, card_code, card_annots)

    else:
        # Aux card — sk maps to a db_key (z9_sr, admin, trash_1, etc.)
        # For support_3 the label is "Support 3" but sk may be empty in reverse map
        if not sk:
            # Try to find by direct ZONE_LABELS value
            for db_k, lbl in _ZL.items():
                if lbl == card_code:
                    sk = db_k
                    break
        if sk:
            s = slot_map.get(sk, {})
            a_name = s.get("tm_name") or ""
            a_id   = s.get("tm_id") or ""
            # Build the rdb_key the same way aux_order does
            _rdb_key_map = {
                "z9_sr": "z9_sr", "admin": "admin",
                "trash_1": "trash_1_5", "trash_2": "trash_6_10",
                "support_1": "support_1", "support_2": "support_2",
                "support_3": "support_3",
            }
            rdb_key = _rdb_key_map.get(sk, sk)
            card_html = render_aux_card(
                rdb_key, a_name,
                {"z9_sr":"red","admin":"purple","trash_1":"orange",
                 "trash_2":"orange","support_1":"grey","support_2":"grey",
                 "support_3":"teal"}.get(sk, "grey"),
                alert=_alert(sk, slot_map),
                group=_grp(sk, slot_map),
            )
            card_html = _apply_tm_annotations(card_html, a_id, a_name, tm_annots)
            card_html = _apply_card_annotations(card_html, card_code, card_annots)

    if not card_html:
        card_html = f'<p style="color:#ef4444">Card "{esc(card_code)}" not found.</p>'

    week_label = week.get("label") or f"Week ending {week_ending}"

    _SINGLE_CARD_CSS = """
@page { size: letter portrait; margin: 0.5in; }
body { margin: 0; font-family: system-ui, sans-serif; }
.sc-masthead {
  display: flex; align-items: baseline; gap: 12px;
  margin-bottom: 12px; padding-bottom: 8px;
  border-bottom: 2px solid #111827;
}
.sc-title { font-size: 18px; font-weight: 700; color: #111827; }
.sc-sub   { font-size: 12px; color: #6b7280; }
.sc-card-wrap {
  display: flex; justify-content: center; padding: 16px 0;
}
.sc-card-wrap > * { max-width: 340px; width: 100%; }
.sc-recipient {
  margin-top: 20px; padding-top: 12px; border-top: 1px solid #e5e7eb;
  font-size: 12px; color: #6b7280;
}
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{esc(card_code)} — {esc(week_label)}</title>
<style>
{CSS}
{_TM_ANNOTATION_CSS}
{_CARD_ANNOTATION_CSS}
{_TASK_ANNOTATION_CSS}
{_PRINT_LAYOUT_CSS}
{_SINGLE_CARD_CSS}
</style>
<script>window.addEventListener('load', function(){{window.print();}});</script>
</head>
<body>
{SVG_SPRITE}
<div class="sc-masthead">
  <span class="sc-title">GLCR Zone Deployment</span>
  <span class="sc-sub">{esc(week_label)} · {esc(day_name)}</span>
</div>
<div class="sc-card-wrap">
  {card_html}
</div>
<div class="sc-recipient">
  <strong>To:</strong> _____________________&nbsp;&nbsp;
  <strong>From:</strong> Brian Killian&nbsp;&nbsp;
  <strong>Night of:</strong> {esc(day_name)}
</div>
</body>
</html>"""
