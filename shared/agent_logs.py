"""
shared/agent_logs.py — Cross-agent action log helper.

Reads/writes the `agent_logs.sessions` and `agent_logs.actions` tables in the
Graves Ops Supabase project (iazgrcainbokkdqunkok). This is the substrate the
webapp-delegation skill depends on so Opus, Sonnet, and Haiku stay in sync
across separate chat windows.

Protocol (codified in skills/webapp-delegation/SKILL.md):

  * On task start, every agent calls `read_recent(session_id)` and ingests
    the slice before doing anything else.
  * After every meaningful action, the agent calls `log_action(...)` with a
    one-line summary and any sync notes the next agent needs.
  * The orchestrator (Opus) creates the session via `start_session(...)` and
    embeds the resulting session_id in every delegation prompt.

NOTE on environment:
  * Imports the existing service_role client from shared.db so this module
    has zero new env-var requirements. SUPABASE_URL + SUPABASE_SERVICE_KEY
    must be set (already required for the rest of the stack).
  * For agents running outside this repo (Sonnet/Haiku in their own chat
    windows), the same operations are available via the Supabase MCP
    `execute_sql` tool — equivalent SQL templates are documented in the
    skill file.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from shared.db import get_client


# ── Vocabulary (kept in sync with the migration's CHECK constraints) ──────────

VALID_AGENTS = {"opus", "sonnet", "haiku"}
VALID_INITIATORS = VALID_AGENTS | {"user"}
VALID_ACTION_TYPES = {
    "read",
    "write",
    "migration",
    "sql",
    "spawn",
    "handoff",
    "decision",
    "tool_call",
    "note",
}
VALID_STATUS = {"pending", "success", "error"}
VALID_SESSION_STATUS = {"active", "completed", "aborted"}


# ── Session helpers ───────────────────────────────────────────────────────────

def start_session(
    title: str,
    *,
    initiated_by: str = "opus",
    context: dict[str, Any] | None = None,
) -> str:
    """
    Create a new delegation session and return its UUID. The orchestrator
    calls this once at the start of an orchestrated task, then passes the
    returned id into every spawned agent's prompt.
    """
    if initiated_by not in VALID_INITIATORS:
        raise ValueError(f"initiated_by must be one of {sorted(VALID_INITIATORS)}")
    payload = {
        "initiated_by": initiated_by,
        "title": title,
        "context": context or {},
    }
    row = (
        get_client()
        .schema("agent_logs")
        .table("sessions")
        .insert(payload)
        .execute()
        .data[0]
    )
    return row["id"]


def end_session(session_id: str, *, status: str = "completed") -> None:
    """Mark a session as completed or aborted."""
    if status not in VALID_SESSION_STATUS - {"active"}:
        raise ValueError("status must be 'completed' or 'aborted'")
    (
        get_client()
        .schema("agent_logs")
        .table("sessions")
        .update({"status": status, "ended_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", session_id)
        .execute()
    )


def get_session(session_id: str) -> dict[str, Any] | None:
    rows = (
        get_client()
        .schema("agent_logs")
        .table("sessions")
        .select("*")
        .eq("id", session_id)
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None


# ── Action logging ────────────────────────────────────────────────────────────

def log_action(
    session_id: str,
    *,
    agent: str,
    action_type: str,
    summary: str,
    target: str | None = None,
    agent_role: str | None = None,
    parent_id: str | None = None,
    payload: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    notes: str | None = None,
    status: str = "success",
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> str:
    """
    Insert one action row. Returns the new row's id. Validates the
    enumerated fields client-side so we get a clear error rather than a
    Postgres CHECK constraint violation.

    `notes` is the single most important field — it's what the next agent
    reads to know what happened and what to do next.
    """
    if agent not in VALID_AGENTS:
        raise ValueError(f"agent must be one of {sorted(VALID_AGENTS)}")
    if action_type not in VALID_ACTION_TYPES:
        raise ValueError(
            f"action_type must be one of {sorted(VALID_ACTION_TYPES)}"
        )
    if status not in VALID_STATUS:
        raise ValueError(f"status must be one of {sorted(VALID_STATUS)}")

    row: dict[str, Any] = {
        "session_id": session_id,
        "agent": agent,
        "action_type": action_type,
        "summary": summary,
        "status": status,
        "payload": payload or {},
        "result": result or {},
    }
    if target is not None:
        row["target"] = target
    if agent_role is not None:
        row["agent_role"] = agent_role
    if parent_id is not None:
        row["parent_id"] = parent_id
    if notes is not None:
        row["notes"] = notes
    if started_at is not None:
        row["started_at"] = started_at.astimezone(timezone.utc).isoformat()
    if completed_at is not None:
        row["completed_at"] = completed_at.astimezone(timezone.utc).isoformat()

    inserted = (
        get_client()
        .schema("agent_logs")
        .table("actions")
        .insert(row)
        .execute()
        .data[0]
    )
    return inserted["id"]


def log_handoff(
    session_id: str,
    *,
    from_agent: str,
    to_agent: str,
    summary: str,
    notes: str,
    parent_id: str | None = None,
) -> str:
    """
    Convenience for the most-common cross-agent operation: 'I'm handing this
    off to <agent> with these instructions.' The receiving agent reads this
    row first.
    """
    return log_action(
        session_id,
        agent=from_agent,
        agent_role="exec" if from_agent == "opus" else None,
        action_type="handoff",
        target=to_agent,
        summary=summary,
        notes=notes,
        parent_id=parent_id,
    )


# ── Reading / catching up ─────────────────────────────────────────────────────

def read_recent(
    session_id: str,
    *,
    limit: int = 50,
    action_types: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Default 'catch me up' query for any spawned agent. Returns most-recent-
    first. Filter by action_types when you only care about decisions or
    handoffs.
    """
    q = (
        get_client()
        .schema("agent_logs")
        .table("actions")
        .select("*")
        .eq("session_id", session_id)
        .order("started_at", desc=True)
        .limit(limit)
    )
    if action_types:
        q = q.in_("action_type", list(action_types))
    return q.execute().data or []


