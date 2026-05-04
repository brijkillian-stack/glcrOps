"""
pages/login.py — Magic-link login page

Single email input + "Send magic link" button.
On success, shows "Magic link sent — check your inbox at {email}".

Design:
  - Brand-on layout (Barlow font, paper-white background)
  - Brand-blue primary button (--accent-blue)
  - Optional client-side hint if email != brijkillian@icloud.com
"""

import reflex as rx
from shared.auth import AuthState


def login_page() -> rx.Component:
    """Main login page component."""

    return rx.el.div(
        # ── Layout wrapper ────────────────────────────────────────────────────
        rx.el.div(
            # ── Logo / header ────────────────────────────────────────────────
            rx.el.div(
                rx.el.h1(
                    "GLCR Memory",
                    style={
                        "fontSize": "28px",
                        "fontWeight": "600",
                        "color": "var(--fg-1)",
                        "margin": "0 0 8px",
                        "fontFamily": "var(--font-body)",
                    },
                ),
                rx.el.p(
                    "Shift intelligence for Gun Lake Casino",
                    style={
                        "fontSize": "14px",
                        "color": "var(--fg-2)",
                        "margin": "0 0 32px",
                        "fontFamily": "var(--font-body)",
                    },
                ),
                style={"marginBottom": "32px"},
            ),

            # ── Form ─────────────────────────────────────────────────────────
            rx.el.form(
                # Email input
                rx.el.div(
                    rx.el.label(
                        "Email address",
                        html_for="email-input",
                        style={
                            "display": "block",
                            "fontSize": "12px",
                            "fontWeight": "500",
                            "color": "var(--fg-2)",
                            "marginBottom": "6px",
                            "fontFamily": "var(--font-body)",
                        },
                    ),
                    rx.el.input(
                        id="email-input",
                        type_="email",
                        placeholder="brijkillian@icloud.com",
                        value=AuthState.email,
                        on_change=AuthState.set_email,
                        disabled=AuthState.magic_link_sent,
                        style={
                            "width": "100%",
                            "padding": "10px 12px",
                            "fontSize": "14px",
                            "border": "1px solid var(--border-subtle)",
                            "borderRadius": "var(--r-md)",
                            "fontFamily": "var(--font-body)",
                            "background": "var(--surface-card)",
                            "color": "var(--fg-1)",
                            "boxSizing": "border-box",
                            "transition": "border-color 200ms var(--ease)",
                        },
                    ),
                    style={"marginBottom": "16px"},
                ),

                # Error message
                rx.cond(
                    AuthState.error != "",
                    rx.el.div(
                        AuthState.error,
                        style={
                            "fontSize": "13px",
                            "color": "var(--accent-flag)",
                            "marginBottom": "16px",
                            "padding": "8px 12px",
                            "background": "var(--accent-flag-bg)",
                            "borderRadius": "var(--r-md)",
                            "fontFamily": "var(--font-body)",
                        },
                    ),
                ),

                # Submit button
                rx.el.button(
                    rx.cond(
                        AuthState.is_loading,
                        "Sending...",
                        rx.cond(
                            AuthState.magic_link_sent,
                            "Link sent — check your email",
                            "Send magic link",
                        ),
                    ),
                    type_="button",
                    on_click=AuthState.request_magic_link(AuthState.email),
                    disabled=AuthState.is_loading | AuthState.magic_link_sent,
                    style={
                        "width": "100%",
                        "padding": "10px 12px",
                        "fontSize": "14px",
                        "fontWeight": "500",
                        "borderRadius": "var(--r-md)",
                        "border": "none",
                        "background": rx.cond(
                            AuthState.magic_link_sent,
                            "var(--accent-positive)",
                            "var(--accent-blue)",
                        ),
                        "color": "white",
                        "cursor": rx.cond(
                            AuthState.is_loading | AuthState.magic_link_sent,
                            "not-allowed",
                            "pointer",
                        ),
                        "opacity": rx.cond(
                            AuthState.is_loading | AuthState.magic_link_sent,
                            "0.7",
                            "1",
                        ),
                        "transition": "background-color 200ms var(--ease)",
                        "fontFamily": "var(--font-body)",
                    },
                ),

                # Success message
                rx.cond(
                    AuthState.magic_link_sent,
                    rx.el.div(
                        rx.el.p(
                            "✓ Magic link sent",
                            style={
                                "fontSize": "13px",
                                "color": "var(--accent-positive)",
                                "margin": "12px 0 4px",
                                "fontFamily": "var(--font-body)",
                            },
                        ),
                        rx.el.p(
                            f"Check your inbox at {AuthState.email}",
                            style={
                                "fontSize": "13px",
                                "color": "var(--fg-2)",
                                "margin": "0",
                                "fontFamily": "var(--font-body)",
                            },
                        ),
                        style={"marginTop": "16px"},
                    ),
                ),

                style={
                    "width": "100%",
                },
            ),

            # ── Help text ────────────────────────────────────────────────────
            rx.el.div(
                rx.el.p(
                    "Click the link in your email to sign in. The link expires in 24 hours.",
                    style={
                        "fontSize": "13px",
                        "color": "var(--fg-3)",
                        "margin": "32px 0 0",
                        "fontFamily": "var(--font-body)",
                    },
                ),
                style={"marginTop": "32px", "textAlign": "center"},
            ),

            # ── Container styles ──────────────────────────────────────────────
            style={
                "maxWidth": "360px",
                "margin": "auto",
                "padding": "64px 24px",
            },
        ),

        # ── Page background ───────────────────────────────────────────────────
        style={
            "minHeight": "100vh",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "background": "var(--surface-canvas)",
            "fontFamily": "var(--font-body)",
        },
    )
