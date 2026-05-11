"""
Integration tests — call real ZDS Forge print and planning endpoints against
a live running server.

These tests are marked ``@pytest.mark.integration`` and skipped automatically
when the required env vars are absent.  They are NOT run in CI by default
(CI uses the Tier 1 golden-integrity and Tier 2 text-regression paths instead).
Run them locally before updating the golden artifacts or merging a renderer change.

Prerequisites
─────────────
  1. Start the Forge API:
       uvicorn apps.zds.api.main:app --port 8001

  2. Export env vars:
       export PRINT_SERVICE_URL=http://localhost:8001
       export PRINT_SERVICE_WEEK_ID=<uuid from: SELECT id FROM weeks WHERE week_ending='YYYY-MM-DD'>
       export PRINT_SERVICE_NIGHT_ID=<uuid from: SELECT id FROM nights WHERE week_id='...' LIMIT 1>
       # PRINT_SERVICE_NIGHT_ID is optional; night-endpoint tests skip without it.

  3. Run:
       pytest tests/print_regression/test_integration.py -v
       # or, to run integration tests from the full suite:
       pytest tests/print_regression/ -v -m integration

Golden regeneration (after Brian's visual approval)
─────────────────────────────────────────────────────
Once these tests pass against the running server, regenerate the goldens:

  python -m tests.print_regression.update_golden \\
      --source print-service \\
      --service-url http://localhost:8001 \\
      --service-week-id $PRINT_SERVICE_WEEK_ID

Then commit the golden/ directory with Brian's sign-off in the message.
"""

from __future__ import annotations

import time
from typing import Optional

import pytest

from tests.print_regression.conftest import (
    PRINT_SERVICE_NIGHT_ID,
    PRINT_SERVICE_URL,
    PRINT_SERVICE_WEEK_ID,
    has_night_service_env,
    has_print_service_env,
)


# ── Module-level skip when the server isn't configured ───────────────────────

pytestmark = pytest.mark.integration


def _skip_if_no_server():
    if not has_print_service_env():
        pytest.skip(
            "Integration tests require PRINT_SERVICE_URL + PRINT_SERVICE_WEEK_ID. "
            "Start the Forge API and export those vars (see module docstring)."
        )


def _client():
    """Return a synchronous httpx client pointed at the Forge API."""
    try:
        import httpx
    except ImportError:
        pytest.skip("httpx not installed — pip install httpx")
    return httpx.Client(base_url=PRINT_SERVICE_URL, timeout=60)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _week_html_url()  -> str: return f"/v1/print/week/{PRINT_SERVICE_WEEK_ID}.html"
def _week_pdf_url()   -> str: return f"/v1/print/week/{PRINT_SERVICE_WEEK_ID}.pdf"
def _night_html_url() -> str: return f"/v1/print/night/{PRINT_SERVICE_NIGHT_ID}.html"
def _night_pdf_url()  -> str: return f"/v1/print/night/{PRINT_SERVICE_NIGHT_ID}.pdf"
def _planning_url()   -> str: return f"/v1/planning/weekly/{PRINT_SERVICE_WEEK_ID}"


# ══════════════════════════════════════════════════════════════════════════════
# Week HTML endpoint
# ══════════════════════════════════════════════════════════════════════════════

