"""
pages/auth_callback.py — Magic-link callback handler

Supabase Auth redirects to this page with tokens in the URL fragment:
    /auth/callback#access_token=...&refresh_token=...

The fragment NEVER gets sent to the server, so we use a small JS snippet
to read it, then redirect to the same URL with the tokens as query params
(which the server CAN see). The server then exchanges them for a session
via `sb.auth.set_session()` and redirects to /today.
"""

import reflex as rx
from shared.auth import AuthState


# JS runs immediately when the page loads.
# If the URL has tokens in the fragment, copy them to query params and reload.
# If they're already in query params (second pass), do nothing.
_FRAGMENT_TO_QUERY_SCRIPT = """
(function () {
    var hash = window.location.hash || "";
    if (hash.indexOf("access_token") === -1) return;
    var params = new URLSearchParams(hash.replace(/^#/, ""));
    var at = params.get("access_token");
    var rt = params.get("refresh_token");
    if (!at || !rt) return;
    var newUrl =
        window.location.pathname +
        "?access_token=" + encodeURIComponent(at) +
        "&refresh_token=" + encodeURIComponent(rt);
    window.location.replace(newUrl);
})();
"""


def auth_callback_page() -> rx.Component:
    return rx.el.div(
        # JS runs as soon as the page is parsed.
        rx.el.script(_FRAGMENT_TO_QUERY_SCRIPT),
        rx.el.div(
            rx.el.h2(
                "Signing you in...",
                style={
                    "fontSize": "20px",
                    "fontWeight": "600",
                    "color": "var(--fg-1)",
                    "margin": "0 0 12px",
                    "fontFamily": "var(--font-body)",
                },
            ),
            rx.el.p(
                "Verifying your magic link.",
                style={
                    "fontSize": "14px",
                    "color": "var(--fg-2)",
                    "margin": "0",
                    "fontFamily": "var(--font-body)",
                },
            ),
            style={
                "textAlign": "center",
                "padding": "64px 24px",
            },
        ),
        style={
            "minHeight": "100vh",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "background": "var(--surface-canvas)",
            "fontFamily": "var(--font-body)",
        },
        on_mount=AuthState.exchange_session_from_url,
    )
