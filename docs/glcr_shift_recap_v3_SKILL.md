---
name: glcr-shift-recap
description: "GLCR grave shift recap skill — v3. LOG mode: captures shift events as natural-language entries throughout the night (call-outs, BEOs, BCOs, MPulse issues, huddle attendees, floor observations, training notes). COMPILE mode: synthesizes captured events into a copy-paste-ready Grave Shift Recap email matching Brian's established structure and voice, addressed to Group - Operations Department. Trigger LOG mode with 'log [entry]', 'add to recap [entry]', 'note [entry]'. Trigger COMPILE mode with 'compile recap', 'draft the recap', 'generate recap', 'build the recap'."
---

# GLCR Shift Recap — v3

This skill runs in two modes. The shift log lives in the GLCR Memory Backend (Supabase `captures` + `events` tables) so COMPILE can pull precisely and `recent()` from any other skill or the dashboard sees entries in real time.

- **LOG mode** — captures shift events via `mcp__glcr-memory__capture` (single) or `capture_batch` (multi-mention bursts)
- **COMPILE mode** — pulls today's captures via `recent(since_days=1)`, drafts the recap email matching Brian's exact structure and voice, outputs as copy-paste text in chat

What changed from v2: schema additions for attendance points / shift attribution / BEO times; tighter LOG-mode parsing; differentiated BCO vs BEO; structured Floor Walk paragraph with voice calibration; copy-paste output (no Outlook integration); iteration support ("rewrite this section / make shorter / drop that mention"); patterns surfaced as a separate chat message (NOT appended to the email body).

---

## Definitions (operational vocabulary — get these right)

| Term | Meaning |
|---|---|
| **Call-out** | TM-initiated absence — they called in, didn't show, or left without permission. Tracked with attendance points like `(7.5pts)`. |
| **BCO** | Business Call-Out — *we* canceled the TM's shift before it started (overstaffed forecast, slow-night cut). Different from a TM call-out. |
| **BEO** | Business Early-Out — *we* let the TM leave their shift early (slow night, overstaffed, request granted). Tracked with rough time. |
| **PTO** | Pre-approved time off. Tracked separately from points. |
| **LOA** | Leave of absence (medical, FMLA, personal). Tracked separately from points. |
| **Possible Intermittent** | Suspected pattern of repeat call-offs; flagged for HR follow-up. |

The recap distinguishes all six. The current SKILL.md often confused them — v3 does not.

---

## Backend tools used

| Tool | When |
|---|---|
| `mcp__glcr-memory__log_event(event_type=shift_log, …)` | At first capture of a shift to anchor the parent event |
| `mcp__glcr-memory__capture` | Per single-event log line |
| `mcp__glcr-memory__capture_batch` | Multi-mention bursts ("Seth callout 7pts, Joy in Z9, BEO Sam 6am") |
| `mcp__glcr-memory__recent(since_days=1)` | COMPILE mode |
| `mcp__glcr-memory__search` | COMPILE mode for any TM-mentioned context not formally logged |

---

## LOG Mode

### Trigger
"log [entry]", "add to recap [entry]", "note [entry]", or any natural-language description of a shift event during graves.

### Step 1 — Determine `shift_date`
Graves runs ~11pm–7am. Use the SHIFT-START date, not the calendar date of the entry. A 2:30am log on April 23 belongs to the April 22 shift.

### Step 2 — On the first capture of the shift, anchor a parent event

```python
log_event(
  event_type="shift_log",
  event_date="YYYY-MM-DD",       # shift_date
  shift="graves",
  title="Graves Shift Log — [Day, Month Date, Year]",
  summary="Supervisor: Brian Killian / Jeff Lawson",
  metadata={"created_via": "glcr-shift-recap-v3"}
)
```

Save the returned `event_id` for use in subsequent captures this shift. Detect "first capture" by querying `recent(content_type=observation, since_days=1)` and checking if any are tagged with today's shift event_id.

### Step 3 — Parse the entry

Map natural-language phrasing into structured captures. Pattern catalog:

