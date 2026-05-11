# ZDS PDF Export — File & Code Reference

Every file, function, constant, CSS section, and call path that participates in producing a Zone Deployment Book PDF. Compiled 2026-05-10.

There is no separate template engine. The system is **one CSS string + one HTML shell**, both embedded in Python, plus design-reference HTML files in `design/zds_redesign/` that the production CSS was lifted from. PDF generation in the webapp is browser-driven (Cmd+P / Save as PDF); the standalone CLI path uses Playwright + Chromium.

---

## 1. Pipeline at a Glance

```
                          ┌──────────────────────────────────┐
                          │  User clicks "Print Day" /       │
                          │  "Print Week" in the ZDS app     │
                          └──────────────┬───────────────────┘
                                         │
            apps/zds/pages/week_overview.py  (Print buttons)
            apps/zds/pages/deployment.py     (Print Day button)
                                         │
                                         ▼
            apps/zds/state.py
              • open_print_night(night_id)
              • open_print_current_night()
              • open_print_current_week()
                                         │
                  render_night_html() / render_week_html()
                                         │
                                         ▼
            apps/zds/print_renderer.py
              • dynamically imports render_deployment_book.py
              • feeds it Supabase data (not an xlsx)
              • stacks annotation CSS layers on top of CSS
                                         │
                                         ▼
            apps/zds/engine/render_deployment_book.py
              • CSS  (the stylesheet)
              • SVG_SPRITE  (icon defs)
              • HTML_SHELL  (the template)
              • render_zone_card / render_aux_card / render_rr_card
              • render_overlap_mini / render_break_col
              • render_day_page / render_break_sheet_page
                                         │
                          HTML string returned
                                         │
                                         ▼
            print_cache/<filename>.html  (written by state.py)
                                         │
                            served by Caddy /print_cache/*
                                         │
                                         ▼
            Browser opens HTML in a new tab
            User hits Cmd+P → Save as PDF
            (Landscape · Letter · No margins · 100% · ☑ Background graphics)
                                         │
                                         ▼
                          Final PDF on the user's machine
```

Standalone CLI path (used by the `glcr-grave-deployment` skill) skips state.py + browser and produces the PDF directly via Playwright:

```
xlsx ─► render_deployment_book.py main(argv) ─► Zone Deployment Book - YYYY-MM-DD.html
                                              ─► Zone Deployment Book - YYYY-MM-DD.pdf
```

---

## 2. The Production Renderer

### 2.1 — `apps/zds/engine/render_deployment_book.py` (2,599 lines)

The canonical renderer. Single source of truth for everything that ends up on a printed page. Imports are at the top of the file:

```python
import sys, re, base64, json
import datetime as dt
from pathlib import Path
from openpyxl import load_workbook

from shared.db import (
    get_overlap_tasks_for_engine,
    get_training_schedule_from_db,
    get_engine_roster_from_db,
    get_engine_profiles_from_db,
    get_zone_tasks_for_engine,
    list_tasks,
)
```

#### File map by line range

