"""
shared/auth.py — Site PIN auth.

DEV MODE (2026-05-05): PIN unlock auto-elevates to full editor.
The magic-link layer is preserved in code (login page, auth_callback,
exchange_session_from_url, etc.) but is no longer wired into the on_load
chain. Anyone with the PIN gets full edit access, simplifying debugging
of the empty-People-page issue. To restore the three-tier model:
  1. Revert verify_pin to leave editor_role = ROLE_VIEWER
  2. Re-enable the magic-link restore in require_unlock / require_editor_any
  3. Optionally re-show the "Sign in as editor" link in the sidebar

Path C+ history (still in module): PIN gates entry. Magic-link sign-in
elevates a known email to ZDS Editor or Editor based on env-var
allowlists, unlocking write actions.

────────────────────────────────────────────────────────────────────────────
Roles
────────────────────────────────────────────────────────────────────────────
  viewer       PIN-only. Browse everything. No writes.
  zds_editor   PIN + magic-link, email in ZDS_EDITOR_EMAILS.
               Permitted: per-night deployment swaps/edits, ZDS Pencil
               annotations (deployment book, week overview).
               NOT permitted: upload schedules, run engine, edit rule files,
               anything in Memory.
  editor       PIN + magic-link, email in EDITOR_EMAILS.
               Full write across the app.

────────────────────────────────────────────────────────────────────────────
Env vars (Render dashboard)
────────────────────────────────────────────────────────────────────────────
  BASIC_AUTH_HASH        bcrypt hash of the PIN (used by site_auth.verify_pin)
  SITE_SESSION_SECRET    HMAC key for site-session token (32-byte hex)
  EDITOR_EMAILS          comma-separated full-editor emails
                         e.g. "brijkillian@icloud.com"
  ZDS_EDITOR_EMAILS      comma-separated zds-only-editor emails
                         e.g. "evs.director@gunlakecasino.com"
  SUPABASE_URL           used by shared.db.get_client (existing)
  SUPABASE_SERVICE_KEY   used by shared.db.get_client (existing)

A magic-link from an email NOT in either allowlist is rejected — the user
stays in viewer mode with a soft toast.

────────────────────────────────────────────────────────────────────────────
Permission helpers (rx.var, usable in event handlers + JSX)
────────────────────────────────────────────────────────────────────────────
  is_authenticated         alias for is_unlocked (PIN gate passed)
  is_editor                full editor (editor_role == "editor")
  is_zds_editor            zds OR full editor
  can_edit_deployment      zds_editor or editor
  can_save_zds_annotation  zds_editor or editor
  can_run_engine           editor only
  can_upload_schedule      editor only
  can_edit_rules           editor only
  can_write_memory         editor only  (capture, comments, write-ups, TM edits)
  can_save_memory_annotation  editor only

Inline gating pattern in any write event:

    @rx.event
    def my_write_event(self, ...):
        if not AuthState.can_write_memory:
            return rx.toast.error("Sign in as editor to make changes")
        # ... do the write
"""

from __future__ import annotations

import os

import reflex as rx

from shared.db import get_client
from shared.site_auth import (
    DEFAULT_TOKEN_TTL_SECONDS,
    SHORT_TOKEN_TTL_SECONDS,
    make_session_token,
    verify_pin as _verify_pin,
    verify_session_token,
)


MAX_PIN_ATTEMPTS = 8

ROLE_VIEWER     = "viewer"
ROLE_ZDS_EDITOR = "zds_editor"
ROLE_EDITOR     = "editor"


def _email_in(env_var_name: str, email: str) -> bool:
    """Check whether `email` appears in a comma-separated env-var allowlist."""
    if not email:
        return False
    raw = os.environ.get(env_var_name, "")
    if not raw:
        return False
    needles = {p.strip().lower() for p in raw.split(",") if p.strip()}
    return email.strip().lower() in needles


