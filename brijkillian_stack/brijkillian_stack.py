"""
brijkillian_stack.py — Unified app entry point

Registers routes from GLCR Memory and ZDS into a single Reflex application
with shared state, authentication, and infrastructure.

The app serves:
  - /login, /auth/callback (public, GLCR auth)
  - / (GLCR Today dashboard, protected)
  - /search, /logs, /people, /threads, /tasks, /patterns, /health, /recap, /floor, /areas, /writeups, /deployment (protected)
  - /zds/* (Zone Deployment System, currently public)
"""

import reflex as rx
from shared.auth import AuthState
from shared.grok_state import GrokState
from shared.components.grok_panel import grok_panel, grok_fab
from shared.components.area_check import area_check_modal

from apps.glcr.routes import ROUTES as GLCR_ROUTES, PUBLIC_ROUTES as GLCR_PUBLIC
from apps.zds.routes import ROUTES as ZDS_ROUTES, PUBLIC_ROUTES as ZDS_PUBLIC

# ── Keyboard shortcut script ──────────────────────────────────────────────────
# Injected once at app level. ⌘K → palette, ⌘N → capture, ⌘J → toggle Grok, Esc → close all

_KBD_SCRIPT = """
document.addEventListener('keydown', function(e) {
  const cmd = e.metaKey || e.ctrlKey;
  if (cmd && e.key === 'k') {
    e.preventDefault();
    window._reflexDispatch && window._reflexDispatch('app_state.open_palette', {});
  } else if (cmd && e.key === 'n') {
    e.preventDefault();
    window._reflexDispatch && window._reflexDispatch('app_state.open_capture', {});
  } else if (cmd && e.key === 'j') {
    e.preventDefault();
    window._reflexDispatch && window._reflexDispatch('grok_state.toggle_panel', {});
  } else if (e.key === 'Escape') {
    window._reflexDispatch && window._reflexDispatch('app_state.close_palette', {});
    window._reflexDispatch && window._reflexDispatch('app_state.close_capture', {});
    window._reflexDispatch && window._reflexDispatch('grok_state.close_panel', {});
  }
});
"""

# ── Session keep-alive (Path A login) ─────────────────────────────────────────
# Refresh the Supabase session on window focus and every 15 min of active use.
# Combined with the long-lived JWT (24h access, 30d refresh) and persisted
# refresh token in localStorage, Brian only sees the magic-link login once
# per ~30 days per device.

_AUTH_KEEPALIVE_SCRIPT = """
(function() {
  function refresh() {
    if (window._reflexDispatch) {
      window._reflexDispatch('auth_state.refresh_session', {});
    }
  }
  window.addEventListener('focus', refresh);
  document.addEventListener('visibilitychange', function() {
    if (document.visibilityState === 'visible') refresh();
  });
  // Periodic refresh every 15 min while the tab is active
  setInterval(refresh, 15 * 60 * 1000);
})();
"""

# ── Service Worker registration ───────────────────────────────────────────────

_SW_REGISTRATION_SCRIPT = """
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function() {
    navigator.serviceWorker.register('/sw.js').catch(function(){});
  });
}
"""

# ── Page wrapper: inject Grok panel + FAB ────────────────────────────────────
# (for GLCR protected pages; ZDS pages don't need Grok yet)

def _with_grok(page_fn):
    """Wrap a page component with Grok panel + Grok FAB + Area Check modal.

    The Area Check overlay is mounted globally here so the sidebar's
    "★ Area Check" action works on any protected GLCR page.
    """
    def wrapped() -> rx.Component:
        return rx.fragment(
            page_fn(),
            grok_fab(),
            grok_panel(),
            area_check_modal(),
        )
    wrapped.__name__ = f"{page_fn.__name__}_with_grok"
    return wrapped


# ── App initialization ────────────────────────────────────────────────────────

app = rx.App(
    stylesheets=[
        # Google Fonts
        "https://fonts.googleapis.com/css2?family=Barlow:wght@300;400;500;600;700&family=PT+Serif:ital,wght@0,400;0,700;1,400;1,700&display=swap",
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
        # Design tokens + component styles
        "/styles.css",
    ],
    head_components=[
        rx.el.script(_KBD_SCRIPT),
        rx.el.script(_AUTH_KEEPALIVE_SCRIPT),
        rx.el.link(rel="manifest", href="/manifest.json"),
        rx.el.meta(name="theme-color", content="#0065BF"),
        rx.el.meta(name="apple-mobile-web-app-capable", content="yes"),
        rx.el.meta(name="apple-mobile-web-app-status-bar-style", content="default"),
        rx.el.link(rel="apple-touch-icon", href="/icons/apple-touch-icon-180.png"),
        rx.el.script(_SW_REGISTRATION_SCRIPT),
        # ── Phase K.1: PencilCanvas component assets ──────────────────────
        # CSS loaded before JS so styles are ready when the canvas renders.
        rx.el.link(rel="stylesheet", href="/pencil_canvas.css"),
        # JS loaded once at boot; exposes window.PencilCanvas and auto-inits
        # via MutationObserver when <script type="application/json" id="pc-config-*">
        # data-islands appear in the DOM (rendered by pencil_canvas() component).
        rx.el.script(src="/pencil_canvas.js"),
        # ── Homepage three-card launchpad styles ──────────────────────────
        rx.el.link(rel="stylesheet", href="/homepage.css"),
    ],
)

# ── Route registration ────────────────────────────────────────────────────────
# Register public routes first (no auth), then protected routes with auth guard

ALL_PUBLIC_ROUTES = GLCR_PUBLIC + ZDS_PUBLIC

# Register GLCR routes
for entry in GLCR_ROUTES:
    page_fn, route, title, on_load = entry

    if route in GLCR_PUBLIC:
        # Public route — no auth, no Grok
        app.add_page(page_fn, route=route, title=title)
    else:
        # Protected route — auth check (with restore-from-storage) runs first,
        # then any page-specific on_load handlers.
        kwargs = {"route": route, "title": title}
        kwargs["on_load"] = [AuthState.require_auth] + (on_load or [])
        app.add_page(_with_grok(page_fn), **kwargs)

# Register ZDS routes
for entry in ZDS_ROUTES:
    page_fn, route, title, on_load = entry

    kwargs = {"route": route, "title": title}
    if on_load:
        kwargs["on_load"] = on_load

    # ZDS routes are currently public; add Grok if you extend them
    app.add_page(page_fn, **kwargs)