| Brian says… | content_type | sentiment | metadata |
|---|---|---|---|
| "Jessica called off, 7.5 points" | flag | flag | `{section: "Call-Outs", points: 7.5, shift: "graves"}` |
| "Mike P on PTO" | flag | neutral | `{section: "Call-Outs", note: "PTO", shift: <inferred>}` |
| "Liz on LOA" | flag | neutral | `{section: "Call-Outs", note: "LOA", shift: <inferred>}` |
| "Sue called in possible intermittent" | flag | flag | `{section: "Call-Outs", note: "Possible Intermittent", shift: <inferred>}` |
| "BCO Eric" | observation | neutral | `{section: "BCOs", shift: <inferred>}` |
| "BEO Joy and Sam at 6am" | observation | neutral | `{section: "BEOs", beo_time: "6am", shift: "graves"}` (one capture per name) |
| "Doug overlap, vacuuming bottles glass" | observation | neutral | `{section: "Overlaps-Graves", task: "Vacuuming, Bottles, and Glass", shift: "graves"}` |
| "Char on overlap, CBK and Shkode" | observation | neutral | `{section: "Overlaps-Days", task: "CBK and Shkode", shift: "days"}` |
| "Z8 men's toilet leaking, addressed" | incident | flag | `{section: "MPulse", location: "Zone 8 Restroom Men's", issue: "toilet leaking excessively", status: "addressed"}` |
| "Joy crushed Z9 SR" | kudos | positive | `{section: "Floor Walk"}` |
| "Liz finished utility training" | observation | positive | `{section: "Floor Walk", subsection: "training"}` |
| "Trenidee no-call no-show, took her off the schedule" | flag | flag | `{section: "Floor Walk", subsection: "incident", action_taken: "removed from schedule"}` |
| "JT, Joy, Carter in huddle" | reference | neutral | `{section: "Huddle"}` (one capture per name OR one combined) |

Inference for `shift`:
- TM identity → which shift they're on (lookup via `entities.metadata.shift` or `tm_profiles.grave_pool`). Default to "graves" if unknown and entry is during graves window.
- For overlaps: explicit ("Doug overlap" = graves PMOL/AMOL; "Char overlap" likely days)

Points/note parsing on call-outs:
- Extract `(N.Npts)` or `(Npts)` → `metadata.points`
- Extract "PTO", "LOA", "Possible Intermittent", "FMLA" → `metadata.note`
- Strip from `content` so the rendered recap reads cleanly

### Step 4 — Capture

Single-event:
```python
capture(
  content="Jessica called off",
  content_type="flag",
  sentiment="flag",
  entities=["Jessica"],
  original_date="YYYY-MM-DD",
  author="brian",
  event_id="<shift_log event_id>",
  metadata={"section": "Call-Outs", "points": 7.5, "shift": "graves",
            "approx_time": "10:30pm"}
)
```

Burst:
```python
capture_batch(items=[
  {"content": "Joy took BEO", "content_type": "observation",
   "sentiment": "neutral", "entities": ["Joy"],
   "metadata": {"section": "BEOs", "beo_time": "6am", "shift": "graves"}},
  {"content": "Sam took BEO", "content_type": "observation",
   "sentiment": "neutral", "entities": ["Sam"],
   "metadata": {"section": "BEOs", "beo_time": "6am", "shift": "graves"}},
])
```

### Step 5 — Confirm
One-line ack: "Logged Jessica callout (7.5pts) under Call-Outs · captured 10:30pm" so Brian knows it landed.

### Step 6 — Pattern surfacing
After every capture, check for:
- **3+ flags for one TM in 14 days** → suggest a coaching conversation, offer `task_create(category=HR)`
- **Repeat MPulse at same location** → search `metadata.location` for prior incidents, surface count
- **No huddle yet by 4am** → prompt Brian if huddle is happening

---

## COMPILE Mode

### Trigger
"compile recap", "draft the recap", "generate recap", "build the recap", "time to write the recap"

### Step 1 — Pull tonight's captures

```python
recent(since_days=1, captured_via=claude)
```

Filter to entries whose `event_id` matches tonight's shift_log event. Group by `metadata.section`.

### Step 2 — Pull supplementary data

- **Engine overrides** for tonight (read from `engine_overrides` table) — surfaces any unavailables not formally logged
- **Email scan** (10:30pm yesterday → 7am today) for call-out notifications, BEO confirmations from Shelly/Josh, BCOs from cross-shift supervisors. Skip Outlook integration; treat as "look here if anything's missing from captures, prompt Brian to add it"
- **TM profiles** for shift attribution (when `metadata.shift` was missing on an entry)

### Step 3 — Compute pattern callouts (held aside for separate chat output)

Before rendering the email body, compute pattern flags:
- **Repeat call-offs**: any TM with 3+ `flag` captures (`section=Call-Outs` or `subsection=incident`) in the last 30 days
- **Repeat MPulse**: same `metadata.location` value with 2+ incidents in the last 14 days
- **No-call/no-show pattern**: any TM with 2+ `action_taken=removed from schedule` in the last 60 days
- **Training milestones**: any TM with `subsection=training` capture this shift — surface for explicit mention in floor-walk paragraph

