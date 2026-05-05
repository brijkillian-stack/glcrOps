# K.4 — Schedule Review Page (architecture sketch)

This is a **design sketch**, not yet an implementation contract. The
intent is to lock the page layout, the dual-pane interaction model, and
the `schedule_overrides` table shape *before* K.2 lands, so Sonnet has
a clear target by the time K.4 starts. Refinements expected once K.2
shows how the canvas behaves on real ZDS pages.

## 1. Why this page exists

The engine reads three input layers today: the ADP weekly schedule
(who's working when), the slots reference data (eligibility, difficulty,
load), and the prior-placement archive (rotation, fatigue). It does NOT
read **supervisor knowledge** — call-offs known in advance, training
days the schedule doesn't encode, "Joy's been having a rough week, give
her something easier Tuesday."

Today that knowledge becomes manual swap edits *after* the engine fills.
Tomorrow it becomes structured input the engine consumes *before* it
fills. K.4 is the page where supervisor knowledge gets encoded.

## 2. Where the page lives

```
Route:  /zds/week/[week_id]/review
File:   apps/zds/pages/schedule_review.py
State:  apps/zds/state.py — extend ZdsState OR new ScheduleReviewState
```

Add a "Review" link in the week-overview header next to the existing
nav. The review page is upstream of `deployment.py` — supervisors land
here AFTER the ADP upload but BEFORE running the engine.

## 3. The page layout (iPad-first, 1024-1366pt)

```
┌──────────────────────────────────────────────────────────────────────┐
│ HEADER                                                               │
│   Week of Fri 5/8 → Thu 5/14                                         │
│   ◀ prev week         next week ▶          [Run Engine]              │
│   ─────────────────────────────────────────────────────              │
│   ⦿ Read   ◯ Annotate   ◯ Override          12 overrides this week   │
└──────────────────────────────────────────────────────────────────────┘
┌────────────────┬─────────────────────────────────────┬───────────────┐
│ TM             │  Fri  Sat  Sun  Mon  Tue  Wed  Thu  │ OVERRIDES PANE│
│ ─────────────  │  ───  ───  ───  ───  ───  ───  ───  │  (override    │
│ Joy            │   ✓    ✓    ·    ✓    ⚠    ✓    ·   │   mode only)  │
│ Cookie         │   ·    ✓    ✓    ✓    ✓    ·    ·   │               │
│ Sheri O        │   ✓    ✓    ✓    ⊘    ·    ·    ·   │               │
│ Seth (D5)      │   ·    ·    ·    ·    ·    ✓◐   ·   │               │
│ ...                                                  │               │
│                                                      │               │
│      [free-form PencilCanvas overlay in annotate mode]               │
└──────────────────────────────────────────────────────────────────────┘
```

Cell glyphs (rendered as small icons when overrides exist, plain ✓ /
· otherwise):
- ✓ — TM scheduled this day per ADP
- · — TM not scheduled
- ⚠ — has override of any kind (badge color matches type)
- ⊘ — `unavailable` override (call-off known in advance)
- ◐ — `training_pair` override (paired with another TM that day)

The badges aren't part of v1 — start with monochrome ✓ / · and a tiny
dot indicator for "has any override." Color/icon variety can come later.

## 4. UI modes

Three modes, exposed as radio segments in the header:

```
READ MODE      Default. Schedule is shown read-only. Override badges
               render. Tapping a cell shows its override list in a
               popover. Pencil does nothing on the grid (Scribble in
               popover text fields still works).

ANNOTATE MODE  PencilCanvas overlay activated. The whole grid sits
               under the canvas; finger taps are ignored on the grid;
               Pencil draws freely. Saves a single PNG against
               (target_type='week', target_id=week_id). Free-form,
               record-only.

OVERRIDE MODE  Tap a cell (finger or Pencil — both fine here) to
               select it. Right-side overrides pane opens with the
               selected cell's existing overrides + a palette of
               override types you can add. Each type has a quick-stamp
               button (one tap = stamp that override on the cell).
               Scribble works in any override's free-text note field.
```

The radio segments correspond exactly to the K.1 `dual_layer_mode`
hook — when in OVERRIDE mode, the page emits cell-coordinate events
to the canvas component which maps them back to (tm_id, date).

