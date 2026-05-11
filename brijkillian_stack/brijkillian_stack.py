"""
brijkillian_stack.py — ZDS-only app entry point (Phase A)

Phase A (2026-05-12): narrowed scope. The ZDS app is the first Reflex app
being migrated to Next.js (FastAPI + Next.js). admin, glcr, and shift are
parked in apps/_archive/ for systematic rebuild later.

The app now serves:
  - /unlock, /login, /auth/callback  (public — auth pages lifted from GLCR)
  - /zds, /zds/week/*, /zds/week/*/day/*, /zds/week/*/schedule  (viewer-OK)

Pre-archive the app served six more route groups; those are documented in
apps/_archive/README.md and can be revived via the pre-archive-2026-05-12 tag.
"""

import reflex as rx
from shared.auth import AuthState
from shared.components.context_menu import global_context_menu
from shared.components.highlight_toolbar import global_highlight_toolbar
from shared.components.undo_toast import global_undo_toast
from shared.components.audit_strip import audit_strip
from shared.components.nav_rail import nav_rail

# Auth pages: self-contained (only depend on shared.auth + reflex).
# Lifted from apps/_archive/glcr/pages/ which is where their history lives.
from apps._archive.glcr.pages.unlock import unlock_page
from apps._archive.glcr.pages.login import login_page
from apps._archive.glcr.pages.auth_callback import auth_callback_page

from apps.zds.routes import ROUTES as ZDS_ROUTES, PUBLIC_ROUTES as ZDS_PUBLIC

# ── Keyboard shortcut script ──────────────────────────────────────────────────
# ⌘K → ZDS context actions (future), ⌘J reserved for Grok when re-added, Esc → close overlays.
# Shift HUD and GLCR palette dispatches are kept as no-ops — they fire into thin air
# on ZDS pages (no matching state) and are harmless.

_KBD_SCRIPT = """
document.addEventListener('keydown', function(e) {
  const cmd = e.metaKey || e.ctrlKey;
  if (e.key === 'Escape') {
    window._reflexDispatch && window._reflexDispatch('app_state.close_palette', {});
    window._reflexDispatch && window._reflexDispatch('app_state.close_capture', {});
    window._reflexDispatch && window._reflexDispatch('grok_state.close_panel', {});
  }
});
"""

# ── Service Worker registration ───────────────────────────────────────────────

_SW_REGISTRATION_SCRIPT = """
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function() {
    navigator.serviceWorker.register('/sw.js').catch(function(){});
  });
}
"""

# ── Theme initializer ─────────────────────────────────────────────────────────
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

# ── ZDS page wrapper ──────────────────────────────────────────────────────────

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
        rx.el.link(rel="stylesheet", href="/pencil_canvas.css"),
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
    ],
)

# ── Route registration ────────────────────────────────────────────────────────
# Auth routes: public (no guard), lifted from archived GLCR pages.
# ZDS routes: viewer-OK (PIN unlock required).

AUTH_PUBLIC = ["/unlock", "/login", "/auth/callback"]
ALL_PUBLIC_ROUTES = AUTH_PUBLIC + ZDS_PUBLIC

# Auth routes (public — no on_load guard needed)
app.add_page(unlock_page,        route="/unlock",        title="Unlock · Graves Ops")
app.add_page(login_page,         route="/login",         title="Sign in as editor")
app.add_page(auth_callback_page, route="/auth/callback", title="Signing in…")

# ZDS routes (all TIER 2 — viewer-OK, PIN required)
for entry in ZDS_ROUTES:
    page_fn, route, title, on_load = entry
    kwargs = {
        "route":   route,
        "title":   title,
        "on_load": [AuthState.require_unlock] + (on_load or []),
    }
    app.add_page(_with_zds_chrome(page_fn), **kwargs)
