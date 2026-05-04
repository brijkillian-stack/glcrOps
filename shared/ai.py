"""
ai.py — xAI Grok client + tool surface for the GLCR dashboard.

The xAI API key is stored in Supabase Vault (secret name: 'xai_api_key').
Server-side code fetches it via supabase-py service-role client at startup.

Phase 5.1 foundation: Handles all async Grok chat, tool dispatch, and
conversation persistence. UI surfaces (chat panel, autocomplete, nightly
analysis) are built in P5.2-P5.5.
"""

import json
import traceback
import uuid
from typing import AsyncIterator

import httpx

from .db import get_client

# ── Constants ────────────────────────────────────────────────────────────
GROK_MODEL = "grok-4"
GROK_API_URL = "https://api.x.ai/v1/chat/completions"
SYSTEM_PROMPT = """\
You are Grok, a thinking partner embedded in Brian Killian's GLCR Memory dashboard.
Brian is the Primary Grave Shift Supervisor at Gun Lake Casino & Resort.
You can read his TM observations, tasks, events, and pattern data via the tools available.
Be concise, specific, and operationally useful. When you spot something Brian should know
that he didn't ask about, surface it. Cite specific notes, TMs, and dates.
"""

# ── xAI key fetch (cached singleton) ─────────────────────────────────────
_XAI_KEY_CACHE: str | None = None


def get_xai_key() -> str:
    """Fetch xAI API key from Supabase Vault via RPC. Cached after first call."""
    global _XAI_KEY_CACHE
    if _XAI_KEY_CACHE:
        return _XAI_KEY_CACHE
    try:
        sb = get_client()
        res = sb.rpc("read_xai_key", {}).execute()
        if not res.data:
            raise RuntimeError("xai_api_key not found in Vault")
        _XAI_KEY_CACHE = res.data
        print(f"[ai] xAI key loaded from Vault ({len(_XAI_KEY_CACHE)} chars)")
        return _XAI_KEY_CACHE
    except Exception as e:
        print(f"[ai] get_xai_key error:\n{traceback.format_exc()}")
        raise


# ── Tool definitions ─────────────────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Hybrid keyword+vector search across notes, entities, events, tasks, files. Use this whenever Brian asks about anything specific.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language or keywords"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_entity",
            "description": "Fetch a TM (or other entity) by name or id, with their recent notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name_or_id": {"type": "string"},
                    "recent_notes": {"type": "integer", "default": 10},
                },
                "required": ["name_or_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_recent_notes",
            "description": "List recent notes within the last N days, optionally filtered by content_type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "since_days": {"type": "integer", "default": 7},
                    "content_type": {"type": "string"},
                    "limit": {"type": "integer", "default": 20},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_open_tasks",
            "description": "List Brian's open tasks, sorted by priority and due date.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_health_metrics",
            "description": "Single-row dashboard health KPIs: total counts, last capture, embedding coverage, search activity.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_team_members",
            "description": "Full TM roster with skill scores. Use for 'who should I put on Z9 SR' style queries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "active_only": {"type": "boolean", "default": True},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "capture_note",
            "description": "Write a new observation/note on Brian's behalf. Only use when he asks you to log something.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "content_type": {
                        "type": "string",
                        "enum": ["observation", "kudos", "feedback", "request", "flag", "idea", "reference", "incident"],
                    },
                    "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral", "flag"]},
                    "entities": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["content", "content_type"],
            },
        },
    },
]


# ── Tool implementations ─────────────────────────────────────────────────
def execute_tool(name: str, args: dict) -> dict:
    """
    Dispatch a Grok tool call to the right db.py function.
    Returns a JSON-serializable result dict.
    """
    from . import db

    try:
        if name == "search":
            hits = db.search_hybrid_text(args["query"], limit=args.get("limit", 10))
            return {"hits": hits or [], "count": len(hits or [])}

        elif name == "get_entity":
            entity_id = db.find_tm_id_by_name(args["name_or_id"])
            if not entity_id:
                return {"error": f"No entity found matching '{args['name_or_id']}'"}
            profile = db.get_tm_full_profile(entity_id)
            # TODO: get_tm_notes when available in db.py
            return {"profile": profile, "entity_id": entity_id}

        elif name == "list_recent_notes":
            since_days = args.get("since_days", 7)
            content_type = args.get("content_type")
            limit = args.get("limit", 20)
            notes = db.get_recent_notes(since_days=since_days, limit=limit)
            if content_type:
                notes = [n for n in notes if n.get("content_type") == content_type]
            return {"notes": notes, "count": len(notes)}

        elif name == "list_open_tasks":
            tasks = db.get_tonight_tasks(limit=20)
            return {"tasks": tasks, "count": len(tasks)}

        elif name == "get_health_metrics":
            metrics = db.get_health_metrics()
            return metrics or {}

        elif name == "list_team_members":
            active_only = args.get("active_only", True)
            roster = db.get_deployment_roster()
            if active_only:
                roster = [r for r in roster if r.get("active")]
            return {"roster": roster, "count": len(roster)}

        elif name == "capture_note":
            note_id = str(uuid.uuid4())
            entities = args.get("entities", [])
            result = db.capture_note(
                content=args["content"],
                content_type=args["content_type"],
                sentiment=args.get("sentiment", "neutral"),
                entities=entities,
            )
            return {"success": bool(result), "note_id": note_id}

        else:
            return {"error": f"Unknown tool: {name}"}

    except Exception as e:
        print(f"[ai] execute_tool({name}) error:\n{traceback.format_exc()}")
        return {"error": str(e)}