class TestWeekHtmlEndpoint:
    """Integration tests for GET /v1/print/week/{id}.html."""

    def setup_method(self):
        _skip_if_no_server()

    def test_week_html_returns_200(self):
        """Existing week → 200."""
        with _client() as c:
            r = c.get(_week_html_url())
        assert r.status_code == 200, (
            f"Expected 200, got {r.status_code}. "
            f"Check that PRINT_SERVICE_WEEK_ID={PRINT_SERVICE_WEEK_ID!r} exists in the DB."
        )

    def test_week_html_content_type(self):
        """Content-Type must be text/html."""
        with _client() as c:
            r = c.get(_week_html_url())
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_week_html_content_size_reasonable(self):
        """The deployment book HTML must be substantially larger than a stub page.

        A real 14-page Zone Deployment Book is ~200 KB+ of HTML.  Anything
        under 10 KB means the renderer returned an empty or error page.
        """
        with _client() as c:
            r = c.get(_week_html_url())
        assert r.status_code == 200
        size = len(r.content)
        assert size >= 10_000, (
            f"Week HTML is only {size:,} bytes — renderer may have returned an error page. "
            "Check the server logs."
        )

    def test_week_html_cache_control_header_present(self):
        """Cache-Control must be present and set to private."""
        with _client() as c:
            r = c.get(_week_html_url())
        assert r.status_code == 200
        cc = r.headers.get("cache-control", "")
        assert cc, "Cache-Control header is missing"
        assert "private" in cc, f"Expected 'private' in Cache-Control, got: {cc!r}"

    def test_week_html_content_disposition_inline(self):
        """Content-Disposition must be inline with a .html filename."""
        with _client() as c:
            r = c.get(_week_html_url())
        assert r.status_code == 200
        cd = r.headers.get("content-disposition", "")
        assert "inline" in cd,   f"Content-Disposition not inline: {cd!r}"
        assert ".html" in cd,    f"Content-Disposition has no .html filename: {cd!r}"
        assert "attachment" not in cd, f"Content-Disposition must not be attachment: {cd!r}"

    def test_week_html_consecutive_calls_consistent(self):
        """Two sequential calls to the same week must return identical body content.

        This also validates the cache layer: the second call should be a cache
        hit and must not produce a different render.
        """
        with _client() as c:
            r1 = c.get(_week_html_url())
            r2 = c.get(_week_html_url())
        assert r1.status_code == r2.status_code == 200
        # Bodies must be identical — the renderer is deterministic.
        assert r1.content == r2.content, (
            "Two consecutive calls returned different HTML content. "
            "The cache layer may be broken or the renderer is non-deterministic."
        )

    def test_week_html_nonexistent_week_returns_404(self):
        """A UUID that doesn't exist in the DB must return 404."""
        with _client() as c:
            r = c.get("/v1/print/week/00000000-0000-0000-0000-000000000000.html")
        assert r.status_code == 404
        body = r.json()
        assert body["detail"]["error"] == "not_found"


# ══════════════════════════════════════════════════════════════════════════════
# Week PDF endpoint
# ══════════════════════════════════════════════════════════════════════════════

class TestWeekPdfEndpoint:
    """Integration tests for GET /v1/print/week/{id}.pdf."""

    def setup_method(self):
        _skip_if_no_server()

    def test_week_pdf_returns_200(self):
        """Existing week → 200."""
        with _client() as c:
            r = c.get(_week_pdf_url())
        if r.status_code == 500:
            body = r.json()
            if body.get("detail", {}).get("error") == "render_failed":
                pytest.skip(
                    "PDF render returned 500 — weasyprint likely not installed on the server. "
                    "Install weasyprint and pango+cairo to enable PDF generation."
                )
        assert r.status_code == 200

    def test_week_pdf_content_type(self):
        """Content-Type must be application/pdf."""
        with _client() as c:
            r = c.get(_week_pdf_url())
        if r.status_code == 500:
            pytest.skip("PDF render unavailable (weasyprint not installed)")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"

    def test_week_pdf_starts_with_pdf_magic_bytes(self):
        """PDF body must start with the %%PDF magic header."""
        with _client() as c:
            r = c.get(_week_pdf_url())
        if r.status_code == 500:
            pytest.skip("PDF render unavailable")
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF", (
            f"Response doesn't start with %PDF: {r.content[:20]!r}"
        )

    def test_week_pdf_content_disposition_inline(self):
        """PDF must be inline (browser opens viewer, not download dialog)."""
        with _client() as c:
            r = c.get(_week_pdf_url())
        if r.status_code == 500:
            pytest.skip("PDF render unavailable")
        assert r.status_code == 200
        cd = r.headers.get("content-disposition", "")
        assert "inline" in cd,      f"Content-Disposition not inline: {cd!r}"
        assert ".pdf" in cd,        f"Content-Disposition has no .pdf filename: {cd!r}"
        assert "attachment" not in cd

    def test_week_pdf_nonexistent_week_returns_404(self):
        """Non-existent week → 404 with structured envelope."""
        with _client() as c:
            r = c.get("/v1/print/week/00000000-0000-0000-0000-000000000000.pdf")
        assert r.status_code == 404
        body = r.json()
        assert body["detail"]["error"] == "not_found"


# ══════════════════════════════════════════════════════════════════════════════
# Night endpoints
# ══════════════════════════════════════════════════════════════════════════════

