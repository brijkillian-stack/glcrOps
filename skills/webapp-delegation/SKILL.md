---
name: webapp-delegation
description: |
  Cross-agent delegation and sync protocol for the GLCR ops webapp
  (brijkillian-stack: GLCR Memory + ZDS, plus the upcoming Shift split).
  Defines who does what across Opus, Sonnet, and Haiku, and codifies the
  agent_logs read/write protocol that keeps all three in sync across
  separate chat windows. Trigger eagerly whenever Brian asks for help with
  the GLCR webapp — features, refactors, deployment, schema changes, page
  builds, debugging — or whenever an agent boots into a session and needs
  to figure out who it is and what's been happening. Also trigger on
  "delegate this", "hand this to Sonnet/Haiku", "what's the next agent
  doing", "catch me up on the session", "log this action", or any mention
  of the agent_logs table.
---

# webapp-delegation

This skill is loaded by **all three agents** (Opus, Sonnet, Haiku) operating
on the GLCR ops webapp (`brijkillian-stack`). It does two jobs:

1. **Defines the delegation matrix** — which agent owns which kind of work.
2. **Codifies the agent_logs protocol** — the Supabase-backed sync substrate
   the three of us use to stay coherent across separate chat windows.

If you are reading this, you are running in one of Brian's three chat
windows. Brian manually copy/pastes prompts between us; we do not call each
other directly. The `agent_logs.actions` table in Supabase
(`iazgrcainbokkdqunkok`) is the only thing that keeps us in sync.

---

## The agents

### Opus — exec / architect / heavy reasoner

- Designs schemas, sub-app splits, page architectures.
- Makes the design and product judgment calls.
- Writes orchestration prompts for Sonnet and Haiku.
- Reviews the final state before declaring a session complete.
- Picks up any task the other two flagged with `status=error` or notes
  that say "needs Opus call."

### Sonnet — implementer

- Multi-file refactors and feature builds.
- Wiring new pages, components, state, routes.
- Code review on diffs.
- Writing migrations and supabase functions when the design is settled.
- Anything that needs careful but not novel reasoning.

### Haiku — searcher / scribe

- Fast targeted searches across the repo or memory backend.
- Single-file edits, find-and-replace, lint sweeps.
- Log digests ("summarize what Sonnet did in this session in 3 bullets").
- Bulk content tasks (renaming, reformatting, simple regex).
- Anything cheap and parallel-friendly.

### Default delegation matrix

| Task shape                                            | Owner   |
|-------------------------------------------------------|---------|
| Architectural calls, naming, IA decisions             | Opus    |
| Sub-app splits, deployment plans                      | Opus    |
| HIG/design audits and critiques                       | Opus    |
| Building a new page from a settled spec               | Sonnet  |
| Multi-file refactor (3+ files)                        | Sonnet  |
| Writing a Supabase migration from a settled schema    | Sonnet  |
| Code review of a Sonnet diff                          | Opus    |
| Searching the repo for "all places that do X"         | Haiku   |
| Single-file lint sweep / formatting                   | Haiku   |
| Summarizing the last N agent_logs rows                | Haiku   |
| Drafting a one-off `tools/*.sh` script                | Haiku   |
| Reading/digesting a long file into 5 takeaways        | Haiku   |
| **Anything you're not sure about**                    | Opus    |

When Opus is unsure whether to delegate, default to Opus doing it.
Capacity is cheaper than rework.

---

## The agent_logs protocol

The substrate is two tables in the `agent_logs` schema of project
`iazgrcainbokkdqunkok`:

- `agent_logs.sessions` — one row per delegation chain.
- `agent_logs.actions`  — one row per meaningful action.
- `agent_logs.recent_actions` — the catch-up view (joins them).

### Rule 1 — Catch up before you act

The first thing **every agent does** when it boots into a session is read
the recent action slice for that session_id. No exceptions. If you don't
have a session_id yet, ask Brian or check `latest_active_session()`.