Save these patterns to a list. They render in Step 7, NOT in the email body.

### Step 4 — Render the subject line

Standard:
```
Graves Recap [Day, Month Date]
```

Escalated variants (auto-detect):
- High incident count (3+ flags + 1+ incident): `Graves Recap [Day, Month Date] — Incident Report`
- Critical short-staffing (filled < target_grave_count - 3): `Graves Recap [Day, Month Date] — Coverage Below Target`

### Step 5 — Render the email body

EXACT template:

```
Grave Shift Recap
Date: [Day] | [Month] [DD], [YYYY]

Team Updates
Days: [list or "None"]
Swings: [list or "None"]
Graves: [list or "None"]
Utilities: [list or "None"]
BCOs: [list or "None"]
BEOs: [list or "None"]

Overlaps
Graves:
[Name] – [task description]
[Name] – [task description]
…

Swings:
[Name] – [task description]
…

Days:
[Name] – [task description]
…

MPulse, Access Control, and Uniform Updates
MPulse: [None, or "[Location] [issue], [status]"]
Access Control: [None or detail]
Uniforms: [None or detail]

Huddle
[List of names] were in huddle today.
OR
No huddle today, [explanation].

Shift & Floor Walk Notes
[3-5 sentence prose paragraph — see voice rules below]

Brian Killian
Operations Supervisor
```

The body ENDS at the signature. No `--- Patterns ---` appended. Patterns go in a separate chat message in Step 7.

### Step 6 — Voice rules for the Shift & Floor Walk Notes paragraph

Compose the paragraph following these rules calibrated from Brian's actual recaps:

1. **First sentence is the night's vibe.** Categorize as: *slow / steady / decently busy / pretty good / busy / hectic*. Pattern: "It was a [vibe] night [optional: with [observation]]."

2. **Capitalize "the Team"** when referring to the crew collectively.

3. **First-person on walks.** "I took her off the schedule." "My final walk through had a few areas of opportunity." "After going through the final walk…"

4. **Training milestones get explicit mention** when they happen. Pattern: "[Name] [milestone description] today, [reflection]." Example: "Liz finished Utility training today, and Eric spent the shift with the swing arm in the Manager Hallway."

5. **Sequence of typical content blocks** (use 2–4 of these per paragraph, not all):
   - Vibe + staffing observation
   - Notable performance / training
   - Calls or incidents handled
   - Final walk findings
   - Closing line

6. **Closing line** — one of:
   - "Nothing too much to report."
   - "Nothing else of major concern to report."
   - "All things considering, everything went well and nothing too much to report."
   - "[Issues] were given attention as they were pointed out."
   - "[Items] were delegated accordingly."

7. **Action verbs:** handled, addressed, delegated, given attention, took care of, accomplished, kept up on, managed.

8. **No personal pronouns about specific TMs in negative context** unless it's an action Brian took ("I took her off the schedule"). Don't write "Trenidee was lazy" — write "Trenidee no called no showed."

9. **Tense:** past tense throughout. The recap is a retrospective.