class TestNightEndpoints:
    """Integration tests for night HTML and PDF endpoints.

    Skipped automatically if PRINT_SERVICE_NIGHT_ID is not set.
    """

    def setup_method(self):
        _skip_if_no_server()
        if not has_night_service_env():
            pytest.skip(
                "Night-endpoint tests require PRINT_SERVICE_NIGHT_ID. "
                "Set it to a UUID from: "
                f"SELECT id FROM nights WHERE week_id='{PRINT_SERVICE_WEEK_ID}' LIMIT 1"
            )

    def test_night_html_returns_200(self):
        """Existing night → HTML 200."""
        with _client() as c:
            r = c.get(_night_html_url())
        assert r.status_code == 200, (
            f"Got {r.status_code}. Check PRINT_SERVICE_NIGHT_ID={PRINT_SERVICE_NIGHT_ID!r}."
        )
        assert "text/html" in r.headers.get("content-type", "")

    def test_night_html_content_size_reasonable(self):
        """Night HTML must be at least 5 KB (2 pages of content)."""
        with _client() as c:
            r = c.get(_night_html_url())
        assert r.status_code == 200
        assert len(r.content) >= 5_000, (
            f"Night HTML only {len(r.content):,} bytes — renderer may have failed."
        )

    def test_night_html_content_disposition_inline(self):
        """Night HTML Content-Disposition must be inline."""
        with _client() as c:
            r = c.get(_night_html_url())
        assert r.status_code == 200
        cd = r.headers.get("content-disposition", "")
        assert "inline" in cd
        assert ".html" in cd

    def test_night_pdf_returns_200(self):
        """Existing night → PDF 200 (or 500 if weasyprint absent)."""
        with _client() as c:
            r = c.get(_night_pdf_url())
        if r.status_code == 500:
            pytest.skip("PDF render unavailable (weasyprint not installed on server)")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        assert r.content[:4] == b"%PDF"

    def test_night_html_nonexistent_night_returns_404(self):
        """Non-existent night UUID → 404."""
        with _client() as c:
            r = c.get("/v1/print/night/00000000-0000-0000-0000-000000000000.html")
        assert r.status_code == 404
        body = r.json()
        assert body["detail"]["error"] == "not_found"


# ══════════════════════════════════════════════════════════════════════════════
# Planning endpoint
# ══════════════════════════════════════════════════════════════════════════════

class TestPlanningEndpointIntegration:
    """Integration tests for GET /v1/planning/weekly/{week_id} (GLC-12)."""

    def setup_method(self):
        _skip_if_no_server()

    def test_planning_weekly_returns_200(self):
        """Existing week → 200 JSON with planning overview."""
        with _client() as c:
            r = c.get(_planning_url())
        assert r.status_code == 200, (
            f"Got {r.status_code}: {r.text[:200]}"
        )
        assert "application/json" in r.headers.get("content-type", "")

    def test_planning_weekly_response_shape(self):
        """Response must have week, nights, metrics, links at the top level."""
        with _client() as c:
            r = c.get(_planning_url())
        assert r.status_code == 200
        body = r.json()
        for key in ("week", "nights", "metrics", "planning_notes",
                    "active_overrides", "links", "cached_at"):
            assert key in body, f"Planning response missing top-level key: {key!r}"

    def test_planning_weekly_week_id_matches(self):
        """The week.id in the response must match the requested week_id."""
        with _client() as c:
            r = c.get(_planning_url())
        assert r.status_code == 200
        assert r.json()["week"]["id"] == PRINT_SERVICE_WEEK_ID

    def test_planning_weekly_links_point_to_print_endpoints(self):
        """Planning links must reference the correct print endpoint URLs."""
        with _client() as c:
            r = c.get(_planning_url())
        assert r.status_code == 200
        links = r.json()["links"]
        assert PRINT_SERVICE_WEEK_ID in links["print_week_html"]
        assert PRINT_SERVICE_WEEK_ID in links["print_week_pdf"]
        assert ".html" in links["print_week_html"]
        assert ".pdf"  in links["print_week_pdf"]

    def test_planning_weekly_cache_control_short_ttl(self):
        """Planning overview must carry short Cache-Control (≤ 15 s)."""
        with _client() as c:
            r = c.get(_planning_url())
        assert r.status_code == 200
        cc = r.headers.get("cache-control", "")
        assert "private" in cc
        # max-age should be 15 (planning is a live tool)
        import re
        m = re.search(r"max-age=(\d+)", cc)
        assert m, f"No max-age in Cache-Control: {cc!r}"
        assert int(m.group(1)) <= 15, (
            f"Planning Cache-Control max-age is {m.group(1)} — expected ≤ 15"
        )

    def test_planning_nonexistent_week_returns_404(self):
        """Non-existent week → 404."""
        with _client() as c:
            r = c.get("/v1/planning/weekly/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404
        body = r.json()
        assert body["detail"]["error"] == "not_found"
