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

    def zone_tasks(n: int) -> list:
        """Use DB display_tasks (respects custom overrides + sweeper); fallback to defaults."""
        sk   = f"zone_{n}"
        s    = slot_map.get(sk, {})
        base = list(s["display_tasks"]) if s.get("display_tasks") is not None \
               else list(TASKS_ZONE.get(n, []))
        # sw_add may carry sweeper task; only append if not already in list
        for t in sw_add.get(f"zone_{n}", []):
            if t not in base:
                base.append(t)
        return base

    def rr_extra_tasks(rr_sk: str) -> list | None:
        """Collect custom-added tasks for an RR bank (sweeper + any user additions)."""
        sm   = slot_map.get(f"{rr_sk}_mens",   {})
        sw   = slot_map.get(f"{rr_sk}_womens", {})
        n    = _RR_NUM.get(_RR_IDX.get(rr_sk, -1), -1)
        base = set(TASKS_RR.get(n, []))
        # Pull user-added tasks from mens or womens display_tasks beyond the defaults
        extras = []
        for s in (sm, sw):
            for t in (s.get("display_tasks") or []):
                if t not in base and t not in extras:
                    extras.append(t)
        # Add sweeper label from sw_add
        for t in sw_add.get(f"rr_{n}", []):
            if t not in extras:
                extras.append(t)
        return extras or None

    def aux_extra_tasks(db_key: str, rdb_key: str) -> list | None:
        """Collect custom-added tasks for an aux slot beyond its defaults."""
        s    = slot_map.get(db_key, {})
        _, sub = TASKS_AUX.get(rdb_key, ("", ""))
        base = {sub} if sub else set()
        extras = []
        for t in (s.get("display_tasks") or []):
            if t not in base and t not in extras:
                extras.append(t)
        for t in sw_add.get(f"aux_{rdb_key}", []):
            if t not in extras:
                extras.append(t)
        return extras or None

    # Zone cards
    zone_cards = []
    for n in range(1, 11):
        sk = f"zone_{n}"
        s  = slot_map.get(sk, {})
        zone_cards.append(render_zone_card(
            n, s.get("tm_name") or "", ZONE_COLOR[n],
            zone_tasks(n),
            alert=_alert(sk, slot_map),
            group=_grp(sk, slot_map),
        ))

    # RR cards
    rr_nums = [1, 6, 7, 8, 10]
    rr_cards = []
    for idx, n in enumerate(rr_nums):
        rr_sk = "rr_1_2" if n == 1 else f"rr_{n}"
        sm    = slot_map.get(f"{rr_sk}_mens",   {})
        sw    = slot_map.get(f"{rr_sk}_womens",  {})
        alert = _alert(f"{rr_sk}_mens", slot_map) or _alert(f"{rr_sk}_womens", slot_map)
        rr_cards.append(render_rr_card(
            n,
            sm.get("tm_name") or "", sw.get("tm_name") or "",
            RR_COLOR[n],
            extra_tasks=rr_extra_tasks(rr_sk),
            alert=alert,
            mens_group=sm.get("group_num") or None,
            womens_group=sw.get("group_num") or None,
        ))

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
        s     = slot_map.get(db_key, {})
        aux_cards.append(render_aux_card(
            rdb_key, s.get("tm_name") or "", color,
            extra_tasks=aux_extra_tasks(db_key, rdb_key),
            alert=_alert(db_key, slot_map),
            group=_grp(db_key, slot_map),
        ))
    s3 = slot_map.get("support_3", {})
    if s3.get("tm_name"):
        aux_cards.append(render_aux_card(
            "support_3", s3["tm_name"], "teal",
            alert=_alert("support_3", slot_map),
            group=_grp("support_3", slot_map),
            conditional=True,
        ))
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
        Zones <span class="meta">{zones_f} / 10 staffed</span>
      </h2>
      <div class="zones-grid">
{zones_html}
      </div>
    </section>
    <section>
      <h2 class="section-label">
        <svg class="glyph"><use href="#g-restroom"/></svg>
        Restrooms <span class="meta">{rr_f} / 10 staffed</span>
      </h2>
      <div class="rr-grid">
{rr_html}
      </div>
    </section>
    <section>
      <h2 class="section-label">
        <svg class="glyph"><use href="#g-aux"/></svg>
        Auxiliary <span class="meta">{aux_f} / {aux_t} staffed</span>
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
        tasks = ([side_label] if side_label else []) + list(TASKS_RR.get(n, []))
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
    if rdb_key:
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
      <div class="group-key">Take breaks together</div>
    </div>
  </header>
  <div class="body">
    <div class="break-cols">
{cols_html}
    </div>
    <section class="overlaps-section">
      <h2 class="section-label">
        <svg class="glyph"><use href="#g-overlap"/></svg>
        Overlaps <span class="meta">{ol_filled} / 12 staffed</span>
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
        css=CSS,
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
        css=CSS,
        sprite=SVG_SPRITE,
        pages="\n".join(pages),
    )