def role_for_email(email: str) -> str:
    """Resolve an email to its role per the env-var allowlists.

    Precedence: EDITOR_EMAILS > ZDS_EDITOR_EMAILS > viewer.
    Pure function — no state. Used by exchange_session_from_url and
    handle_callback to decide what to do after a successful magic-link.
    """
    if _email_in("EDITOR_EMAILS", email):
        return ROLE_EDITOR
    if _email_in("ZDS_EDITOR_EMAILS", email):
        return ROLE_ZDS_EDITOR
    return ROLE_VIEWER


class AuthState(rx.State):
    """Two-tier auth state. See module docstring."""

    # ── Tier 1: site PIN (anyone with the PIN) ───────────────────────────────
    is_authenticated: bool = False                       # ← is_unlocked
    persisted_site_token: str = rx.LocalStorage("")

    # PIN-form UI state
    pin_input: str = ""
    remember_device: bool = True
    error: str = ""
    is_loading: bool = False
    failed_attempts: int = 0

    # ── Tier 2: editor elevation (magic-link Supabase identity) ──────────────
    editor_role: str = ROLE_VIEWER                       # 'viewer' | 'zds_editor' | 'editor'
    editor_email: str = ""
    editor_user_id: str = ""

    # Persisted across reloads — silently restores editor session on next visit
    persisted_refresh_token: str = rx.LocalStorage("")
    persisted_email:         str = rx.LocalStorage("")

    # Magic-link form state
    magic_link_email: str = ""
    magic_link_sent: bool = False
    magic_link_error: str = ""

    # ── Compatibility aliases (existing pages reference these) ───────────────
    email: str = ""        # mirrors editor_email; empty for viewers
    user_id: str = ""      # mirrors editor_user_id
    jwt_token: str = ""    # only populated for editors (Supabase access token)

    # ─────────────────────────────────────────────────────────────────────────
    # Permission helpers
    # ─────────────────────────────────────────────────────────────────────────

    @rx.var
    def is_editor(self) -> bool:
        return self.editor_role == ROLE_EDITOR

    @rx.var
    def is_zds_editor(self) -> bool:
        return self.editor_role in (ROLE_EDITOR, ROLE_ZDS_EDITOR)

    @rx.var
    def can_edit_deployment(self) -> bool:
        return self.is_authenticated and self.is_zds_editor

    @rx.var
    def can_save_zds_annotation(self) -> bool:
        return self.is_authenticated and self.is_zds_editor

    @rx.var
    def can_run_engine(self) -> bool:
        return self.is_authenticated and self.is_editor

    @rx.var
    def can_upload_schedule(self) -> bool:
        return self.is_authenticated and self.is_editor

    @rx.var
    def can_edit_rules(self) -> bool:
        return self.is_authenticated and self.is_editor

    @rx.var
    def can_write_memory(self) -> bool:
        return self.is_authenticated and self.is_editor

    @rx.var
    def can_save_memory_annotation(self) -> bool:
        return self.is_authenticated and self.is_editor

    @rx.var
    def role_label(self) -> str:
        """Short human-readable role label for sidebar / chrome."""
        if not self.is_authenticated:
            return "Locked"
        if self.editor_role == ROLE_EDITOR:
            return "Editor"
        if self.editor_role == ROLE_ZDS_EDITOR:
            return "ZDS Editor"
        return "Viewer"

    # ─────────────────────────────────────────────────────────────────────────
    # Tier 1 — site PIN flow
    # ─────────────────────────────────────────────────────────────────────────

    @rx.event
    def set_pin_input(self, value: str):
        self.pin_input = "".join(ch for ch in value if ch.isdigit())[:6]
        self.error = ""

    @rx.event
    def toggle_remember_device(self, checked: bool):
        self.remember_device = bool(checked)

    @rx.event
    def verify_pin(self):
        self.error = ""
        self.is_loading = True

        if self.failed_attempts >= MAX_PIN_ATTEMPTS:
            self.error = "Too many attempts. Reload the page and try again."
            self.is_loading = False
            return

        pin = (self.pin_input or "").strip()
        if not pin:
            self.error = "Enter the PIN."
            self.is_loading = False
            return

        if not _verify_pin(pin):
            self.failed_attempts += 1
            remaining = MAX_PIN_ATTEMPTS - self.failed_attempts
            self.error = (
                f"Incorrect PIN. {remaining} attempt{'s' if remaining != 1 else ''} remaining."
                if remaining > 0
                else "Too many attempts. Reload the page and try again."
            )
            self.pin_input = ""
            self.is_loading = False
            return

        try:
            ttl = DEFAULT_TOKEN_TTL_SECONDS if self.remember_device else SHORT_TOKEN_TTL_SECONDS
            token = make_session_token(ttl_seconds=ttl)
        except Exception as exc:
            self.error = f"Server misconfigured: {exc}"
            self.is_loading = False
            return

        self.persisted_site_token = token
        self.is_authenticated = True
        # DEV MODE: PIN unlock auto-elevates to full editor.
        self.editor_role = ROLE_EDITOR
        self.pin_input = ""
        self.failed_attempts = 0
        self.error = ""
        self.is_loading = False
        return rx.redirect("/")

    @rx.event
    def lock_device(self):
        """Clear EVERYTHING — site session and editor identity. Back to /unlock."""
        self.persisted_site_token = ""
        self.persisted_refresh_token = ""
        self.persisted_email = ""
        self.is_authenticated = False
        self.editor_role = ROLE_VIEWER
        self.editor_email = ""
        self.editor_user_id = ""
        self.email = ""
        self.user_id = ""
        self.jwt_token = ""
        self.pin_input = ""
        self.failed_attempts = 0
        self.error = ""
        return rx.redirect("/unlock")

    @rx.event
    def restore_unlock_from_storage(self):
        """Verify the persisted site token. Sets is_authenticated if valid."""
        if self.is_authenticated:
            return
        if not self.persisted_site_token:
            return
        ok, _ = verify_session_token(self.persisted_site_token)
        if ok:
            self.is_authenticated = True
            # DEV MODE: anyone with a valid PIN session is treated as editor.
            self.editor_role = ROLE_EDITOR
        else:
            self.persisted_site_token = ""
            self.is_authenticated = False

    @rx.event
    def require_unlock(self):
        """on_load gate for every protected page. PIN required; redirects to
        /unlock if not unlocked. DEV MODE: anyone unlocked is auto-editor,
        so no magic-link chain call here.
        """
        if not self.is_authenticated:
            self.restore_unlock_from_storage()
        if not self.is_authenticated:
            return rx.redirect("/unlock")

    @rx.event
    def require_editor_any(self):
        """DEV MODE: identical to require_unlock — magic-link role gating is
        disabled. Any PIN-unlocked user has full edit access. To restore the
        three-tier model, see the module docstring at the top of this file.
        """
        if not self.is_authenticated:
            self.restore_unlock_from_storage()
        if not self.is_authenticated:
            return rx.redirect("/unlock")

    # Legacy aliases — kept so existing on_load entries keep working.
    @rx.event
    def require_auth(self):
        return self.require_unlock()

    @rx.event
    def sign_out(self):
        return self.lock_device()

    # ─────────────────────────────────────────────────────────────────────────
    # Tier 2 — magic-link editor elevation
    # ─────────────────────────────────────────────────────────────────────────

    @rx.event
    def set_magic_link_email(self, value: str):
        self.magic_link_email = value
        self.magic_link_error = ""

    @rx.event
    async def request_magic_link(self):
        """Send a magic link to magic_link_email. Email must be in one of
        the allowlists or the elevation will fail at callback."""
        self.magic_link_error = ""
        self.magic_link_sent = False
        self.is_loading = True

        email = (self.magic_link_email or "").strip()
        if not email or "@" not in email:
            self.magic_link_error = "Please enter a valid email."
            self.is_loading = False
            return

        # Soft-warn at request time if the email isn't in any allowlist; we
        # still send the link (so attackers can't probe the allowlist), but
        # let the user know they may not get editor privileges.
        role = role_for_email(email)
        if role == ROLE_VIEWER:
            self.magic_link_error = (
                "Heads up: this email isn't in the editor allowlist. "
                "The link will work but you'll stay in viewer mode."
            )

        try:
            sb = get_client()
            redirect_url = self._get_redirect_url()
            sb.auth.sign_in_with_otp({
                "email": email,
                "options": {"email_redirect_to": redirect_url},
            })
            self.magic_link_sent = True
        except Exception as e:
            self.magic_link_error = f"Failed to send magic link: {e}"
            self.magic_link_sent = False
        finally:
            self.is_loading = False

    @rx.event
    async def exchange_session_from_url(self):
        """Magic-link callback handler. Reads access_token + refresh_token
        from URL params (placed there by JS in auth_callback page), calls
        sb.auth.set_session(...), persists refresh token, sets editor_role
        based on email allowlists.

        On success → redirect to / (homepage).
        On failure → redirect to /unlock (PIN required first; magic-link is
                     elevation, not entry).
        """
        try:
            params = self.router.page.params
        except Exception:
            params = {}
        access_token  = params.get("access_token")  if params else None
        refresh_token = params.get("refresh_token") if params else None

        if not access_token or not refresh_token:
            # First mount — wait for JS to add the params to URL.
            return

        try:
            sb = get_client()
            res = sb.auth.set_session(access_token, refresh_token)
            if not (res and res.user and res.session):
                self.magic_link_error = "Authentication failed: session not returned."
                return rx.redirect("/unlock")

            email = res.user.email or ""
            role = role_for_email(email)

            self.editor_email = email
            self.editor_user_id = res.user.id
            self.editor_role = role
            self.email = email
            self.user_id = res.user.id
            self.jwt_token = res.session.access_token

            # Persist refresh token only if the user got a real role —
            # viewers don't need editor session continuity.
            if role != ROLE_VIEWER:
                self.persisted_refresh_token = res.session.refresh_token or refresh_token
                self.persisted_email = email
            else:
                self.persisted_refresh_token = ""
                self.persisted_email = ""

            return rx.redirect("/")
        except Exception as e:
            self.magic_link_error = f"Authentication failed: {e}"
            return rx.redirect("/unlock")

    @rx.event
    def restore_editor_from_storage(self):
        """Silently restore editor identity from persisted refresh token.
        Called from require_unlock so editor role is correct on every page."""
        if not self.persisted_refresh_token:
            return
        try:
            sb = get_client()
            res = sb.auth.refresh_session(self.persisted_refresh_token)
            if not (res and res.user and res.session):
                self._clear_editor_state()
                return
            email = res.user.email or self.persisted_email or ""
            role = role_for_email(email)
            if role == ROLE_VIEWER:
                # Email was removed from the allowlist between sessions.
                self._clear_editor_state()
                return
            self.editor_email = email
            self.editor_user_id = res.user.id
            self.editor_role = role
            self.email = email
            self.user_id = res.user.id
            self.jwt_token = res.session.access_token
            if res.session.refresh_token:
                self.persisted_refresh_token = res.session.refresh_token
            self.persisted_email = email
        except Exception:
            # Silent fail — keep viewer mode, don't disrupt the page render.
            self._clear_editor_state()

    @rx.event
    def sign_out_editor(self):
        """Drop editor identity, stay on the app as viewer. Site PIN
        session is preserved — only the magic-link layer goes away."""
        self._clear_editor_state()
        return rx.toast.success("Signed out — viewer mode")

    def _clear_editor_state(self):
        """Internal helper: clear editor fields without redirecting."""
        self.persisted_refresh_token = ""
        self.persisted_email = ""
        self.editor_role = ROLE_VIEWER
        self.editor_email = ""
        self.editor_user_id = ""
        self.email = ""
        self.user_id = ""
        self.jwt_token = ""

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _get_redirect_url(self) -> str:
        """Magic-link callback URL. Honours SUPABASE_CALLBACK_URL env override."""
        callback_url = os.environ.get("SUPABASE_CALLBACK_URL", "")
        if callback_url:
            return callback_url
        return "/auth/callback"
