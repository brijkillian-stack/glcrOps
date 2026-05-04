"""
components/grok_panel.py — Grok chat panel UI + floating button

Phase 5.2: Floating chat-bubble FAB in bottom-right, slides in panel from right edge.
Renders messages, tool calls, streaming responses. Wired to GrokState.
"""

import reflex as rx
from shared.grok_state import GrokState


def grok_fab() -> rx.Component:
    """Floating action button (bottom-right) to open Grok panel."""
    return rx.el.button(
        rx.el.span("✨", style={"fontSize": "18px", "lineHeight": "1"}),
        class_name="grok-fab",
        on_click=GrokState.toggle_panel,
        title="Grok (Cmd+J)",
        aria_label="Open Grok chat",
    )


def tool_call_chip(text) -> rx.Component:
    """Small inline chip showing tool call. `text` may be a Reflex Var or
    a Python string. We do NOT use Python `if` on it — that fails on Vars.
    The caller is responsible for formatting the full chip text."""
    return rx.el.span(text, class_name="grok-tool-chip")


def message_bubble(msg) -> rx.Component:
    """Render a single message bubble. `msg` is a Reflex Var (a dict) coming
    from rx.foreach over GrokState.messages, so we cannot use Python `if`
    branches on its fields — every condition must use `rx.cond` / `rx.match`.
    Each variant renders the bubble shape that fits its role."""
    return rx.match(
        msg["role"],
        (
            "user",
            rx.el.div(
                rx.el.div(
                    msg["content"],
                    class_name="grok-message-content",
                ),
                class_name="grok-message grok-message-user",
            ),
        ),
        (
            "assistant",
            rx.el.div(
                rx.markdown(msg["content"], class_name="grok-message-content"),
                class_name="grok-message grok-message-assistant",
            ),
        ),
        (
            "tool",
            rx.el.div(
                rx.el.span(
                    rx.text(msg["name"], ": ", msg["result_summary"]),
                    class_name="grok-tool-result",
                ),
                class_name="grok-message grok-message-tool",
            ),
        ),
        # Default — unknown role, render nothing visible
        rx.fragment(),
    )


def grok_panel() -> rx.Component:
    """Full Grok chat panel: header, message list, composer."""
    return rx.el.div(
        # Backdrop overlay (close on click)
        rx.cond(
            GrokState.panel_open,
            rx.el.div(
                class_name="grok-backdrop",
                on_click=GrokState.close_panel,
            ),
        ),

        # Panel slide-in
        rx.el.div(
            # Header
            rx.el.div(
                rx.el.div(
                    rx.el.h2("Grok", class_name="grok-title"),
                    rx.el.button(
                        "×",
                        class_name="grok-close-btn",
                        on_click=GrokState.close_panel,
                        aria_label="Close Grok",
                    ),
                    class_name="grok-header-top",
                ),
                rx.el.div(
                    rx.el.button(
                        "New chat",
                        class_name="grok-new-chat-btn",
                        on_click=GrokState.new_conversation,
                    ),
                    class_name="grok-header-actions",
                ),
                class_name="grok-header",
            ),

            # Message list
            rx.el.div(
                rx.cond(
                    GrokState.messages.length() > 0,
                    rx.foreach(
                        GrokState.messages,
                        message_bubble,
                    ),
                    rx.el.div(
                        rx.el.div(
                            rx.el.p(
                                "Ask Grok anything about your shift, team, or data.",
                                class_name="grok-empty-hint",
                            ),
                            rx.el.ul(
                                rx.el.li("How's Joy doing this week?"),
                                rx.el.li("Anything brewing I should know?"),
                                rx.el.li("Who should I put on Z9 SR Friday?"),
                                class_name="grok-empty-prompts",
                            ),
                            class_name="grok-empty-state",
                        ),
                    ),
                ),
                class_name="grok-message-list",
                id="grok-message-list",
            ),

            # Streaming indicator
            rx.cond(
                GrokState.streaming,
                rx.el.div(
                    rx.el.div(
                        rx.cond(
                            GrokState.streaming_tool != "",
                            tool_call_chip(f"🔍 {GrokState.streaming_tool}"),
                            rx.el.span("Thinking...", class_name="grok-thinking"),
                        ),
                        class_name="grok-streaming-indicator",
                    ),
                ),
            ),

            # Error display
            rx.cond(
                GrokState.error != "",
                rx.el.div(
                    GrokState.error,
                    class_name="grok-error",
                ),
            ),

            # Composer (textarea — debounce_input doesn't wrap rx.el.textarea
            # cleanly in Reflex 0.9; keystroke lag is tolerable for paragraph
            # input where users pause naturally).
            rx.el.div(
                rx.el.textarea(
                    placeholder="Ask Grok anything...",
                    value=GrokState.current_input,
                    on_change=GrokState.set_input,
                    class_name="grok-composer-input",
                    disabled=GrokState.streaming,
                ),
                rx.el.button(
                    "↵",
                    class_name="grok-send-btn",
                    on_click=GrokState.send_message,
                    disabled=GrokState.streaming | (GrokState.current_input == ""),
                    title="Send (Enter)",
                    aria_label="Send message",
                ),
                class_name="grok-composer",
            ),

            class_name=rx.cond(GrokState.panel_open, "grok-panel grok-panel-open", "grok-panel"),
        ),

        class_name="grok-root",
    )