# ── Conversation persistence ─────────────────────────────────────────────
def _persist_message(conversation_id: str, role: str, content: str | None = None,
                      tool_call: dict | None = None, tool_result: dict | None = None) -> None:
    """Log a message to ai_messages table for conversation history."""
    try:
        sb = get_client()
        msg_id = str(uuid.uuid4())
        sb.table("ai_messages").insert({
            "id": msg_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "tool_call": tool_call,
            "tool_result": tool_result,
            "model": GROK_MODEL,
        }).execute()
    except Exception:
        print(f"[ai] _persist_message error:\n{traceback.format_exc()}")


# ── Main chat call (streaming) ───────────────────────────────────────────
async def grok_chat_stream(
    messages: list[dict],
    conversation_id: str | None = None,
) -> AsyncIterator[dict]:
    """
    Streaming Grok chat with tool support. Yields events as dicts:
      {'type': 'token', 'content': str}     # incremental text
      {'type': 'tool_call', 'name': str, 'args': dict, 'call_id': str}
      {'type': 'tool_result', 'name': str, 'result': dict}
      {'type': 'done', 'final_message': str}

    Tool-call loop: Grok calls a tool → we execute it → we append result
    and re-call Grok. Terminates on text-only response or max rounds.

    Caller is responsible for rendering. Conversation history is persisted
    to ai_messages table after each turn.
    """
    if not conversation_id:
        conversation_id = str(uuid.uuid4())

    api_key = get_xai_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Preserve system prompt at the top
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}, *messages]

    # Tool-call loop: max 8 rounds
    for round_num in range(8):
        payload = {
            "model": GROK_MODEL,
            "messages": full_messages,
            "tools": TOOLS,
            "stream": True,
            "temperature": 0.7,
        }

        accumulated_text = ""
        final_tool_call = None
        tool_call_id = None

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST", GROK_API_URL, headers=headers, json=payload
                ) as response:
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue

                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break

                        try:
                            event = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        # Handle streaming text content
                        if "choices" in event:
                            choice = event["choices"][0]
                            if choice.get("finish_reason") == "tool_calls":
                                # Tool call detected; don't emit text
                                pass
                            elif "delta" in choice:
                                delta = choice["delta"]
                                if "content" in delta:
                                    content = delta["content"]
                                    accumulated_text += content
                                    yield {"type": "token", "content": content}

                                # Tool call in delta
                                if "tool_calls" in delta:
                                    for tc in delta["tool_calls"]:
                                        if "id" in tc:
                                            tool_call_id = tc["id"]
                                        if "function" in tc:
                                            func = tc["function"]
                                            tool_name = func.get("name", "")
                                            args_str = func.get("arguments", "{}")
                                            try:
                                                args = json.loads(args_str)
                                            except json.JSONDecodeError:
                                                args = {}
                                            final_tool_call = {
                                                "name": tool_name,
                                                "args": args,
                                                "call_id": tool_call_id,
                                            }
                                            yield {
                                                "type": "tool_call",
                                                "name": tool_name,
                                                "args": args,
                                                "call_id": tool_call_id,
                                            }

        except httpx.HTTPError as e:
            print(f"[ai] HTTP error in grok_chat_stream: {e}")
            yield {"type": "error", "message": f"HTTP error: {e}"}
            return

        # Persist assistant message
        if accumulated_text:
            _persist_message(
                conversation_id,
                "assistant",
                content=accumulated_text,
            )

        # If no tool call, we're done
        if not final_tool_call:
            yield {"type": "done", "final_message": accumulated_text}
            return

        # Execute tool and loop
        tool_result = execute_tool(final_tool_call["name"], final_tool_call["args"])
        yield {
            "type": "tool_result",
            "name": final_tool_call["name"],
            "result": tool_result,
        }

        # Persist tool call and result
        _persist_message(
            conversation_id,
            "tool",
            tool_call={"name": final_tool_call["name"], "args": final_tool_call["args"]},
        )
        _persist_message(
            conversation_id,
            "tool",
            tool_result=tool_result,
        )

        # Append tool result to messages and loop
        full_messages.append({
            "role": "assistant",
            "content": accumulated_text or "",
            "tool_calls": [{
                "id": final_tool_call["call_id"],
                "type": "function",
                "function": {
                    "name": final_tool_call["name"],
                    "arguments": json.dumps(final_tool_call["args"]),
                },
            }],
        })
        full_messages.append({
            "role": "tool",
            "tool_call_id": final_tool_call["call_id"],
            "content": json.dumps(tool_result),
        })

        # Continue loop


# ── Non-streaming completion (for autocomplete) ──────────────────────────
async def grok_complete(prompt: str, max_tokens: int = 60, stop: list[str] | None = None) -> str:
    """
    Quick, non-streaming completion. Used by capture-box autocomplete.
    Returns raw text completion.
    """
    api_key = get_xai_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": GROK_MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Provide concise, brief responses."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.5,
    }
    if stop:
        payload["stop"] = stop

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(GROK_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            if data.get("choices"):
                return data["choices"][0].get("message", {}).get("content", "")
    except Exception as e:
        print(f"[ai] grok_complete error:\n{traceback.format_exc()}")

    return ""