| Lines | Section | Purpose |
|---|---|---|
| 1–60 | Module docstring | Documents v2.3 page model, redesign decisions, color taxonomy |
| 60–155 | **Configuration constants** | `ZONE_COLOR`, `RR_COLOR`, `DAY_COLOR`, `BG_ZONE`, `BG_RR_M`, `BG_RR_W`, `BG_AUX`, `MANUAL_ALERTS`, `SWEEPER_REASSIGNMENTS`, `OVERLAP_OVERRIDES`, task lists (`TASKS_ZONE`, `TASKS_RR`, `TASKS_AUX`, `TASKS_PM_OL`, `TASKS_AM_OL`) |
| 154–198 | `_load_tasks_from_db()` | Pulls canonical task lists from Supabase via `list_tasks()` |
| 199–244 | `load_overlap_tasks()` | Loads PM/AM overlap task strings + per-day overrides |
| 245–362 | `compute_alerts(day)` | Auto-derived coverage banners ("And Zone 9" etc.) from staffing |
| 363–435 | Glyph & banner helpers | `icon_for_task`, `_render_task_li`, `alert_to_short`, `cover_tag`, `alert_banner_text`, `alert_strip` |
| 436–523 | Counters & summaries | `count_summary`, `count_break_groups`, `total_in_rotation`, `abbrev_task`, `join_assigns` |
| 524–664 | **Break-sheet logic** | `build_break_groups(day, sweeper_add)` and `render_break_col(group_num, rows)` |
| 665–744 | Data loaders | `load_utility_porters`, `read_week(xlsx_path)`, `load_training_config`, `load_gender_info` |
| 793–846 | `assign_sweepers(day, males, no_sweeper)` | Per-day sweeper auto-assignment |
| 847–855 | `esc(s)`, `name_or_unfilled(s, classes)` | HTML escape + empty-slot placeholder |
| **856–917** | **`render_zone_card(num, name_str, color, tasks, alert, group, ...)`** | One zone card (Z1 – Z10) |
| **918–991** | **`render_aux_card(key, name_str, color, extra_tasks, alert, group, ...)`** | Z9 SR, Admin, Trash 1-5, Trash 6-10, Support 1, Support 2, Support 3 |
| **992–1038** | **`render_rr_card(rr_num, mens, womens, color, extra_tasks, alert, ...)`** | Split men's/women's restroom card |
| **1039–1053** | **`render_overlap_mini(name, task)`** | PM/AM overlap mini-card |
| 1054–1068 | `_compute_sweeper_add(day, males, no_sweeper_tms)` | Sweeper-add map for break sheet |
| **1069–1306** | **`render_day_page(day, idx, total, days, current_idx, ...)`** | The Daily Deployment page (one of the two pages per day) |
| **1307–1400** | **`render_break_sheet_page(day, idx, total, ...)`** | The Break Sheet page (page 2 per day) |
| **1407 – ~2440** | **`CSS = r"""..."""`** | The full landscape stylesheet (≈1,000 lines) |
| **2441 – 2475** | **`SVG_SPRITE = """..."""`** | All icon `<symbol>` defs |
| **2476 – 2528** | **`HTML_SHELL = """..."""`** | Top-level HTML template literal |
| 2529 – 2599 | `main(argv)` | CLI entry. Reads xlsx, builds pages, writes HTML, runs Playwright for PDF |

#### The three template literals

**`CSS`** at line 1407 — the entire stylesheet, prefixed with the comment:

```
# CSS — LANDSCAPE REDESIGN (Phase 6, 5/6/26)
# Lifted directly from design/zds_redesign/zds_print_landscape_template.html
# Operational color taxonomy (DAY_COLORS, ZONE_COLOR, RR_COLOR) UNCHANGED.
# Page model: 11in × 8.5in landscape. CSS variables inject --day-color and
# --card-color per-page and per-card. Renders as-is with no mediator layer.
```

Major CSS sections inside the string:

| Selector / block | Purpose |
|---|---|
| `@import url('https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=Barlow:wght@400;500;600;700;800&display=swap')` | Type imports — Atkinson Hyperlegible primary, Barlow display |
| `:root { --safe, --page-w, --page-h, --ink-900…--ink-100, --gold, --gold-lt, --hairline, --c-yellow, --c-red, --c-pink, --c-blue, --c-brown, --c-green, --c-orange, --c-purple, --c-grey, --c-teal }` | All design tokens. Card colors injected via `--card-color` per element |
| `.c-yellow { --card-color: var(--c-yellow); }` etc. | Color-family classes that bind `--card-color` for the 3px top stripe on `.zone-card::before` |
| `body { background: url("data:image/svg+xml;base64,...") }` | Big base64-embedded SVG playing-card scatter watermark behind every page (line ~1484) |
| `.page` | 11×8.5in landscape container, one per physical sheet |
| `.zone-card`, `.zone-card::before`, `.zone-card .zone-name`, `.zone-card .tasks` | Zone card layout and 3px top stripe |
| `.aux-card`, `.aux-card::before` | Auxiliary cards (Z9 SR, Admin, Trash, Support) |
| `.rr-card`, `.rr-mens`, `.rr-womens`, `.rr-tasks` | Restroom split card |
| `.overlap-mini` | PM/AM overlap mini-card |
| `.break-page`, `.break-col`, `.break-row` | Break sheet grid |
| `.masthead`, `.day-number`, `.day-name`, `.day-of-7`, `.break-bar` | Daily page masthead |
| `.foot-mark`, `.swatch` | "GLCR · Grave" page-foot slug |
| `@media print { @page { size: 11in 8.5in landscape; margin: 0; } ... }` | Print-mode rules. Forces background graphics, hides screen-only chrome, pins each `.page` to one physical sheet |