## 5. The schedule_overrides table (proposed schema)

```sql
CREATE TABLE public.schedule_overrides (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    week_id         uuid NOT NULL REFERENCES public.weeks(id) ON DELETE CASCADE,
    tm_id           text NOT NULL REFERENCES public.tm_profiles(tm_id) ON DELETE CASCADE,
    override_date   date NOT NULL,
    override_type   text NOT NULL CHECK (override_type IN (
        'unavailable',           -- TM out for the day (early call-off, LOA gap)
        'prefer_easier',         -- soft pref toward lower-load slots
        'avoid_high_load',       -- hard cap on load score this day
        'priority_placement',    -- prioritize for a specific slot (target_slot in payload)
        'training_pair',         -- pair with another TM (target_tm_id in payload)
        'skip_rotation',         -- ignore area-rotation constraint this day
        'special_context'        -- freeform note (no engine effect, record only)
    )),
    payload         jsonb NOT NULL DEFAULT '{}'::jsonb,
                                 -- override-type-specific:
                                 --   unavailable:        {reason}
                                 --   prefer_easier:      {max_difficulty}
                                 --   avoid_high_load:    {max_load}
                                 --   priority_placement: {target_slot, rationale}
                                 --   training_pair:      {target_tm_id, day_number}
                                 --   skip_rotation:      {reason}
                                 --   special_context:    {note} (mirrored to .note)
    note            text,        -- supervisor reasoning, plain text
    source          text NOT NULL DEFAULT 'supervisor'
                        CHECK (source IN ('supervisor','system','auto_detect')),
    created_by      text,        -- author email or display name
    created_at      timestamptz NOT NULL DEFAULT now(),
    expires_at      timestamptz, -- defaults to end-of-week-night (Thu 23:59)
    applied_count   int NOT NULL DEFAULT 0,
                                 -- engine increments each time it consumes this row
    last_applied_at timestamptz,
    UNIQUE (week_id, tm_id, override_date, override_type)
);

CREATE INDEX schedule_overrides_week_idx     ON public.schedule_overrides (week_id, override_date);
CREATE INDEX schedule_overrides_tm_idx       ON public.schedule_overrides (tm_id, override_date DESC);
CREATE INDEX schedule_overrides_active_idx   ON public.schedule_overrides (week_id, expires_at)
    WHERE expires_at IS NULL OR expires_at > now();

ALTER TABLE public.schedule_overrides ENABLE ROW LEVEL SECURITY;
```

The unique constraint allows multiple override TYPES per cell but only
one of each type — so a TM can have both `prefer_easier` AND
`training_pair` on Tuesday, but not two `priority_placement`s. Real
use cases all fit this.

`applied_count` + `last_applied_at` are observability hooks — when the
engine reads an override, it bumps the counter. Lets you ask "which
overrides am I writing that the engine never actually uses?" — feedback
loop for whether your supervisor knowledge is matching engine behavior.

## 6. Engine consumption pattern