def latest_active_session(within_hours: int = 4) -> dict[str, Any] | None:
    """
    Find the most recent active session started within the given window.
    Useful when an agent comes online without an explicit session_id and
    needs to figure out whether to join an existing chain or start fresh.
    """
    rows = (
        get_client()
        .schema("agent_logs")
        .table("sessions")
        .select("*")
        .eq("status", "active")
        .order("started_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        return None
    row = rows[0]
    started = datetime.fromisoformat(row["started_at"].replace("Z", "+00:00"))
    age_hours = (datetime.now(timezone.utc) - started).total_seconds() / 3600
    return row if age_hours <= within_hours else None


# ── Tiny CLI for shell-only agents ────────────────────────────────────────────
# Lets a spawned agent that has bash but not Python fluency log without
# writing a Python file. Usage:
#   python -m shared.agent_logs log <session_id> <agent> <action_type> "<summary>" [notes...]
#   python -m shared.agent_logs read <session_id> [limit]
#   python -m shared.agent_logs start "<title>" [initiated_by]

if __name__ == "__main__":
    import json
    import sys

    cmd, *args = sys.argv[1:] if len(sys.argv) > 1 else ["help"]

    if cmd == "start":
        title = args[0] if args else "(untitled)"
        initiated_by = args[1] if len(args) > 1 else "opus"
        sid = start_session(title, initiated_by=initiated_by)
        print(sid)
    elif cmd == "log":
        if len(args) < 4:
            sys.exit("usage: log <session_id> <agent> <action_type> <summary> [notes]")
        session_id, agent, action_type, summary, *rest = args
        notes = " ".join(rest) if rest else None
        aid = log_action(
            session_id,
            agent=agent,
            action_type=action_type,
            summary=summary,
            notes=notes,
        )
        print(aid)
    elif cmd == "read":
        if not args:
            sys.exit("usage: read <session_id> [limit]")
        session_id = args[0]
        limit = int(args[1]) if len(args) > 1 else 50
        rows = read_recent(session_id, limit=limit)
        print(json.dumps(rows, indent=2, default=str))
    elif cmd == "end":
        if not args:
            sys.exit("usage: end <session_id> [status]")
        session_id = args[0]
        status = args[1] if len(args) > 1 else "completed"
        end_session(session_id, status=status)
        print("ok")
    else:
        print(__doc__)
        print("commands: start <title> | log <sid> <agent> <type> <summary> [notes] | read <sid> [n] | end <sid> [status]")
