"""
brijkillian_stack.py — Unified app entry point

Registers routes from GLCR Memory, ZDS, Shift HUD, and Admin into a single
Reflex application with shared state, authentication, and infrastructure.

The app serves:
  - /login, /auth/callback (public, GLCR auth)
  - / (GLCR Today dashboard, protected)
  - /shift (Shift HUD, viewer-OK)
  - /search, /logs, /people, /threads, /tasks, /patterns, /health, /recap, /floor, /areas, /writeups, /deployment (protected)
  - /zds/* (Zone Deployment System, viewer-OK)
"""

import reflex as rx
from shared.auth import AuthState
from shared.grok_state import GrokState
from shared.components.grok_panel import grok_panel, grok_fab
from shared.components.area_check import area_check_modal
from shared.components.context_menu import global_context_menu
from shared.components.highlight_toolbar import global_highlight_toolbar
from shared.components.undo_toast import global_undo_toast
from shared.components.audit_strip import audit_strip
from shared.components.nav_rail import nav_rail

from apps.glcr.routes import (
    ROUTES as GLCR_ROUTES,
    PUBLIC_ROUTES as GLCR_PUBLIC,
    VIEWER_OK_ROUTES as GLCR_VIEWER_OK,
)
from apps.zds.routes import ROUTES as ZDS_ROUTES, PUBLIC_ROUTES as ZDS_PUBLIC
from apps.shift.routes import ROUTES as SHIFT_ROUTES
from apps.admin.routes import ROUTES as ADMIN_ROUTES

# ── Keyboard shortcut script ──────────────────────────────────────────────────
# Injected once at app level. ⌘K → palette, ⌘N → capture, ⌘J → toggle Grok, Esc → close all

