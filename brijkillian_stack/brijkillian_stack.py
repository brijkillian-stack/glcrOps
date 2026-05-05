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
from shared.components.context_menu import global_context_menu

from apps.glcr.routes import (
    ROUTES as GLCR_ROUTES,
    PUBLIC_ROUTES as GLCR_PUBLIC,
    VIEWER_OK_ROUTES as GLCR_VIEWER_OK,
)
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

# ── (removed) Session keep-alive ──────────────────────────────────────────────
# Path A's Supabase magic-link auth was replaced by Path C's site-PIN gate
# (2026-05-05). The site-session token is HMAC-signed, lives in localStorage,
# and is valid for ~1 year. No periodic refresh is needed; verification is a
# pure HMAC check on every protected-page mount via AuthState.require_unlock.

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
    """Wrap a page component with Grok panel + Grok FAB + Area Check modal
    + global context menu.

    The Area Check overlay is mounted globally here so the sidebar's
    "★ Area Check" action works on any protected GLCR page. The context
    menu is mounted here so it's available on every protected page (ZDS
    pages have their own wrapping below — the menu is also added there).
    """
    def wrapped() -> rx.Component:
        return rx.fragment(
            page_fn(),
            grok_fab(),
            grok_panel(),
            area_check_modal(),
            global_context_menu(),
        )
    wrapped.__name__ = f"{page_fn.__name__}_with_grok"
    return wrapped


def _with_zds_chrome(page_fn):
    """Wrap a ZDS page with the global context menu only (no Grok yet)."""
    def wrapped() -> rx.Component:
        return rx.fragment(
            page_fn(),
            global_context_menu(),
        )
    wrapped.__name__ = f"{page_fn.__name__}_zds"
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
        # ── Unlock screen styles (site PIN gate, Path C) ──────────────────
        rx.el.link(rel="stylesheet", href="/unlock.css"),
        # ── Role chip styles (sidebar viewer/zds_editor/editor indicator) ─
        rx.el.link(rel="stylesheet", href="/role.css"),
        # ── Context menu (right-click + long-press) ───────────────────────
        rx.el.link(rel="stylesheet", href="/context_menu.css"),
        rx.el.script(src="/context_menu.js"),
    ],
)

# ── Route registration ────────────────────────────────────────────────────────
# Register public routes first (no auth), then protected routes with auth guard

ALL_PUBLIC_ROUTES = GLCR_PUBLIC + ZDS_PUBLIC

# Register GLCR routes
# Three guard tiers:
#   - PUBLIC: no guard at all (unlock, login, auth callback)
#   - VIEWER_OK: PIN required, role is irrelevant (homepage, /today)
#   - default: PIN + any editor role required (everything else in Memory)
for entry in GLCR_ROUTES:
    page_fn, route, title, on_load = entry

    if route in GLCR_PUBLIC:
        # Public route — no auth, no Grok
        app.add_page(page_fn, route=route, title=title)
    elif route in GLCR_VIEWER_OK:
        # Viewer-OK protected route — PIN required, role doesn't matter
        kwargs = {"route": route, "title": title}
        kwargs["on_load"] = [AuthState.require_unlock] + (on_load or [])
        app.add_page(_with_grok(page_fn), **kwargs)
    else:
        # Editor-required route — PIN + zds_editor or editor role.
        # Viewers redirected to / with a toast.
        kwargs = {"route": route, "title": title}
        kwargs["on_load"] = [AuthState.require_editor_any] + (on_load or [])
        app.add_page(_with_grok(page_fn), **kwargs)

# Register ZDS routes — viewer-OK (PIN is sufficient to view).
# Per-action write gating happens at the event-handler level — see
# docs/role_gating_spec.md. ZDS pages get the global context menu via
# _with_zds_chrome wrapping.
for entry in ZDS_ROUTES:
    page_fn, route, title, on_load = entry

    kwargs = {"route": route, "title": title}
    kwargs["on_load"] = [AuthState.require_unlock] + (on_load or [])
    app.add_page(_with_zds_chrome(page_fn), **kwargs)