**`SVG_SPRITE`** at line 2441 — every glyph the daily and break pages reference. Lives once in `<body>`, referenced via `<use href="#g-...">`:

| Sprite id | Use |
|---|---|
| `g-zones`, `g-aux`, `g-restroom`, `g-overlap` | Section icons in masthead / break-sheet headers |
| `g-walk`, `g-smoke`, `g-toilet`, `g-trash`, `g-glass`, `g-table`, `g-broom`, `g-pit`, `g-elevator` | Task-list bullet icons (`icon_for_task` picks the glyph by task keyword) |
| `g-alert`, `g-question`, `g-key`, `g-link` | Coverage / alert banner glyphs |
| `sh-1` through `sh-10` | Zone shape sprites (5/1/26 accessibility — one geometric mark per zone, distinct at a glance for low-vision TMs). RR cards inherit the shape of their corresponding zone |

**`HTML_SHELL`** at line 2476 — the page template literal:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Zone Deployment Book — {week_end_short}</title>
<style>{css}</style>
</head>
<body>
{sprite}
<aside class="print-helper screen-only" id="ph-helper">
  <button class="print-helper-close" onclick="hidePrintHelper()" ...>×</button>
  <button class="print-btn" onclick="window.print()">Print Book</button>
  <div class="print-tips">
    <strong>Print Settings:</strong>
    Landscape · Letter (8.5×11) · No margins · 100% scale · ☑ Background graphics
  </div>
</aside>
<button class="print-mini screen-only" id="ph-mini"
        onclick="if(event.shiftKey){{showPrintHelper()}}else{{window.print()}}"
        title="Click to print · Shift+Click to show settings">Print</button>
<script>
  /* persist hide/show preference via localStorage('glcr_print_helper_hidden') */
</script>
{pages}
</body>
</html>
```

Slots: `{week_end_short}`, `{css}`, `{sprite}`, `{pages}`. The screen-only "Print Book" floating button and its minimised counterpart are stripped by `@media print { .screen-only { display: none } }`.

#### Configuration constants (lines 60–155)

```python
ZONE_COLOR = {
    1: "yellow", 2: "yellow", 3: "red", 4: "red", 5: "red",
    6: "pink",   7: "blue",   8: "brown", 9: "red", 10: "green",
}
RR_COLOR = { 1: "yellow", 6: "pink", 7: "blue", 8: "brown", 10: "green" }
DAY_COLOR = { "Friday": ..., "Saturday": ..., ... }  # per-day accent

# Canonical per-slot task lists
TASKS_ZONE, TASKS_RR, TASKS_AUX, TASKS_PM_OL, TASKS_AM_OL

# Background tint per card family
BG_ZONE, BG_RR_M, BG_RR_W, BG_AUX

# Manual overrides editable in-script:
MANUAL_ALERTS = {
    # "2026-04-28": {"aux_mp_1": "ADP Training"}
}
SWEEPER_REASSIGNMENTS = {
    # "2026-04-29": {"sweeper_9_10_sr": "rr_8"}
}
OVERLAP_OVERRIDES = {
    # per-day PM/AM overlap task overrides
}
```

#### CLI invocation

```bash
python3 apps/zds/engine/render_deployment_book.py \
    "Outputs/2026-04-30/Week Overview - Filled - 2026-04-30.xlsx" \
    "Zone Deployment Book - 2026-04-30.html"
```

Produces both the `.html` and a matching `.pdf` (Playwright + Chromium, landscape Letter, no margins).

---

### 2.2 — `apps/zds/print_renderer.py` (1,427 lines)

The webapp's print path. Does *not* reimplement the renderer — dynamically imports it and reuses everything.

```python
# Lines 20–32 — dynamic import of the engine
_RDB_PATH = Path(__file__).resolve().parent / "engine" / "render_deployment_book.py"
_spec = importlib.util.spec_from_file_location("_rdb", _RDB_PATH)
_rdb  = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_rdb)

