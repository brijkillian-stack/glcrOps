"""
state/grok.py — GrokState for Phase 5.2 chat panel

Streaming Grok conversation state, message history, panel UI state.
"""

import reflex as rx
from datetime import datetime
from uuid import uuid4


class GrokState(rx.State):
    """State for Grok chat panel: messages, conversation ID, streaming status."""

    # ── Panel visibility ──────────────────────────────────────────────────────
    panel_open: bool = False

    # ── Conversation ──────────────────────────────────────────────────────────
    conversation_id: str = ""           # Current conversation UUID
    messages: list[dict] = []           # [{role, content, tool_call?, tool_result?}]

    # ── Composer ──────────────────────────────────────────────────────────────
    current_input: str = ""             # Textarea value

    # ── Streaming ─────────────────────────────────────────────────────────────
    streaming: bool = False             # Response in flight
    streaming_text: str = ""            # Partial assistant text accumulating
    streaming_tool: str = ""            # Name of tool currently being called (for chip)

    # ── Errors ────────────────────────────────────────────────────────────────
    error: str = ""

    # ── Recent conversations (dropdown) ────────────────────────────────────────
    recent_conversations: list[dict] = []  # [{id, last_message, ts}]

    # ── Events ────────────────────────────────────────────────────────────────

    @rx.event
    def toggle_panel(self):
        """Toggle Grok panel open/closed (Cmd+J)."""
        self.panel_open = not self.panel_open
        if self.panel_open and not self.conversation_id:
            # Auto-create new conversation on first open
            self.new_conversation()

    @rx.event
    def open_panel(self):
        """Open Grok panel."""
        self.panel_open = True
        if not self.conversation_id:
            self.new_conversation()

    @rx.event
    def close_panel(self):
        """Close Grok panel."""
        self.panel_open = False

    @rx.event
    def new_conversation(self):
        """Start a fresh conversation."""
        from ..db import list_recent_conversations

        self.conversation_id = str(uuid4())
        self.messages = []
        self.current_input = ""
        self.streaming_text = ""
        self.streaming_tool = ""
        self.error = ""

        # Load recent conversations for dropdown
        try:
            self.recent_conversations = list_recent_conversations(limit=10)
        except Exception as e:
            print(f"[grok] list_recent_conversations error: {e}")
            self.recent_conversations = []

    @rx.event
    def load_conversation(self, conv_id: str):
        """Load a saved conversation by ID."""
        from ..db import get_conversation_messages

        try:
            msgs = get_conversation_messages(conv_id)
            self.conversation_id = conv_id
            self.messages = msgs or []
            self.current_input = ""
            self.streaming_text = ""
            self.streaming_tool = ""
            self.error = ""
        except Exception as e:
            self.error = f"Failed to load conversation: {e}"

    @rx.event
    def set_input(self, value: str):
        """Update textarea value."""
        self.current_input = value

    @rx.event(background=True)
    async def send_message(self):
        """
        Send user message and stream Grok response.

        Core streaming loop: yields after each token, tool call, and final message.
        """
        if not self.current_input.strip():
            return

        # Add user message to history. Every message dict must carry all three
        # fields (content, name, result_summary) because rx.foreach + rx.match
        # in the renderer needs uniform schema — Reflex Vars get compiled at
        # build time, not per-row at runtime.
        user_msg = {
            "role": "user",
            "content": self.current_input.strip(),
            "name": "",
            "result_summary": "",
        }

        async with self:
            self.messages = [*self.messages, user_msg]
            self.streaming = True
            self.streaming_text = ""
            self.streaming_tool = ""
            self.error = ""
            self.current_input = ""
        yield  # Push user message + spinner to client immediately

        # Import Grok streaming client
        from ..ai import grok_chat_stream

        # Build message history for API (user + assistant only, no tool messages in the calls)
        full_messages = [
            {"role": m["role"], "content": m.get("content", "")}
            for m in self.messages
            if m["role"] in ("user", "assistant")
        ]

        try:
            async for event in grok_chat_stream(full_messages, conversation_id=self.conversation_id):
                if event["type"] == "token":
                    # Streaming text token
                    async with self:
                        self.streaming_text += event["content"]
                    yield

                elif event["type"] == "tool_call":
                    # Tool call detected
                    async with self:
                        args_summary = ""
                        if event.get("args"):
                            # Make a short summary for the chip
                            args = event["args"]
                            if isinstance(args, dict):
                                # Try to extract a meaningful key
                                if "query" in args:
                                    args_summary = f"'{args['query'][:20]}...'" if len(str(args.get("query", ""))) > 20 else f"'{args['query']}'"
                                elif "name_or_id" in args:
                                    args_summary = f"'{args['name_or_id']}'"
                                else:
                                    first_val = next(iter(args.values()), "")
                                    args_summary = f"'{str(first_val)[:20]}...'" if len(str(first_val)) > 20 else f"'{first_val}'"
                        self.streaming_tool = f"{event['name']}({args_summary})"
                    yield

                elif event["type"] == "tool_result":
                    # Tool result received
                    async with self:
                        # Append tool result message to history
                        result = event.get("result") or {}
                        if isinstance(result, dict):
                            count = result.get("count", "ok")
                        else:
                            count = "ok"
                        self.messages = [*self.messages, {
                            "role": "tool",
                            "content": "",
                            "name": event["name"],
                            "result_summary": str(count),
                        }]
                        self.streaming_tool = ""
                    yield

                elif event["type"] == "done":
                    # Response complete
                    async with self:
                        # Append final assistant message
                        if self.streaming_text:
                            self.messages = [*self.messages, {
                                "role": "assistant",
                                "content": self.streaming_text,
                                "name": "",
                                "result_summary": "",
                            }]
                        self.streaming_text = ""
                        self.streaming = False
                    yield

                elif event["type"] == "error":
                    # Error occurred
                    async with self:
                        self.error = f"Grok error: {event.get('message', 'Unknown error')}"
                        self.streaming = False
                    yield

        except Exception as exc:
            async with self:
                self.error = f"Grok error: {exc}"
                self.streaming = False
            yield
