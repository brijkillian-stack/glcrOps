"""
shared/site_auth.py — Site PIN gate + HMAC-signed session tokens.

Path C — site password, no Supabase magic-link.

The bcrypt hash of the PIN lives in env var BASIC_AUTH_HASH (reused from
the prior Caddy basic_auth setup). The HMAC signing key for session
tokens lives in env var SITE_SESSION_SECRET — generate once and never
share. Rotating SITE_SESSION_SECRET invalidates every existing site
session (your "force everyone to re-enter the PIN" lever, separate from
rotating the PIN itself).

Token format:
    "<expires_at_unix>.<nonce_hex>.<hmac_sha256_b64url>"

Signed with SITE_SESSION_SECRET; carried client-side in rx.LocalStorage.
Server verifies on every protected-page mount via AuthState.require_unlock.

This module is pure functions — no Reflex coupling. Tested via shared/auth.py.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from typing import Optional

import bcrypt

# ── Constants ────────────────────────────────────────────────────────────────

ENV_PIN_HASH        = "BASIC_AUTH_HASH"
ENV_SESSION_SECRET  = "SITE_SESSION_SECRET"

DEFAULT_TOKEN_TTL_SECONDS = 365 * 24 * 60 * 60   # 1 year (when "remember device" is on)
SHORT_TOKEN_TTL_SECONDS   =       4 * 60 * 60    # 4 hours (when "remember device" is off)


# ── PIN verification ─────────────────────────────────────────────────────────

def verify_pin(pin: str, *, expected_hash: Optional[str] = None) -> bool:
    """Verify the user-supplied PIN against the bcrypt hash in env.

    `expected_hash` defaults to env[BASIC_AUTH_HASH]. Returns True on
    successful match, False on mismatch or any error (silent — the
    attacker should not learn whether the env var was missing vs. wrong PIN).

    Caller is responsible for rate-limiting / lockout — this function
    does no throttling. AuthState.verify_pin tracks attempt counts.
    """
    if not pin:
        return False
    h = expected_hash or os.environ.get(ENV_PIN_HASH, "")
    if not h:
        return False
    try:
        return bcrypt.checkpw(pin.encode("utf-8"), h.encode("utf-8"))
    except Exception:
        return False


def hash_pin(pin: str, *, rounds: int = 12) -> str:
    """Bcrypt-hash a PIN. Used by the setup CLI helper, not the runtime gate.

    Brian runs this once to generate the BASIC_AUTH_HASH value he sets in
    Render. Returns a string suitable for direct env-var storage.
    """
    return bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt(rounds=rounds)).decode("utf-8")


# ── HMAC-signed session tokens ───────────────────────────────────────────────

def _get_secret() -> bytes:
    """Read SITE_SESSION_SECRET from env. Raise if not set — fail closed."""
    s = os.environ.get(ENV_SESSION_SECRET, "")
    if not s:
        raise RuntimeError(
            f"{ENV_SESSION_SECRET} is not set. Generate one with:\n"
            f"  python -c 'import secrets; print(secrets.token_hex(32))'\n"
            f"and set it in the Render environment for this service."
        )
    return s.encode("utf-8")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def make_session_token(*, ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS) -> str:
    """Generate a fresh HMAC-signed session token.

    Format: "<expires_at>.<nonce>.<sig>"

    expires_at — unix seconds (int)
    nonce      — 16 random bytes, b64url
    sig        — HMAC-SHA256 over "<expires_at>.<nonce>", b64url

    Caller persists this client-side (rx.LocalStorage). verify_session_token
    parses and validates on every protected-page mount.
    """
    secret = _get_secret()
    # Allow negative ttl_seconds for explicit expired-token generation
    # (useful for diagnostics + force-logout). verify_session_token will
    # reject it as expected.
    expires_at = int(time.time()) + int(ttl_seconds)
    nonce = _b64url(secrets.token_bytes(16))
    payload = f"{expires_at}.{nonce}".encode("ascii")
    sig = hmac.new(secret, payload, hashlib.sha256).digest()
    return f"{expires_at}.{nonce}.{_b64url(sig)}"


def verify_session_token(token: str) -> tuple[bool, int]:
    """Validate a session token.

    Returns (is_valid, seconds_remaining). seconds_remaining is 0 when
    invalid (signature mismatch, expired, malformed, secret missing).

    Constant-time signature comparison via hmac.compare_digest. Token
    expiry is enforced separately so an attacker can't extend a token
    by modifying the timestamp without breaking the signature.
    """
    if not token or token.count(".") != 2:
        return False, 0
    try:
        secret = _get_secret()
    except RuntimeError:
        return False, 0
    try:
        expires_str, nonce, sig_b64 = token.split(".", 2)
        expires_at = int(expires_str)
    except (ValueError, AttributeError):
        return False, 0
    payload = f"{expires_at}.{nonce}".encode("ascii")
    expected_sig = hmac.new(secret, payload, hashlib.sha256).digest()
    try:
        provided_sig = _b64url_decode(sig_b64)
    except Exception:
        return False, 0
    if not hmac.compare_digest(expected_sig, provided_sig):
        return False, 0
    now = int(time.time())
    if expires_at <= now:
        return False, 0
    return True, expires_at - now


# ── Tiny CLI for env-var setup ───────────────────────────────────────────────
# Brian runs these once during setup; not invoked from the running app.
#
#   python -m shared.site_auth hash 123456
#       Prints a bcrypt hash of "123456" — paste into Render as BASIC_AUTH_HASH.
#
#   python -m shared.site_auth secret
#       Prints a fresh 32-byte hex string — paste into Render as
#       SITE_SESSION_SECRET. Keep secret. Rotating invalidates every active
#       site session.
#
#   python -m shared.site_auth verify 123456 '<hash>'
#       Tests a PIN against a hash. For sanity-checking your env config.

if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    args = sys.argv[2:]

    if cmd == "hash":
        if not args:
            sys.exit("usage: hash <pin>")
        print(hash_pin(args[0]))
    elif cmd == "secret":
        print(secrets.token_hex(32))
    elif cmd == "verify":
        if len(args) < 2:
            sys.exit("usage: verify <pin> <bcrypt_hash>")
        pin, h = args[0], args[1]
        ok = verify_pin(pin, expected_hash=h)
        print("MATCH" if ok else "MISMATCH")
        sys.exit(0 if ok else 1)
    else:
        print(__doc__)
        print("commands: hash <pin> | secret | verify <pin> <hash>")