The engine refactor (Sonnet's session 579194af) is rewiring the
fill_engine to read from Supabase. K.4 extends that with a single
additional query per fill:

```python
def get_schedule_overrides(week_id: str, night_date: date) -> dict:
    """All non-expired overrides for this week, indexed by tm_id."""
    rows = (db.table('schedule_overrides')
              .select('*')
              .eq('week_id', week_id)
              .eq('override_date', night_date)
              .or_('expires_at.is.null,expires_at.gt.now()')
              .execute().data)
    by_tm = defaultdict(list)
    for r in rows: by_tm[r['tm_id']].append(r)
    return by_tm
```

The engine's eligibility filter (already being designed in 579194af)
applies overrides as it builds the candidate list per slot:

```
1. Start with tm_eligibility for slot_id (long-form Y/N triplets).
2. Filter to TMs scheduled this night per the ADP schedule.
3. Filter OUT TMs with override_type='unavailable' for this date.
4. Apply soft scoring adjustments to remaining candidates:
     - prefer_easier      → boost candidates whose target slot
                            difficulty <= payload.max_difficulty
     - avoid_high_load    → filter OUT candidates whose target slot
                            load > payload.max_load
     - priority_placement → boost candidate when target_slot matches
                            this slot
     - training_pair      → if this slot is the trainer's, prefer
                            placing trainer + trainee adjacent
     - skip_rotation      → ignore the rotation-distance penalty
                            for this candidate
5. Score, rank, place per existing scorecard logic.
6. Increment applied_count for each override row consumed.
```

The hard filter (unavailable) and the soft scoring (everything else)
keep the override types in two clean categories. The engine should
**audit** every override consumed — i.e., the audit JSON the engine
emits should list which overrides influenced which placement, so
supervisors can verify the engine honored their knowledge.

## 7. State shape (sketch)

```python
class ScheduleReviewState(rx.State):
    # Loaded data
    week_id: str = ""
    week_start: str = ""
    week_end: str = ""
    tm_rows: list[dict] = []                 # [{tm_id, display_name, scheduled_dates: [date,...]}]
    overrides: list[dict] = []               # all schedule_overrides rows for this week
    annotation_url: str = ""                 # signed URL of the latest free-form PNG

    # UI state
    ui_mode: str = "read"                    # 'read' | 'annotate' | 'override'
    selected_cell: dict = {}                 # {tm_id, override_date} when in override mode
    palette_open: bool = False

    # Handlers
    @rx.event
    def load_week(self): ...
    @rx.event
    def switch_mode(self, mode: str): ...
    @rx.event
    def select_cell(self, tm_id: str, date_str: str): ...
    @rx.event
    def add_override(self, override_type: str, payload: dict): ...
    @rx.event
    def remove_override(self, override_id: str): ...
    @rx.event
    def handle_pencil_save(self, payload: dict): ...   # canvas → annotations bucket
    @rx.event
    def run_engine(self): ...                # delegates to existing engine_bridge
```

## 8. ADP parsing question

The ADP schedule today is a `.xlsx` file. It gets parsed by the
fill_engine when the engine runs. K.4 needs to render the parsed
schedule **before** the engine runs. Two options:

```
Option A — Re-parse on page load
  schedule_review.py loads the latest xlsx for this week from the
  schedules bucket, parses it, holds the result in state. No persistent
  table for the parsed schedule. Fast to ship; one xlsx parse per page
  load is cheap.

Option B — Persist the parsed schedule
  Create a public.schedule_entries table (week_id, tm_id, work_date,
  shift_start, shift_end, role) and persist after each ADP upload.
  Schedule review reads from the table. More queryable but adds a
  table and an ingest step.
```

**Recommended: Option A for v1.** Adding the persistence table is
cheap to retrofit if it becomes a hot path; YAGNI in the meantime.

## 9. Out of scope for K.4

- Multi-week override views (one week at a time).
- Conflict detection between overrides (e.g., training_pair pointing
  at an unavailable TM). Add when it bites.
- Override templates / saved snippets ("apply my standard easy-night
  preference").
- Engine consumption of `special_context` notes (LLM-driven
  interpretation). Defer to a Phase J integration where Grok reads
  these notes as part of its review pass.
- Real-time sync if multiple supervisors edit the same week.

## 10. Open questions (collect during K.2/K.3, decide at K.4 start)

1. Should the engine refuse to run when `unavailable` overrides leave
   a slot uncoverable? Or run anyway with that slot blank and a loud
   audit flag? Probably the latter (engine never blocks).
2. Override expiry default — strictly end-of-week, or 30 days from
   creation? End-of-week is cleaner; longer TTLs muddy the data.
3. Who can create overrides — only the auth'd user, or any
   pre-authenticated session? Probably auth-gated since this affects
   engine behavior.
4. Engine audit — should consumed overrides be visible in the
   per-night deployment output, so the team sees "Joy avoiding
   high-load slots tonight per supervisor"? Probably yes for the
   internal audit, no for the printed deployment book.

## 11. Build order when K.4 starts

```
1. Apply Migration 7: schedule_overrides table + indexes + RLS
2. Add load_schedule_overrides + apply_overrides helpers in shared/db.py
3. Build ScheduleReviewState + schedule_review.py page
4. Wire PencilCanvas in annotate mode
5. Build the override palette + selected-cell pane
6. Extend the engine refactor's eligibility filter to consume overrides
7. Smoke test: create one override, run engine, verify it's honored
   and applied_count increments
```

Estimated total: **5-7 hr Sonnet time**, after K.1 lands.