# Lines 33–60 — pull in constants + card-level render functions
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
HTML_SHELL         = _rdb.HTML_SHELL
SVG_SPRITE         = _rdb.SVG_SPRITE
CSS                = _rdb.CSS
```

#### Public entry points

| Function | Returns | Used by |
|---|---|---|
| `render_week_html(week_id: str) -> str` | Full 14-page book HTML | `state.open_print_current_week` |
| `render_night_html(night_id: str) -> str` | 2-page single night HTML | `state.open_print_night` / `state.open_print_current_night` |
| `render_single_card_html(night_id: str, card_code: str) -> str` | One-card handout HTML | "Print this card" path |

#### Additional CSS layers stacked on top of `CSS`

```python
# Line 61
_TM_ANNOTATION_CSS = """
  /* TM annotation badges (e.g. trainee, restricted, new) on names */
"""

# Line 80
_CARD_ANNOTATION_CSS = """
  /* Card-level annotation overlays (highlight, dim, note pill) */
"""

# Line 115
_TASK_ANNOTATION_CSS = """
  /* Task-level annotations: strikethrough, highlight, sub-note */
"""

# Line 130
_PRINT_LAYOUT_CSS = """
  /* Webapp print-mode overrides — page geometry, header/footer */
"""

# Line 1377 — used only by render_single_card_html
_SINGLE_CARD_CSS = """
  @page { size: letter portrait; margin: 0.5in; }
  body { margin: 0; font-family: system-ui, sans-serif; }
  .sc-masthead { ... }
  .sc-title    { ... }
  .sc-sub      { ... }
  .sc-card-wrap, .sc-recipient { ... }
"""
```

Composition at call sites:

```python
# Line 1216 — render_night_html / render_week_html
return HTML_SHELL.format(
    css=CSS + _TM_ANNOTATION_CSS + _CARD_ANNOTATION_CSS + _TASK_ANNOTATION_CSS + _PRINT_LAYOUT_CSS,
    sprite=SVG_SPRITE,
    pages=pages_html,
    week_end_short=...,
)

# Line 1408 — render_single_card_html uses its own template (not HTML_SHELL)
return f"""<!DOCTYPE html>...<style>
{CSS}
{_TM_ANNOTATION_CSS}
{_CARD_ANNOTATION_CSS}
{_TASK_ANNOTATION_CSS}
{_PRINT_LAYOUT_CSS}
{_SINGLE_CARD_CSS}
</style>
<script>window.addEventListener('load', function(){{window.print();}});</script>
..."""
```

#### Internal helpers (file map)

| Lines | Function | Purpose |
|---|---|---|
| 154–188 | `_inject_coverage_outline(card_html, display_tasks)` | Re-emits coverage outline tags on cards |
| 189–215 | `_week_dots_html(day_idx)` | Week-strip dot indicator (1 of 7 …) |
| 216–305 | `_fetch_night_data(night_id)` | Pulls slot data from Supabase for one night |
| 306–326 | `_sweeper_add(slot_map)` | Sweeper-add mapping built from DB rows |
| 327–345 | `_alert(sk, slot_map)`, `_grp(sk, slot_map)` | Per-slot alert text + break-group lookup |
| 346–402 | `_day_key_from_weekday`, `_apply_task_annotations` | Day-key derivation; task annotation merge |
| 403–443 | `_inject_task_highlights(card_html, task_items, annots)` | Mutates task `<li>`s to add highlight classes |
| 444–497 | `_apply_tm_annotations(card_html, tm_id, tm_name, ...)` | Wraps TM name in badge spans |
| 498–577 | `_apply_card_annotations(card_html, card_code, ...)` | Card-level note pill / dim / highlight |
| 578–592 | `_notice_badges_html(slot_key, notices_by_slot)` | Per-slot notice badges (e.g. callout pending) |
| **593–904** | **`_render_deployment_page(night, day, slot_map, ...)`** | Builds one Daily Deployment page from DB data |
| 905–951 | `_wave_for_slot_ref`, `_break_row_meta` | Break-wave classification |
| **1079–1185** | **`_render_break_page(night, day, slot_map, ...)`** | Builds one Break Sheet page from DB data |
| **1186–1202** | **`_build_page_pair(night_id, day_idx, total_days, ...)`** | Returns `(deployment_html, break_html)` for one night |
| 1203–1248 | `render_night_html`, `render_week_html` | Compose final HTML via `HTML_SHELL.format(...)` |
| 1249–1426 | `render_single_card_html` | One-card handout path |

---

## 3. The Webapp Trigger Path

### 3.1 — `apps/zds/state.py` (lines 1495 – 1565)

Three Reflex state handlers wire the Print buttons:

```python
_PRINT_CACHE = _PROJ_ROOT / "print_cache"   # line 45