_KBD_SCRIPT = """
document.addEventListener('keydown', function(e) {
  const cmd = e.metaKey || e.ctrlKey;
  // Ignore shortcuts when focus is inside a text input / textarea
  const tag = document.activeElement ? document.activeElement.tagName : '';
  const inInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
  if (cmd && e.key === 'k') {
    e.preventDefault();
    // GLCR Memory pages: open their command palette
    window._reflexDispatch && window._reflexDispatch('app_state.open_palette', {});
    // Shift HUD: toggle its command palette (no-op on non-Shift pages)
    window._reflexDispatch && window._reflexDispatch('command_palette_state.toggle', {});
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
    // Shift HUD: close command palette + all capture modals
    window._reflexDispatch && window._reflexDispatch('command_palette_state.close', {});
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

# ── Theme initializer (GShiftPage Phase 1) ───────────────────────────────────
# Runs synchronously in <head> before first paint to prevent FOUC.
# Reads localStorage["glcr-theme"] and stamps data-theme on <html>.
# Also migrates users who still have the old Reflex-default key "theme"
# (values: "zds-dark" → "dark").
_THEME_INIT_SCRIPT = """
(function() {
  var old = localStorage.getItem('theme');
  if (old !== null) {
    localStorage.setItem('glcr-theme', old === 'zds-dark' ? 'dark' : 'light');
    localStorage.removeItem('theme');
  }
  var t = localStorage.getItem('glcr-theme') || 'light';
  document.documentElement.setAttribute('data-theme', t);
})();
"""

# ── Page wrapper: inject Grok panel + FAB ────────────────────────────────────
# (for GLCR protected pages; ZDS pages don't need Grok yet)

def _with_grok(page_fn):
    """Wrap a GLCR Memory page with the unified nav rail + Grok panel/FAB
    + Area Check modal + global overlays.

    Layout: 60px rail | 1fr page content  (CSS grid via .app-shell).
    The page_fn() result goes in the right column; overlays are portalled
    at the top level so they float above the rail.
    """
    def wrapped() -> rx.Component:
        return rx.el.div(
            nav_rail(),
            rx.el.div(
                page_fn(),
                grok_fab(),
                grok_panel(),
                area_check_modal(),
                global_context_menu(),
                global_highlight_toolbar(),
                global_undo_toast(),
                style={"minHeight": "100vh", "position": "relative"},
            ),
            class_name="app-shell",
        )
    wrapped.__name__ = f"{page_fn.__name__}_with_grok"
    return wrapped


def _with_zds_chrome(page_fn):
    """Wrap a ZDS page with the unified nav rail + theme system + ZDS overlays.

    Layout: 60px rail | 1fr ZDS content  (CSS grid via .app-shell).
    data-theme on <html> is set by _THEME_INIT_SCRIPT (runs in <head>) and
    synced via rx.call_script in ZdsState.toggle_theme.
    The .zds-casino-bg div is position:fixed so it renders behind all content.
    """

    def wrapped() -> rx.Component:
        return rx.el.div(
            nav_rail(),
            rx.box(
                rx.box(class_name="zds-casino-bg"),   # fixed SVG scatter behind content
                page_fn(),
                global_context_menu(),
                global_highlight_toolbar(),
                global_undo_toast(),
                audit_strip(),
                min_height="100vh",
                position="relative",
                flex="1",
                overflow_x="hidden",
            ),
            class_name="app-shell",
        )
    wrapped.__name__ = f"{page_fn.__name__}_zds"
    return wrapped


# ── App initialization ────────────────────────────────────────────────────────

app = rx.App(
    # Note: show_built_with_reflex was removed in Reflex 0.9.2.
    # Badge suppression is no longer a constructor arg.
    stylesheets=[
        # Google Fonts
        "https://fonts.googleapis.com/css2?family=Barlow:wght@300;400;500;600;700&family=PT+Serif:ital,wght@0,400;0,700;1,400;1,700&display=swap",
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
        # Design tokens (T2 un-prefixed + --zds-* backward-compat aliases, dual-theme)
        "/ops_tokens.css",
        # Design tokens + component styles
        "/styles.css",
        # ZDS component overrides (scoped to [data-theme="dark"] / [data-theme="light"])
        "/zds_dark.css",
    ],
    head_components=[
        # Theme init: stamp data-theme on <html> before first paint (anti-FOUC).
        # Must be first so CSS token selectors resolve on initial render.
        rx.el.script(_THEME_INIT_SCRIPT),
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
        # ── Highlight toolbar (left-click highlight chips on TM spans) ────
        rx.el.link(rel="stylesheet", href="/highlight_toolbar.css"),
        rx.el.script(src="/highlight_toolbar.js"),
        # ── Undo toast (5-second auto-dismiss + manual Undo / × buttons) ──
        rx.el.link(rel="stylesheet", href="/undo_toast.css"),
        rx.el.script(src="/undo_toast.js"),
        # ── Nav rail (Phase 2: 60px unified left rail) ────────────────────
        rx.el.link(rel="stylesheet", href="/nav_rail.css"),
        rx.el.script(src="/avatar_menu.js"),
        # ── Shift HUD (Phase 3: /shift page) ──────────────────────────────
        rx.el.link(rel="stylesheet", href="/shift_hud.css"),
        # ── Sudo Admin hub (Phase 4b: /admin hub + sub-pages) ─────────────
        rx.el.link(rel="stylesheet", href="/admin_hub.css"),
    ],
)

# ── Route registration ────────────────────────────────────────────────────────
# Three auth tiers for GLCR routes:
#
#   TIER 1 — PUBLIC      No guard.  /unlock, /login, /auth/callback.
#   TIER 2 — VIEWER_OK   PIN required; role is irrelevant. /, /today.
#   TIER 3 — EDITOR_ANY  PIN + any editor role required. All other Memory pages.
#                        Viewers see a redirect-to-home toast.
#
# ZDS routes all run at TIER 2 (viewer-OK). Per-action write gating for ZDS
# lives at the event-handler level — see docs/role_gating_spec.md.

ALL_PUBLIC_ROUTES = GLCR_PUBLIC + ZDS_PUBLIC


def _on_load_for(route: str, base_on_load: list | None) -> list | None:
    """Return the on_load chain for a GLCR route based on its auth tier.

    Returns None for public routes (no on_load needed).
    Returns a list with the appropriate auth guard prepended for protected routes.
    """
    base = base_on_load or []
    if route in GLCR_PUBLIC:
        return None                                              # TIER 1 — no guard
    if route in GLCR_VIEWER_OK:
        return [AuthState.require_unlock] + base                # TIER 2 — PIN only
    return [AuthState.require_editor_any] + base                # TIER 3 — PIN + role


# Register GLCR routes
for entry in GLCR_ROUTES:
    page_fn, route, title, on_load = entry
    computed_on_load = _on_load_for(route, on_load)

    if route in GLCR_PUBLIC:
        app.add_page(page_fn, route=route, title=title)
    else:
        kwargs: dict = {"route": route, "title": title, "on_load": computed_on_load}
        app.add_page(_with_grok(page_fn), **kwargs)

# Register Shift HUD routes (TIER 2 — viewer-OK)
for entry in SHIFT_ROUTES:
    page_fn, route, title, on_load = entry
    kwargs = {
        "route":   route,
        "title":   title,
        "on_load": [AuthState.require_unlock] + (on_load or []),
    }
    app.add_page(_with_zds_chrome(page_fn), **kwargs)

# Register ZDS routes (all TIER 2 — viewer-OK)
for entry in ZDS_ROUTES:
    page_fn, route, title, on_load = entry
    kwargs = {
        "route":   route,
        "title":   title,
        "on_load": [AuthState.require_unlock] + (on_load or []),
    }
    app.add_page(_with_zds_chrome(page_fn), **kwargs)

# Register Admin stub routes (TIER 2 — viewer-OK for now)
for entry in ADMIN_ROUTES:
    page_fn, route, title, on_load = entry
    kwargs = {
        "route":   route,
        "title":   title,
        "on_load": [AuthState.require_unlock] + (on_load or []),
    }
    app.add_page(_with_zds_chrome(page_fn), **kwargs)
