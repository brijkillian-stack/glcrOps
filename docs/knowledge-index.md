# Ops Knowledge Index

**Last updated:** 2026-10-11  
**Purpose:** Living index of active protocols, skills, standing rules, storage locations, and cleanup status for Grok Bot / Graves Ops. Update when material changes occur. Use this as the entry point for durable context.

## Storage Hierarchy (recommended)
- **Durable procedures & checklists:** Skills in `docs/skills/` (version-controlled) + protocol files (e.g. `/workspace/work/paycom/...` or equivalent).
- **Standing rules & preferences:** High-importance entries in Supabase `ai_memories` + Bot memory / description.
- **Transient / nightly state:** Blackboard (`ownership-map.md`, `night-context.md`) and operational tables in Supabase.
- **Compiled understanding / Wiki:** Documents folder or promoted captures.
- **Live ops data:** Graves Ops / Supabase tables (zone_assignments, tm_profiles, etc.).

## Active Skills & Protocols
- **Graves TM Timecard Approval**  
  Path: `docs/skills/Graves_TM_Timecard_Approval_Skill.md`  
  Also: `/workspace/work/paycom/graves-tm-timecard-approval-protocol.md`  
  Key rules: No redundant pulls (<30-60 min verified), outlier tracker, hold-for-send, Paycom locks, primary sup map, short reply style.

- **GLCR Shift Recap v3**  
  Path: `docs/glcr_shift_recap_v3_SKILL.md`  
  Modes: LOG (captures) and COMPILE (email draft). Voice-matched, patterns separate, no auto-send.

## Standing Rules (locked)
- C-Suite facilitation: Own the direction (never “Brian said”), lock after one clear recommendation + evidence, no restating, track to close, “approved” tag for live changes, tighter stand-up.
- Hierarchy: Directors room for peer discussion only. No incorrect direct messaging (e.g. Docket to Brian).
- Email: Recipient-aware drafting. Paste-ready body only (Apple Mail, no send cards). Prefer “previously discussed TMs”.
- Knowledge promotion tiers: Tonight/this week → AgentHub/STATE; locked prefs → standing-rules + ai_memories; compiled → Wiki; live data → Graves Ops.

## Key Maps & Contacts
- Primary supervisors: Lincoln Varano → Selner-bell; Tara Martin → Marcia Little; others under Director of Operations.
- Payroll OUT punch edits: Rosie.
- Grave hours: Stay on punch-in date.

## Cleanup / Prune Status (as of 2026-10-11)
- **Retired:** Glitch bot (never route). Confirmed archived/stopped.
- **Discretionary automations under review:** Elon watch, Machine watch, Cascade news/lot, Meritage, changelog, insiders daily — paused or low-priority if not delivering value on graves.
- **Early experimental:** OpenClaw / Vesper / Maxim / local LLM configs from early 2026 — archive if unused.
- **Docs prune:** Older May 2026 engine findings and superseded specs can be archived to `docs/archive/`.
- **Memories:** Prefer high-importance tagged entries for standing rules. Prune one-off or duplicate low-value ai_memories periodically.

## How to Use
1. Start here for context on active processes.
2. Follow linked skills/protocols for execution details.
3. After successful runs, promote new durable rules here or to skills/memories.
4. Monthly audit: review lastTurnAt on bots, prune unused, update this index.

**Next review:** After next graves approval cycle or on request.