def open_print_night(self, night_id: str):
    """Generate and open a 2-page print view for a specific night."""
    _PRINT_CACHE.mkdir(parents=True, exist_ok=True)
    from .print_renderer import render_night_html
    ts = int(_t.time())
    fname = f"night_{night_id}_{ts}.html"
    try:
        html = render_night_html(night_id)
        (_PRINT_CACHE / fname).write_text(html, encoding="utf-8")
        return rx.call_script(f"window.open('/print_cache/{fname}', '_blank')")
    except Exception as e:
        # falls back to writing an error-page HTML and opening that
        ...

def open_print_current_night(self):
    """2-page print for the currently-loaded night."""
    # same shape, uses self.current_night_id

def open_print_current_week(self):
    """14-page print for the currently-loaded week."""
    # same shape, calls render_week_html
```

There is **no headless-Chromium / weasyprint step in the webapp** — the user's browser does the PDF rendering via Cmd+P → Save as PDF. The standalone CLI path (`render_deployment_book.py main`) is the only one that produces a `.pdf` file directly.

### 3.2 — `apps/zds/pages/week_overview.py`

```python
# Line 150 — per-night Print button on each night row
rx.icon("printer", size=13),
...
on_click=ZdsState.open_print_night(night["id"]),

# Line 237 — Print Week button in the page header
rx.icon("printer", size=14),
...
on_click=ZdsState.open_print_current_week,
```

### 3.3 — `apps/zds/pages/deployment.py`

```python
# Line 864 — Print Day button on the deployment (zone-card) page
rx.icon("printer", size=14),
...
on_click=ZdsState.open_print_current_night,
```

### 3.4 — `apps/zds/routes.py`

```python
PUBLIC_ROUTES = ["/zds", "/zds/", "/zds/week/[week_id]",
                 "/zds/week/[week_id]/day/[night_id]",
                 "/zds/week/[week_id]/schedule"]