In Python (when you're running in the brijkillian-stack repo):
```python
from shared.agent_logs import read_recent
rows = read_recent(session_id, limit=50)
```

In raw SQL (Sonnet/Haiku in their own chat windows can use the Supabase
MCP `execute_sql`):
```sql
SELECT agent, agent_role, action_type, target, summary, notes, started_at
FROM agent_logs.recent_actions
WHERE session_id = '<session_id>'
ORDER BY started_at DESC
LIMIT 50;
```

### Rule 2 — Log every meaningful action

"Meaningful" means: a decision, a file write, a migration, a spawn, a
handoff, a deliberate tool call whose record matters for the next agent.
**It does NOT mean every Read/Grep/Glob.** That's noise. Log at the level
where the next agent would be confused without it.

Required fields on every action: `session_id`, `agent`, `action_type`,
`summary`. The single most important optional field is `notes` — use it to
tell the next agent what they need to know.

In Python:
```python
from shared.agent_logs import log_action
log_action(
    session_id,
    agent="sonnet",                          # opus | sonnet | haiku
    agent_role="implementer",                # freeform
    action_type="write",                     # see VALID_ACTION_TYPES
    target="apps/shift/pages/today.py",
    summary="Created Shift app's Today page from the Memory page minus the search box",
    notes="Sidebar links not wired yet — Opus needs to decide if /shift becomes default route.",
)
```

In raw SQL:
```sql
INSERT INTO agent_logs.actions
  (session_id, agent, agent_role, action_type, target, summary, notes)
VALUES
  ('<session_id>', 'sonnet', 'implementer', 'write',
   'apps/shift/pages/today.py',
   'Created Shift app''s Today page from the Memory page minus the search box',
   'Sidebar links not wired yet — Opus needs to decide if /shift becomes default route.');
```

### Rule 3 — Log handoffs explicitly

When you finish a chunk and the next move is for a different agent, write
a `handoff` action. Put the receiving agent in `target` and a complete
brief in `notes`. The receiving agent will read this row first.

```sql
INSERT INTO agent_logs.actions
  (session_id, agent, action_type, target, summary, notes)
VALUES
  ('<session_id>', 'opus', 'handoff', 'sonnet',
   'Hand off Shift sub-app skeleton implementation to Sonnet',
   'Spec: split apps/glcr/ into apps/memory/ and apps/shift/ along the lines documented in actions row <opus_decision_id>. Routes table updated. Three open questions: default route, capture box parity, Grok presence in Shift. Don''t answer those — log them as decision actions and hand back to Opus.');
```

### Rule 4 — End the session when done

The orchestrator (usually Opus) closes out:
```python
from shared.agent_logs import end_session
end_session(session_id, status="completed")
```

```sql
UPDATE agent_logs.sessions
   SET status = 'completed', ended_at = now()
 WHERE id = '<session_id>';
```

---

## Action type vocabulary

| Type        | When to use                                                   |
|-------------|---------------------------------------------------------------|
| `read`      | Read a file/table/resource that mattered for context.         |
| `write`     | Created or edited a file.                                     |
| `migration` | Applied a Supabase migration.                                 |
| `sql`       | Ran a query whose result mattered.                            |
| `spawn`     | Brian was asked to fire a delegation prompt to another agent. |
| `handoff`   | Explicit handoff with full brief in `notes`.                  |
| `decision`  | Recorded a design / architecture / naming call.               |
| `tool_call` | Significant external tool usage (Chrome, MCP, etc.).          |
| `note`      | Freeform sync note for the next agent.                        |

---

## Standard prompt format Opus uses for delegations

When Opus delegates, the output Brian copy/pastes is structured like this:

```
You are the [Sonnet | Haiku] agent in Brian's GLCR ops webapp delegation chain.

SESSION: <session_id>
PARENT ACTION: <parent_action_id>   (optional — set if there's a specific row that triggered you)
ROLE: <implementer | searcher | etc.>

FIRST, READ THE LOG:
  Run: SELECT * FROM agent_logs.recent_actions WHERE session_id='<session_id>' ORDER BY started_at DESC LIMIT 50;
  Or:  read_recent('<session_id>') if you're in the brijkillian-stack repo.

YOUR TASK:
  <one paragraph — what to do, with file paths and line numbers if known>

CONSTRAINTS:
  <anything load-bearing — naming, conventions, things NOT to touch>

WHEN DONE:
  1. Log a `write` (or appropriate) action describing what changed and where.
  2. If anything is ambiguous, log a `note` action with the question.
  3. Log a `handoff` action targeting 'opus' with a one-paragraph brief.
  4. Reply to Brian with the row IDs you wrote so he can confirm.
```

---

## Quick reference

- **Project ID:** `iazgrcainbokkdqunkok`
- **Schema:** `agent_logs`
- **Tables:** `sessions`, `actions`. **View:** `recent_actions`.
- **Helper module:** `shared/agent_logs.py` (in brijkillian-stack repo).
- **Migration of record:** `supabase/migrations/20260505_000001_create_agent_logs_schema.sql`.
- **Bootstrap session id:** `bdf5705e-058e-4592-b9d3-620ec3b7108a`.
