"""
state/auth.py — Authentication state

Manages magic-link login flow:
  - request_magic_link(email) → calls Supabase Auth OTP endpoint
  - handle_callback(token) → exchanges token for JWT, verifies, stores session
  - sign_out() → clears session

All protected routes check is_authenticated before render.
"""

import reflex as rx
from shared.db import get_client


class AuthState(rx.State):
    """Authentication state for magic-link flow.

    Phase: Path A login simplification (2026-05-05)
    ─────────────────────────────────────────────────
    Refresh token + email are persisted in browser localStorage so the
    session survives reloads and PWA cold-starts. On every protected-page
    mount, ``restore_session_from_storage`` runs first — if there's a
    persisted refresh token, it gets exchanged for a fresh access token
    silently (no magic link required).

    Combined with the dashboard-side JWT TTL bump (access 24h, refresh 30d),
    this means Brian logs in via magic link once per ~30 days per device,
    not "every few minutes." Activity-driven refresh on window focus keeps
    long sessions alive.
    """

    # ── User session (in-memory only — reset on each browser reload) ─────────
    email: str = ""
    is_authenticated: bool = False
    user_id: str = ""  # Brian's UUID from auth.users
    jwt_token: str = ""  # JWT (stored server-side, never sent to browser as cookie)

    # ── Persisted across reloads (localStorage) ──────────────────────────────
    persisted_refresh_token: str = rx.LocalStorage("")
    persisted_email: str = rx.LocalStorage("")

    # ── UI state ──────────────────────────────────────────────────────────────
    magic_link_sent: bool = False
    error: str = ""
    is_loading: bool = False

    # ── Authentication events ─────────────────────────────────────────────────

    @rx.event
    async def request_magic_link(self, email: str):
        """Request a magic link for the given email via Supabase Auth."""
        self.error = ""
        self.magic_link_sent = False
        self.is_loading = True

        if not email or "@" not in email:
            self.error = "Please enter a valid email."
            self.is_loading = False
            return

        # Optional client-side hint (not enforcement)
        if email != "brijkillian@icloud.com":
            self.error = "This dashboard only allows brijkillian@icloud.com. Still attempting to send magic link..."

        try:
            sb = get_client()
            # Determine the redirect URL — infer from browser if possible
            # For now, assume deployed URL is set via environment or default to localhost
            redirect_url = self._get_redirect_url()

            # Supabase Auth OTP (magic link) endpoint
            res = sb.auth.sign_in_with_otp({
                "email": email,
                "options": {
                    "email_redirect_to": redirect_url,
                }
            })

            self.email = email
            self.magic_link_sent = True
            self.error = ""

        except Exception as e:
            self.error = f"Failed to send magic link: {str(e)}"
            self.magic_link_sent = False
        finally:
            self.is_loading = False

    @rx.event
    async def handle_callback(self, token: str):
        """
        Exchange the magic-link token for a JWT.
        Called by /auth/callback page after Supabase redirects back.
        """
        self.error = ""
        self.is_loading = True

        try:
            sb = get_client()

            # Supabase Auth OTP verification
            # The token is passed as code= in the URL; we extract and verify it
            res = sb.auth.verify_otp({
                "token": token,
                "type": "email",  # Type of OTP (email, phone, etc.)
            })

            # On success, res contains user and session info
            if res.user and res.session:
                self.user_id = res.user.id  # Brian's UUID
                self.jwt_token = res.session.access_token
                self.is_authenticated = True
                self.email = res.user.email or self.email
                # Persist refresh token + email for cross-reload session restore
                self.persisted_refresh_token = res.session.refresh_token or ""
                self.persisted_email = self.email
                self.error = ""
                return True
            else:
                self.error = "Failed to verify magic link. Session not returned."
                self.is_authenticated = False
                return False

        except Exception as e:
            self.error = f"Authentication failed: {str(e)}"
            self.is_authenticated = False
            return False
        finally:
            self.is_loading = False

    @rx.event
    async def exchange_session_from_url(self):
        """
        Establish a Supabase session from access_token + refresh_token sitting
        in the URL query params (placed there by JS that read the fragment).

        Flow:
            1. Magic-link redirect lands at /auth/callback#access_token=...&refresh_token=...
            2. JS in pages/auth_callback.py reads the fragment, redirects to the
               same URL with the tokens as ?access_token=...&refresh_token=...
            3. This handler runs on the second page mount, reads the params,
               calls sb.auth.set_session(at, rt), and redirects to /today.
        """
        try:
            params = self.router.page.params
        except Exception:
            params = {}
        access_token = params.get("access_token") if params else None
        refresh_token = params.get("refresh_token") if params else None

        # First mount (before JS redirects): no params yet — wait for the
        # second mount to fire with tokens.
        if not access_token or not refresh_token:
            return

        try:
            sb = get_client()
            res = sb.auth.set_session(access_token, refresh_token)
            if res and res.user and res.session:
                self.user_id = res.user.id
                self.jwt_token = res.session.access_token
                self.is_authenticated = True
                self.email = res.user.email or self.email
                # Persist for cross-reload session restore
                self.persisted_refresh_token = res.session.refresh_token or refresh_token
                self.persisted_email = self.email
                self.error = ""
                return rx.redirect("/")
            self.error = "Authentication failed: session not returned by Supabase."
            self.is_authenticated = False
            return rx.redirect("/login")
        except Exception as e:
            self.error = f"Authentication failed: {e}"
            self.is_authenticated = False
            return rx.redirect("/login")

    @rx.event
    def sign_out(self):
        """Clear the session and any persisted tokens."""
        self.is_authenticated = False
        self.user_id = ""
        self.jwt_token = ""
        self.email = ""
        self.magic_link_sent = False
        self.error = ""
        # Clear persisted tokens so the next page load goes to /login
        self.persisted_refresh_token = ""
        self.persisted_email = ""

    @rx.event
    async def restore_session_from_storage(self):
        """Restore Supabase session from persisted refresh token (Path A login).

        Called on every protected-page mount before require_auth fires. If we
        already have an in-memory session, this is a no-op. If we have a
        persisted refresh token, exchange it for a fresh access token without
        a magic-link round-trip.
        """
        if self.is_authenticated:
            return                                  # session already in memory
        if not self.persisted_refresh_token:
            return                                  # nothing to restore from
        try:
            sb = get_client()
            res = sb.auth.refresh_session(self.persisted_refresh_token)
            if res and res.user and res.session:
                self.user_id = res.user.id
                self.jwt_token = res.session.access_token
                self.email = res.user.email or self.persisted_email
                self.is_authenticated = True
                # Refresh tokens rotate — store the new one
                if res.session.refresh_token:
                    self.persisted_refresh_token = res.session.refresh_token
                self.persisted_email = self.email
                self.error = ""
        except Exception:
            # Refresh failed (token revoked, expired, or Supabase auth changed).
            # Clear persisted state so the next page load goes to /login cleanly.
            self.persisted_refresh_token = ""
            self.persisted_email = ""
            self.is_authenticated = False

    @rx.event
    async def refresh_session(self):
        """Activity-driven session refresh.

        Wired to a JS focus listener in brijkillian_stack.py — fires when the
        user returns to the browser tab/PWA. Silent on failure (the next
        protected-page navigation will catch and redirect if needed).
        """
        if not self.is_authenticated or not self.persisted_refresh_token:
            return
        try:
            sb = get_client()
            res = sb.auth.refresh_session(self.persisted_refresh_token)
            if res and res.session:
                self.jwt_token = res.session.access_token
                if res.session.refresh_token:
                    self.persisted_refresh_token = res.session.refresh_token
        except Exception:
            pass                                    # silent — next nav handles it

    @rx.event
    async def require_auth(self):
        """
        Gate event: try to restore from storage, then redirect to /login if
        still unauthenticated. Used as on_load hook on protected pages.
        """
        if not self.is_authenticated:
            await self.restore_session_from_storage()
        if not self.is_authenticated:
            return rx.redirect("/login")

    # ── UI event handlers ──────────────────────────────────────────────────────

    @rx.event
    def set_email(self, value: str):
        """Update email field in login form."""
        self.email = value

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_redirect_url(self) -> str:
        """
        Infer the callback URL.
        In production: https://<render-url>/auth/callback
        In dev: http://localhost:3000/auth/callback

        Reflex doesn't easily expose the request origin, so we rely on environment
        variable SUPABASE_CALLBACK_URL or default to relative path.
        Supabase will honor relative paths if configured correctly in Auth redirect URIs.
        """
        import os
        # Try environment variable first (set by deployment)
        callback_url = os.getenv("SUPABASE_CALLBACK_URL")
        if callback_url:
            return callback_url
        # Fallback: relative path (Supabase allows this if registered in dashboard)
        return "/auth/callback"
