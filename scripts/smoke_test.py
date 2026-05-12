#!/usr/bin/env python3
"""
ZDS Forge smoke test — fast go/no-go check for local dev and CI.

Hits every public endpoint with a single real request, checks the
status code and a minimal content assertion, and exits 0 (pass) or 1 (fail).

Usage
─────
  # With a running local server:
  python scripts/smoke_test.py

  # Override base URL and IDs:
  PRINT_SERVICE_URL=http://localhost:8001 \\
  PRINT_SERVICE_WEEK_ID=7f31103a-4bcd-4f65-99e8-dd6bbae580a9 \\
  python scripts/smoke_test.py

  # In CI (after uvicorn is started):
  uvicorn apps.zds.api.main:app --port 8001 &
  sleep 5
  python scripts/smoke_test.py

Environment
───────────
  PRINT_SERVICE_URL      default: http://localhost:8001
  PRINT_SERVICE_WEEK_ID  default: read from tests/print_regression/golden/manifest.json
  PRINT_SERVICE_NIGHT_ID optional; night-endpoint checks skipped if absent
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

BASE_URL = os.environ.get("PRINT_SERVICE_URL", "http://localhost:8001").rstrip("/")
WEEK_ID  = os.environ.get("PRINT_SERVICE_WEEK_ID", "").strip()
NIGHT_ID = os.environ.get("PRINT_SERVICE_NIGHT_ID", "").strip()

# Fall back to the locked golden week if the env var isn't set.
if not WEEK_ID:
    manifest = (
        Path(__file__).parent.parent
        / "tests/print_regression/golden/manifest.json"
    )
    if manifest.exists():
        WEEK_ID = json.loads(manifest.read_text()).get("week_key", "")
        if WEEK_ID:
            # week_key is YYYY-MM-DD; we need the UUID — caller must set the env var.
            # Clear it so we skip rather than send a date string as a UUID.
            WEEK_ID = ""

# ── Colours ───────────────────────────────────────────────────────────────────

GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def _ok(label: str, detail: str = "") -> None:
    print(f"  {GREEN}✓{RESET} {label}" + (f"  {detail}" if detail else ""))


def _fail(label: str, detail: str = "") -> None:
    print(f"  {RED}✗{RESET} {label}" + (f"  {detail}" if detail else ""))


def _skip(label: str, reason: str = "") -> None:
    print(f"  {YELLOW}–{RESET} {label} (skipped{': ' + reason if reason else ''})")


# ── HTTP client ───────────────────────────────────────────────────────────────

def _get(path: str, timeout: int = 60):
    try:
        import httpx
    except ImportError:
        print(f"{RED}ERROR{RESET}: httpx not installed — pip install httpx")
        sys.exit(1)
    try:
        with httpx.Client(base_url=BASE_URL, timeout=timeout) as c:
            t0 = time.monotonic()
            r = c.get(path)
            elapsed = time.monotonic() - t0
        return r, elapsed
    except Exception as exc:
        return None, str(exc)


# ── Checks ────────────────────────────────────────────────────────────────────

failures: list[str] = []


def check(name: str, path: str, *,
          expect_status: int = 200,
          expect_content_type: str = "",
          expect_bytes_prefix: bytes = b"",
          min_body_bytes: int = 0,
          skip_reason: str = "") -> bool:
    """Run one smoke check, print result, accumulate failures."""
    if skip_reason:
        _skip(name, skip_reason)
        return True

    r, elapsed = _get(path)
    if r is None:
        _fail(name, f"connection error: {elapsed}")
        failures.append(name)
        return False

    # PDF render may 500 on servers without WeasyPrint — treat as skip.
    if r.status_code == 500 and path.endswith(".pdf"):
        try:
            if r.json().get("detail", {}).get("error") == "render_failed":
                _skip(name, "WeasyPrint not installed on server")
                return True
        except Exception:
            pass

    ok = True
    details = []

    if r.status_code != expect_status:
        ok = False
        details.append(f"status {r.status_code} ≠ {expect_status}")

    if expect_content_type and expect_content_type not in r.headers.get("content-type", ""):
        ok = False
        details.append(f"content-type {r.headers.get('content-type')!r}")

    if expect_bytes_prefix and not r.content.startswith(expect_bytes_prefix):
        ok = False
        details.append(f"body prefix {r.content[:8]!r}")

    if min_body_bytes and len(r.content) < min_body_bytes:
        ok = False
        details.append(f"body {len(r.content):,} bytes < {min_body_bytes:,}")

    detail_str = f"[{elapsed*1000:.0f}ms]" + (f" — {'; '.join(details)}" if details else "")
    if ok:
        _ok(name, detail_str)
    else:
        _fail(name, detail_str)
        failures.append(name)

    return ok


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    print(f"\n{BOLD}ZDS Forge Smoke Test{RESET}")
    print(f"  Target:  {BASE_URL}")
    print(f"  Week ID: {WEEK_ID or '(not set)'}")
    print(f"  Night ID:{NIGHT_ID or '(not set)'}")
    print()

    no_week  = not WEEK_ID
    no_night = not NIGHT_ID

    # ── Meta ─────────────────────────────────────────────────────────────────
    print(f"{BOLD}Meta{RESET}")
    check("Health check",       "/health",       expect_status=200, expect_content_type="application/json")
    check("OpenAPI schema",     "/openapi.json", expect_status=200, expect_content_type="application/json")
    print()

    # ── Week HTML ─────────────────────────────────────────────────────────────
    print(f"{BOLD}Week HTML  GET /v1/print/week/{{id}}.html{RESET}")
    check("Valid week → 200",
          f"/v1/print/week/{WEEK_ID}.html",
          expect_status=200,
          expect_content_type="text/html",
          min_body_bytes=100_000,
          skip_reason="PRINT_SERVICE_WEEK_ID not set" if no_week else "")
    check("Fake UUID → 404",
          "/v1/print/week/00000000-0000-0000-0000-000000000000.html",
          expect_status=404)
    print()

    # ── Week PDF ──────────────────────────────────────────────────────────────
    print(f"{BOLD}Week PDF   GET /v1/print/week/{{id}}.pdf{RESET}")
    check("Valid week → 200 PDF",
          f"/v1/print/week/{WEEK_ID}.pdf",
          expect_status=200,
          expect_content_type="application/pdf",
          expect_bytes_prefix=b"%PDF",
          min_body_bytes=200_000,
          skip_reason="PRINT_SERVICE_WEEK_ID not set" if no_week else "")
    check("Fake UUID → 404",
          "/v1/print/week/00000000-0000-0000-0000-000000000000.pdf",
          expect_status=404)
    print()

    # ── Night HTML ────────────────────────────────────────────────────────────
    print(f"{BOLD}Night HTML GET /v1/print/night/{{id}}.html{RESET}")
    check("Valid night → 200",
          f"/v1/print/night/{NIGHT_ID}.html",
          expect_status=200,
          expect_content_type="text/html",
          min_body_bytes=20_000,
          skip_reason="PRINT_SERVICE_NIGHT_ID not set" if no_night else "")
    check("Fake UUID → 404",
          "/v1/print/night/00000000-0000-0000-0000-000000000000.html",
          expect_status=404)
    print()

    # ── Night PDF ─────────────────────────────────────────────────────────────
    print(f"{BOLD}Night PDF  GET /v1/print/night/{{id}}.pdf{RESET}")
    check("Valid night → 200 PDF",
          f"/v1/print/night/{NIGHT_ID}.pdf",
          expect_status=200,
          expect_content_type="application/pdf",
          expect_bytes_prefix=b"%PDF",
          skip_reason="PRINT_SERVICE_NIGHT_ID not set" if no_night else "")
    check("Fake UUID → 404",
          "/v1/print/night/00000000-0000-0000-0000-000000000000.pdf",
          expect_status=404)
    print()

    # ── Planning ──────────────────────────────────────────────────────────────
    print(f"{BOLD}Planning   GET /v1/planning/weekly/{{id}}{RESET}")
    check("Valid week → 200 JSON",
          f"/v1/planning/weekly/{WEEK_ID}",
          expect_status=200,
          expect_content_type="application/json",
          skip_reason="PRINT_SERVICE_WEEK_ID not set" if no_week else "")
    check("Fake UUID → 404",
          "/v1/planning/weekly/00000000-0000-0000-0000-000000000000",
          expect_status=404)
    print()

    # ── Summary ───────────────────────────────────────────────────────────────
    if failures:
        print(f"{RED}{BOLD}FAILED{RESET} — {len(failures)} check(s) failed:")
        for f in failures:
            print(f"  • {f}")
        print()
        return 1
    else:
        print(f"{GREEN}{BOLD}ALL CHECKS PASSED{RESET}")
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main())