ROUTES = [
    (index,                "/zds",                               "GLCR Deployments", [ZdsState.load_weeks]),
    (week_overview,        "/zds/week/[week_id]",                "Week Overview",    [ZdsState.on_week_overview_load]),
    (deployment,           "/zds/week/[week_id]/day/[night_id]", "Zone Sheet",       [ZdsState.on_day_load]),
    (schedule_editor_page, "/zds/week/[week_id]/schedule",       "Week Schedule",    [ScheduleEditorState.on_load]),
]
```

No `/api/print/*` endpoint — Print uses Reflex's `rx.call_script` to open the HTML file directly from `/print_cache/`.

---

## 4. Serving the HTML

### 4.1 — `Caddyfile` (lines 43 – 53)

```caddy
# Print cache (2026-05-06 — fixes Print Day 404).
# apps/zds/state.py writes per-night and per-week deployment HTML to
# /app/print_cache/. Decoupled from Reflex's .web/build/client/ so it
# survives reflex-export hiccups and doesn't depend on the static-export
# path layout staying stable across Reflex versions.
handle /print_cache/* {
    root * /app
    file_server
}
```

The output filename pattern (set in state.py):

```
print_cache/night_<night_id>_<ts>.html
print_cache/week_<week_id>_<ts>.html
```

The timestamp keeps each open-print a unique URL so cached HTML never overrides a fresh render.

---

## 5. Design References (Source-of-Truth Mockups)

`design/zds_redesign/` — these are reference comps, not loaded at runtime. The CSS in `render_deployment_book.py` was lifted from `zds_print_landscape_template.html`.

| File | Lines | Purpose |
|---|---|---|
| `zds_print_landscape_template.html` | 937 | **Current production source.** Landscape print layout. Production `CSS` constant was lifted from this file (Phase 6, 5/6/26). |
| `zds_print.html` | 937 | Portrait predecessor — kept for diff reference. |
| `zds_dark_v3.html` | 1,845 | On-screen dark-mode comp — not used in print. |
| `screenshots/` | — | Visual baseline snaps for regression eyeballing. |

Editing rule: touching the production renderer's CSS is the right path. The `design/` HTML files are reference comps; changes there don't propagate.

---

## 6. Sample Outputs

`apps/zds/engine/Outputs/`

```
2026-05-07/                              — week of 5/7 (live)
  Zone Deployment Book - 2026-05-07.html
2026-05-14/                              — week of 5/14 (live)
sim_20260507_202725/                     — simulation run
sim_20260507_210335/                     — simulation run
sim_20260507_210355/                     — simulation run
sim_20260507_210459/                     — simulation run
sim_20260507_230235/                     — simulation run
```

Useful as before/after diff targets when changing the renderer.

---

## 7. Tests

`apps/zds/engine/tests/test_regression_weights.py` — covers scorecard weights, not rendering. There is currently no automated visual regression on the print output. Print audit is manual: re-render the book and print one page on the floor printer (see `references/workbook-contract.md §8 — Audit Recipe` in the grave-deployment skill).

---

## 8. Related but Separate Code Paths

| Path | What it is | Why it's not part of print |
|---|---|---|
| `apps/zds/engine/fill_engine.py` | Produces the *data* (workbook) the renderer reads | Upstream — feeds the renderer |
| `apps/zds/components/zone_card.py` | On-screen Reflex card component | Same visual idea, different code path. Lives in the live UI, not the print HTML |
| `apps/zds/engine/glcr_engine/scorecard.py`, `lap_solver.py`, `swap.py` | Placement engine internals | Upstream — produces the slot assignments |
| `apps/zds/database.py` | Supabase reads/writes | Data source for `print_renderer.py` |
| `shared/db.py` | DB helpers (roster, tasks, training, overlap) | Shared by engine + renderer |

---

## 9. Print Settings (Browser-Driven)

Documented in the floating Print Helper in `HTML_SHELL` and in the CSS print block. When the user hits Cmd+P in the opened HTML tab:

| Setting | Value |
|---|---|
| Destination | Save as PDF (or printer) |
| Layout | Landscape |
| Paper size | Letter (8.5 × 11) |
| Margins | None (or "Default" — `@page` sets to 0) |
| Scale | 100% / Default (NOT Fit-to-page) |
| Background graphics | ☑ REQUIRED — turns on color stripes, watermarks, alert banners |

Result: exactly 14 pages for a week book (7 days × 2 pages = Daily + Break Sheet), or 2 pages for a single night.

---

## 10. The Edit Surface

If anything about a printed page needs to change, the edit lives in **`apps/zds/engine/render_deployment_book.py` between lines 1407 and 2528** — that's the only place. Everything else just feeds it.

| Want to change… | Edit at |
|---|---|
| Card top stripe color | `ZONE_COLOR` / `RR_COLOR` (lines 64–67) or the `--c-*` palette in `CSS` :root (line ~1417) |
| Card layout / spacing | `.zone-card`, `.aux-card`, `.rr-card` in `CSS` |
| Page geometry | `@media print { @page { size: 11in 8.5in landscape; margin: 0; } }` (line ~2399) |
| Add / change an icon | `SVG_SPRITE` (line 2441) + the keyword map in `icon_for_task` (line 363) |
| Alert banner copy / glyph | `alert_strip()` (line 429) + `compute_alerts()` (line 245) |
| Manual one-off alert for a date | `MANUAL_ALERTS` dict (top of file) |
| Move a sweeper for a day | `SWEEPER_REASSIGNMENTS` dict (top of file) |
| Task list per slot | `TASKS_ZONE` / `TASKS_RR` / `TASKS_AUX` (top of file) or the DB rows behind `list_tasks()` |
| Webapp annotation badges | `_TM_ANNOTATION_CSS` / `_CARD_ANNOTATION_CSS` / `_TASK_ANNOTATION_CSS` in `print_renderer.py` |
| Single-card handout layout | `_SINGLE_CARD_CSS` + the f-string template at the bottom of `print_renderer.py` (line ~1377) |
| HTML wrapper / Print Helper button | `HTML_SHELL` (line 2476) |
| Background watermark scatter | Base64 SVG inside `body { background: url(...) }` at line ~1484 |

---

## 11. Total LOC

```
apps/zds/print_renderer.py                            1,427 lines
apps/zds/engine/render_deployment_book.py             2,599 lines
design/zds_redesign/zds_print_landscape_template.html    937 lines  (reference)
design/zds_redesign/zds_print.html                       937 lines  (reference)
design/zds_redesign/zds_dark_v3.html                  1,845 lines  (reference)
────────────────────────────────────────────────────────────────
                                          Total       7,745 lines
```

Of which the **live print code path** is `print_renderer.py` (1,427) + `render_deployment_book.py` (2,599) = **4,026 lines**.