10. **Length:** 3–5 sentences. NOT shorter (feels lazy), NOT longer (loses operations dept's attention).

### Step 7 — Output (TWO separate chat messages)

**Message 1 — the email itself, copy-paste ready.** Output two clearly-labeled blocks:

```
**Subject:**
Graves Recap Wed, May 6

**Body:**
[full email text, signature, no patterns]
```

DO NOT navigate to Outlook. DO NOT attempt to send. Brian copy-pastes manually.

**Message 2 — patterns reference (only if any patterns were detected in Step 3).** Send AFTER Message 1, in a separate chat message clearly framed as supervisor-only reference. Format:

```
📊 **Patterns flagged for your reference (not part of the email):**

• Eric — 4th call-out this month
• Zone 8 men's RR — 2nd MPulse this week
• Trenidee — 2nd no-call/no-show in 30 days
• Training milestone tonight: Liz finished Utility training (already woven into the floor-walk paragraph above)

These don't go in the email. Action items: consider an HR conversation for Eric, escalate the recurring Z8 MPulse to facilities, document Trenidee's removal.
```

If no patterns detected, skip Message 2 entirely. Don't send a "no patterns to report" stub.

### Step 8 — Log the COMPILE event

```python
log_event(
  event_type="shift_recap",
  event_date="YYYY-MM-DD",
  shift="graves",
  title="Recap drafted - graves [date]",
  summary="<first 200 chars of body>",
  metadata={
    "compiled_at": "<now>",
    "n_captures": N,
    "n_emails_referenced": M,
    "patterns_flagged": [...],
  }
)
```

### Step 9 — Iteration support

After the initial output, accept refinement requests:
- "Rewrite the floor walk section, more detail" → regenerate just that paragraph, output the full body again
- "Drop the BEO mention" → remove the BEOs row, recompose
- "Make this shorter" → cut floor-walk paragraph to 3 sentences max
- "Add that Eric was on training" → augment the floor-walk paragraph
- "Change Sue's points to 5pts" → edit the captured entry's metadata, regenerate

Each iteration outputs a fresh full-body block (don't show diffs). Don't re-send the patterns message unless new patterns surface.

### Step 10 — Flag gaps

After the email + patterns output, summarize in chat (NOT in the email):
- Sections that were empty (no captures, no email evidence)
- Anything in emails that seemed important but didn't fit the template
- Any `[?]` placeholders that need filling

---

## Guardrails

- Captured notes are the permanent record. Do not delete or edit captures after compile (use iteration step to overlay corrections in metadata, not destructive edits)
- Output is copy-paste only. Never attempt to send the email or open Outlook
- If the zone sheet can't be parsed, skip Overlaps section and note it; do not halt the compile
- Match Brian's voice — never write platitudes ("It was a great night working with the amazing Team!"). Factual + slightly conversational + closes neatly
- HR-related captures auto-tag — they show in the right Inbox section
- Patterns NEVER appear in the email body. They go in Message 2 only.
- Empty patterns list → no Message 2 at all. Don't send a "no patterns" stub.

---

## Reference recaps (4 samples for voice calibration)

The following are real recaps Brian sent. Match this structure, cadence, and voice exactly.

### Sample 1 — Tuesday, May 5, 2026 (slow night, multiple call-offs)

```
Grave Shift Recap
Date: Tuesday | May 05, 2026

Team Updates
Days: Auggie is off and Sue called in (Possible Intermittent)
Swings: Griffin called off, Doug moved from Overlap to Step Up
Graves: Jessica left early (8pts).
Utilities: None.
BCOs: None.
BEOs: None.

Overlaps
Graves:
Gage - Glass, Counters, and Trash
Becca - Tables and Restrooms

Swings:
Darlene – Executive Offices
Sherry B – Zone 6
Jared – Restroom and Zone 1

Days:
Char – CBK and Shkode
Christina – Sandhill and Lobby Bar
LeeAnn - Hotel Offices and Trash

MPulse, Access Control, and Uniform Updates
MPulse: None
Access Control: None
Uniforms: None

Huddle
No huddle today, the two of them will be in tomorrow.

Shift & Floor Walk Notes
We had a few call offs and needed to all carry multiple responsibilities, but the Team managed very well considering. We had 14 Porters, all doubled on areas but the night was relatively slow and any calls were able to be quickly addressed. Liz finished Utility training today, and Eric spent the shift with the swing arm in the Manager Hallway and Executive Floor. All things considering, everything went well and nothing too much to report.

Brian Killian
Operations Supervisor
```

### Sample 2 — Monday, May 4, 2026 (slow + LOA)

```
Grave Shift Recap
Date: Monday | May 04, 2026

Team Updates
Days: LeeAnn called off (7pts), Auggie.
Swings: Alan left at 7pm. Mary and Nicole on PTO.
Graves: Jessica (7.5pts) and Chris (LOA).
Utilities: None.
BCOs: None.
BEOs: None.

Overlaps
Graves:
   * Doug – Vacuuming, Bottles, and Glass
   * Gage - Glass, Counters, and Trash
   * Becca - Tables and Restrooms

Swings:
   * Darlene – Executive Offices
   * Sherry B – Zone 6
   * Jared – Restroom and Zone 1

Days:
   * Char – CBK and Shkode
   * Christina – Hotel Offices, Sandhill and Lobby Bar

MPulse, Access Control, and Uniform Updates
MPulse: None
Access Control: None
Uniforms: None

Huddle
Darryl, Jason, Cookie, and Sam were in huddle today.

Shift & Floor Walk Notes
It was a slow night which worked out well with the low staffing count. 15 Porters for Graves and only 2 AM Overlaps but they were able to all work together and ensure everything was addressed. Liz kept up on training tonight which Brooke is saying is going well – Liz seems to be enjoying it. The floor walk was presentable and there was nothing major that needs attention.
```

### Sample 3 — Saturday, May 2, 2026 (busy + no-call/no-show)

```
Grave Shift Recap
Date: Saturday | May 02, 2026

Team Updates
Days: None
Swings: Michelle B is off, Troy and Mary on PTO
Graves: Trenidee (9pts) and Jeff (5pts)
Utilities: None
BCOs: None
BEOs: Abby, Amanda, Gary, and Tawnya

Overlaps
Graves:
·   Allistair – Vacuuming, Bottles, and Glass
·   Gage - Glass, Counters, and Trash
·   Missy - Tables and Restrooms

Swings:
   * Robby and Jared did trash.
   * Amanda did zone 7.
   * Mike did bottles and glasses.
   * Sherry did executive offices.
   * Tawnya did hotel lobby.

Days:
   * Char – Hotel Offices
   * Christina – Sandhill and Lobby Bar
   * Eric – CBK, Shkode, and Trash
   * LeeAnn – 131 and CBK Offices
   * Mike – CBK and Shkode
   * Tiffany – Trash

MPulse, Access Control, and Uniform Updates
MPulse: None
Access Control: None
Uniforms: None

Huddle
JT, Joy, Carter, Peter, Kaiden, Sherri O, and Jamie were in huddle today.

Shift & Floor Walk Notes
The night was decently busy overall. There were several call throughout the night up until huddle, and the Team was able to address them all accordingly. Trenidee no called no showed, I took her off the schedule for now while we wait to see if she is here on Thursday. My final walk through had a some areas of opportunity but they were given attention as they were pointed out. Nothing else of major concern to report.
```

### Sample 4 — Friday, May 1, 2026 (steady, MPulse incident)

```
Grave Shift Recap
Date: Friday | May 01, 2026

Team Updates
Days: None
Swings: Michelle B is off
Graves: Trenidee (4pts), Peter (7pts), Carter (9pts), and Kaiden (1pt) called off. Jamie is on PTO.
Utilities: None
BCOs: None
BEOs: Joy and Sam took a BEO around 6am

Overlaps
Graves:
   * Allistair – Vacuuming
   * Polly - Glass, Counters, and Trash
   * Becca - Tables and Restrooms
   * Missy - Vacuum, Bottles, and Glass

Swings:
   * Tawnya did executive offices.
   * Amanda and Robby did bottles and glasses.
   * Jared did zone 9 (outside of the smoking room).
   * Mike did zone 10 men's restroom.
   * Alec did trash.

Days:
   * ChyAnn and Char - CBK and Shkode
   * Eric - Hotel Offices, Sandhill, and Lobby Bar
   * Mike - 131 and CBK Offices
   * Tiffany - Trash

MPulse, Access Control, and Uniform Updates
MPulse: Zone 8 Restroom Men's toilet leaking excessively, has been addressed.
Access Control: None
Uniforms: None

Huddle
Scott, Steve, Nikki, Jared, Seth, Jessica, Brooke, and Liz were in huddle today.

Shift & Floor Walk Notes
It was a pretty good night overall with nothing too out of the ordinary happening. Compared to most Fridays it was a slower night which worked in our favor with having to move people around. Liz started Utility Porter training today which went well and she seemed to enjoy the change of pace. There were very few calls starting off but picked up for a moment later in the shift. The Team handled everything well, after going through the final walk there were a few items to take care of and were delegated accordingly.
```

---

## What changed from v2

- Schema additions: `metadata.points` (attendance points), `metadata.note` (PTO/LOA/Possible Intermittent), `metadata.shift` (Days/Swings/Graves), `metadata.beo_time` (rough BEO time), `metadata.location` + `metadata.issue` + `metadata.status` (MPulse-format)
- Differentiated BCO (Business Call-Out, *we* canceled) from BEO (Business Early-Out, *we* let leave early)
- LOG-mode parsing rules for "(7.5pts)", "(LOA)", "(PTO)", "(Possible Intermittent)" patterns
- Subject line variants (standard / incident report / coverage below target)
- Voice calibration block — 10 explicit rules + 4 sample recaps embedded
- Output mode: copy-paste in chat. Outlook integration removed
- Iteration support — "rewrite this section / make shorter / drop that mention"
- **Patterns surfaced as a SEPARATE chat message after the email blocks. Not in the body.** (changed from earlier draft that appended `--- Patterns ---` to the body)
- Removed legacy `Shift Logs/[date]_graves.md` references — backend is source of truth
